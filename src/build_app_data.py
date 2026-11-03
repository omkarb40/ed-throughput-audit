"""S17: precompute everything the app shows, so the app needs no model library and no raw data.

app/data/hospitals.parquet  one row per ED in the current CMS list (acute care, critical access, DoD, lists an ED):
    latest published OP-18b (rolling window ending 2025-09-30) with its footnote flag, or, when CMS publishes none,
    the public-profile estimate; a 90% and 80% range for the next 12 months from the S14 per-group conformal factors.
app/data/neighbors.parquet  the 3 nearest other EDs for each ED, with miles.
app/data/pick_accuracy.csv  how often the lower published number was the faster ED in 2024, by published gap (S13 pairs).
app/data/meta.json          window dates, counts, coverage results, sources.
"""
import json, math, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.neighbors import BallTree

R_MILES = 3958.8
p = pd.read_parquet("data/interim/ed_panel.parquet")
geo = pd.read_parquet("data/interim/hospital_geo.parquet")
snap = pd.read_parquet("data/interim/hospital_attrs_by_snapshot.parquet")
cur = snap[snap.snapshot_date == snap.snapshot_date.max()]
t = pd.read_parquet("data/interim/analysis_table.parquet")

pool = geo.merge(cur[["ccn", "hospital_type", "ownership", "emergency_services"]], on="ccn")
pool = pool[(pool.emergency_services == "Yes") & pool.lat.notna()].copy()

# latest published window
b = p[p.measure_id == "OP_18b"]
last_end = b.window_end.max()
w = b[b.window_end == last_end].set_index("ccn")
pool["window_start"], pool["window_end"] = w.window_start.iloc[0], last_end
pool["published"] = pool.ccn.map(w.score)
pool["footnoted"] = pool.ccn.map(w.is_flagged).fillna(False).astype(bool) & pool.published.notna()
pool["footnote_codes"] = pool.ccn.map(w.footnote_codes)

# when did CMS last publish a number for this ED? (no number now can mean small volume, not reporting, or closed)
bn = b[b.score.notna()].sort_values("window_end").drop_duplicates("ccn", keep="last").set_index("ccn")
pool["last_number"] = pool.ccn.map(bn.score)
pool["last_number_window_end"] = pool.ccn.map(bn.window_end)
first_window = b.window_start.min()

# latest attributes for the profile model (most recent calendar-year row per hospital)
lt = t.sort_values("year").drop_duplicates("ccn", keep="last").set_index("ccn")
meta_m = json.load(open("models/profile_model_meta.json"))
pi = pool.set_index("ccn")
X = pd.DataFrame(index=pi.index)
for c in meta_m["features"]:
    if c == "log_county_pop":
        X[c] = np.log(pi.index.map(lt.county_pop).astype(float))
    elif c in lt.columns:
        X[c] = pi.index.map(lt[c])
    else:
        X[c] = pi[c]
X["type"] = X["type"].fillna(pi.hospital_type)
for c, cats in meta_m["categories"].items():
    X[c] = pd.Categorical(X[c].astype(str), categories=cats)
booster = lgb.Booster(model_file="models/profile_model.txt")
pool["profile_estimate"] = np.exp(booster.predict(X[meta_m["features"]]) + meta_m["level_log"])

# per-group conformal factors from S14
q = json.load(open("reports/14_conformal_quantiles.json"))
pool["type2"] = np.where(pool.hospital_type == "Critical Access Hospitals", "critical access", "acute care")
pool["group"] = pool.type2 + np.where(pool.footnoted, ", last value footnoted", "")
pool["source"] = np.where(pool.published.notna(), "published", "profile estimate")
pool["point"] = pool.published.fillna(pool.profile_estimate)
for lvl in (80, 90):
    for src, key in (("published", "persistence"), ("profile estimate", "profile")):
        qq = q[f"{key}_{lvl}"]
        lo = pool.group.map(lambda g: qq["mondrian_q"].get(g, qq["marginal_q"])[0])
        hi = pool.group.map(lambda g: qq["mondrian_q"].get(g, qq["marginal_q"])[1])
        m = pool.source == src
        pool.loc[m, f"lo{lvl}"] = pool.loc[m, "point"] * np.exp(lo[m])
        pool.loc[m, f"hi{lvl}"] = pool.loc[m, "point"] * np.exp(hi[m])

# EDs with no current number but a recent one: the hospital's own older number beats a profile guess (S7, S10).
# Range: split-conformal factors from calendar-year pairs 2 or 3+ years apart (calibrated on pairs ending <= 2023),
# by type. Back-tested on pairs ending 2024: coverage 85.7-89.5% for a 90% target, so the app states that.
ty = pd.read_parquet("data/interim/analysis_table.parquet")
yy = ty[ty.op18b.notna()][["ccn", "year", "op18b", "type"]]
yy["type2"] = np.where(yy.type == "Critical Access Hospitals", "critical access", "acute care")
pp = yy.merge(yy[["ccn", "year", "op18b"]], on="ccn", suffixes=("_a", "_b"))
pp = pp[(pp.year_b > pp.year_a) & (pp.year_b <= 2023)]
pp["gap"] = (pp.year_b - pp.year_a).clip(upper=3); pp = pp[pp.gap >= 2]
pp["r"] = np.log(pp.op18b_b) - np.log(pp.op18b_a)
def cq(r, a):
    r = np.sort(np.asarray(r)); n = len(r)
    return r[max(1, math.floor((n + 1) * a / 2)) - 1], r[min(n, math.ceil((n + 1) * (1 - a / 2))) - 1]
stale_q = {(g, t2, lvl): cq(pp[(pp.gap == g) & (pp.type2 == t2)].r, 1 - lvl / 100)
           for g in (2, 3) for t2 in ("acute care", "critical access") for lvl in (80, 90)}
age = (last_end - pool.last_number_window_end).dt.days / 365.25
stale = (pool.source == "profile estimate") & pool.last_number.notna() & (age <= 4)
pool["number_age_years"] = age.round(1)
pool.loc[stale, "source"] = "older published"
pool.loc[stale, "point"] = pool.loc[stale, "last_number"]
for i in pool[stale].index:
    g = 2 if age[i] <= 2.25 else 3
    for lvl in (80, 90):
        lo, hi = stale_q[(g, pool.at[i, "type2"], lvl)]
        pool.at[i, f"lo{lvl}"] = pool.at[i, "point"] * np.exp(lo)
        pool.at[i, f"hi{lvl}"] = pool.at[i, "point"] * np.exp(hi)

h = pool[["ccn", "facility_name", "city", "state", "zip", "county", "hospital_type", "ownership", "rurality",
          "lat", "lon", "coord_source", "window_start", "window_end", "source", "published", "footnoted",
          "footnote_codes", "profile_estimate", "point", "lo80", "hi80", "lo90", "hi90", "last_number",
          "last_number_window_end", "number_age_years"]].reset_index(drop=True)
FIX = {"Umass": "UMass", "Healthalliance": "HealthAlliance", "Llc": "LLC", "Va ": "VA ", "Ii ": "II ",
       "Iii": "III", "Nyu": "NYU", "Ucsf": "UCSF", "Ucla": "UCLA", "Uc ": "UC ", "Unc ": "UNC ", "Hca ": "HCA ",
       "Chi ": "CHI ", "Ssm ": "SSM ", "Osf ": "OSF ", "Uab ": "UAB ", "Uw ": "UW ", "Ohsu": "OHSU", "Phs ": "PHS ",
       "Ut ": "UT ", "Upmc": "UPMC", "Dlp ": "DLP ", "Cah": "CAH", "'S ": "'s ", "Mcallen": "McAllen"}
def tidy(name):
    n = name.strip().rstrip("-").strip().title() + " "
    for a, b in FIX.items():
        n = n.replace(a, b)
    return n.strip()
h["facility_name"] = h.facility_name.map(tidy)
h["city"] = h.city.str.title()
h.to_parquet("app/data/hospitals.parquet", index=False)

# 3 nearest other EDs
tree = BallTree(np.radians(h[["lat", "lon"]].to_numpy()), metric="haversine")
dist, idx = tree.query(np.radians(h[["lat", "lon"]].to_numpy()), k=8)
nb = []
for r in range(len(h)):
    k = [j for j in range(8) if idx[r, j] != r][:3]
    for rank, j in enumerate(k, 1):
        nb.append({"ccn": h.ccn[r], "rank": rank, "alt_ccn": h.ccn[idx[r, j]], "miles": dist[r, j] * R_MILES})
pd.DataFrame(nb).to_parquet("app/data/neighbors.parquet", index=False)

# how often "lower published number" was the faster ED in 2024, by size of the published gap
d = pd.read_parquet("data/interim/pair_decisions_2024.parquet")
d = d[d.last_year_a != d.last_year_b].copy()
d["pub_gap"] = (d.last_year_a - d.last_year_b).abs()
d["correct"] = ((d.last_year_a < d.last_year_b) == (d.actual_a < d.actual_b)).astype(float)
d.loc[d.actual_a == d.actual_b, "correct"] = 0.5
d["bucket"] = pd.cut(d.pub_gap, [0, 10, 20, 40, 1e9], labels=["under 10 min", "10-20 min", "20-40 min", "over 40 min"])
acc = d.groupby("bucket", observed=True).agg(pairs=("correct", "size"), pct_correct=("correct", "mean")).reset_index()
acc["pct_correct"] = (100 * acc.pct_correct).round(1)
acc.to_csv("app/data/pick_accuracy.csv", index=False)

cov = pd.read_csv("reports/14_coverage.csv")
c90 = cov[(cov.level == 0.9) & (cov.method == "mondrian") & (cov.group == "all")].set_index("forecast").coverage
json.dump({"first_window_start": str(first_window.date()), "window_start": str(h.window_start.iloc[0].date()), "window_end": str(last_end.date()),
           "cms_release": str(w.source_snapshot.iloc[0].date()), "n_eds": len(h),
           "n_published": int((h.source == "published").sum()), "n_no_current": int((h.source != "published").sum()),
           "n_older_published": int((h.source == "older published").sum()),
           "n_profile": int((h.source == "profile estimate").sum()),
           "coverage_90_older_backtest": "86-90",
           "coverage_90_published_2024": round(float(c90["persistence"]), 1),
           "coverage_90_profile_2024": round(float(c90["profile"]), 1),
           "repo": "https://github.com/omkarb40/ed-throughput-audit"},
          open("app/data/meta.json", "w"), indent=1)
print(h.source.value_counts().to_dict())
print(acc.to_string(index=False))
print(h[["facility_name", "state", "source", "point", "lo90", "hi90"]].sample(5, random_state=1).round(0).to_string(index=False))
import os; print({f: f"{os.path.getsize('app/data/'+f)/1e3:.0f} KB" for f in os.listdir("app/data")})
