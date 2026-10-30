"""S11 add-on: nested feature groups -> share of the noise-corrected between-hospital variance explained (5-fold CV)."""
import json, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.model_selection import KFold

t = pd.read_parquet("data/interim/analysis_table.parquet")
t = t[t.op18b.notna() & t.type.isin(["Acute Care Hospitals", "Critical Access Hospitals"])].copy()
t["ly"] = np.log(t.op18b); t["log_county_pop"] = np.log(t.county_pop)
runs = {r["label"]: r for r in json.load(open("reports/11_fe_results.json"))}

GROUPS = [("type", ["type"]),
          ("+ state", ["type", "state"]),
          ("+ ED volume", ["type", "state", "edv_mean"]),
          ("+ rurality, location", ["type", "state", "edv_mean", "rurality", "rucc_2023", "lat", "lon"]),
          ("+ county population, income, insurance, age", ["type", "state", "edv_mean", "rurality", "rucc_2023", "lat", "lon",
                                                         "log_county_pop", "county_median_hh_income",
                                                         "county_pct_uninsured", "county_pct_65plus"]),
          ("+ ownership (all)", ["type", "state", "edv_mean", "rurality", "rucc_2023", "lat", "lon", "log_county_pop",
                                 "county_median_hh_income", "county_pct_uninsured", "county_pct_65plus", "ownership_group"])]
CAT = {"type", "state", "rurality", "ownership_group"}

def effects(d):
    y = d.ly.to_numpy(); i = d.ccn.to_numpy(); yr = d.year.to_numpy()
    a = pd.Series(0.0, index=pd.unique(i))
    for _ in range(300):
        g = pd.Series(y - a.reindex(i).to_numpy()).groupby(yr).mean()
        a = pd.Series(y - g.reindex(yr).to_numpy()).groupby(i).mean()
    return a

out = []
for label, typ in [("all", None), ("acute care", "Acute Care Hospitals"), ("critical access", "Critical Access Hospitals")]:
    d = t if typ is None else t[t.type == typ]
    a = effects(d.reset_index(drop=True))
    h = d.groupby("ccn").agg(edv_mean=("edv", "mean"), **{c: (c, "first") for c in
        ["type", "state", "rurality", "ownership_group", "rucc_2023", "lat", "lon", "log_county_pop",
         "county_median_hh_income", "county_pct_uninsured", "county_pct_65plus"]}).join(a.rename("a"))
    h = h.dropna(subset=["log_county_pop", "rucc_2023"])
    s2h = runs[label]["sigma2_hospital"]
    for gname, feats in GROUPS:
        feats = [f for f in feats if not (typ and f == "type")]
        if not feats: continue
        X = h[feats].copy()
        for c in feats:
            if c in CAT: X[c] = X[c].astype("category")
        oof = np.zeros(len(h))
        for tr, te in KFold(5, shuffle=True, random_state=0).split(h):
            m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=30,
                                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
            oof[te] = m.fit(X.iloc[tr], h.a.iloc[tr]).predict(X.iloc[te])
        expl = (np.var(h.a) - np.mean((h.a - oof) ** 2)) / s2h
        out.append({"population": label, "features": gname, "share_true_between_explained": round(float(expl), 3)})
        print(f"{label:16s} {gname:48s} {expl:.3f}")
pd.DataFrame(out).to_csv("reports/11_feature_groups.csv", index=False)
