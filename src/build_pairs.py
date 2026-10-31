"""S12: pair every ED with its nearest alternative ED.

Pool: in-scope hospitals (acute care, critical access, DoD) that are in the most recent CMS hospital list (2026-08-13),
list emergency services, and have coordinates.
Distance: great-circle miles between ZIP centroids (county centroid for 110 PO-box ZIPs) — approximate to a few miles.
Each hospital gets its nearest OTHER ED (self explicitly excluded: with several hospitals on one ZIP centroid the
search can return a neighbour before the hospital itself). Pairs are de-duplicated (A->B and B->A count once).
Pairs farther apart than MAX_MILES are kept but flagged as not a realistic alternative (islands, remote Alaska).
"""
import numpy as np, pandas as pd
from sklearn.neighbors import BallTree

R_MILES = 3958.8
MAX_MILES = 50
g = pd.read_parquet("data/interim/hospital_geo.parquet")
a = pd.read_parquet("data/interim/hospital_attrs_latest.parquet")[["ccn", "hospital_type", "emergency_services"]]
g = g.merge(a, on="ccn", how="left")
snap = pd.read_parquet("data/interim/hospital_attrs_by_snapshot.parquet")
current = set(snap[snap.snapshot_date == snap.snapshot_date.max()].ccn)
pool = g[(g.emergency_services == "Yes") & g.lat.notna() & g.ccn.isin(current)].reset_index(drop=True)

tree = BallTree(np.radians(pool[["lat", "lon"]].to_numpy()), metric="haversine")
dist, idx = tree.query(np.radians(pool[["lat", "lon"]].to_numpy()), k=12)
pick = np.array([next(j for j in range(12) if idx[r, j] != r) for r in range(len(pool))])
rows = np.arange(len(pool))
nn = pd.DataFrame({"ccn": pool.ccn, "alt_ccn": pool.ccn.to_numpy()[idx[rows, pick]],
                   "miles": dist[rows, pick] * R_MILES})
assert (nn.ccn != nn.alt_ccn).all(), "self-pair"
nn["realistic"] = nn.miles <= MAX_MILES

# a hospital's nearest may tie with several at distance 0 (same ZIP); BallTree picks one deterministically
nn["same_zip_centroid"] = nn.miles < 0.01
nn["approx_coords"] = nn.ccn.map(pool.set_index("ccn").coord_source).ne("zcta_centroid") | \
                      nn.alt_ccn.map(pool.set_index("ccn").coord_source).ne("zcta_centroid")
nn["pair_id"] = [ "|".join(sorted(p)) for p in zip(nn.ccn, nn.alt_ccn)]
pairs = nn.drop_duplicates("pair_id").reset_index(drop=True)

info = pool.set_index("ccn")[["facility_name", "city", "state", "hospital_type", "rurality"]]
for side, col in (("a", "ccn"), ("b", "alt_ccn")):
    for c in info.columns:
        pairs[f"{c}_{side}"] = pairs[col].map(info[c])
pairs = pairs.rename(columns={"ccn": "ccn_a", "alt_ccn": "ccn_b"})
pairs["same_state"] = pairs.state_a == pairs.state_b
pairs.to_parquet("data/interim/hospital_pairs.parquet", index=False)

print(f"ED pool: {len(pool)} hospitals | nearest-neighbour links: {len(nn)} | unique pairs: {len(pairs)}")
print("miles to nearest ED (per hospital):", nn.miles.describe(percentiles=[.25, .5, .75, .9, .99]).round(1).to_dict())
print("same ZIP centroid:", int(nn.same_zip_centroid.sum()), "| approx coords involved:", int(nn.approx_coords.sum()))
print("per hospital, nearest within 10 / 25 / 50 miles:",
      [round(100 * (nn.miles <= m).mean(), 1) for m in (10, 25, 50)])
by = nn.merge(pool[["ccn", "rurality", "hospital_type"]], on="ccn")
print(by.groupby("rurality", observed=True).miles.median().round(1).to_dict())
print(by.groupby("hospital_type").miles.median().round(1).to_dict())
print("cross-state pairs:", int((~pairs.same_state).sum()), "| pairs beyond", MAX_MILES, "mi:", int((~pairs.realistic).sum()))
