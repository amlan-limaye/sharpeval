"""Self-contained cohort report. Components remain separate from evidence rank."""

from html import escape
import json


def e(value):
    return escape(str(value), quote=True)


def fmt(value, digits=6):
    return "Unavailable" if value is None else f"{value:.{digits}g}"


def render_cohort_html(report):
    protocol = report["protocol"]
    rows, details = [], []
    for a in report["agents"]:
        primary, raw = a["primary"], a["raw_psr"]
        metrics = primary["metrics"] or {}
        status = "Qualified conditionally" if a["evidence_qualified"] else "Not qualified" if a["score"] is not None else "Unscored"
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in [
            e(a["rank"] if a["rank"] is not None else "—"), e(a["agent_id"]), e(fmt(a["score"], 10)), e(status),
            e(fmt(metrics.get("sharpe_per_period"))), e(fmt(raw["value"] if raw else None)),
            e(fmt(a["holm_adjusted_p"])), e(fmt(metrics.get("total_return"))),
            e(fmt(primary["efficiency"].get("value"))), e(fmt(primary["independence"].get("value")))]) + "</tr>")
        reasons = "".join(f"<li>{e(reason)}</li>" for reason in a["reasons"])
        details.append(f"<details><summary>{e(a['agent_id'])}: evidence, eligibility and execution records</summary>"
                       f"<p>Version: {e(a['version'])}; primary seed: {e(a['ranking_seed_id'])}; run: {e(a['ranking_run_id'])}.</p>"
                       f"<ul>{reasons or '<li>Declared eligibility checks passed, conditional on producer claims.</li>'}</ul>"
                       f"<p>Sharpe gap above the common hurdle: {e(fmt(a['sharpe_gap_to_hurdle']))} per period. "
                       f"Raw one-sided p: {e(fmt(a['raw_p']))}. Family slot p: {e(fmt(a['family_p_used']))}. "
                       f"Distinct market periods: {a['replays']['distinct_market_periods']}; planned executions: {a['replays']['planned']}; "
                       f"completed: {a['replays']['completed']}; failed: {a['replays']['failed']}; missing: {a['replays']['missing']}.</p>"
                       f"<p>Replay Sharpe range (descriptive): {e(a['replays']['sharpe_range'])}. No inferential aggregation.</p>"
                       f"<pre>{e(json.dumps({'efficiency':primary['efficiency'], 'reference_correlation':primary['independence'], 'discovery_context':a['discovery_context']}, indent=2, allow_nan=False))}</pre></details>")
    run_rows = "".join("<tr>" + "".join(f"<td>{e(value)}</td>" for value in [r["agent_id"], r["seed_id"], r["run_id"], r["status"], r["reason"] or "—"]) + "</tr>" for r in report["runs"])
    warnings = "".join(f"<li>{e(w)}</li>" for w in report["warnings"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{e(report['title'])} · SharpeVal</title><style>
body{{font:16px/1.6 system-ui,sans-serif;color:#172c38;background:#f5f7f8;margin:0}}main{{max-width:1250px;margin:auto;padding:32px 22px}}
h1{{line-height:1.2;font-size:2rem}}h2{{margin-top:2rem}}.notice{{border-left:5px solid #276774;background:#e8f2f4;padding:16px}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;background:white;width:100%}}th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #d7e0e4;white-space:nowrap}}
th{{background:#173d4b;color:white}}details{{margin:12px 0;padding:12px;background:white;border:1px solid #d7e0e4}}summary{{cursor:pointer;font-weight:650}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}code{{overflow-wrap:anywhere}}.meta{{color:#465966}}footer{{margin-top:30px;border-top:1px solid #b9c8cf;padding-top:16px}}
</style></head><body><main><p class="meta">SharpeVal · {e(report['tool']['calculation_profile'])} · {'SYNTHETIC' if report['synthetic'] else 'Imported records'}</p>
<h1>{e(report['title'])}</h1><p class="notice"><strong>Conditional evidence against a common Sharpe hurdle.</strong>
This score is not a probability of skill, a forecast, a pairwise superiority test or proof of repeatable performance.
It ranks one frozen execution per agent on one declared window. Unknown evidence remains unscored.</p>
<p>Common hurdle: <strong>{e(fmt(protocol['hurdle_sharpe_per_period']))} Sharpe per period</strong>; alpha: {e(protocol['alpha'])};
registered family: {report['family_size']} agents; scored: {report['coverage']['scored_agents']};
window: {e(report['calendar']['window_id'])}; {len(report['calendar']['timestamps'])} distinct periods.</p>
<h2>Evidence ranking and separate diagnostics</h2><p>Score = 100 × (1 − Holm-adjusted one-sided p). Raw PSR is a conditional normal tail area.
Equal scores share a rank; IDs only order the display. All returns below are decimal, net of declared costs. Sharpe is not annualized.</p>
<div class="scroll"><table><thead><tr>{''.join('<th>'+h+'</th>' for h in ['Rank','Agent','Evidence score','Status','Sharpe / period','Raw PSR','Holm p','Net total return','Return / exposure','Reference correlation'])}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p>Efficiency uses measured average gross exposure; correlation uses a frozen external reference. Neither changes the primary evidence score.
Low correlation does not establish independence or turn a losing history into skilled performance.</p>
{''.join(details)}<h2>Every planned execution</h2><div class="scroll"><table><thead><tr><th>Agent</th><th>Seed</th><th>Run</th><th>Status</th><th>Reason</th></tr></thead><tbody>{run_rows}</tbody></table></div>
<h2>Declared conditions and common risk limits</h2><pre>{e(json.dumps(protocol, indent=2, allow_nan=False))}</pre>
<h2>Interpretation and limits</h2><ul>{warnings}</ul><footer>Input SHA-256: <code>{e(report['input_sha256'])}</code><br>
Design SHA-256: <code>{e(report['design_sha256'])}</code><p>The design fingerprint identifies declarations; it is not independent proof of preregistration or an untouched holdout.
Swing-inspired, independently specified. No official Swing score, eligibility decision or skill certification.</p></footer></main></body></html>
"""
