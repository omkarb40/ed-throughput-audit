"""S13 robustness: (1) the nearby-pair test repeated for each consecutive pair of calendar years;
(2) a 95% CI for the 2024 result that resamples hospitals, not pairs (a hospital can sit in up to 4 pairs)."""
import numpy as np, pandas as pd

t = pd.read_parquet("data/interim/analysis_table.parquet")
v = t[t.op18b.notna()].pivot_table(index="ccn", columns="year", values="op18b")
p = pd.read_parquet("data/interim/hospital_pairs.parquet"); p = p[p.realistic]
rows = []
for prev, cur in [(2021, 2022), (2022, 2023), (2023, 2024)]:
    d = p.assign(pa=p.ccn_a.map(v[prev]), pb=p.ccn_b.map(v[prev]), a=p.ccn_a.map(v[cur]),
                 b=p.ccn_b.map(v[cur])).dropna(subset=["pa", "pb", "a", "b"])
    c = np.where(d.a == d.b, 0.5, np.where(d.pa == d.pb, 0.5, ((d.pa < d.pb) == (d.a < d.b)).astype(float)))
    pick = np.where(d.pa < d.pb, d.a, np.where(d.pb < d.pa, d.b, (d.a + d.b) / 2))
    rows.append({"number_year": prev, "outcome_year": cur, "pairs": len(d), "pct_correct": round(100 * c.mean(), 1),
                 "median_gap_vs_coin_min": round(((d.a + d.b) / 2 - pick).mean(), 1)})
by_year = pd.DataFrame(rows)

d = pd.read_parquet("data/interim/pair_decisions_2024.parquet")
a, b, pa, pb = d.actual_a.values, d.actual_b.values, d.last_year_a.values, d.last_year_b.values
corr = np.where(a == b, 0.5, np.where(pa == pb, 0.5, ((pa < pb) == (a < b)).astype(float)))
counts = pd.concat([d.ccn_a, d.ccn_b]).value_counts()
idx = {k: [] for k in counts.index}
for i, (x, y) in enumerate(zip(d.ccn_a, d.ccn_b)):
    idx[x].append(i); idx[y].append(i)
rng = np.random.default_rng(0); hosp = counts.index.to_numpy()
bs = [corr[np.concatenate([idx[k] for k in rng.choice(hosp, len(hosp))])].mean() * 100 for _ in range(2000)]
lo, hi = np.percentile(bs, [2.5, 97.5])
by_year["note"] = ""
by_year.loc[len(by_year)] = {"number_year": 2023, "outcome_year": 2024, "pairs": len(d), "pct_correct": round(100 * corr.mean(), 1),
                             "median_gap_vs_coin_min": None,
                             "note": f"main S13 set; hospital-clustered 95% CI {lo:.1f}-{hi:.1f}; "
                                     f"{counts.size} hospitals, {int((counts > 1).sum())} in more than one pair"}
by_year.to_csv("reports/13_decision_by_year.csv", index=False)
print(by_year.to_string(index=False))
