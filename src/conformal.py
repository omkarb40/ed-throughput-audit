"""S14: split-conformal prediction intervals, calibrated on 2023, tested once on 2024.

Two point forecasts, both on the log scale:
  persistence : log(last reported value)                    -> for hospitals with a published number
  profile     : Model A cross-fitted by hospital (5 folds on the stable hash), trained only on years before the
                target year, level = national median of the previous year  -> for hospitals with no number
Residual r = log(actual) - log(forecast). Interval = forecast * exp([q_lo, q_hi]) where q_lo, q_hi are the
finite-sample conformal quantiles of calibration residuals at alpha/2 and 1 - alpha/2 (asymmetric).
Marginal: one set of quantiles for everyone. Mondrian: separate quantiles per group, groups known before the
target year: hospital type x whether last year's number carried a CMS footnote.
"""
import json, math, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from features import add_lag_features
from splits import hospital_bucket

SEED = 0
CAT = ["type", "ownership_group", "state", "rurality", "emergency_services"]
NUM = ["rucc_2023", "lat", "lon", "log_county_pop", "county_median_hh_income", "county_pct_uninsured",
       "county_pct_65plus", "edv"]
LEVELS = (0.80, 0.90)

t = pd.read_parquet("data/interim/analysis_table.parquet")
t["log_county_pop"] = np.log(t.county_pop)
df = add_lag_features(t[t.op18b.notna()].reset_index(drop=True))
df["ly"] = np.log(df.op18b)
for c in CAT: df[c] = df[c].astype("category")

# prior-year footnote flag on the last REPORTED value (known before the target year)
obs = df[["ccn", "year", "op18b_flagged"]].sort_values("year").rename(columns={"op18b_flagged": "prev_flagged"})
df = pd.merge_asof(df.sort_values("year"), obs, on="year", by="ccn", allow_exact_matches=False)
df["prev_flagged"] = df.prev_flagged.fillna(False).astype(bool)
df["type2"] = np.where(df.type == "Critical Access Hospitals", "critical access", "acute care")
df["group"] = df.type2 + np.where(df.prev_flagged, ", last value footnoted", "")

# ---- cross-fitted profile model for target years 2023 (calibration) and 2024 (test)
info = json.load(open("reports/10_model_info.json"))["A"]
params = dict(num_leaves=info["num_leaves"], min_child_samples=info["min_child_samples"],
              n_estimators=info["n_estimators"], learning_rate=0.03, subsample=0.8, subsample_freq=1,
              colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, verbose=-1)
fold = df.ccn.map(lambda c: hospital_bucket(c, 5))
df["profile"] = np.nan
for Y in (2023, 2024):
    hist = df[df.year < Y]; nat = hist.groupby("year").ly.median()
    for k in range(5):
        tr = hist[fold.loc[hist.index] != k]
        m = lgb.LGBMRegressor(**params).fit(tr[CAT + NUM], tr.ly - tr.year.map(nat))
        te = df[(df.year == Y) & (fold == k)]
        df.loc[te.index, "profile"] = np.exp(m.predict(te[CAT + NUM]) + nat[Y - 1])
df["persistence"] = df.prev_op18b


def conf_q(r, alpha):
    """Finite-sample split-conformal quantiles, asymmetric, at alpha/2 and 1-alpha/2."""
    r = np.sort(np.asarray(r)); n = len(r)
    k_hi = min(n, math.ceil((n + 1) * (1 - alpha / 2))); k_lo = max(1, math.floor((n + 1) * (alpha / 2)))
    return r[k_lo - 1], r[k_hi - 1]


cal_all = df[df.year == 2023]; test_all = df[df.year == 2024]
rows, out = [], {}
for fc in ("persistence", "profile"):
    cal = cal_all.dropna(subset=[fc]); test = test_all.dropna(subset=[fc]).copy()
    r_cal = np.log(cal.op18b) - np.log(cal[fc])
    for lvl in LEVELS:
        a = 1 - lvl
        lo_m, hi_m = conf_q(r_cal, a)
        qg = {g: conf_q(r_cal[cal.group == g], a) for g in cal.group.unique()}
        for method in ("marginal", "mondrian"):
            if method == "marginal":
                lo, hi = np.full(len(test), lo_m), np.full(len(test), hi_m)
            else:
                lo = test.group.map(lambda g: qg.get(g, (lo_m, hi_m))[0]).to_numpy()
                hi = test.group.map(lambda g: qg.get(g, (lo_m, hi_m))[1]).to_numpy()
            L, U = test[fc].to_numpy() * np.exp(lo), test[fc].to_numpy() * np.exp(hi)
            cov = (test.op18b.to_numpy() >= L) & (test.op18b.to_numpy() <= U)
            test[f"lo_{fc}_{method}_{int(lvl*100)}"], test[f"hi_{fc}_{method}_{int(lvl*100)}"] = L, U
            d = test.assign(cov=cov, width=U - L)
            for gname, sub in [("all", d)] + list(d.groupby("group")) + list(d.groupby("rurality", observed=True)):
                rows.append({"forecast": fc, "level": lvl, "method": method, "group": gname, "n": len(sub),
                             "coverage": 100 * sub["cov"].mean(), "median_width_min": sub.width.median(),
                             "pct_above_interval": 100 * (sub.op18b > sub[f"hi_{fc}_{method}_{int(lvl*100)}"]).mean(),
                             "pct_below_interval": 100 * (sub.op18b < sub[f"lo_{fc}_{method}_{int(lvl*100)}"]).mean()})
        out[f"{fc}_{int(lvl*100)}"] = {"n_cal": len(cal), "marginal_q": [lo_m, hi_m],
                                       "mondrian_q": {g: list(v) for g, v in qg.items()},
                                       "cal_group_sizes": cal.group.value_counts().to_dict()}
    out[f"{fc}_test"] = test[["ccn", "year", "op18b", fc, "group"] + [c for c in test.columns if c.startswith(("lo_", "hi_"))]]

res = pd.DataFrame(rows); res.to_csv("reports/14_coverage.csv", index=False)
# one row per 2024 hospital: both forecasts and their intervals (persistence is missing where there is no prior value)
pers = out.pop("persistence_test")
prof = out.pop("profile_test")
iv = prof.merge(pers.drop(columns=["year", "op18b", "group"]), on="ccn", how="left")
iv.to_parquet("data/interim/intervals_2024.parquet", index=False)
json.dump(out, open("reports/14_conformal_quantiles.json", "w"), indent=1, default=float)

pd.set_option("display.width", 200)
print(json.dumps({k: v["cal_group_sizes"] for k, v in out.items() if k.endswith("_90")}, indent=1))
show = res[res.group.isin(["all", "acute care", "critical access", "acute care, last value footnoted",
                           "critical access, last value footnoted", "metro", "rural"])]
print(show.round(1).to_string(index=False))
