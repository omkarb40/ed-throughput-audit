"""S15: who does the system serve worse? 2024 errors, interval coverage and decision accuracy by group.

Error in minutes is confounded with level (critical access EDs are faster, so their minute errors are smaller),
so every slice also reports median absolute percent error.
Forecasts: last year's number (what a posted number shows) and the cross-fitted public-profile estimate.
"""
import warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from metrics import evaluate

t = pd.read_parquet("data/interim/analysis_table.parquet")
iv = pd.read_parquet("data/interim/intervals_2024.parquet")
a24 = t[t.year == 2024][["ccn", "type", "ownership_group", "rurality", "edv", "county_median_hh_income",
                         "county_pct_uninsured", "state"]]
d = iv.merge(a24, on="ccn", how="left")
d["type2"] = np.where(d.type == "Critical Access Hospitals", "critical access", "acute care")
d["edv_cat"] = d.edv.map({1: "low", 2: "medium", 3: "high", 4: "very high"}).fillna("not reported")
inc_q = pd.qcut(t.drop_duplicates("ccn").county_median_hh_income, 4, retbins=True)[1]
d["income_q"] = pd.cut(d.county_median_hh_income, inc_q, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"], include_lowest=True)
uni_q = pd.qcut(t.drop_duplicates("ccn").county_pct_uninsured, 4, retbins=True)[1]
d["uninsured_q"] = pd.cut(d.county_pct_uninsured, uni_q, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"], include_lowest=True)

pairs = pd.read_parquet("data/interim/pair_decisions_2024.parquet")
SLICES = ["type2", "rurality", "ownership_group", "edv_cat", "income_q", "uninsured_q"]
rows = []
for col in SLICES:
    for g, sub in d.groupby(col, observed=True):
        if len(sub) < 40: continue
        row = {"slice": col, "group": str(g), "hospitals": len(sub)}
        for fc in ("persistence", "profile"):
            s = sub.dropna(subset=[fc])
            if len(s) < 40: continue
            m = evaluate(s, fc, n_boot=500)
            ape = (np.abs(s[fc] - s.op18b) / s.op18b).median() * 100
            cov = ((s.op18b >= s[f"lo_{fc}_mondrian_90"]) & (s.op18b <= s[f"hi_{fc}_mondrian_90"])).mean() * 100
            row.update({f"{fc}_n": len(s), f"{fc}_mae": m["mae_min"], f"{fc}_mae_lo": m["mae_min_lo"],
                        f"{fc}_mae_hi": m["mae_min_hi"], f"{fc}_medape": ape, f"{fc}_bias": m["bias_min"],
                        f"{fc}_cov90": cov, f"{fc}_spearman": m["spearman"]})
        rows.append(row)
res = pd.DataFrame(rows)

# decision accuracy (last year's number) by slice of hospital A, where the slice exists on the pair frame
dp = pairs.merge(d[["ccn"] + SLICES].rename(columns={"ccn": "ccn_a"}), on="ccn_a", how="left")
corr = np.where(dp.last_year_a == dp.last_year_b, 0.5, ((dp.last_year_a < dp.last_year_b) == (dp.actual_a < dp.actual_b)).astype(float))
dp["correct"] = np.where(dp.actual_a == dp.actual_b, 0.5, corr)
dec = []
for col in SLICES:
    for g, sub in dp.groupby(col, observed=True):
        if len(sub) >= 40:
            dec.append({"slice": col, "group": str(g), "pairs": len(sub), "pct_correct": 100 * sub.correct.mean(),
                        "median_true_diff": sub.true_diff.median()})
dec = pd.DataFrame(dec)
res = res.merge(dec, on=["slice", "group"], how="left")

# who is missing a 2024 number at all (the information gap), same slices
t24 = t[t.year == 2024].copy()
t24["type2"] = np.where(t24.type == "Critical Access Hospitals", "critical access", "acute care")
t24["edv_cat"] = t24.edv.map({1: "low", 2: "medium", 3: "high", 4: "very high"}).fillna("not reported")
t24["income_q"] = pd.cut(t24.county_median_hh_income, inc_q, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"], include_lowest=True)
t24["uninsured_q"] = pd.cut(t24.county_pct_uninsured, uni_q, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"], include_lowest=True)
miss = []
for col in SLICES:
    for g, sub in t24.groupby(col, observed=True):
        miss.append({"slice": col, "group": str(g), "pct_no_2024_number": 100 * sub.op18b.isna().mean(), "listed": len(sub)})
res = res.merge(pd.DataFrame(miss), on=["slice", "group"], how="left")
res.to_csv("reports/15_slices.csv", index=False)

pd.set_option("display.width", 260)
cols = ["slice", "group", "listed", "pct_no_2024_number", "persistence_n", "persistence_mae", "persistence_medape",
        "persistence_bias", "persistence_cov90", "pct_correct", "pairs", "median_true_diff", "profile_mae",
        "profile_medape", "profile_bias", "profile_cov90"]
print(res[cols].round(1).to_string(index=False))
print("\nincome quartile cutoffs ($):", [round(x) for x in inc_q], "| uninsured % cutoffs:", [round(x, 1) for x in uni_q])
