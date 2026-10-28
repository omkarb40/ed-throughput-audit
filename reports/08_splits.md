# S8 — Split design

Run 2026-10-26. Code: `src/splits.py`, `src/features.py`. Tests: `tests/test_splits.py`
(`PYTHONPATH=src python3 -m pytest tests -q` → 7 passed). Sizes: `reports/08_split_sizes.csv`.

## Gate verdict: PASS

Zero hospitals shared between train/val/test in the grouped split; every partition is strictly later in time
than the one before it; lag features use only years strictly before the target year.

## Two regimes, because there are two questions

| Regime | Question | Used by | Hospitals shared across partitions? |
|---|---|---|---|
| `temporal_split` | Can you forecast next year? | Persistence baseline, Model B | Yes, deliberately: a hospital's past is the input |
| `grouped_temporal_split` | Can you predict an ED from what it *is*? | Model A (structural only) | **No** |

Both: train ≤ 2022 (2018, 2019, 2021, 2022), validate 2023, test 2024. Calendar-year windows only, so no two rows share
months of data (S7: overlapping windows agree at r = 0.99).

Hospital groups come from `md5(ccn) mod 10`: buckets 0–1 test, 2–3 validate, 4–9 train. Stable regardless of
row order, random seed, or newly added hospitals.

## Sizes

| Split | Part | Rows | Hospitals | Years | % critical access | % rural | Median OP_18b |
|---|---|---|---|---|---|---|---|
| temporal | train | 16,265 | 4,304 | 2018–2022 | 27.2 | 21.2 | 142 |
| temporal | val | 4,036 | 4,036 | 2023 | 28.8 | 21.5 | 152 |
| temporal | test | 4,052 | 4,052 | 2024 | 29.8 | 21.8 | 148 |
| grouped | train | 9,900 | 2,615 | 2018–2022 | 27.1 | 21.0 | 142 |
| grouped | val | 760 | 760 | 2023 | 31.1 | 22.4 | 148 |
| grouped | test | 832 | 832 | 2024 | 28.0 | 21.9 | 150 |

Held-out hospitals match training on critical-access and rural share within ~4 points.

2024 test rows with a prior reported year: 3,997 of 4,052; gap to that year is 1 year for 3,966 of them.

## The level shift problem (carried into S9–S10)

Training years have a median of 142 min; the test year 148–150 (post-COVID rise, S7). A model trained on 2018–2022
under-predicts 2024 everywhere, independent of how well it ranks hospitals. Evaluation will therefore report:
1. **Absolute error** in minutes (includes the level shift — what a patient would see).
2. **Relative error**: log(OP_18b) minus that year's national median log, i.e. ranking quality with the level removed.

## Tests can fail (mutation check)

Two leaks were planted in a scratch copy:
- lag features allowed to use the target year (`<` → `<=`) → **2 tests failed**
- grouped test partition allowed to include all hospitals → **1 test failed**
