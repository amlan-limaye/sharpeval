"""Self-contained v2 report. Display failures and assumptions before tail areas."""

from .report import bps, change_table, chart, ci_text, e, metric_table, num, pct, table


def _stat(value):
    if value["status"] != "conditional":
        return "Unavailable"
    return f'{value["value"]:.4f} (conditional)'


def render_experiment_html(r):
    coverage = r["coverage"]
    tag = "SYNTHETIC EXAMPLE" if r["synthetic"] else "IMPORTED HISTORICAL EXPERIMENT"
    body = [f'<header><div class="wordmark">SharpeVal <span>LOCAL EVIDENCE REPORT · v0.2</span></div><h1>Did the change hold across executions?</h1><p class="subtitle">{e(r["title"])}</p><div class="badge">{tag}</div><p>Run variation, market-time uncertainty and search selection are separate pieces of evidence. None certifies future skill.</p></header>']
    body.append('<div class="cards">' + ''.join(f'<article><span>{label}</span><strong>{value}</strong></article>' for label, value in (
        ("Planned runs", coverage["planned_runs"]), ("Completed", coverage["completed_runs"]),
        ("Failed / missing", f'{coverage["failed_runs"]} / {coverage["missing_runs"]}'),
        ("Unique planned market periods", r["aggregate"]["unique_planned_market_periods"]))) + '</div>')
    body.append('<section><h2>1. Coverage comes first</h2><p>Every declared seed × window × version cell remains visible. Failed and absent runs are not zero returns. An affected window receives no mean-path aggregate or confidence interval.</p>')
    rows = []
    for run in r["runs"]:
        m = run["metrics"] or {}
        cost = run["cost_accounting"] or {}
        rows.append([e(run["window_id"]), e(run["seed_id"]), e(run["version"]), e(run["status"]),
                     pct(m.get("total_return")), pct(m.get("max_drawdown")), bps(cost.get("mean_period_cost_fraction")),
                     e(run["reason"] or run["run_id"])])
    body.append(table(["Window", "Seed", "Version", "Status", "Net return", "Drawdown", "Mean cost", "Run identity / reason"], rows))
    body.append('<p class="note">Per-run mean, volatility, Sharpe, annualization, cost coverage and net returns are retained in the JSON. Gross costs are deducted once; supplied net returns are not charged again.</p>')
    overlap_rows = [[e(o["left_window"]), e(o["right_window"]), str(o["shared_periods"])] for o in r["aggregate"]["overlap_pairs"]]
    if overlap_rows:
        body.append('<div class="callout"><b>Overlapping market windows are present.</b> Shared periods are counted once in the coverage union. No pooled statistic or across-window interval is produced.</div>')
        body.append(table(["Window", "Overlaps", "Shared periods"], overlap_rows))
    else:
        body.append('<p>The declared windows do not overlap. They are still reported separately; disjoint dates do not establish independent regimes.</p>')
    body.append('</section><section><h2>2. Execution variation and market time</h2>')
    for window in r["windows"]:
        c = window["coverage"]
        body.append(f'<h3>{e(window["window_id"])} · {c["complete_pairs"]}/{c["planned_pairs"]} complete pairs</h3>')
        spread = window["execution_dispersion"]["paired_changes"]
        body.append(table(["Observed paired change across executions", "Mean", "Sample spread (SD)", "Range", "Defined / supplied"], [
            [e(metric.replace("_", " ")), (num if metric == "sharpe_per_period" else pct)(values["mean"], True),
             (num if metric == "sharpe_per_period" else pct)(values["sample_std"]),
             (num if metric == "sharpe_per_period" else pct)(values["min"], True) + " to " + (num if metric == "sharpe_per_period" else pct)(values["max"], True),
             f'{values["defined_values"]}/{values["expected_values"]}'] for metric, values in spread.items()]))
        body.append(f'<p class="note">{e(window["execution_dispersion"]["warning"])} This spread is not a standard error or confidence interval. Runs share a market path.</p>')
        if window["identical_pair_seed_groups"]:
            body.append('<p><b>Identical paired paths:</b> ' + e("; ".join(", ".join(group) for group in window["identical_pair_seed_groups"])) + '. Copies do not add market-time observations.</p>')
        aggregate = window["aggregate"]
        if aggregate["status"] == "unavailable":
            body.append('<div class="callout"><b>Window aggregate unavailable.</b><ul>' + ''.join(f'<li>{e(reason)}</li>' for reason in aggregate["reasons"]) + '</ul></div>')
            continue
        comp = aggregate["comparison"]
        old_id, new_id = comp["comparison"]["old"], comp["comparison"]["new"]
        body.append(f'<h4>Mean-execution path: {aggregate["seeds_averaged"]} seeds, {aggregate["distinct_market_periods"]} time observations</h4><p>{e(aggregate["interpretation"])}</p>')
        body.append(metric_table([(r["versions"]["old"], comp["series"][old_id]["metrics"]), (r["versions"]["new"], comp["series"][new_id]["metrics"])]))
        body.append(chart([(r["versions"]["old"], comp["series"][old_id]["metrics"]["net_wealth"]), (r["versions"]["new"], comp["series"][new_id]["metrics"]["net_wealth"])], "Per-window mean execution paths"))
        primary = comp["uncertainty"]["primary"]
        body.append(change_table(comp["comparison"]["observed_change"], primary["contrasts"].get("new_minus_old", {})))
        body.append(f'<p class="note">{comp["uncertainty"]["confidence"]:.0%} paired temporal-block intervals, conditional on observed executions. Seed {comp["uncertainty"]["seed"]}; {comp["uncertainty"]["resamples"]} draws. Changes are new minus old; negative volatility/drawdown changes mean smaller observed risk.</p>')
        sensitivity = comp["uncertainty"]["sensitivity"]
        body.append(table(["Block length", "Mean-change interval / period", "Status"], [[str(s["block_length"]), ci_text(s["contrasts"].get("new_minus_old", {}).get("mean_return")), e(s["status"])] for s in sensitivity]))
        if primary["status"] != "available":
            body.append(f'<p>{e(primary["reason"])}</p>')
        portfolio = comp["portfolio"]
        if portfolio["status"] == "available":
            body.append('<details><summary>Fixed-rule portfolio contribution of the mean-execution path</summary>')
            body.append(f'<p>Candidate weight {portfolio["rules"]["candidate_weight"]:.0%}, reset every period, extra allocation cost {bps(portfolio["rules"]["overlay_cost_per_period"])} per period. No allocation optimization. This mean path is not an executable seed portfolio.</p>')
            body.append(metric_table([(key.replace("_", " "), portfolio["metrics"][key]) for key in ("base", "with_old", "with_new")]))
            body.append(change_table(portfolio["changes"]["with_new_minus_base"], primary["contrasts"].get("with_new_minus_base", {})))
            body.append(f'<p>New versus base correlation: {num(portfolio["candidate_vs_base_correlation"])}. <b>Low correlation is not skill.</b></p></details>')
        body.append('<details><summary>Cost coverage and inherited diagnostic limits</summary>')
        cost_rows = []
        for role, sid in (("old", old_id), ("new", new_id)):
            cost = comp["series"][sid]["cost_accounting"]
            cost_rows.append([e(r["versions"][role]), bps(cost["mean_period_cost_fraction"]),
                              e(", ".join(cost["included"]) or "None declared"),
                              e(", ".join(cost["excluded"]) or "None declared"), e(cost["notes"])])
        body.append(table(["Version", "Mean period cost", "Included", "Excluded", "Cost notes"], cost_rows))
        body.append('<ul>' + ''.join(f'<li>{e(w)}</li>' for w in comp["warnings"]) + '</ul></details>')
    body.append('</section><section><h2>3. Selection-bias diagnostics</h2><div class="callout"><b>These are conditional normal-tail areas, not probabilities that an agent is truly skilled.</b><p>PSR compares a named run with a stated Sharpe bar. DSR applies a selection-adjusted bar under an explicit trial model. Neither is a paired test that the new version improves on the old.</p></div>')
    if not r["selection"]["targets"]:
        body.append('<p>Selection inputs were not supplied. Unknown search history is not treated as zero trials.</p>')
    for target in r["selection"]["targets"]:
        body.append(f'<h3>{e(target["target_run_id"])}</h3>')
        body.append(table(["Diagnostic", "Conditional tail area", "Per-period Sharpe benchmark"], [["Probabilistic Sharpe (PSR)", _stat(target["psr"]), num(target["psr"].get("benchmark_sharpe_per_period"))], ["Deflated Sharpe (DSR)", _stat(target["dsr"]), num(target["dsr"].get("benchmark_sharpe_per_period"))]]))
        for name in ("psr", "dsr"):
            if target[name]["status"] == "unavailable":
                body.append(f'<p><b>{name.upper()} unavailable:</b> ' + e(" ".join(target[name]["reasons"])) + '</p>')
        moments = target.get("moments", {})
        if moments.get("status") == "available":
            body.append(table(["T (actual periods)", "Sharpe / period", "Skewness", "Kurtosis (non-excess)"], [[str(moments["observations"]), num(moments["sharpe_per_period"]), num(moments["skewness"]), num(moments["kurtosis_non_excess"])]]))
            body.append(f'<p class="note">{e(moments["moment_convention"])}. Sharpe uses sample standard deviation (n−1). Ratios are never silently annualized.</p>')
        search = target.get("search")
        if search:
            dispersion = target.get("trial_dispersion_used") or {}
            body.append(table(["Observed attempts", "Assumed independent trials", "Search completeness", "Trial Sharpe SD / period"], [[e(search["observed_trial_count"] if search["observed_trial_count"] is not None else "Unknown"), e(search["effective_independent_trials"] if search["effective_independent_trials"] is not None else "Unknown"), e(search["completeness"]), num(dispersion.get("value"))]]))
            body.append(f'<p>Count source: {e(target.get("trial_count_source", "unavailable"))}. Dispersion source: {e(dispersion.get("source", "unknown"))}. {e(search["notes"])}</p>')
            if target["dsr"].get("sensitivity"):
                body.append(table(["Assumed independent trials (other inputs fixed)", "Selection bar / period", "Conditional DSR"], [[str(s["effective_independent_trials"]), num(s["benchmark_sharpe_per_period"]), f'{s["value"]:.4f}'] for s in target["dsr"]["sensitivity"]]))
        screen = target.get("dependence_screen")
        if screen:
            body.append(f'<p><b>Dependence screen:</b> {e(screen["status"])}. {e(screen["limitation"])}</p>')
        body.append('<details><summary>Declared assumptions and formula limits</summary>')
        if target.get("assumptions"):
            body.append(table(["Assumption", "Producer declaration"], [[e(key.replace("_", " ")), e(value)] for key, value in target["assumptions"].items()]))
        body.append(f'<p>{e(target.get("notes", ""))}</p><ul>' + ''.join(f'<li>{e(w)}</li>' for w in target.get("limitations", [])) + '</ul></details>')
    body.append('</section><section><h2>4. What remains uncertain</h2><ul>' + ''.join(f'<li>{e(w)}</li>' for w in r["warnings"]) + '</ul><p>Input declarations are not independently audited. Choosing seeds, windows, strategies or costs after inspecting outcomes can still bias these results. Missing outcomes and unseen search attempts cannot be repaired by a formula.</p>')
    body.append(f'<p class="hash">Input SHA-256: {e(r["input_sha256"])}<br>Engine {e(r["tool"]["version"])} · Python {e(r["tool"]["python"])}</p></section><footer>Published formula reference: <a href="https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf">Bailey &amp; López de Prado (2014)</a>. Independent implementation; not an official SharpeBench score. Next useful step: collect fresh predeclared market windows while preserving every run and every search attempt.</footer>')
    style = '''body{font:16px/1.58 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#243746;background:#f2f5f7;margin:0}*{box-sizing:border-box}main{max-width:1150px;margin:auto;padding:36px 30px}.wordmark{color:#0e6156;font-size:23px;font-weight:750}.wordmark span{font-size:11px;letter-spacing:.1em;color:#637583;margin-left:14px}h1{font-size:40px;line-height:1.15;letter-spacing:-.035em;margin:26px 0 12px}h2{font-size:25px;line-height:1.3}h3{margin-top:34px;font-size:20px}h4{font-size:17px}.subtitle{color:#586977;font-size:19px}.badge{display:inline-block;padding:6px 12px;background:#fff1c9;border:1px solid #dfc574;font-size:12px;font-weight:bold;border-radius:5px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:25px 0}.cards article,section{background:#fff;border:1px solid #dce3e7;border-radius:12px;padding:24px}.cards span{font-size:12px;color:#637583;display:block}.cards strong{font-size:31px;color:#183f3a;display:block;margin-top:8px}section{margin:22px 0;padding:28px}.callout{background:#f0f6f8;border-left:4px solid #3a7186;padding:16px 20px;border-radius:4px}.note,.small{font-size:13px;color:#637583}.small{display:block}.table-scroll{overflow-x:auto;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:13px;text-align:left;font-variant-numeric:tabular-nums}th,td{padding:11px;border-bottom:1px solid #e3e9ed;vertical-align:top}th{font-size:12px;background:#f5f8f9;color:#586977}td{overflow-wrap:anywhere}p{margin:14px 0}.chart svg{width:100%;height:auto}.legend{display:flex;gap:20px;flex-wrap:wrap;font-size:13px}.legend i{display:inline-block;width:19px;height:3px;margin:0 6px 3px 0}details{margin-top:18px;border-top:1px solid #e3e9ed;padding:16px 0}summary{cursor:pointer;font-weight:650}li{margin:9px 0}.hash{font:12px/1.7 ui-monospace,monospace;overflow-wrap:anywhere}footer{font-size:14px;color:#586977;padding:10px 0 25px}a{color:#007b68}@media(max-width:700px){main{padding:22px 14px}section{padding:20px 14px}.cards{grid-template-columns:1fr 1fr}h1{font-size:31px}.wordmark span{display:block;margin-left:0}}'''
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>' + e(r["title"]) + ' — SharpeVal</title><style>' + style + '</style></head><body><main>' + ''.join(body) + '</main></body></html>'
