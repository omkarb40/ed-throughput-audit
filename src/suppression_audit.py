"""S5: is OP_18b missingness random? Unit = hospital x calendar year."""
import json, warnings
import numpy as np, pandas as pd
import statsmodels.formula.api as smf
warnings.filterwarnings("ignore")

p = pd.read_parquet("data/interim/ed_panel.parquet")
attrs = pd.read_parquet("data/interim/hospital_attrs_latest.parquet")

b = p[(p.measure_id == "OP_18b") & p.is_calendar_year].copy()
b["status"] = np.select([b.score.isna(), b.is_flagged], ["suppressed", "flagged"], "clean")
edv = p[(p.measure_id == "EDV") & p.is_calendar_year][["ccn", "year", "score"]].rename(columns={"score": "edv"})
d = (b.merge(edv, on=["ccn", "year"], how="left")
      .merge(attrs[["ccn", "hospital_type", "ownership", "emergency_services", "state"]], on="ccn", how="left"))
d["edv_cat"] = d.edv.map({1: "1 low", 2: "2 medium", 3: "3 high", 4: "4 very high"}).fillna("missing")
d["own"] = d.ownership.fillna("unknown").str.split(" - ").str[0]
d["type"] = d.hospital_type.fillna("unknown")
out = {}

def rates(col):
    t = pd.crosstab(d[col], d.status, normalize="index").mul(100).round(1)
    t["n"] = d[col].value_counts()
    return t.sort_values("n", ascending=False)

out["overall"] = d.status.value_counts().to_dict()
print("hospital-years:", len(d), out["overall"])
for col in ["type", "edv_cat", "emergency_services", "own", "year"]:
    t = rates(col); out[col] = t.reset_index().to_dict("records")
    print(f"\n% by {col}\n", t.to_string())

# why suppressed
sup = d[d.status == "suppressed"]
reasons = sup.footnote_codes.fillna("none").value_counts()
out["suppressed_reasons"] = reasons.to_dict()
print("\nsuppressed footnote codes:\n", reasons.head(8).to_string())

# logistic: P(suppressed) ~ type + volume + ownership + year, among ED-providing types
m = d[d.type.isin(["Acute Care Hospitals", "Critical Access Hospitals"]) & (d.edv_cat != "missing")].copy()
m["y"] = (m.status == "suppressed").astype(int)
fit = smf.logit("y ~ C(type) + C(edv_cat) + C(own) + C(year)", data=m).fit(disp=0)
orr = pd.DataFrame({"odds_ratio": np.exp(fit.params), "p": fit.pvalues}).round(3)
print(f"\nlogit P(suppressed), n={len(m)}, pseudo-R2={fit.prsquared:.3f}\n", orr.to_string())
orr.to_csv("reports/05_suppression_logit.csv")

# balanced vs unbalanced hospitals: do the ones we'd drop look different where observed?
yrs = d[d.status != "suppressed"].groupby("ccn").year.nunique()
d["balanced"] = d.ccn.map(yrs).eq(6)
obs = d[d.status != "suppressed"]
cmp = obs.groupby("balanced").agg(hospitals=("ccn", "nunique"), median_op18b=("score", "median"),
                                  pct_cah=("type", lambda s: round(100 * (s == "Critical Access Hospitals").mean(), 1)),
                                  pct_low_volume=("edv", lambda s: round(100 * (s == 1).mean(), 1)))
print("\nobserved OP_18b: balanced core vs hospitals with gaps\n", cmp.to_string())
by_type = obs.groupby(["type", "balanced"]).score.median().unstack().round(0)
print("\nmedian OP_18b by type x balanced\n", by_type.to_string())
out["balanced_compare"] = cmp.reset_index().to_dict("records")
d.to_parquet("data/interim/op18b_status.parquet", index=False)
json.dump(out, open("reports/05_suppression.json", "w"), indent=1, default=str)
