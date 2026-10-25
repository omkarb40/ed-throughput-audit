# S1 — Data recon: CMS Timely & Effective Care archives

Run 2026-10-24. Every number here comes from `src/inventory_zips.py`, `src/recon_schema.py`, `src/recon_op18.py`
(raw outputs: `reports/03_download_log.csv`, `01_zip_inventory.csv`, `01_schema_by_snapshot.json`, `01_op18_by_snapshot.csv`).

## Gate verdict: PASS, with "vintage" redefined

34 snapshots downloaded, all valid ZIPs. 33 contain the hospital-level T&E file.
But a snapshot is **not** an observation. The unit of analysis is the **collection window**.

| | Count |
|---|---|
| Snapshots downloaded | 34 |
| Snapshots with T&E hospital file | 33 (2026-09-30 is a partial release, no T&E) |
| Distinct OP_18b collection windows | 28 |
| Snapshots republishing an earlier window | 5 |
| Non-overlapping calendar-year windows | 6: CY2018, 2019, 2021, 2022, 2023, 2024 |

## Findings that change the design

1. **Rolling 12-month windows advance one quarter at a time.** Consecutive windows share 9 of 12 months.
   The 28 windows are not 28 independent observations. Independent panel for the FE model = the 6 calendar-year windows.
   The other 22 are useful only for drift/stability analysis, never as extra training rows.
2. **2020 Q1–Q2 is never reported** (COVID). Windows jump; two are short: 07/2020–12/2020 (6 mo) and 07/2020–03/2021 (9 mo).
   There is no CY2020 window. Panel years: 2018, 2019, [gap], 2021–2024.
3. **Structural level shift.** National OP_18b median: 134–137 min pre-COVID → 143 (late 2020) → 154 (CY2022) → 148 (2024–25).
   Any model must account for year effects; a pooled model will read this as hospital signal.
4. **Duplicates and revisions.** Exact duplicate data: 2021-01-27 = 2021-03-31, 2022-01-06 = 2022-04-06.
   Same window but revised values: 2020-10-16 / 2021-01-27 / 2021-04-28 (CY2019), 2023-07-06 / 2023-10-06.
   Rule: for each window, keep the **latest** snapshot.
5. **OP_22 (left without being seen) is a weak target.** Reported as an integer percent, national median 1–2%,
   annual windows only, 16–38% suppressed (38% in the 2021 release of CY2019). Keep as a secondary covariate, not a target.
6. **OP_18b suppression 12–20%** of hospitals per window, trending down. Missingness analysis is S5.
7. **OP_18a/OP_18d added in the Oct 2025 release** (data dictionary). OP_18b was relabeled ("excluding transfers and psych")
   but its median shows no break at that point (149 → 148). Treated as label change, not redefinition. [Likely, not proven.]
8. **ED_1b / ED_2b / ED_2_Strata** (boarding measures) exist only in some eras and were retired Oct 2025. Not usable as a panel.

## Schema

Long format, one row per hospital × measure. Three column-name variants, all rename-mappable:
`Provider ID`/`Facility ID` → ccn; `Measure Start Date`/`Start Date`; `City`/`City/Town`; `County Name`/`County/Parish`.
Columns used: ccn, measure_id, measure_name, score, sample, footnote, start_date, end_date.
Encoding: UTF-8 except 2023-01-06, 2023-04-06, 2023-07-06 (Latin-1).
File naming has 4 eras; `src/locate.py` matches on dataset ID `yv7e-xc69` first, then on file title.

## Decisions for S2

- Primary target: **OP_18b**. Secondary: OP_18c (psych). OP_22 as a covariate.
- Panel key: `(ccn, window_start, window_end)`, deduplicated to the latest snapshot per window.
- FE / modeling panel: 6 calendar-year windows. Rolling windows kept separately for the drift stage.
- Exclude 2026-09-30 from everything.
