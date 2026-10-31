"""S13: would the numbers have sent a patient to the faster of two nearby EDs in 2024?

For each pair of nearest-neighbour EDs (<= 50 miles) where both hospitals have a 2024 OP-18b:
  truth   = which ED was actually faster in 2024
  signals = last year's published value (what a posted number shows), Model B forecast,
            structural Model A prediction (cross-fitted: each hospital predicted by a model that never saw it),
            coin flip
Scores: % of pairs where the signal picks the faster ED (ties count 1/2); minutes saved versus a coin flip,
and the share of the best possible saving (always picking the faster one) that this captures.
95% CIs from 2,000 bootstrap resamples of pairs.
Structural features and settings are the same as Model A in S10 (reports/10_model_info.json).
"""
import json, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from features import add_lag_features
from splits import hospital_bucket

SEED = 0
CAT = ["type", "ownership_group", "state", "rurality", "emergency_services"]
NUM = ["rucc_2023", "lat", "lon", "log_county_pop", "county_median_hh_income", "county_pct_uninsured",
       "county_pct_65plus", "edv"]

t = pd.read_parquet("data/interim/analysis_table.parquet")
t["log_county_pop"] = np.log(t.county_pop)
df = add_lag_features(t[t.op18b.notna()].reset_index(drop=True))
df["ly"] = np.log(df.op18b)
for c in CAT: df[c] = df[c].astype("category")

# ---- structural predictions for every 2024 hospital, cross-fitted by hospital (5 folds on the stable hash)
info = json.load(open("reports/10_model_info.json"))["A"]
params = dict(num_leaves=info["num_leaves"], min_child_samples=info["min_child_samples"],
              n_estimators=info["n_estimators"], learning_rate=0.03, subsample=0.8, subsample_freq=1,
              colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, verbose=-1)
fold = df.ccn.map(lambda c: hospital_bucket(c, 5))
hist = df[df.year <= 2023]
nat = hist.groupby("year").ly.median()
df["A_cf"] = np.nan
for k in range(5):
    tr = hist[fold.loc[hist.index] != k]
    m = lgb.LGBMRegressor(**params).fit(tr[CAT + NUM], tr.ly - tr.year.map(nat))
    te = df[(df.year == 2024) & (fold == k)]
    df.loc[te.index, "A_cf"] = np.exp(m.predict(te[CAT + NUM]) + nat[2023])

y24 = df[df.year == 2024].set_index("ccn")
fc = pd.read_parquet("data/interim/preds_2024.parquet").query("regime == 'forecast'").set_index("ccn")
sig = pd.DataFrame({"actual": y24.op18b, "last_year": y24.prev_op18b, "model_B": fc.B, "model_A": y24.A_cf})

pairs = pd.read_parquet("data/interim/hospital_pairs.parquet")
pairs["pair_kind"] = np.where((pairs.hospital_type_a == "Critical Access Hospitals") |
                              (pairs.hospital_type_b == "Critical Access Hospitals"), "involves critical access", "acute only")
realistic = pairs[pairs.realistic].copy()

# information gap: realistic pairs where a patient would NOT have both numbers to compare
has_prior = sig.last_year.notna()
both_prior = realistic.ccn_a.map(has_prior).fillna(False) & realistic.ccn_b.map(has_prior).fillna(False)
gap = realistic.assign(both=both_prior).groupby("rurality_a", observed=True).both.agg(["size", "mean"])
gap_kind = realistic.assign(both=both_prior).groupby("pair_kind").both.agg(["size", "mean"])

SIGNALS = ["last_year", "model_B", "model_A"]
d = realistic.copy()
for s in ["actual"] + SIGNALS:
    d[f"{s}_a"], d[f"{s}_b"] = d.ccn_a.map(sig[s]), d.ccn_b.map(sig[s])
d = d.dropna(subset=[f"{s}_{x}" for s in ["actual"] + SIGNALS for x in "ab"]).reset_index(drop=True)
d["true_diff"] = (d.actual_a - d.actual_b).abs()


def score(sub, s):
    a, b = sub.actual_a.to_numpy(), sub.actual_b.to_numpy()
    pa, pb = sub[f"{s}_a"].to_numpy(), sub[f"{s}_b"].to_numpy()
    pick = np.where(pa < pb, a, np.where(pb < pa, b, (a + b) / 2))
    correct = np.where(a == b, 0.5, np.where(pa == pb, 0.5, ((pa < pb) == (a < b)).astype(float)))
    saved, oracle = (a + b) / 2 - pick, np.abs(a - b) / 2
    return correct.mean(), saved.mean(), saved.sum() / oracle.sum() if oracle.sum() > 0 else np.nan


def table(sub, label):
    rng = np.random.default_rng(SEED); rows = []
    for s in SIGNALS:
        acc, sav, cap = score(sub, s)
        bs = np.array([score(sub.iloc[rng.integers(0, len(sub), len(sub))], s) for _ in range(2000)])
        rows.append({"subset": label, "signal": s, "pairs": len(sub), "pct_correct": 100 * acc,
                     "pct_lo": 100 * np.percentile(bs[:, 0], 2.5), "pct_hi": 100 * np.percentile(bs[:, 0], 97.5),
                     "min_saved_vs_coin": sav, "saved_lo": np.percentile(bs[:, 1], 2.5),
                     "saved_hi": np.percentile(bs[:, 1], 97.5), "pct_of_best_saving": 100 * cap,
                     "best_possible_saving": (sub.true_diff / 2).mean()})
    return rows


rows = table(d, "all realistic pairs")
d["diff_bucket"] = pd.cut(d.true_diff, [-0.1, 15, 30, 60, 1e9], labels=["<15 min", "15-30", "30-60", ">60"])
d["dist_bucket"] = pd.cut(d.miles, [-0.1, 5, 15, 50], labels=["<5 mi", "5-15 mi", "15-50 mi"])
for col in ["diff_bucket", "pair_kind", "dist_bucket", "rurality_a"]:
    for g, sub in d.groupby(col, observed=True):
        if len(sub) >= 50: rows += table(sub, f"{col}={g}")
res = pd.DataFrame(rows)
res.to_csv("reports/13_decision.csv", index=False)
d.to_parquet("data/interim/pair_decisions_2024.parquet", index=False)

pd.set_option("display.width", 220)
print(f"pairs: all {len(pairs)}, realistic (<=50 mi) {len(realistic)}, scorable (both have all signals) {len(d)}")
print("\nrealistic pairs where both hospitals have last year's number to compare, by rurality of hospital A:\n",
      gap.round(3).to_string())
print(gap_kind.round(3).to_string())
print("\ntrue difference between the two EDs in 2024:", d.true_diff.describe(percentiles=[.25, .5, .75]).round(1).to_dict())
print(res.round(1).to_string(index=False))
