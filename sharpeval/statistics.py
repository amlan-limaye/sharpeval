"""Transparent descriptive statistics, independently implemented using stdlib."""

import math
import statistics


def mean(values):
    return math.fsum(values) / len(values)


def stdev(values):
    return statistics.stdev(values) if len(values) >= 2 else None


def correlation(x, y):
    if len(x) != len(y):
        raise ValueError("correlation needs aligned equal-length vectors")
    if len(x) < 2 or max(x) == min(x) or max(y) == min(y):
        return None
    # Normalize before squaring so tiny but varying inputs do not underflow.
    sx, sy = max(abs(v) for v in x), max(abs(v) for v in y)
    nx, ny = [v / sx for v in x], [v / sy for v in y]
    mx, my = mean(nx), mean(ny)
    dx, dy = [v - mx for v in nx], [v - my for v in ny]
    vx, vy = math.fsum(v * v for v in dx), math.fsum(v * v for v in dy)
    if vx == 0 or vy == 0:
        return None
    return max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(dx, dy)) / (math.sqrt(vx) * math.sqrt(vy))))


def wealth_stats(returns, include_path=False):
    log_equity, peak, max_dd = 0.0, 0.0, 0.0
    ruined, overflow = False, False
    path = [1.0] if include_path else None
    for r in returns:
        if r == -1:
            ruined = True
        if ruined:
            max_dd = 1.0
            equity = 0.0
        else:
            log_equity += math.log1p(r)
            peak = max(peak, log_equity)
            max_dd = max(max_dd, -math.expm1(log_equity - peak))
            try:
                equity = math.exp(log_equity) if include_path else None
            except OverflowError:
                overflow = True
                equity = None
        if include_path:
            path.append(equity)
    try:
        total = -1.0 if ruined else math.expm1(log_equity)
    except OverflowError:
        total, overflow = None, True
    return {"total_return": total, "max_drawdown": max_dd, "bankrupt": ruined,
            "wealth_overflow": overflow, "net_wealth": path, "log_wealth": None if ruined else log_equity}


def snapshot(returns, cash=0.0):
    mu, vol = mean(returns), stdev(returns)
    wealth = wealth_stats(returns)
    sharpe = None if vol is None or vol == 0 else (mu - cash) / vol
    if sharpe is not None and not math.isfinite(sharpe):
        sharpe = None
    return {"mean_return": mu, "total_return": wealth["total_return"], "volatility": vol,
            "max_drawdown": wealth["max_drawdown"], "sharpe_per_period": sharpe}


def diagnostics(returns, cash, periods_per_year):
    result = snapshot(returns, cash)
    path = wealth_stats(returns, include_path=True)
    result.update({"observations": len(returns), "worst_period": min(returns), "best_period": max(returns),
                   "positive_fraction": sum(v > 0 for v in returns) / len(returns),
                   "lag1_correlation": correlation(returns[:-1], returns[1:]),
                   "bankrupt": path["bankrupt"], "net_wealth": path["net_wealth"],
                   "wealth_overflow": path["wealth_overflow"]})
    midpoint = len(returns) // 2
    result["half_sample_mean"] = {"first": mean(returns[:midpoint]) if midpoint else None,
                                  "second": mean(returns[midpoint:]) if midpoint else None}
    annual = {"periods_per_year": periods_per_year, "geometric_return": None,
              "arithmetic_mean": None, "volatility_iid_scaling": None, "sharpe_iid_scaling": None,
              "note": "Unavailable: periods_per_year was not declared."}
    if periods_per_year is not None:
        annual["note"] = "Conventional scaling, not a forecast. Volatility and Sharpe sqrt(time) scaling assumes uncorrelated, stable returns."
        annual["arithmetic_mean"] = result["mean_return"] * periods_per_year
        annual["volatility_iid_scaling"] = None if result["volatility"] is None else result["volatility"] * math.sqrt(periods_per_year)
        annual["sharpe_iid_scaling"] = None if result["sharpe_per_period"] is None else result["sharpe_per_period"] * math.sqrt(periods_per_year)
        if annual["sharpe_iid_scaling"] is not None and not math.isfinite(annual["sharpe_iid_scaling"]):
            annual["sharpe_iid_scaling"] = None
            annual["note"] += " Annualized Sharpe exceeds numeric range and is unavailable."
        try:
            annual["geometric_return"] = -1.0 if path["bankrupt"] else math.expm1(path["log_wealth"] * periods_per_year / len(returns))
        except OverflowError:
            annual["note"] += " Geometric annualization overflowed and is unavailable."
    result["annualized"] = annual
    return result


def regression(agent, benchmark, cash):
    if len(agent) != len(benchmark):
        raise ValueError("regression needs aligned equal-length vectors")
    if len(agent) < 3 or max(benchmark) == min(benchmark):
        return {"status": "unavailable", "reason": "Need at least 3 periods and a nonconstant benchmark."}
    mx, my = mean(benchmark), mean(agent)
    sx, sy = max(abs(v) for v in benchmark), max(abs(v) for v in agent) or 1.0
    xs, ys = [v / sx for v in benchmark], [v / sy for v in agent]
    xn, yn = mean(xs), mean(ys)
    variance = math.fsum((x - xn) ** 2 for x in xs)
    if variance == 0:
        return {"status": "unavailable", "reason": "Benchmark variance is below numeric resolution."}
    covariance = math.fsum((x - xn) * (y - yn) for x, y in zip(xs, ys))
    beta = 0.0 if covariance == 0 else (covariance / variance) * (sy / sx)
    intercept = (my - cash) - beta * (mx - cash)
    if not math.isfinite(beta) or not math.isfinite(intercept):
        return {"status": "unavailable", "reason": "Regression exceeds floating-point range."}
    return {"status": "descriptive_only", "beta": beta, "intercept_per_period": intercept,
            "correlation": correlation(agent, benchmark),
            "note": "OLS association against one supplied benchmark. The intercept is not causal attribution or certified alpha."}


def quantile(sorted_values, probability):
    index = (len(sorted_values) - 1) * probability
    low = math.floor(index)
    high = math.ceil(index)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (index - low)
