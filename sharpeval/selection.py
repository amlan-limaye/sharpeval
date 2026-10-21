"""Conditional PSR/DSR diagnostics; independent implementation of published formulas.

Bailey & Lopez de Prado (2014), equation (2), using the observed-Sharpe
plug-in variance. No third-party code or market data is bundled.
"""

import math
from statistics import NormalDist, stdev

from .statistics import correlation, mean
from .validation import InputError, integer, number, object_fields, text

EULER_GAMMA = 0.5772156649015329
ASSUMPTIONS = ("serial_independence", "stationarity", "finite_fourth_moment",
               "normal_trial_sharpes", "comparable_trial_sharpes")


def unavailable(*reasons):
    return {"status": "unavailable", "value": None, "reasons": list(reasons)}


def expected_max_sharpe(independent_trials, trial_sharpe_std):
    """Zero-centered Normal trial-SR model. N=1 has exactly zero selection bar."""
    integer(independent_trials, "effective_independent_trials", 1, 1_000_000_000)
    if independent_trials == 1 and trial_sharpe_std is None:
        return 0.0
    dispersion = number(trial_sharpe_std, "trial_sharpe_std_per_period")
    if not 0 <= dispersion <= 1000:
        raise InputError("trial Sharpe dispersion must be in [0, 1000]")
    if independent_trials == 1 or dispersion == 0:
        return 0.0
    normal = NormalDist()
    n = independent_trials
    return dispersion * ((1 - EULER_GAMMA) * normal.inv_cdf(1 - 1 / n)
                         + EULER_GAMMA * normal.inv_cdf(1 - 1 / (math.e * n)))


def psr_from_summary(sharpe, observations, skewness, kurtosis, benchmark=0.0):
    """Formula-only primitive; callers must establish applicability separately.

    Returns an approximate normal tail area, NOT a posterior skill probability.
    Kurtosis is non-excess. No denominator floor or invented effective T is used.
    """
    integer(observations, "observations", 3, 100_000_000)
    sr = number(sharpe, "sharpe")
    skew = number(skewness, "skewness")
    kurt = number(kurtosis, "kurtosis")
    benchmark = number(benchmark, "benchmark_sharpe")
    if kurt < 1 or kurt + 1e-10 < skew * skew + 1:
        raise InputError("incompatible skewness/non-excess kurtosis moments")
    factor = 1 - skew * sr + (kurt - 1) * sr * sr / 4
    if not math.isfinite(factor) or factor <= 0:
        raise InputError("PSR variance factor is nonpositive or outside numeric range")
    standard_error = math.sqrt(factor / (observations - 1))
    z = (sr - benchmark) / standard_error
    if not math.isfinite(z):
        raise InputError("PSR z statistic is outside numeric range")
    return {"value": NormalDist().cdf(z), "z": z, "variance_factor": factor,
            "standard_error": standard_error, "benchmark_sharpe_per_period": benchmark}


def return_moments(returns, cash=0.0):
    if len(returns) < 3 or min(returns) == max(returns):
        return unavailable("At least three observations and nonzero variance are required.")
    excess = [v - cash for v in returns]
    scale = max(abs(v) for v in excess)
    scaled = [v / scale for v in excess]
    center = mean(scaled)
    deviations = [v - center for v in scaled]
    m2 = mean([v * v for v in deviations])
    sigma = stdev(scaled)
    if m2 <= 0 or sigma <= 0:
        return unavailable("Variance is below numeric resolution.")
    standardized = [v / math.sqrt(m2) for v in deviations]
    sr = center / sigma
    skew = mean([v**3 for v in standardized])
    kurt = mean([v**4 for v in standardized])
    if not all(math.isfinite(v) for v in (sr, skew, kurt)):
        return unavailable("Moments exceed numeric range.")
    return {"status": "available", "observations": len(returns), "sharpe_per_period": sr,
            "skewness": skew, "kurtosis_non_excess": kurt,
            "sharpe_denominator": "sample standard deviation, ddof=1",
            "moment_convention": "population central moments m_k = sum((x-mean)^k)/T; no finite-sample bias adjustment; kurtosis is non-excess (Normal=3)",
            "cash_return_per_period": cash}


def dependence_screen(returns):
    """Conservative applicability screen, not an independence test or skill gate."""
    n = len(returns)
    cutoff = 3 / math.sqrt(n)
    center = mean(returns)
    # Scale before squaring so very small finite returns remain representable.
    scale = max(abs(v - center) for v in returns) or 1.0
    squared = [((v - center) / scale) ** 2 for v in returns]
    lags = []
    flagged = []
    for lag in range(1, min(10, n // 5) + 1):
        raw = correlation(returns[:-lag], returns[lag:])
        sq = correlation(squared[:-lag], squared[lag:])
        lags.append({"lag": lag, "return_correlation": raw, "squared_centered_return_correlation": sq})
        for kind, value in (("returns", raw), ("squared_centered_returns", sq)):
            if value is not None and abs(value) > cutoff:
                flagged.append({"lag": lag, "series": kind, "correlation": value})
    return {"status": "flagged" if flagged else "no_flag_detected", "lags": lags,
            "threshold": cutoff, "flagged": flagged,
            "rule": "Withhold standard PSR/DSR if abs(Pearson lag correlation) > 3/sqrt(T), on returns or squared centered returns, lags 1..min(10,floor(T/5)).",
            "limitation": "Prespecified heuristic, not a formal independence test; no flag does not establish independence, stationarity or a finite fourth moment. T is never adjusted."}


def validate_selection(spec):
    object_fields(spec, {"target_run_id", "benchmark_sharpe_per_period", "sharpe_unit", "assumptions", "notes", "search"}, path="selection item")
    text(spec["target_run_id"], "selection.target_run_id", 120)
    text(spec["notes"], "selection.notes")
    if spec["sharpe_unit"] != "per_period":
        raise InputError("selection Sharpe ratios and dispersion must explicitly be per_period; no automatic annualized conversion")
    if abs(number(spec["benchmark_sharpe_per_period"], "benchmark_sharpe_per_period")) > 1000:
        raise InputError("benchmark Sharpe exceeds supported range [-1000,1000]")
    object_fields(spec["assumptions"], ASSUMPTIONS, path="selection.assumptions")
    for name in ASSUMPTIONS:
        if spec["assumptions"][name] not in ("assumed", "unknown", "unsupported"):
            raise InputError(f"selection.assumptions.{name}: use assumed, unknown or unsupported")
    search = spec["search"]
    if search is None:
        return
    object_fields(search, {"observed_trial_count", "effective_independent_trials", "completeness",
                           "dispersion_source", "trial_sharpe_std_per_period", "trial_sharpes",
                           "selected_trial_id", "null_mean_sharpe_per_period", "notes"}, path="selection.search")
    text(search["notes"], "search.notes")
    for name in ("observed_trial_count", "effective_independent_trials"):
        if search[name] is not None:
            integer(search[name], name, 1, 1_000_000_000)
    if search["observed_trial_count"] is not None and search["effective_independent_trials"] is not None:
        if search["effective_independent_trials"] > search["observed_trial_count"]:
            raise InputError("effective independent trials cannot exceed the declared observed trial count")
    if search["completeness"] not in ("complete", "incomplete", "unknown"):
        raise InputError("search.completeness must be complete, incomplete or unknown")
    if search["dispersion_source"] not in ("observed_trial_sharpes", "assumed", "unknown"):
        raise InputError("invalid dispersion_source")
    dispersion = search["trial_sharpe_std_per_period"]
    if dispersion is not None and not 0 <= number(dispersion, "trial_sharpe_std_per_period") <= 1000:
        raise InputError("trial Sharpe dispersion must be in [0,1000], or null")
    if search["dispersion_source"] != "assumed" and dispersion is not None:
        raise InputError("explicit dispersion is permitted only with dispersion_source=assumed; observed dispersion is computed from the complete ledger")
    number(search["null_mean_sharpe_per_period"], "null_mean_sharpe_per_period")
    if search["selected_trial_id"] is not None:
        text(search["selected_trial_id"], "selected_trial_id", 120)
    ledger = search["trial_sharpes"]
    if ledger is None:
        return
    if not isinstance(ledger, list) or not 1 <= len(ledger) <= 10_000:
        raise InputError("trial_sharpes must be null or a list of 1..10,000 entries")
    ids = set()
    for row in ledger:
        object_fields(row, {"trial_id", "sharpe_per_period"}, path="trial_sharpes entry")
        tid = text(row["trial_id"], "trial_id", 120)
        if tid in ids:
            raise InputError("duplicate trial_id; search attempts must have unique identities")
        ids.add(tid)
        if row["sharpe_per_period"] is not None and abs(number(row["sharpe_per_period"], "trial sharpe")) > 1000:
            raise InputError("trial Sharpe exceeds supported range")
    count = search["observed_trial_count"]
    if count is not None and len(ledger) > count:
        raise InputError("trial ledger contains more entries than observed_trial_count")


def selection_diagnostics(returns, cash, spec):
    validate_selection(spec)
    moments = return_moments(returns, cash)
    screen = dependence_screen(returns)
    result = {"target_run_id": spec["target_run_id"], "sharpe_unit": "per_period", "moments": moments,
              "dependence_screen": screen, "assumptions": spec["assumptions"], "notes": spec["notes"],
              "psr": unavailable("Not evaluated."), "dsr": unavailable("Not evaluated."),
              "search": spec["search"], "trial_dispersion_used": None, "trial_count_source": "unknown",
              "effective_trial_count_source": "explicit user assumption; never inferred from execution seeds or an effective time sample size",
              "interpretation": "Conditional approximate normal tail area (one minus a plug-in one-sided p-value) against the stated Sharpe bar. Not a posterior probability of skill, not odds of future profit, and not a paired version-improvement test.",
              "formula": "Phi((SR - bar)*sqrt(T-1)/sqrt(1 - skew*SR + (kurtosis-1)*SR^2/4)); standard error evaluated at observed SR",
              "limitations": ["The time-series formula is not serial-correlation robust. No effective T correction is invented.",
                              "Search completeness, trial independence and distribution assumptions are producer claims, not verified facts.",
                              "Moment and trial-dispersion estimates are uncertain; their uncertainty is not propagated.",
                              "Expected maximum is an asymptotic Normal-trial approximation, less accurate for small N."]}
    reasons = []
    if len(returns) < 20:
        reasons.append("Fewer than 20 periods: v0.2 operational floor, not proof that longer histories are adequate.")
    if -1 in returns:
        reasons.append("Bankruptcy invalidates this v0.2 inference contract.")
    if moments["status"] != "available":
        reasons.extend(moments["reasons"])
    for name in ASSUMPTIONS[:3]:
        if spec["assumptions"][name] != "assumed":
            reasons.append(f"Required {name} assumption is {spec['assumptions'][name]}.")
    if screen["flagged"]:
        reasons.append("Serial-dependence screen flagged returns or volatility dependence; standard PSR/DSR withheld.")
    if reasons:
        result["psr"] = unavailable(*reasons)
    else:
        try:
            result["psr"] = {"status": "conditional", **psr_from_summary(moments["sharpe_per_period"], len(returns),
                              moments["skewness"], moments["kurtosis_non_excess"], spec["benchmark_sharpe_per_period"])}
        except InputError as exc:
            reasons.append(str(exc))
            result["psr"] = unavailable(str(exc))
    search = spec["search"]
    dsr_reasons = list(reasons)
    dispersion = None
    if search is None:
        dsr_reasons.append("Search history not supplied; unknown trials are not zero.")
    else:
        count, effective = search["observed_trial_count"], search["effective_independent_trials"]
        ledger = search["trial_sharpes"]
        result["trial_count_source"] = "enumerated but unaudited" if ledger is not None and count == len(ledger) else "user declared, not audited"
        if count is None:
            dsr_reasons.append("Observed trial count is unknown.")
        if effective is None:
            dsr_reasons.append("Effective independent trial count was not explicitly assumed.")
        if search["completeness"] != "complete":
            dsr_reasons.append("Search history is incomplete or unknown; an omitted-loser correction is not identifiable.")
        if search["null_mean_sharpe_per_period"] != 0:
            dsr_reasons.append("v0.2 implements the original zero-centered trial-Sharpe null only.")
        if effective != 1:
            if spec["assumptions"]["normal_trial_sharpes"] != "assumed":
                dsr_reasons.append("Normal trial-Sharpe estimate approximation was not assumed.")
            if spec["assumptions"]["comparable_trial_sharpes"] != "assumed":
                dsr_reasons.append("Trial Sharpes were not declared comparable in frequency, cash benchmark, cost convention and evaluation protocol.")
        if ledger is not None:
            if count is None or len(ledger) != count:
                dsr_reasons.append("Trial ledger does not account for every declared observed attempt.")
            if any(row["sharpe_per_period"] is None for row in ledger):
                dsr_reasons.append("Trial ledger has missing/undefined outcomes; they are counted and never silently dropped.")
            selected = next((row for row in ledger if row["trial_id"] == search["selected_trial_id"]), None)
            if selected is None:
                dsr_reasons.append("Selected trial is not identified in the supplied ledger.")
            elif moments["status"] == "available" and (selected["sharpe_per_period"] is None or not math.isclose(
                    selected["sharpe_per_period"], moments["sharpe_per_period"], rel_tol=1e-8, abs_tol=1e-8)):
                dsr_reasons.append("Selected trial Sharpe does not match the target run under the declared per-period convention.")
        if effective == 1:
            result["trial_dispersion_used"] = {"value": None, "source": "not_required_for_one_effective_trial", "ddof": None}
        elif search["dispersion_source"] == "observed_trial_sharpes":
            if ledger is not None and len(ledger) >= 2 and all(row["sharpe_per_period"] is not None for row in ledger) and count == len(ledger):
                dispersion = stdev(row["sharpe_per_period"] for row in ledger)
                result["trial_dispersion_used"] = {"value": dispersion, "source": "sample dispersion of supplied complete trial Sharpe ledger", "ddof": 1}
            else:
                dsr_reasons.append("A complete ledger with at least two defined trial Sharpes is needed to measure dispersion.")
        elif search["dispersion_source"] == "assumed" and search["trial_sharpe_std_per_period"] is not None:
            dispersion = search["trial_sharpe_std_per_period"]
            result["trial_dispersion_used"] = {"value": dispersion, "source": "user_assumed", "ddof": None}
        else:
            dsr_reasons.append("Required cross-trial Sharpe dispersion is unknown.")
        if not dsr_reasons:
            try:
                bar = expected_max_sharpe(effective, dispersion)
                result["dsr"] = {"status": "conditional", **psr_from_summary(moments["sharpe_per_period"], len(returns),
                                   moments["skewness"], moments["kurtosis_non_excess"], bar),
                                 "effective_independent_trials": effective, "observed_trial_count": count,
                                 "null_mean_sharpe_per_period": 0.0,
                                 "selection_bar_formula": "sigma_SR * [(1-gamma)*Phi^-1(1-1/N) + gamma*Phi^-1(1-1/(N*e))]; bar=0 for N=1",
                                 "sensitivity": []}
                if dispersion is not None:
                    for n in sorted({1, effective, count}):
                        trial_bar = expected_max_sharpe(n, dispersion)
                        result["dsr"]["sensitivity"].append({"effective_independent_trials": n,
                            "benchmark_sharpe_per_period": trial_bar,
                            "value": psr_from_summary(moments["sharpe_per_period"], len(returns), moments["skewness"], moments["kurtosis_non_excess"], trial_bar)["value"]})
            except InputError as exc:
                dsr_reasons.append(str(exc))
    if dsr_reasons:
        result["dsr"] = unavailable(*dsr_reasons)
    return result
