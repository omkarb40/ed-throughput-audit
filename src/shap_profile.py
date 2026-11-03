"""S16: SHAP attribution for the public-profile model (Model A settings).

Fit once on every hospital, years 2018-2023, target = log OP-18b minus the year's national median log.
Exact TreeSHAP via LightGBM's pred_contrib. Reports mean |SHAP| per feature, in log units and as approximate
percent change in ED time, on 2024 rows. This is a description of the fitted model, not a causal claim.
The fitted model is saved for the app (models/profile_model.txt) together with the level it needs.
"""
import json, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd, lightgbm as lgb

CAT = ["type", "ownership_group", "state", "rurality", "emergency_services"]
NUM = ["rucc_2023", "lat", "lon", "log_county_pop", "county_median_hh_income", "county_pct_uninsured",
       "county_pct_65plus", "edv"]
NAMES = {"type": "Hospital type", "ownership_group": "Ownership", "state": "State", "rurality": "Rurality",
         "emergency_services": "Emergency services listed", "rucc_2023": "Rural-urban code", "lat": "Latitude",
         "lon": "Longitude", "log_county_pop": "County population", "county_median_hh_income": "County income",
         "county_pct_uninsured": "County % uninsured", "county_pct_65plus": "County % aged 65+", "edv": "ED volume category"}

t = pd.read_parquet("data/interim/analysis_table.parquet")
t = t[t.op18b.notna()].copy()
t["log_county_pop"] = np.log(t.county_pop); t["ly"] = np.log(t.op18b)
cats = {c: sorted(t[c].dropna().astype(str).unique()) for c in CAT}
for c in CAT: t[c] = pd.Categorical(t[c].astype(str), categories=cats[c])
info = json.load(open("reports/10_model_info.json"))["A"]
params = dict(num_leaves=info["num_leaves"], min_child_samples=info["min_child_samples"],
              n_estimators=info["n_estimators"], learning_rate=0.03, subsample=0.8, subsample_freq=1,
              colsample_bytree=0.8, reg_lambda=1.0, random_state=0, verbose=-1)
tr = t[t.year <= 2023]; nat = tr.groupby("year").ly.median()
m = lgb.LGBMRegressor(**params).fit(tr[CAT + NUM], tr.ly - tr.year.map(nat))

Path("models").mkdir(exist_ok=True)
m.booster_.save_model("models/profile_model.txt")
json.dump({"features": CAT + NUM, "categories": cats, "level_log": float(nat[2023]), "level_year": 2023,
           "trained_on_years": sorted(int(y) for y in tr.year.unique())},
          open("models/profile_model_meta.json", "w"), indent=1)

X = t[t.year == 2024][CAT + NUM]
contrib = m.booster_.predict(X, pred_contrib=True)[:, :-1]
mean_abs = pd.Series(np.abs(contrib).mean(0), index=CAT + NUM).sort_values(ascending=False)
out = pd.DataFrame({"feature": [NAMES[f] for f in mean_abs.index], "mean_abs_shap_log": mean_abs.values,
                    "approx_pct": 100 * (np.exp(mean_abs.values) - 1)})
out.to_csv("reports/16_shap.csv", index=False)
print(out.round(3).to_string(index=False))
print("check: contributions + base reproduce predictions:",
      np.allclose(m.booster_.predict(X, pred_contrib=True).sum(1), m.predict(X)))
