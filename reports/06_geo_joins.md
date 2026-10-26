# S6 — Covariate joins

Run 2026-10-25. Code: `src/build_geo.py`, `src/build_analysis_table.py`. Sources: `data/external_sources.md`.
Outputs (git-ignored): `data/interim/hospital_geo.parquet`, `data/interim/analysis_table.parquet`.

## Gate verdict: PASS for geography and rurality; ACS pending (API key)

| Join | Matched | Note |
|---|---|---|
| County FIPS | 4,921 / 4,922 | Only miss: 1 US Virgin Islands hospital (no RUCC coverage; out of scope) |
| RUCC 2023 rurality | 4,921 / 4,922 | metro 2,978 · nonmetro adjacent/large 865 · rural 1,078 |
| Coordinates | 4,921 / 4,922 | ZIP centroid 4,805 · county centroid 110 · CT town centroid 6 |
| ACS 2022 county profile | — | Census API now requires a key; first two requests returned "Missing Key" / "Invalid Key" pages |

## County assignment: CMS name first, ZIP second

First attempt used ZIP → ZCTA → county (largest land overlap). It disagreed with CMS's own county name for 133 hospitals.
Inspection showed CMS was right in the cases checked:
- ZIPs straddle counties (e.g. Barrington IL hospital in Lake Co.; ZIP's largest area is Cook).
- Virginia independent cities (Salem city, Franklin city) are county-equivalents; ZIP method assigned the surrounding county.
- Accent mismatch in Puerto Rico (MANATI vs Manatí) — normalization bug, fixed.

Final order: CMS county name + state → 2023 Gazetteer (4,869) · Connecticut town → planning region (30) · ZIP fallback (22).
Cross-check where both exist: CMS-name county = ZIP county for **98.0%** of 4,759 hospitals.

## Connecticut

Census replaced CT's 8 counties with 9 planning regions in 2022; RUCC 2023 and ACS 2022 use the new codes, the 2020
ZCTA file uses the old ones. CT hospitals are mapped town → planning region via the 2023 county-subdivision Gazetteer
(region = first 5 digits of the town GEOID). Two CMS "cities" are villages, not towns: Willimantic (→ Windham town,
Southeastern CT region) and Stafford Springs (→ Stafford town, Capitol region), assigned by nearest town centroid
to the ZIP centroid; both recorded in `fips_source`.

## Analysis table

`analysis_table.parquet`: 27,642 rows = 4,922 hospitals × reported calendar years (2018, 2019, 2021–2024).
Acute care 3,470 · critical access 1,417 · DoD 35.
Columns: op18b (target, 88.1% non-null), status, op18b_flagged, op18c (67.1%), op22_lwbs_pct (78.9%), edv (79.0%),
type, ownership_group, emergency_services, state, fips, rucc_2023, rurality, lat, lon, coord_source (+ ACS when available).

Caveat: rurality and ACS are single-vintage county attributes (2023 / 2018–22), so they are constant within a
hospital over the panel. In the fixed-effects model (S11) they are absorbed by the hospital effect; they matter for
the between-hospital model (S10, Model A) and for slicing (S15).
