"""S9: frozen baselines on the 2024 test year (2023 validation shown for reference).

Forecasting regime (temporal_split; a hospital's own past is allowed):
  B0  persistence      : last reported calendar-year OP_18b
  B0m history mean     : exp(mean of all prior log OP_18b)
Structural regime (grouped_temporal_split; test hospitals never seen):
  B1  state x type     : median OP_18b of TRAIN hospitals, same state and type, latest train year (2022);
                         falls back to national type median when a state x type cell has < 5 hospitals
  B2  national type    : national median of train hospitals by type, 2022
All baselines use only information available before the target year.
"""
import json
import numpy as np
import pandas as pd
from splits import grouped_temporal_split, temporal_split, TRAIN_MAX_YEAR
from features import add_lag_features
from metrics import evaluate_by

t = pd.read_parquet("data/interim/analysis_table.parquet")
df = add_lag_features(t[t.op18b.notna()].reset_index(drop=True))
df["B0"] = df.prev_op18b
df["B0m"] = np.exp(df.prior_mean_log_op18b)
results, frozen = [], []

# ---- forecasting regime
ts = temporal_split(df)
for part in ("val", "test"):
    d = ts[part]
    for b in ("B0", "B0m"):
        r = evaluate_by(d, b); r.insert(0, "baseline", b); r.insert(0, "part", part); r.insert(0, "regime", "forecast")
        results.append(r)
    frozen.append(d[["ccn", "year"]].assign(regime="forecast", part=part, has_prior=d.B0.notna()))

# ---- structural regime
gs = grouped_temporal_split(df)
tr = gs["train"][gs["train"].year == TRAIN_MAX_YEAR]
cell = tr.groupby(["state", "type"]).op18b.agg(["median", "size"])
nat = tr.groupby("type").op18b.median()
for part in ("val", "test"):
    d = gs[part].copy()
    key = list(zip(d.state, d.type))
    med = cell["median"].reindex(key).to_numpy(); n = cell["size"].reindex(key).to_numpy()
    d["B2"] = d.type.map(nat)
    d["B1"] = np.where(n >= 5, med, d.B2)
    d["B1_fallback"] = ~(n >= 5)
    for b in ("B1", "B2"):
        r = evaluate_by(d, b); r.insert(0, "baseline", b); r.insert(0, "part", part); r.insert(0, "regime", "structural")
        results.append(r)
    print(f"structural {part}: B1 fell back to national type median for {int(d.B1_fallback.sum())} of {len(d)} rows")
    frozen.append(d[["ccn", "year"]].assign(regime="structural", part=part, has_prior=d.prev_op18b.notna()))

res = pd.concat(results, ignore_index=True)
res.to_csv("reports/09_baselines.csv", index=False)
pd.concat(frozen).to_csv("reports/09_eval_rows.csv", index=False)
show = ["regime", "part", "baseline", "group", "n", "mae_min", "mae_min_lo", "mae_min_hi", "medae_min", "bias_min",
        "rel_rmse_log", "spearman", "spearman_lo", "spearman_hi", "pct_under_15", "pct_over_15"]
pd.set_option("display.width", 250)
print(res[show].round(3).to_string(index=False))
