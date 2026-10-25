# S2 — Single-snapshot loader

Run 2026-10-24. Code: `src/locate.py`, `src/load.py`, `src/build_long.py`. Per-snapshot checks: `reports/02_load_checks.csv`.

## Gate verdict: PASS — zero silent drops

- 33 snapshots loaded; source CSV record count (csv module, independent of pandas) == loaded rows for **every** snapshot.
- Total: **3,383,120** fact rows (all measures, all snapshots), 155,321 hospital-dimension rows.
- Every CCN is 6 characters; leading zeros preserved (read as strings, `keep_default_na=False`).
- 0 unparsed start/end dates. 0 unmapped columns (loader raises on any new column name).

## Outputs (git-ignored, regenerate with `PYTHONPATH=src python3 src/build_long.py`)

- `data/interim/te_long.parquet` (17.6 MB): snapshot_date, ccn, condition, measure_id, measure_name,
  score_raw, score, sample_raw, sample, footnote, footnote_codes, is_flagged, start_date, end_date.
- `data/interim/hospital_dims.parquet` (1.8 MB): name, address, city, state, zip, county per (snapshot, ccn).

## Data quirks found and how they're handled

| Quirk | Handling |
|---|---|
| One duplicated (ccn, measure) key: CCN 220126, IMM_3, in 4 snapshots; one copy blank | Kept as published. Not an ED measure. ED measures have 0 duplicate keys. |
| Footnotes in two formats: bare codes (`3, 29`) and sentences (`5 - Results are...`) | Normalized to `footnote_codes` (sorted list, e.g. `3,29`). |
| One footnote `***` with no code (CCN 521348, 2021-10-27) | `is_flagged = True`, `footnote_codes` = NA. |
| Suppressed scores published as the string `Not Available` | `score` = NaN, `score_raw` keeps the original. |
| OP_18b: 8,806 scores are numeric **and** footnoted (top codes 3, 3+29, 1+3) | Kept, flagged. Inclusion rule decided in S5, not here. |
| OP_18b range 38 to 1,344 min (p1 = 70, p50 = 144, p99 = 301) | Kept. Outlier treatment decided in S7. |

## OP_18b at a glance

155,321 hospital-snapshot rows; 133,399 numeric (85.9%); of those, 8,806 flagged.
