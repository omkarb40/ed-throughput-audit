# S4 — Panel assembly

Run 2026-10-25. Code: `src/build_panel.py`. Outputs: `data/interim/ed_panel.parquet` (git-ignored),
`reports/04_window_coverage.csv`, `reports/04_revisions.csv`.

## Gate verdict: PASS

- Key `(ccn, measure_id, window_start, window_end)` is unique (asserted in code).
- 375,784 rows across 6 measures: OP_18a, OP_18b, OP_18c, OP_18d, OP_22, EDV.
- Hospital counts per OP_18b window move smoothly, 4,623–4,784; no jumps.

## Dedup rule (and a bug caught on the way)

Each `(measure, window)` is taken **wholesale from its latest snapshot**.
First attempt kept the latest row per hospital instead; that resurrected hospitals CMS had dropped in a later
revision (CY2019 showed 4,799 hospitals vs 4,775 in its latest snapshot). Fixed before any downstream use.

## What's in the panel

| Measure | Windows | Calendar-year windows | Note |
|---|---|---|---|
| OP_18b | 28 | 6 (2018, 2019, 2021–2024) | **Primary target** |
| OP_18c | 28 | 6 | Psych patients; secondary target |
| OP_18a, OP_18d | 4 | 1 (2024) | Only since Oct 2025 release; too short for panel use |
| OP_22 | 8 | 8 (2017–2024) | Left without being seen; covariate |
| EDV | 8 | 8 (2017–2024) | ED volume, ordinal 1–4 (low/medium/high/very high); covariate. Has CY2020. |

EDV text arrived in mixed case (`low` vs `Low`); normalized before mapping.

## OP_18b calendar-year panel

| Year | Hospitals | Numeric scores | % flagged | Median (min) |
|---|---|---|---|---|
| 2018 | 4,757 | 4,066 | 19.0 | 135 |
| 2019 | 4,775 | 4,064 | 22.6 | 136 |
| 2021 | 4,708 | 4,066 | 19.7 | 150 |
| 2022 | 4,692 | 4,069 | 18.0 | 154 |
| 2023 | 4,647 | 4,036 | 19.2 | 152 |
| 2024 | 4,659 | 4,052 | 19.0 | 148 |

4,405 hospitals have a numeric OP_18b in at least one calendar year. Years present per hospital:
6 → 3,680 · 5 → 170 · 4 → 181 · 3 → 102 · 2 → 121 · 1 → 151.
The **balanced core is 3,680 hospitals × 6 years**. Whether the other 725 enter the FE model is an S5/S8 decision,
because dropping them is non-random.

## CMS revises published numbers

When the same window was republished in a later snapshot, values changed:

| Measure | Hospital-windows seen twice+ | Revised | Max change |
|---|---|---|---|
| OP_18b | 12,177 | 3,054 (25%) | 64 min |
| OP_18c | 8,961 | 2,238 (25%) | 1,020 min |
| OP_22 | 29,333 | 7 | 4 pts |
| EDV | 29,398 | 7 | 3 categories |

A quarter of republished OP_18b values changed. Any evaluation that scores predictions against a
"first published" value would be scoring against numbers CMS itself later corrected. Latest-snapshot rule avoids that.
