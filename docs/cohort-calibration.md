# Can the rank distinguish stipulated effects from lucky outcomes?

Under a controlled generator, it often identifies a strong known effect while
leaving modest effects unconvincing. It also produces some false qualifications,
as a statistical procedure should be expected to do. This is useful evidence about
the evaluator's behavior, **not evidence of any real agent's skill**.

The protocol was frozen on **22 October 2026 at 16:53:39 UTC**, before its declared
calibration seeds were evaluated. One unrelated fixed demonstration fixture had
already been smoke-tested during implementation. No results were used to choose
these seeds, change the rules or exclude worlds. The original protocol bytes have
SHA-256 `59f15c6565afcbab3ce741496ab57948a75ee0f0aa91079a33d9721b10131c5d`.

## Fixed experiment

All five scenarios, all 1,600 seeds and their outcomes are retained in
[`examples/cohort/calibration.json`](../examples/cohort/calibration.json).
The full [protocol](../examples/cohort/calibration-protocol.json),
[tabulated summary](../examples/cohort/summary.md) and
[generator](../sharpeval/cohort_fixtures.py) are included in the source release.

Each world contains six registered agents and 252 equally spaced synthetic
sessions. Supported worlds use iid Gaussian sessions, a per-session standard
deviation of 0.01, a hypothetical known fee of 0.0001 of starting equity, a common
net Sharpe hurdle of 0.05 and alpha 0.05. The gross return includes the fee, which
the evaluator deducts once. Correlated cases share a Gaussian shock; the losing
mixed-case agent is independently generated. Normal simple returns are a teaching
model with unbounded support, not a realistic execution simulator. No generated
path hit the input bounds and no world was discarded or resampled.

The all-null agents' population Sharpes all equal the hurdle. In mixed worlds they
are 0.30, 0.15, 0.05, 0.05, 0 and -0.10. These are stipulated population effects,
not learned strategies. A common risk policy, positive net wealth relative to
cash, moment checks and the dependence screen remain active in every world.
Their refusals stay in the denominator, so power is not conditional on survivors.

The serial stress has AR(1) coefficient 0.7 and explicitly unsupported serial
independence. The reuse stress explicitly declares a reused evaluation window.
These exercise refusal behavior; zero qualifications there cannot validate PSR
under serial dependence or reused holdouts.

Independent simulated worlds are repeated experiments for measuring the
procedure's behavior. Re-running an actual agent's seeds on the same market
history is different: those replays do not multiply distinct market observations.
Calibration uses one primary execution per agent and never pools worlds into a
larger Sharpe sample.

## All predeclared results

The error measure is **the fraction of worlds with any false qualification in the
whole registered family**, not the per-agent false-positive fraction. Intervals
below are two-sided 95% Wilson Monte Carlo intervals for world counts.

| Scenario | Any false qualification | 95% Monte Carlo interval |
| --- | ---: | ---: |
| All-null, independent agents, 500 worlds | 20/500 = 4.0% | 2.6%–6.1% |
| All-null, correlated agents (rho 0.6), 500 worlds | 17/500 = 3.4% | 2.1%–5.4% |
| Mixed effects, correlated agents (rho 0.4), 500 worlds | 13/500 = 2.6% | 1.5%–4.4% |
| Unsupported serial stress, 50 worlds | 0/50 | All 300 agents unscored |
| Reused-window stress, 50 worlds | 0/50 | All 300 agents unscored |

The all-null estimates are consistent with the nominal 5% familywise level in
these particular experiments. Their intervals extend above 5%; they do **not**
prove a universal error bound or exact finite-sample calibration. Holm's theoretical
guarantee requires valid marginal p-values, whereas the PSR approximation and
moment estimates are imperfect. A clean independence screen is not a proof of iid.

For the 500 mixed worlds:

| Agent's stipulated net Sharpe | Qualified | 95% Monte Carlo interval | Eligible | Rank 1, including ties |
| --- | ---: | ---: | ---: | ---: |
| Strong effect: 0.30 | 427/500 = 85.4% | 82.0%–88.2% | 463/500 | 459/500 = 91.8% |
| Modest effect: 0.15 | 88/500 = 17.6% | 14.5%–21.2% | 453/500 | 39/500 = 7.8% |
| Boundary A: 0.05 | 8/500 = 1.6% | 0.8%–3.1% | 351/500 | 7/500 |
| Boundary B: 0.05 | 7/500 = 1.4% | 0.7%–2.9% | 353/500 | 9/500 |
| Zero effect: 0.00 | 1/500 = 0.2% | 0.0%–1.1% | 212/500 | 3/500 |
| Losing, independent: -0.10 | 0/500 | 0.0%–0.8% | 24/500 | 1/500 |

Only the first two qualification fractions are power. The others are false-positive
fractions; do not add them to estimate familywise error because multiple false
qualifications may occur in one world. The losing agent received no qualification
despite low peer correlation. It can still have a lucky positive sample and get a
low or zero score; the method does not have access to the true effect.

The strong-effect agent ranked strictly above the modest-effect agent in 413/500
worlds (82.6%, interval 79.0%–85.7%). Both were scored in 420 worlds, with three ties.
The full rank histograms include an `unscored` bucket. Rank-1 fractions include
ties and can sum above 100%. If all eligible agents have score zero, all share
rank 1 while none qualifies. Always read score and qualification together.

The low power for the modest effect is a substantive limitation of this
252-session, six-candidate experiment. Failure to qualify does not establish no
skill. The value is an explicit, inspectable distinction between a noisy point
estimate and evidence above a chosen hurdle, with the cost of selection visible.
It is not a magic skill detector.

## Reproduce and audit

From a checkout or source release using Python 3.11+:

```sh
python -m unittest discover -s tests -v
python -m tools.calibrate_cohort \
  --protocol examples/cohort/calibration-protocol.json --output output/calibration
python -m sharpeval fixture-cohort --out output/cohort.json
python -m sharpeval rank output/cohort.json --output output/cohort-report
```

No network or dependency installation is needed for this source route. The
calibration script records the actual generator/ranking source hashes, runtime,
canonical protocol hash, every seed, raw/adjusted p-values, scores, eligibility
reasons and ranks. Progress prints every 50 worlds. The frozen run used Python
3.13.7. Different Python versions may change floating-point details or metadata.
Never reroll a failed or inconvenient world. A correctness repair must be recorded
and every world rerun, retaining the earlier artifact.

The single report fixture uses seed 20261022, declared before this calibration.
Its ordering puts a boundary agent above the modest-effect agent. This noisy
example is retained as-is; the aggregate experiment explains why one leaderboard
cannot prove repeatability or pairwise superiority.

All generators, data and scripts here are original MIT-licensed synthetic work.
There is no private or third-party market data, adoption measurement, real AI-agent
evaluation, prospective trading record or independently unseen market holdout.
Browser rendering remains unverified; structural HTML checks are separate evidence.
