# Fixed-world synthetic calibration

Every predeclared world is included. These are known generator effects, not demonstrated real trading skill.

The common per-period Sharpe hurdle is 0.05, alpha is 0.05, and each world has six registered candidates and 252 distinct sessions. Primary runs only; no seed pooling.

Rank 1 includes ties and does not imply qualification: several agents can share a zero score and rank 1. Rank-1 fractions can therefore sum above 100%.

| Scenario | Supported assumptions | Any false qualification | Completed worlds |
| --- | --- | --- | --- |
| null-independent | True | 20/500 (4.0%; 95% MC interval 2.6%–6.1%) | 500 |
| null-correlated | True | 17/500 (3.4%; 95% MC interval 2.1%–5.4%) | 500 |
| mixed-correlated | True | 13/500 (2.6%; 95% MC interval 1.5%–4.4%) | 500 |
| unsupported-serial | False | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 50 |
| unsupported-reused | False | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 50 |

## null-independent

Qualification is power only for population Sharpe above the hurdle. The other rows are nulls; their qualification is a false positive. Rates include abstentions.

| Agent | Population net Sharpe | Qualified | Eligible | Rank 1 |
| --- | ---: | --- | --- | --- |
| strong-edge | 0.05 | 4/500 (0.8%; 95% MC interval 0.3%–2.0%) | 359/500 (71.8%; 95% MC interval 67.7%–75.6%) | 187/500 (37.4%; 95% MC interval 33.3%–41.7%) |
| modest-edge | 0.05 | 2/500 (0.4%; 95% MC interval 0.1%–1.4%) | 358/500 (71.6%; 95% MC interval 67.5%–75.4%) | 174/500 (34.8%; 95% MC interval 30.8%–39.1%) |
| boundary-a | 0.05 | 4/500 (0.8%; 95% MC interval 0.3%–2.0%) | 349/500 (69.8%; 95% MC interval 65.6%–73.7%) | 177/500 (35.4%; 95% MC interval 31.3%–39.7%) |
| boundary-b | 0.05 | 4/500 (0.8%; 95% MC interval 0.3%–2.0%) | 368/500 (73.6%; 95% MC interval 69.6%–77.3%) | 182/500 (36.4%; 95% MC interval 32.3%–40.7%) |
| zero-edge | 0.05 | 3/500 (0.6%; 95% MC interval 0.2%–1.7%) | 348/500 (69.6%; 95% MC interval 65.4%–73.5%) | 183/500 (36.6%; 95% MC interval 32.5%–40.9%) |
| losing-independent | 0.05 | 4/500 (0.8%; 95% MC interval 0.3%–2.0%) | 350/500 (70.0%; 95% MC interval 65.8%–73.9%) | 172/500 (34.4%; 95% MC interval 30.4%–38.7%) |

Strong-edge ranks above modest-edge in 58/500 (11.6%; 95% MC interval 9.1%–14.7%); both were scored in 259 worlds, with 152 ties. This is rank recovery only in mixed worlds; all-null agent names carry no effect ordering.
All candidates were unscored in 0 worlds. Full rank histograms, refusal reasons and every seed are in calibration.json.

## null-correlated

Qualification is power only for population Sharpe above the hurdle. The other rows are nulls; their qualification is a false positive. Rates include abstentions.

| Agent | Population net Sharpe | Qualified | Eligible | Rank 1 |
| --- | ---: | --- | --- | --- |
| strong-edge | 0.05 | 4/500 (0.8%; 95% MC interval 0.3%–2.0%) | 358/500 (71.6%; 95% MC interval 67.5%–75.4%) | 224/500 (44.8%; 95% MC interval 40.5%–49.2%) |
| modest-edge | 0.05 | 5/500 (1.0%; 95% MC interval 0.4%–2.3%) | 351/500 (70.2%; 95% MC interval 66.0%–74.0%) | 202/500 (40.4%; 95% MC interval 36.2%–44.8%) |
| boundary-a | 0.05 | 3/500 (0.6%; 95% MC interval 0.2%–1.7%) | 340/500 (68.0%; 95% MC interval 63.8%–71.9%) | 201/500 (40.2%; 95% MC interval 36.0%–44.6%) |
| boundary-b | 0.05 | 6/500 (1.2%; 95% MC interval 0.6%–2.6%) | 343/500 (68.6%; 95% MC interval 64.4%–72.5%) | 199/500 (39.8%; 95% MC interval 35.6%–44.2%) |
| zero-edge | 0.05 | 5/500 (1.0%; 95% MC interval 0.4%–2.3%) | 360/500 (72.0%; 95% MC interval 67.9%–75.8%) | 209/500 (41.8%; 95% MC interval 37.6%–46.2%) |
| losing-independent | 0.05 | 5/500 (1.0%; 95% MC interval 0.4%–2.3%) | 345/500 (69.0%; 95% MC interval 64.8%–72.9%) | 196/500 (39.2%; 95% MC interval 35.0%–43.5%) |

Strong-edge ranks above modest-edge in 58/500 (11.6%; 95% MC interval 9.1%–14.7%); both were scored in 286 worlds, with 183 ties. This is rank recovery only in mixed worlds; all-null agent names carry no effect ordering.
All candidates were unscored in 25 worlds. Full rank histograms, refusal reasons and every seed are in calibration.json.

## mixed-correlated

Qualification is power only for population Sharpe above the hurdle. The other rows are nulls; their qualification is a false positive. Rates include abstentions.

| Agent | Population net Sharpe | Qualified | Eligible | Rank 1 |
| --- | ---: | --- | --- | --- |
| strong-edge | 0.30 | 427/500 (85.4%; 95% MC interval 82.0%–88.2%) | 463/500 (92.6%; 95% MC interval 90.0%–94.6%) | 459/500 (91.8%; 95% MC interval 89.1%–93.9%) |
| modest-edge | 0.15 | 88/500 (17.6%; 95% MC interval 14.5%–21.2%) | 453/500 (90.6%; 95% MC interval 87.7%–92.9%) | 39/500 (7.8%; 95% MC interval 5.8%–10.5%) |
| boundary-a | 0.05 | 8/500 (1.6%; 95% MC interval 0.8%–3.1%) | 351/500 (70.2%; 95% MC interval 66.0%–74.0%) | 7/500 (1.4%; 95% MC interval 0.7%–2.9%) |
| boundary-b | 0.05 | 7/500 (1.4%; 95% MC interval 0.7%–2.9%) | 353/500 (70.6%; 95% MC interval 66.5%–74.4%) | 9/500 (1.8%; 95% MC interval 0.9%–3.4%) |
| zero-edge | 0.00 | 1/500 (0.2%; 95% MC interval 0.0%–1.1%) | 212/500 (42.4%; 95% MC interval 38.1%–46.8%) | 3/500 (0.6%; 95% MC interval 0.2%–1.7%) |
| losing-independent | -0.10 | 0/500 (0.0%; 95% MC interval 0.0%–0.8%) | 24/500 (4.8%; 95% MC interval 3.2%–7.0%) | 1/500 (0.2%; 95% MC interval 0.0%–1.1%) |

Strong-edge ranks above modest-edge in 413/500 (82.6%; 95% MC interval 79.0%–85.7%); both were scored in 420 worlds, with 3 ties. This is rank recovery only in mixed worlds; all-null agent names carry no effect ordering.
All candidates were unscored in 1 worlds. Full rank histograms, refusal reasons and every seed are in calibration.json.

## unsupported-serial

Qualification is power only for population Sharpe above the hurdle. The other rows are nulls; their qualification is a false positive. Rates include abstentions.

| Agent | Population net Sharpe | Qualified | Eligible | Rank 1 |
| --- | ---: | --- | --- | --- |
| strong-edge | 0.30 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| modest-edge | 0.15 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| boundary-a | 0.05 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| boundary-b | 0.05 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| zero-edge | 0.00 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| losing-independent | -0.10 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |

Strong-edge ranks above modest-edge in 0/50 (0.0%; 95% MC interval 0.0%–7.1%); both were scored in 0 worlds, with 0 ties. This is rank recovery only in mixed worlds; all-null agent names carry no effect ordering.
All candidates were unscored in 50 worlds. Full rank histograms, refusal reasons and every seed are in calibration.json.

## unsupported-reused

Qualification is power only for population Sharpe above the hurdle. The other rows are nulls; their qualification is a false positive. Rates include abstentions.

| Agent | Population net Sharpe | Qualified | Eligible | Rank 1 |
| --- | ---: | --- | --- | --- |
| strong-edge | 0.30 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| modest-edge | 0.15 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| boundary-a | 0.05 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| boundary-b | 0.05 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| zero-edge | 0.00 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |
| losing-independent | -0.10 | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) | 0/50 (0.0%; 95% MC interval 0.0%–7.1%) |

Strong-edge ranks above modest-edge in 0/50 (0.0%; 95% MC interval 0.0%–7.1%); both were scored in 0 worlds, with 0 ties. This is rank recovery only in mixed worlds; all-null agent names carry no effect ordering.
All candidates were unscored in 50 worlds. Full rank histograms, refusal reasons and every seed are in calibration.json.

## Limits

- All worlds and population effects are original synthetic teaching data, not actual agent capability or market evidence.
- PSR supplies approximate marginal p-values. Holm controls familywise error only when those p-values are valid; finite simulations cannot prove universal calibration.
- All rates include eligibility and positive-wealth gates. Their abstentions reduce power and can reduce familywise error.
- Wilson intervals describe Monte Carlo world-count uncertainty, not uncertainty in a real strategy or a posterior probability of skill.
- Correlated agents are supported only with valid serially independent marginal returns. Unsupported serial/reused scenarios test refusal, not robust inference.
- Rank stability is not a statistical test of pairwise superiority. One window cannot establish repeatable performance across markets or regimes.

## Reproduction fingerprints

Python: 3.13.7. Canonical protocol SHA-256: 8d6ae389312bc5e1686e21d78905d4e3b8238fe7addc80780d5038f31e5e39fb.

```json
{
  "sharpeval.cohort": "ac12f7d6667307a8a89fa9404f51bdd9473ea198f29fcdfecacd2e8f7ff7cc3e",
  "sharpeval.cohort_fixtures": "cff5c8d1bc3476282547d07b32c48aa8973c5177e0072e3192367952f3f33c3b"
}
```
