"""S8 report: rows, hospitals, years and composition of every split partition -> reports/08_split_sizes.csv"""
import pandas as pd
from splits import temporal_split, grouped_temporal_split

t = pd.read_parquet("data/interim/analysis_table.parquet")
df = t[t.op18b.notna()].reset_index(drop=True)
rows = []
for name, fn in [("temporal", temporal_split), ("grouped_temporal", grouped_temporal_split)]:
    for k, v in fn(df).items():
        rows.append({"split": name, "part": k, "rows": len(v), "hospitals": v.ccn.nunique(),
                     "years": ",".join(map(str, sorted(v.year.unique()))),
                     "pct_cah": round(100 * (v.type == "Critical Access Hospitals").mean(), 1),
                     "pct_rural": round(100 * (v.rurality == "rural").mean(), 1),
                     "median_op18b": v.op18b.median()})
r = pd.DataFrame(rows); r.to_csv("reports/08_split_sizes.csv", index=False); print(r.to_string(index=False))
