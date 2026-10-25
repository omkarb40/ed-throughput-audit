"""S4: assemble the ED panel — one row per (ccn, measure, collection window).

Dedup rule: each (measure, window) can appear in several snapshots; keep the LATEST snapshot.
Window identity comes from the row's own start/end dates, never from snapshot position.
"""
import pandas as pd

ED_MEASURES = ["OP_18a", "OP_18b", "OP_18c", "OP_18d", "OP_22", "EDV"]
EDV_ORDER = {"low": 1, "medium": 2, "high": 3, "very high": 4}

f = pd.read_parquet("data/interim/te_long.parquet")
f = f[f.measure_id.isin(ED_MEASURES)].copy()
f = f.rename(columns={"start_date": "window_start", "end_date": "window_end",
                      "snapshot_date": "source_snapshot"})

# EDV is categorical text with inconsistent case -> ordinal 1..4
edv = f.measure_id == "EDV"
f.loc[edv, "score"] = f.loc[edv, "score_raw"].str.lower().map(EDV_ORDER)

key = ["ccn", "measure_id", "window_start", "window_end"]
f["n_snapshots_with_window"] = f.groupby(["measure_id", "window_start", "window_end"]) \
                                .source_snapshot.transform("nunique")

# revision audit before dedup: same hospital+window, different score across snapshots
rev = (f.groupby(key).score.agg(["nunique", "min", "max", "count"]).reset_index())
rev = rev[rev["count"] > 1]
rev_summary = (rev.assign(revised=rev["nunique"] > 1, delta=rev["max"] - rev["min"])
                  .groupby("measure_id")
                  .agg(pairs_seen_twice=("revised", "size"), pairs_revised=("revised", "sum"),
                       max_abs_change=("delta", "max")))

# Take each (measure, window) WHOLESALE from its latest snapshot. Row-level "latest per hospital"
# would resurrect hospitals CMS dropped in a later revision of the same window.
latest = f.groupby(["measure_id", "window_start", "window_end"]).source_snapshot.transform("max")
panel = f[f.source_snapshot == latest].reset_index(drop=True)
panel["window_months"] = ((panel.window_end.dt.year - panel.window_start.dt.year) * 12
                          + panel.window_end.dt.month - panel.window_start.dt.month + 1)
panel["is_calendar_year"] = ((panel.window_start.dt.month == 1) & (panel.window_start.dt.day == 1)
                             & (panel.window_end.dt.month == 12) & (panel.window_end.dt.day == 31)
                             & (panel.window_start.dt.year == panel.window_end.dt.year))
panel["year"] = panel.window_start.dt.year.where(panel.is_calendar_year)

cols = ["ccn", "measure_id", "window_start", "window_end", "window_months", "is_calendar_year",
        "year", "score", "score_raw", "sample", "is_flagged", "footnote_codes",
        "source_snapshot", "n_snapshots_with_window"]
panel = panel[cols]

assert not panel.duplicated(key).any(), "duplicate panel keys"
panel.to_parquet("data/interim/ed_panel.parquet", index=False)

# ---- drift / coverage report
cov = (panel.groupby(["measure_id", "window_start", "window_end"])
            .agg(months=("window_months", "first"), cal_year=("is_calendar_year", "first"),
                 n_ccn=("ccn", "nunique"), n_numeric=("score", lambda s: int(s.notna().sum())),
                 pct_flagged=("is_flagged", lambda s: round(100 * s.mean(), 1)),
                 median=("score", "median"), source=("source_snapshot", "max"))
            .reset_index())
cov.to_csv("reports/04_window_coverage.csv", index=False)
rev_summary.to_csv("reports/04_revisions.csv")

pd.set_option("display.width", 220)
print("panel:", panel.shape)
print(panel.assign(w=panel.window_start.astype(str) + panel.window_end.astype(str))
           .groupby("measure_id").agg(windows=("w", "nunique"),
                                      cal_windows=("year", "nunique"), rows=("ccn", "size")))
print("\nrevisions across snapshots of the same window:\n", rev_summary)
print("\nOP_18b windows:\n", cov[cov.measure_id == "OP_18b"].drop(columns="measure_id").to_string(index=False))
