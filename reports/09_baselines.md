# S9 — Baselines (FROZEN)

Run 2026-10-27. Code: `src/metrics.py` (shared scorer for every later model), `src/baselines.py`.
Full table incl. validation and 95% CIs: `reports/09_baselines.csv`. Exact evaluation rows: `reports/09_eval_rows.csv`.
**These numbers do not change.** Every model in S10+ is scored by the same `metrics.py` on the same rows and
reported next to them.

## Metrics

- **Absolute**: MAE and median absolute error in minutes; bias = mean(pred − actual).
- **Relative**: RMSE of log error after removing the median log error (level shift removed); Spearman rank correlation.
- **Asymmetry**: % of hospitals under-predicted / over-predicted by more than 15 min.
- 95% CIs from 1,000 bootstrap resamples (one row per hospital in a single test year).

## Test year 2024

### Forecasting regime — the hospital's own past is allowed (n = 3,997 with a prior reported year)

| Baseline | MAE (min) [95% CI] | Median AE | Bias | Rel. RMSE (log) | Spearman [95% CI] | Under >15 | Over >15 |
|---|---|---|---|---|---|---|---|
| **B0 persistence** (last reported year) | **11.9 [11.5, 12.3]** | 9 | +2.5 | 0.102 | **0.953 [0.949, 0.956]** | 9.9% | 16.6% |
| B0m mean of all prior years | 15.4 [15.0, 15.8] | 11.7 | −6.4 | 0.124 | 0.924 [0.919, 0.929] | 28.2% | 11.2% |

By type, B0: acute care MAE 12.9, Spearman 0.939 (n = 2,798) · critical access MAE 9.4, Spearman 0.852 (n = 1,168).

B0m is worse because averaging in 2018–2019 drags the forecast toward the pre-COVID level (bias −6.4 min,
28% of hospitals under-predicted by >15 min). The most recent year is the better summary of a hospital.

### Structural regime — test hospitals never seen in training (n = 832)

| Baseline | MAE (min) [95% CI] | Median AE | Bias | Rel. RMSE (log) | Spearman [95% CI] | Under >15 | Over >15 |
|---|---|---|---|---|---|---|---|
| **B1 state × type median** (2022 train hospitals) | **29.0 [27.0, 30.8]** | 21 | −1.3 | 0.238 | **0.675 [0.634, 0.713]** | 28.6% | 32.7% |
| B2 national type median | 32.4 [30.4, 34.3] | 24.5 | −0.5 | 0.260 | 0.595 [0.553, 0.635] | 29.4% | 35.9% |

B1 falls back to the national type median for 26 of 832 test rows (state × type cells with < 5 training hospitals).
By type, B1: acute care MAE 33.3, Spearman 0.466 · critical access MAE 17.6, Spearman 0.221.
B2 has no within-type Spearman by construction (one value per type).

## What the baselines already say

1. **The gap to beat.** Knowing *which hospital* (persistence) gives MAE 11.9 min and rank r = 0.95. Knowing only its
   state and type gives MAE 29.0 and r = 0.68. Model A's job is to show how much of that 17-minute gap is explained by
   what a hospital *is* (volume, rurality, ownership, county context) rather than its identity.
2. **Within type, state alone ranks critical access EDs poorly** (Spearman 0.22) and acute care moderately (0.47).
3. **Persistence over-predicts more than it under-predicts in 2024** (16.6% vs 9.9% beyond 15 min) — consistent with the
   national acute-care median easing from 174 (2023) to 170 (2024).
4. **Level shift is small for these splits.** The structural baselines use 2022, already post-COVID, so their bias is
   ≈ −1 min. The relative metrics are still reported so later models can't win on level alone.
