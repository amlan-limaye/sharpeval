"""Offline HTML: escaped user text, no JavaScript, remote assets or telemetry."""

from html import escape
import math


def e(value):
    return escape(str(value), quote=True)


def pct(value, signed=False):
    return "—" if value is None else format(value * 100, "+.2f" if signed else ".2f") + "%"


def num(value, signed=False):
    return "—" if value is None else format(value, "+.3f" if signed else ".3f")


def bps(value):
    return "—" if value is None else f"{value * 10000:+.2f} bp"


LABELS = {"total_return": "Compounded net return", "mean_return": "Average net return / period",
          "volatility": "Volatility / period", "max_drawdown": "Maximum drawdown",
          "sharpe_per_period": "Sharpe / period (vs declared cash)"}


def table(headers, rows):
    return '<div class="table-scroll"><table><thead><tr>' + ''.join(f'<th scope="col">{e(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def metric_table(named_metrics):
    rows = []
    for key, label in LABELS.items():
        fmt = num if key == "sharpe_per_period" else pct
        rows.append([e(label)] + [fmt(m[key]) for _, m in named_metrics])
    return table(["Observed, same window"] + [name for name, _ in named_metrics], rows)


def ci_text(interval, fmt=pct):
    if not interval or interval["status"] != "available":
        return "Unavailable"
    return fmt(interval["lower"], True) + " to " + fmt(interval["upper"], True)


def change_table(changes, intervals):
    rows = []
    for key, label in LABELS.items():
        fmt = num if key == "sharpe_per_period" else pct
        ci = intervals.get(key)
        reason = "" if ci and ci["status"] == "available" else '<span class="small">Undefined or insufficient data</span>'
        rows.append([e(label), fmt(changes[key], True), ci_text(ci, fmt) + reason])
    return table(["Change", "Observed difference", "Block bootstrap interval"], rows)


def chart(named_paths, chart_title):
    colors = ["#4f6bd8", "#007b68", "#b56626"]
    finite = [v for _, path in named_paths for v in path if v is not None and math.isfinite(v)]
    if not finite or any(v is None for _, path in named_paths for v in path):
        return '<p class="note">Wealth chart unavailable because one path exceeds numeric range.</p>'
    low, high = min(finite), max(finite)
    pad = max((high - low) * 0.1, 0.015)
    low, high = max(0, low - pad), high + pad
    if not math.isfinite(high):
        return '<p class="note">Wealth chart unavailable beyond plotting range.</p>'
    def y(v):
        return 220 - (v - low) / (high - low) * 185
    paths, lines = [], []
    for i in range(5):
        value = low + (high - low) * i / 4
        line_y = y(value)
        lines.append(f'<line x1="65" y1="{line_y:.2f}" x2="960" y2="{line_y:.2f}" stroke="#dce3e7"/><text x="52" y="{line_y + 4:.2f}" text-anchor="end" fill="#586977" font-size="12">{value:.3f}</text>')
    for i, (name, path) in enumerate(named_paths):
        coords = " ".join(f'{65 + j / (len(path) - 1) * 895:.2f},{y(value):.2f}' for j, value in enumerate(path))
        paths.append(f'<polyline points="{coords}" fill="none" stroke="{colors[i % len(colors)]}" stroke-width="2.6" stroke-linejoin="round"/>')
    legend = ''.join(f'<span><i style="background:{colors[i % len(colors)]}"></i>{e(name)}</span>' for i, (name, _) in enumerate(named_paths))
    return f'<div class="chart"><div class="legend">{legend}</div><svg viewBox="0 0 1000 260" role="img" aria-label="{e(chart_title)}"><title>{e(chart_title)}</title>{"".join(lines + paths)}<text x="65" y="250" font-size="12" fill="#586977">Initial equity = 1</text><text x="960" y="250" text-anchor="end" font-size="12" fill="#586977">End of aligned window</text></svg></div>'


def render_html(report):
    r = report
    if r.get("schema_version") == 2:
        from .experiment_report import render_experiment_html
        return render_experiment_html(r)
    comp = r["comparison"]
    old_id, new_id = comp["old"], comp["new"]
    old, new = r["series"][old_id], r["series"][new_id]
    u = r["uncertainty"]
    primary = u["primary"]
    intervals = primary["contrasts"].get("new_minus_old", {})
    mean_ci = intervals.get("mean_return")
    if not mean_ci or mean_ci["status"] != "available":
        direction = "There is not enough usable evidence to report a mean-change interval under these settings."
    elif mean_ci["lower"] <= 0 <= mean_ci["upper"]:
        direction = "The interval includes zero: the direction of the average change remains uncertain."
    else:
        direction = "The interval lies " + ("above" if mean_ci["lower"] > 0 else "below") + " zero under these assumptions. It is not adjusted for strategy selection."
    type_label = "SYNTHETIC EXAMPLE" if r["synthetic"] else "IMPORTED HISTORICAL RECORDS"
    notice = ("Generated fixtures test the tool’s behavior. They provide no evidence of real-world alpha." if r["synthetic"] else
              "Imported historical records are user-declared and unverified. Historical performance does not establish future skill.")
    period_label = f'{r["alignment"]["periods"]} aligned periods · {r["source_type"]} · {r["currency"]} · {r["calendar"]["frequency_seconds"]:,} seconds / period'
    cards = f'''<div class="cards"><article><span>Old · {e(old["version"])}</span><strong>{pct(old["metrics"]["total_return"])}</strong><small>Compounded net return</small></article><article><span>New · {e(new["version"])}</span><strong>{pct(new["metrics"]["total_return"])}</strong><small>Compounded net return</small></article><article><span>New − old</span><strong>{bps(comp["observed_change"]["mean_return"])}</strong><small>Average change per period</small></article></div>'''
    body = [f'''<header><div class="wordmark">SharpeVal <span>LOCAL EVIDENCE REPORT · v0.1</span></div><h1>What changed in the new version?</h1><p class="subtitle">{e(r["title"])}</p><div class="badge">{type_label}</div><p>{e(notice)}</p><p class="meta">{e(period_label)}<br>{e(r["alignment"]["start"])} → {e(r["alignment"]["end"])}</p></header>''', cards]
    body.append(f'''<section><h2>1. Read the change, then its uncertainty</h2><p>Over this shared window, <b>{e(new_id)}</b> returned {pct(new["metrics"]["total_return"])} after declared costs, compared with {pct(old["metrics"]["total_return"])} for <b>{e(old_id)}</b>.</p><div class="callout"><b>{e(direction)}</b><p>The {u["confidence"]:.0%} block interval for the average change is <b>{ci_text(mean_ci)}</b> per period. This is a sampling interval under stated assumptions, not the probability that the new version will win.</p></div>''')
    body.append(metric_table([(old_id, old["metrics"]), (new_id, new["metrics"])]))
    body.append(chart([(old_id, old["metrics"]["net_wealth"]), (new_id, new["metrics"]["net_wealth"])], "Net wealth of old and new versions on identical periods"))
    body.append(change_table(comp["observed_change"], intervals))
    body.append('<p class="note">Differences are new minus old. Negative volatility or drawdown changes mean smaller observed risk. Drawdown is a positive loss magnitude. Sharpe uses the declared constant cash return; an em dash means unavailable, never zero.</p>')
    out = comp["outlier_sensitivity"]
    body.append(f'<p><b>One-period sensitivity:</b> the largest absolute paired difference was {bps(out["largest_absolute_period_change"])} on {e(out["timestamp"])}. Excluding only that observation, average change would be {bps(out["mean_change_excluding_that_period"])}. This is a descriptive stress check; the period remains in all primary results.</p></section>')
    p = r["portfolio"]
    body.append('<section><h2>2. Does it change the existing portfolio?</h2>')
    if p["status"] != "available":
        body.append(f'<div class="callout">Unavailable: {e(p["reason"])}</div>')
    else:
        rules = p["rules"]
        weights = ", ".join(f'{sid} {weight:.0%}' for sid, weight in rules["weights"].items())
        body.append(f'<p>The existing portfolio uses <b>{e(weights)}</b>. The comparison allocates <b>{rules["candidate_weight"]:.0%}</b> to either version and scales all existing weights by {1 - rules["candidate_weight"]:.0%}, rebalancing each period. The declared extra allocation cost is {bps(rules["overlay_cost_per_period"])} per period.</p>')
        body.append('<p class="note">Weights were declared before evaluation by the data producer; that claim is not independently verified. No allocation search is performed.</p>')
        body.append(metric_table([(key.replace("_", " ").title(), p["metrics"][key]) for key in ("base", "with_old", "with_new")]))
        body.append(chart([(key.replace("_", " ").title(), p["metrics"][key]["net_wealth"]) for key in ("base", "with_old", "with_new")], "Fixed-weight portfolio net wealth: base, with old, with new"))
        body.append('<h3>Adding new versus keeping the base portfolio</h3>')
        body.append(change_table(p["changes"]["with_new_minus_base"], primary["contrasts"].get("with_new_minus_base", {})))
        body.append('<h3>Using new versus old at the same allocation</h3>')
        body.append(change_table(p["changes"]["with_new_minus_with_old"], primary["contrasts"].get("with_new_minus_with_old", {})))
        correlations = [("Existing portfolio", p["candidate_vs_base_correlation"], "new_vs_portfolio")]
        correlations.extend((sid, value, "new_vs_member:" + sid) for sid, value in p["correlations"].items())
        body.append(table(["New version correlated with", "Pearson correlation", "Block interval"],
                          [[e(name), num(value), ci_text(primary["correlations"].get(key), num)] for name, value, key in correlations]))
        body.append(f'<p><b>Low correlation is not skill.</b> Diversification can change risk without adding return or predictive ability. Constituent trading costs are already included; only the declared overlay is subtracted again. {e(rules["overlay_cost_notes"])}</p>')
    body.append('</section><section><h2>3. Benchmark exposure and costs</h2>')
    bm = r["benchmark"]
    if bm["status"] == "not_supplied":
        body.append(f'<p>{e(bm["reason"])}</p>')
    else:
        rows = []
        for sid, reg in bm["regressions"].items():
            rows.append([e(sid), num(reg.get("beta")), pct(reg.get("intercept_per_period")), num(reg.get("correlation"))])
        body.append(f'<p>Descriptive regression against <b>{e(bm["id"])}</b>, whose net return was {pct(r["series"][bm["id"]]["metrics"]["total_return"])}.</p>')
        body.append(table(["Version", "Beta", "Intercept / period", "Correlation"], rows))
        body.append('<p class="note">A higher return can reflect leveraged benchmark exposure. One-factor beta and intercept are descriptive associations; they do not identify decisions, causal effects or future alpha.</p>')
    cost_rows = []
    for sid, h in r["series"].items():
        c = h["cost_accounting"]
        cost_rows.append([e(sid), e(c["input_basis"]), pct(c["gross_total_return"]), pct(h["metrics"]["total_return"]), bps(c["mean_period_cost_fraction"]), e(", ".join(c["excluded"]) or "None declared")])
    body.append(table(["History", "Input basis", "Gross compounded", "Net compounded", "Mean cost / period", "Excluded costs"], cost_rows))
    body.append('<p class="note">Gross input: net = return − cost. Net input: the return is used as supplied; disclosed cost is not subtracted twice. Unknown costs remain unavailable. Costs are fractions of starting period equity. Average or summed fractions are not cash amounts or compounded wealth drag.</p>')
    body.append('<details><summary>Declared cost coverage and assumptions</summary>')
    for sid, h in r["series"].items():
        c = h["cost_accounting"]
        body.append(f'<p><b>{e(sid)}</b> · included: {e(", ".join(c["included"]) or "None declared")}<br>{e(c["notes"])}</p>')
    body.append('</details></section><section><h2>4. How much should you trust this comparison?</h2>')
    body.append(f'<p>The paired circular moving-block bootstrap uses <b>{u["resamples"]:,} resamples</b>, seed <b>{u["seed"]}</b>, and blocks of <b>{u["block_length"]} periods</b> ({e(u["block_length_source"])}). All streams share each resampling path, preserving contemporaneous cross-agent dependence and within-block time order.</p>')
    sensitivity_rows = []
    for run in u["sensitivity"]:
        interval = run["contrasts"].get("new_minus_old", {}).get("mean_return")
        contribution = run["contrasts"].get("with_new_minus_base", {}).get("mean_return")
        sensitivity_rows.append([str(run["block_length"]) + (" (primary)" if run["block_length"] == u["block_length"] else ""),
                                 f'{run["approximate_blocks"]:.1f}', ci_text(interval), ci_text(contribution), e(run["status"])])
    body.append(table(["Block length", "Approx. blocks", "Version mean-change interval", "Portfolio mean-change interval", "Status"], sensitivity_rows))
    if primary["status"] != "available":
        body.append(f'<div class="callout">{e(primary["reason"])}</div>')
    body.append('<p>Changing block length changes the dependence assumption. Short blocks may miss persistent regimes; long blocks leave few distinct blocks. None of these choices fixes nonstationarity, data leakage, bad cost estimates or selecting a winner after many experiments.</p>')
    body.append(f'<p><b>Search-trial count:</b> {e("unknown" if r["selection_adjustment"]["search_trials"] is None else str(r["selection_adjustment"]["search_trials"]) + " (declared, unverified)")}. <b>Deflated Sharpe and selection correction:</b> not implemented. Repeated executions are not pooled into extra history. No eligibility gate or overall score is produced.</p>')
    body.append('<details><summary>Annualization, calendar and reproducibility</summary>')
    body.append(f'<p>Periods per year: {e(r["calendar"]["periods_per_year"] if r["calendar"]["periods_per_year"] is not None else "not supplied — annualization unavailable")}. Constant cash return per period: {pct(r["cash_return_per_period"])}. Alignment: {e(r["alignment"]["mode"])}; excluded calendar periods: {len(r["alignment"]["excluded_calendar_timestamps"])}. {e(r["calendar"]["notes"])}</p>')
    annual_rows = []
    for sid in (old_id, new_id):
        a = r["series"][sid]["metrics"]["annualized"]
        annual_rows.append([e(sid), pct(a["geometric_return"]), pct(a["volatility_iid_scaling"]), num(a["sharpe_iid_scaling"])])
    body.append(table(["History", "Annualized geometric return", "Volatility, conventional scaling", "Sharpe, conventional scaling"], annual_rows))
    body.append('<p class="note">Square-root time scaling assumes uncorrelated, stable returns and can mislead on serially dependent histories. Annualization of a short window magnifies estimation noise. The primary table stays per period.</p>')
    body.append(f'<p class="hash">Canonical input SHA-256: {e(r["input_sha256"])}<br>Engine: {e(r["tool"]["version"])} · Python: {e(r["tool"]["python"])}</p></details>')
    annotations = [(sid, a) for sid, h in r["series"].items() for a in h["annotations"]]
    if annotations:
        body.append('<details><summary>Supplied annotations (not inferred explanations)</summary>')
        body.append(table(["History", "Period end", "Producer annotation"], [[e(sid), e(a["timestamp"]), e(a["text"])] for sid, a in annotations[:20]]))
        if len(annotations) > 20:
            body.append('<p>First 20 shown; all supplied annotations are retained in the JSON report.</p>')
        body.append('</details>')
    body.append('<details open><summary>Limitations and missing evidence</summary><ul>' + ''.join(f'<li>{e(w)}</li>' for w in r["warnings"]) + '</ul></details></section>')
    body.append('<footer><b>Useful next experiment:</b> freeze the versions, cost model, weights and analysis settings before collecting a fresh held-out period. Record every attempted version and evaluation run.<br><br>Independent implementation; methodology informed by <a href="https://github.com/general-liquidity/sharpebench/blob/main/docs/book/src/methodology.md">SharpeBench</a>. This report is not its official benchmark score. SharpeVal · local evaluation.</footer>')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"><title>''' + e(r["title"]) + ''' — SharpeVal</title><style>
    :root{color-scheme:light;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#243746;background:#f2f5f7;font-size:16px;line-height:1.58}*{box-sizing:border-box}body{margin:0}main{max-width:1100px;padding:44px 34px 60px;margin:auto}header{padding:8px 0 24px}.wordmark{font-weight:750;letter-spacing:-.03em;font-size:22px;color:#0e6156}.wordmark span{display:inline-block;letter-spacing:.12em;font-weight:500;font-size:11px;color:#637583;margin-left:14px}h1{font-size:42px;line-height:1.13;letter-spacing:-.04em;margin:28px 0 12px;max-width:800px}h2{font-size:25px;letter-spacing:-.025em;line-height:1.25;margin:0 0 20px}h3{font-size:18px;margin:28px 0 12px}p{margin:12px 0}.subtitle{font-size:19px;color:#586977}.badge{display:inline-block;padding:5px 11px;background:#fff1c9;border:1px solid #dfc574;border-radius:5px;font-weight:700;font-size:12px;letter-spacing:.07em;margin-top:12px}.meta{font-size:13px;color:#637583}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:0 0 26px}.cards article{background:#fff;border:1px solid #dce3e7;border-radius:12px;padding:23px}.cards span,.cards small{display:block;color:#637583;font-size:13px}.cards strong{display:block;font-size:33px;letter-spacing:-.04em;color:#183f3a;margin:8px 0}section{background:#fff;border:1px solid #dce3e7;border-radius:12px;padding:30px;margin:22px 0}.callout{background:#f0f6f8;border-left:4px solid #3a7186;border-radius:4px;padding:16px 20px;margin:20px 0}.callout p{margin:8px 0 0}.note,.small{color:#637583;font-size:13px}.small{display:block}.table-scroll{overflow-x:auto;margin:16px 0}table{border-collapse:collapse;width:100%;text-align:left;font-variant-numeric:tabular-nums;font-size:14px}th{color:#586977;font-size:12px;letter-spacing:.01em;background:#f5f8f9;font-weight:650}th,td{padding:12px;border-bottom:1px solid #e3e9ed;vertical-align:top}td:not(:first-child){min-width:95px}.chart{margin:24px 0 18px}.chart svg{width:100%;height:auto;display:block}.legend{display:flex;flex-wrap:wrap;gap:20px;padding-left:12px;font-size:13px}.legend i{display:inline-block;width:19px;height:3px;margin:0 6px 3px 0}details{border-top:1px solid #e3e9ed;padding:18px 0 4px;margin-top:18px}summary{font-weight:650;cursor:pointer}li{margin:8px 0;font-size:14px}ul{padding-left:22px}.hash{font-family:ui-monospace,monospace;font-size:12px;overflow-wrap:anywhere}footer{padding:8px 8px 24px;color:#586977;font-size:14px}a{color:#007b68}b{font-weight:650}@media(max-width:650px){main{padding:24px 15px}h1{font-size:32px}section{padding:20px 16px}.cards{grid-template-columns:1fr}.cards article{padding:16px}.cards strong{font-size:30px}.wordmark span{display:block;margin:4px 0}table{font-size:13px}}@media print{body{background:#fff}main{max-width:none;padding:0}section,.cards article{break-inside:avoid}details{display:block}summary{list-style:none}}
    </style></head><body><main>''' + ''.join(body) + '</main></body></html>'
