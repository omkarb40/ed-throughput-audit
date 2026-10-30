"""S11: how much of the variation in log OP-18b is between hospitals vs within a hospital over time,
and how much of the between-hospital part is explained by public characteristics.

1. Two-way fixed effects  log y_it = a_i + g_t + e_it, solved by alternating projections (unbalanced panel).
   Naive shares use the fitted a_i, which include sampling noise for hospitals with few years.
2. Random-intercept model (REML), year fixed effects: sigma2_hospital and sigma2_within, noise-corrected.
   ICC = sigma2_hospital / (sigma2_hospital + sigma2_within).
3. Hospital effects a_i regressed on structural features (5-fold CV, OLS and LightGBM). Explained variance is
   reported against the noise-corrected sigma2_hospital, not against Var(a_i).
Run for all in-scope hospitals, acute care, and critical access; plus sensitivity runs.
"""
import json, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import statsmodels.formula.api as smf
import lightgbm as lgb
from sklearn.model_selection import KFold
from sklearn.linear_model import LinearRegression

t = pd.read_parquet("data/interim/analysis_table.parquet")
jump = pd.read_parquet("data/interim/op18b_jump.parquet")
t = t.merge(jump, on=["ccn", "year"], how="left")
t = t[t.op18b.notna() & t.type.isin(["Acute Care Hospitals", "Critical Access Hospitals"])].copy()
t["ly"] = np.log(t.op18b)
t["log_county_pop"] = np.log(t.county_pop)


def twoway_fe(d, tol=1e-10, max_iter=500):
    y = d.ly.to_numpy(); i = d.ccn.to_numpy(); yr = d.year.to_numpy()
    a = pd.Series(0.0, index=pd.unique(i)); g = pd.Series(0.0, index=np.unique(yr))
    for _ in range(max_iter):
        g_new = pd.Series(y - a.reindex(i).to_numpy()).groupby(yr).mean()
        a_new = pd.Series(y - g_new.reindex(yr).to_numpy()).groupby(i).mean()
        if max(np.abs(a_new - a.reindex(a_new.index)).max(), np.abs(g_new - g).max()) < tol:
            a, g = a_new, g_new; break
        a, g = a_new, g_new
    mu = g.mean(); g = g - mu; a = a + mu
    fa, fg = a.reindex(i).to_numpy(), g.reindex(yr).to_numpy()
    e = y - fa - fg
    tot = np.var(y)
    return a, g, e, {
        "rows": len(y), "hospitals": len(a), "var_total": tot,
        "share_hospital_naive": np.var(fa) / tot, "share_year": np.var(fg) / tot,
        "share_within": np.var(e) / tot, "share_cov_hosp_year": 2 * np.cov(fa, fg)[0, 1] / tot,
        "r2_fe": 1 - np.var(e) / tot,
        "year_effects_pct": {int(k): round(100 * (np.exp(v) - 1), 1) for k, v in g.items()},
    }


def reml(d):
    m = smf.mixedlm("ly ~ C(year)", d, groups=d["ccn"]).fit(reml=True, method="lbfgs")
    s2h, s2e = float(m.cov_re.iloc[0, 0]), float(m.scale)
    return {"sigma2_hospital": s2h, "sigma2_within": s2e, "icc": s2h / (s2h + s2e),
            "sd_hospital_pct": 100 * (np.exp(np.sqrt(s2h)) - 1), "sd_within_pct": 100 * (np.exp(np.sqrt(s2e)) - 1)}


CAT = ["type", "ownership_group", "state", "rurality"]
NUM = ["rucc_2023", "lat", "lon", "log_county_pop", "county_median_hh_income", "county_pct_uninsured",
       "county_pct_65plus", "edv_mean"]


def explain_effects(d, a, s2h, s2e):
    h = (d.groupby("ccn").agg(n_years=("year", "size"), edv_mean=("edv", "mean"),
                              **{c: (c, "first") for c in CAT + NUM if c != "edv_mean"})
           .join(a.rename("a")))
    h = h.dropna(subset=["log_county_pop", "rucc_2023"])
    noise = s2e / h.n_years            # sampling variance of each a_i
    X_lin = pd.get_dummies(h[CAT].astype(str), drop_first=True).join(h[NUM].fillna(h[NUM].median()))
    X_gbm = h[CAT + NUM].copy()
    for c in CAT: X_gbm[c] = X_gbm[c].astype("category")
    oof = {"ols": np.zeros(len(h)), "lgbm": np.zeros(len(h))}
    for tr, te in KFold(5, shuffle=True, random_state=0).split(h):
        oof["ols"][te] = LinearRegression().fit(X_lin.iloc[tr], h.a.iloc[tr]).predict(X_lin.iloc[te])
        g = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=30,
                              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
        oof["lgbm"][te] = g.fit(X_gbm.iloc[tr], h.a.iloc[tr]).predict(X_gbm.iloc[te])
    out = {"hospitals": len(h), "var_a": float(np.var(h.a)), "mean_noise_var": float(noise.mean()),
           "reliability_of_a": float(1 - noise.mean() / np.var(h.a))}
    for k, p in oof.items():
        explained = np.var(h.a) - np.mean((h.a - p) ** 2)     # out-of-fold explained variance of a_i
        out[f"cv_r2_vs_var_a_{k}"] = float(explained / np.var(h.a))
        out[f"share_true_between_explained_{k}"] = float(explained / s2h)
    return out


def run(d, label):
    a, g, e, fe = twoway_fe(d)
    re = reml(d)
    ex = explain_effects(d, a, re["sigma2_hospital"], re["sigma2_within"])
    tot_re = re["sigma2_hospital"] + re["sigma2_within"]
    best = max(ex["share_true_between_explained_ols"], ex["share_true_between_explained_lgbm"])
    return {"label": label, **fe, **re, **{f"x_{k}": v for k, v in ex.items()},
            "share_total_structural": re["icc"] * best, "share_total_hospital_unexplained": re["icc"] * (1 - best),
            "share_total_within": 1 - re["icc"]}


runs = []
for label, d in [("all", t),
                 ("acute care", t[t.type == "Acute Care Hospitals"]),
                 ("critical access", t[t.type == "Critical Access Hospitals"]),
                 ("all, clean rows", t[~t.op18b_flagged & ~(t.jump > np.log(2))]),
                 ("all, post-COVID 2021-2024", t[t.year >= 2021]),
                 ("all, hospitals with 6 years", t[t.groupby("ccn").year.transform("size") == 6])]:
    r = run(d.reset_index(drop=True), label); runs.append(r)
    print(f"\n== {label}: rows {r['rows']}, hospitals {r['hospitals']}")
    print(f"  FE naive: hospital {r['share_hospital_naive']:.3f}  year {r['share_year']:.3f}  within {r['share_within']:.3f}"
          f"  cov {r['share_cov_hosp_year']:.3f}")
    print(f"  REML: ICC {r['icc']:.3f}  sd hospital ±{r['sd_hospital_pct']:.1f}%  sd within ±{r['sd_within_pct']:.1f}%")
    print(f"  effects: reliability {r['x_reliability_of_a']:.3f}  CV R2 (vs Var a) ols {r['x_cv_r2_vs_var_a_ols']:.3f}"
          f" lgbm {r['x_cv_r2_vs_var_a_lgbm']:.3f}  | share of TRUE between explained ols "
          f"{r['x_share_true_between_explained_ols']:.3f} lgbm {r['x_share_true_between_explained_lgbm']:.3f}")
    print(f"  total = structural {r['share_total_structural']:.3f} + hospital-specific {r['share_total_hospital_unexplained']:.3f}"
          f" + within {r['share_total_within']:.3f}")
    print("  year effects % vs average year:", r["year_effects_pct"])
json.dump(runs, open("reports/11_fe_results.json", "w"), indent=1, default=float)
