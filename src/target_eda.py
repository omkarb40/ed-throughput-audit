"""S7: target EDA for OP_18b — distribution, outliers, window overlap."""
import json
import numpy as np, pandas as pd

t = pd.read_parquet("data/interim/analysis_table.parquet")
p = pd.read_parquet("data/interim/ed_panel.parquet")
y = t[t.op18b.notna()].copy()
out = {}

# 1. distribution
q = [0, .01, .05, .25, .5, .75, .95, .99, 1]
dist = y.groupby("type").op18b.quantile(q).unstack().round(0)
dist["n"] = y.type.value_counts(); dist["skew"] = y.groupby("type").op18b.skew().round(2)
dist["skew_log"] = y.groupby("type").op18b.apply(lambda s: np.log(s).skew()).round(2)
print("OP_18b quantiles by type\n", dist.to_string())
by_year = y.pivot_table(index="year", columns="type", values="op18b", aggfunc="median")
print("\nmedian by year x type\n", by_year.round(0).to_string())
out["quantiles_by_type"] = dist.reset_index().to_dict("records")

# 2. sample column: what is it?
s = p[(p.measure_id == "OP_18b") & p.is_calendar_year]
print("\nOP_18b sample_raw examples:", s["sample"].describe().round(0).to_dict())
yy = y.merge(s[["ccn", "year", "sample"]], on=["ccn", "year"], how="left")
print("corr(log sample, log op18b):", round(np.log(yy["sample"]).corr(np.log(yy.op18b)), 3))

# 3. outliers
hi = yy.sort_values("op18b", ascending=False).head(12)
print("\ntop 12 hospital-years\n", hi[["ccn", "year", "type", "op18b", "sample", "op18b_flagged", "op18b_footnotes", "edv", "rurality"]].to_string(index=False))
ccn_max = hi.ccn.iloc[0]
print(f"\nfull OP_18b history of {ccn_max}:")
print(p[(p.ccn == ccn_max) & (p.measure_id == "OP_18b")][["window_start", "window_end", "score", "sample", "footnote_codes"]].to_string(index=False))
iqr_fence = y.groupby("type").op18b.transform(lambda s: s.quantile(.75) + 3 * (s.quantile(.75) - s.quantile(.25)))
n_far = int((y.op18b > iqr_fence).sum())
lo = y.op18b < 45
print(f"\nhospital-years beyond Q3+3*IQR within type: {n_far}  | below 45 min: {int(lo.sum())}")
out["n_beyond_q3_3iqr"] = n_far

# 4. window overlap: how much does window t tell you about window t+k?
w = s0 = p[(p.measure_id == "OP_18b") & p.score.notna() & (p.window_months == 12)].copy()
w = w.sort_values("window_end")
ends = sorted(w.window_end.unique())
piv = w.pivot_table(index="ccn", columns="window_end", values="score")
rows = []
for i, e in enumerate(ends):
    for k in (1, 2, 3, 4, 8):
        if i + k < len(ends):
            a, b = piv[e], piv[ends[i + k]]
            m = a.notna() & b.notna()
            gap = round((pd.Timestamp(ends[i + k]) - pd.Timestamp(e)).days / 30.4)
            rows.append({"lag_windows": k, "gap_months": gap, "overlap_months": max(0, 12 - gap),
                         "r_log": np.corrcoef(np.log(a[m]), np.log(b[m]))[0, 1],
                         "mae_min": float((a[m] - b[m]).abs().median())})
ov = pd.DataFrame(rows)
ovs = ov.groupby("gap_months").agg(overlap_months=("overlap_months", "first"), pairs=("r_log", "size"),
                                   r_log=("r_log", "median"), median_abs_diff_min=("mae_min", "median")).round(3)
print("\nconsecutive-window agreement (12-month windows only)\n", ovs.to_string())
out["overlap"] = ovs.reset_index().to_dict("records")

# 5. calendar-year to calendar-year (non-overlapping) agreement
cy = y.pivot_table(index="ccn", columns="year", values="op18b")
pairs = [(2018, 2019), (2021, 2022), (2022, 2023), (2023, 2024), (2019, 2021), (2018, 2024)]
cyr = []
for a, b in pairs:
    m = cy[a].notna() & cy[b].notna()
    cyr.append({"from": a, "to": b, "n": int(m.sum()), "r_log": round(np.corrcoef(np.log(cy[a][m]), np.log(cy[b][m]))[0, 1], 3),
                "median_abs_change_min": float((cy[a][m] - cy[b][m]).abs().median())})
cyr = pd.DataFrame(cyr); print("\ncalendar-year agreement (no overlap)\n", cyr.to_string(index=False))
out["calendar_year_agreement"] = cyr.to_dict("records")
json.dump(out, open("reports/07_target_eda.json", "w"), indent=1, default=str)
