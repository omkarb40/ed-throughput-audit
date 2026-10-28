"""S10: Model A (structure only, unseen hospitals) and Model B (forecast), scored against the frozen baselines.

Targets are relative to that year's national median log OP_18b, so neither model can win on the nationwide level.
  Model A: y_rel = log(OP_18b) - national median log (train hospitals, same year)
           prediction = exp(y_rel_hat + national median log of 2022)        [same level info as baseline B1]
  Model B: y_rel = (log OP_18b - log prev) - national median of that change in that year
           prediction = prev * exp(y_rel_hat)                               [no national drift, like persistence]
Tuning on 2023 only; refit on train+val with the chosen settings; 2024 scored once.
"""
import itertools, json, warnings
warnings.filterwarnings("ignore")
import lightgbm as lgb
import numpy as np, pandas as pd
from features import add_lag_features
from metrics import evaluate_by, paired_diff
from splits import grouped_temporal_split, temporal_split, TRAIN_MAX_YEAR

SEED = 0
CAT = ["type", "ownership_group", "state", "rurality", "emergency_services"]
NUM_STRUCT = ["rucc_2023", "lat", "lon", "log_county_pop", "county_median_hh_income",
              "county_pct_uninsured", "county_pct_65plus"]

t = pd.read_parquet("data/interim/analysis_table.parquet")
t["log_county_pop"] = np.log(t.county_pop)

# prior-year values of other measures, for the forecast model (strictly earlier years)
def prior_value(col):
    s = t[["ccn", "year", col]].dropna().sort_values("year").rename(columns={col: f"prev_{col}"})
    s["year_src"] = s.year
    out = pd.merge_asof(t[["ccn", "year"]].sort_values("year"), s.drop(columns="year_src"),
                        on="year", by="ccn", allow_exact_matches=False)
    return out.set_index(["ccn", "year"])[f"prev_{col}"]
for c in ("edv", "op22_lwbs_pct"):
    t = t.join(prior_value(c), on=["ccn", "year"])

df = add_lag_features(t[t.op18b.notna()].reset_index(drop=True))
df["log_y"] = np.log(df.op18b)
df["log_prev"] = np.log(df.prev_op18b)
df["dev_from_history"] = df.prior_mean_log_op18b - df.log_prev
for c in CAT:
    df[c] = df[c].astype("category")

jump = pd.read_parquet("data/interim/op18b_jump.parquet")
df = df.merge(jump, on=["ccn", "year"], how="left")
df["clean_row"] = ~df.op18b_flagged & ~(df.jump > np.log(2))

FEAT_A = CAT + NUM_STRUCT + ["edv"]
FEAT_A_NOVOL = CAT + NUM_STRUCT
FEAT_B = CAT + NUM_STRUCT + ["prev_edv", "prev_op22_lwbs_pct", "log_prev", "prev_op18b_gap_years",
                             "n_prior_op18b", "dev_from_history"]

GRID = [dict(num_leaves=nl, min_child_samples=mc, learning_rate=0.03, subsample=0.8, subsample_freq=1,
             colsample_bytree=0.8, reg_lambda=1.0, n_estimators=3000, random_state=SEED, verbose=-1)
        for nl, mc in itertools.product([15, 31, 63], [20, 50, 100])]


def tune_and_fit(Xtr, ytr, Xva, yva, Xfull, yfull):
    best = None
    for params in GRID:
        m = lgb.LGBMRegressor(**params).fit(Xtr, ytr, eval_set=[(Xva, yva)],
                                            callbacks=[lgb.early_stopping(100, verbose=False)])
        rmse = float(np.sqrt(np.mean((m.predict(Xva) - yva) ** 2)))
        if best is None or rmse < best[0]:
            best = (rmse, params, m.best_iteration_)
    rmse, params, n_iter = best
    final = lgb.LGBMRegressor(**{**params, "n_estimators": n_iter}).fit(Xfull, yfull)
    return final, {"val_rmse_rel_log": rmse, "num_leaves": params["num_leaves"],
                   "min_child_samples": params["min_child_samples"], "n_estimators": n_iter}


results, info, preds = [], {}, []

# ================= Model A: structural, unseen hospitals =================
gs = grouped_temporal_split(df)
tr_h = df[df.ccn.isin(gs["train"].ccn)]
nat = tr_h.groupby("year").log_y.median()            # national level from train hospitals only
for k in gs: gs[k] = gs[k].assign(y_rel=gs[k].log_y - gs[k].year.map(nat).fillna(nat[TRAIN_MAX_YEAR]))
level = nat[TRAIN_MAX_YEAR]

test_a = gs["test"].copy()
cell_tr = gs["train"][gs["train"].year == TRAIN_MAX_YEAR]
cell = cell_tr.groupby(["state", "type"], observed=True).op18b.agg(["median", "size"])
natt = cell_tr.groupby("type", observed=True).op18b.median()
key = list(zip(test_a.state, test_a.type))
med, n = cell["median"].reindex(key).to_numpy(), cell["size"].reindex(key).to_numpy()
test_a["B1"] = np.where(n >= 5, med, test_a.type.map(natt).astype(float))

for name, feats in [("A", FEAT_A), ("A_no_volume", FEAT_A_NOVOL)]:
    full = pd.concat([gs["train"], gs["val"]])
    m, meta = tune_and_fit(gs["train"][feats], gs["train"].y_rel, gs["val"][feats], gs["val"].y_rel,
                           full[feats], full.y_rel)
    test_a[name] = np.exp(m.predict(test_a[feats]) + level)
    info[name] = meta
    imp = pd.Series(m.booster_.feature_importance("gain"), index=feats)
    info[name]["gain_share"] = (imp / imp.sum()).round(3).sort_values(ascending=False).to_dict()

for col in ("B1", "A", "A_no_volume"):
    for subset, d in [("all", test_a), ("clean", test_a[test_a.clean_row])]:
        r = evaluate_by(d, col); r.insert(0, "subset", subset); r.insert(0, "model", col)
        r.insert(0, "regime", "structural"); results.append(r)
preds.append(test_a[["ccn", "year", "type", "op18b", "B1", "A", "A_no_volume"]].assign(regime="structural"))

# ================= Model B: forecast =================
ts = temporal_split(df)
for k in ts:
    d = ts[k][ts[k].log_prev.notna()].copy()
    ch = d.log_y - d.log_prev
    d["y_rel"] = ch - ch.groupby(d.year).transform("median")
    ts[k] = d
full = pd.concat([ts["train"], ts["val"]])
m, meta = tune_and_fit(ts["train"][FEAT_B], ts["train"].y_rel, ts["val"][FEAT_B], ts["val"].y_rel,
                       full[FEAT_B], full.y_rel)
test_b = ts["test"].copy()
test_b["B0"] = test_b.prev_op18b
test_b["B"] = test_b.prev_op18b * np.exp(m.predict(test_b[FEAT_B]))
info["B"] = meta
imp = pd.Series(m.booster_.feature_importance("gain"), index=FEAT_B)
info["B"]["gain_share"] = (imp / imp.sum()).round(3).sort_values(ascending=False).to_dict()
info["B"]["train_target_years"] = sorted(ts["train"].year.unique().tolist())

for col in ("B0", "B"):
    for subset, d in [("all", test_b), ("clean", test_b[test_b.clean_row])]:
        r = evaluate_by(d, col); r.insert(0, "subset", subset); r.insert(0, "model", col)
        r.insert(0, "regime", "forecast"); results.append(r)
preds.append(test_b[["ccn", "year", "type", "op18b", "B0", "B"]].assign(regime="forecast"))

pairs = []
for regime, d, mcol, bcol in [("structural", test_a, "A", "B1"), ("structural", test_a, "A_no_volume", "B1"),
                              ("structural", test_a, "A", "A_no_volume"), ("forecast", test_b, "B", "B0")]:
    for grp, sub in [("all", d)] + [(g, s) for g, s in d.groupby("type", observed=True) if len(s) >= 100]:
        pairs.append({"regime": regime, "model": mcol, "vs": bcol, "group": grp, **paired_diff(sub, mcol, bcol)})
pairs = pd.DataFrame(pairs); pairs.to_csv("reports/10_paired_diffs.csv", index=False)
print(pairs.round(3).to_string(index=False))

res = pd.concat(results, ignore_index=True)
res.to_csv("reports/10_models.csv", index=False)
json.dump(info, open("reports/10_model_info.json", "w"), indent=1, default=str)
pd.concat(preds).to_parquet("data/interim/preds_2024.parquet", index=False)

show = ["regime", "model", "subset", "group", "n", "mae_min", "mae_min_lo", "mae_min_hi", "bias_min",
        "rel_rmse_log", "spearman", "spearman_lo", "spearman_hi", "pct_under_15", "pct_over_15"]
pd.set_option("display.width", 250)
print(res[(res.group != "Acute Care - Department of Defense")][show].round(3).to_string(index=False))
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "gain_share"} for k, v in info.items()}, indent=1))
for k, v in info.items(): print(k, "top gain:", dict(list(v["gain_share"].items())[:6]))
