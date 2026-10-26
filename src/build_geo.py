"""S6: attach county FIPS, rurality (RUCC 2023), and coordinates to every in-scope hospital.

County assignment, in priority order:
  1. CMS county name + state -> 2023 Gazetteer county   (hospital's own address; authoritative)
  2. Connecticut: CMS city -> 2023 county subdivision -> planning region (CT replaced counties in 2022)
  3. Hospital ZIP -> 2020 ZCTA -> county with largest land overlap   (fallback)
The ZCTA result is also kept for every hospital as an independent cross-check.
Coordinates: ZCTA centroid; else county-subdivision (CT) or county centroid, flagged lower precision.
"""
import os, re, unicodedata, zipfile
import pandas as pd

EXT = "data/external"
SCOPE = ["Acute Care Hospitals", "Critical Access Hospitals", "Acute Care - Department of Defense"]
ALIASES = {"DC|THEDISTRICT": "11001", "DC|DISTRICTOFCOLUMBIA": "11001", "DC|WASHINGTON": "11001"}

def norm(s):
    if not isinstance(s, str): return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    s = s.replace("SAINT ", "ST ").replace("ST. ", "ST ").replace("STE. ", "STE ")
    s = re.sub(r"\b(COUNTY|PARISH|BOROUGH|CENSUS AREA|MUNICIPIO|MUNICIPALITY|CITY AND BOROUGH|PLANNING REGION|TOWN|ISLAND)\b", "", s)
    return re.sub(r"[^A-Z]", "", s)

def read_gaz(name):
    with zipfile.ZipFile(f"{EXT}/{name}") as z:
        g = pd.read_csv(z.open(z.namelist()[0]), sep="\t", dtype=str)
    g.columns = g.columns.str.strip()
    return g

# --- hospitals in scope, latest published location
st = pd.read_parquet("data/interim/op18b_status.parquet")
scope_ccn = st[st.type.isin(SCOPE)].ccn.unique()
dm = pd.read_parquet("data/interim/hospital_dims.parquet")
h = (dm[dm.ccn.isin(scope_ccn)].sort_values("snapshot_date").drop_duplicates("ccn", keep="last")
       [["ccn", "facility_name", "city", "state", "zip", "county"]].reset_index(drop=True))

# --- reference tables
gc = read_gaz("2023_Gaz_counties_national.zip").rename(columns={"USPS": "state", "GEOID": "fips", "NAME": "county_ref"})
gc[["lat_c", "lon_c"]] = gc[["INTPTLAT", "INTPTLONG"]].astype(float)
gc["key"] = gc.state + "|" + gc.county_ref.map(norm)
county_by_key = gc.drop_duplicates("key").set_index("key").fips
county_info = gc.set_index("fips")[["county_ref", "lat_c", "lon_c"]]

rel = pd.read_csv(f"{EXT}/tab20_zcta520_county20_natl.txt", sep="|", dtype=str, encoding="utf-8-sig")
rel = rel.dropna(subset=["GEOID_ZCTA5_20"])
rel["AREALAND_PART"] = rel.AREALAND_PART.astype(float)
z2c = (rel.sort_values("AREALAND_PART", ascending=False).drop_duplicates("GEOID_ZCTA5_20")
          .set_index("GEOID_ZCTA5_20").GEOID_COUNTY_20)

gz = read_gaz("2023_Gaz_zcta_national.zip").rename(columns={"GEOID": "zip"})
gz = gz.set_index("zip")[["INTPTLAT", "INTPTLONG"]].astype(float)

ru = pd.read_csv(f"{EXT}/2023-rural-urban-continuum-codes.csv", dtype=str, encoding="latin-1")
ru = ru[ru.Attribute == "RUCC_2023"].set_index("FIPS").Value.astype(int)

# --- 1. CMS county name
h["key"] = h.state + "|" + h.county.map(norm)
h["fips"] = h.key.map(county_by_key).fillna(h.key.map(ALIASES))
h["fips_source"] = h.fips.notna().map({True: "cms_county_name", False: pd.NA})

# --- 2. Connecticut via town -> planning region (only if the cousub gazetteer is present)
ct_path = f"{EXT}/2023_Gaz_cousubs_national.zip"
cs = None
if os.path.exists(ct_path):
    cs = read_gaz("2023_Gaz_cousubs_national.zip")
    cs = cs[cs.USPS == "CT"].copy()
    cs["town"] = cs.NAME.map(norm)
    cs["region_fips"] = cs.GEOID.str[:5]
    cs[["lat_t", "lon_t"]] = cs[["INTPTLAT", "INTPTLONG"]].astype(float)
    town = cs.drop_duplicates("town").set_index("town")
    ct = (h.state == "CT")
    h.loc[ct, "fips"] = h.loc[ct, "city"].map(norm).map(town.region_fips)
    h.loc[ct & h.fips.notna(), "fips_source"] = "ct_town_to_region"

    # villages (e.g. Willimantic, Stafford Springs) are not towns: nearest town centroid to the ZIP centroid
    miss = ct & h.fips.isna() & h.zip.isin(gz.index)
    for i in h[miss].index:
        la, lo = gz.loc[h.at[i, "zip"], ["INTPTLAT", "INTPTLONG"]]
        d2 = (cs.lat_t - la) ** 2 + ((cs.lon_t - lo) * 0.75) ** 2
        j = d2.idxmin()
        h.at[i, "fips"], h.at[i, "fips_source"] = cs.at[j, "region_fips"], f"ct_nearest_town:{cs.at[j, 'NAME']}"

# --- 3. ZCTA fallback + cross-check
h["fips_zcta"] = h.zip.map(z2c)
fb = h.fips.isna() & h.fips_zcta.notna() & (h.state != "CT")
h.loc[fb, "fips"] = h.loc[fb, "fips_zcta"]
h.loc[fb, "fips_source"] = "zcta_fallback"
chk = h[(h.fips_source == "cms_county_name") & h.fips_zcta.notna()]
h["zcta_agrees"] = pd.NA
h.loc[chk.index, "zcta_agrees"] = chk.fips == chk.fips_zcta

# --- rurality
h["county_ref"] = h.fips.map(county_info.county_ref)
h["rucc_2023"] = h.fips.map(ru)
h["rurality"] = pd.cut(h.rucc_2023, [0, 3, 6, 9], labels=["metro", "nonmetro_adjacent_or_large", "rural"])

# --- coordinates
h["lat"], h["lon"] = h.zip.map(gz.INTPTLAT), h.zip.map(gz.INTPTLONG)
h["coord_source"] = h.lat.notna().map({True: "zcta_centroid", False: pd.NA})
if cs is not None:
    m = h.lat.isna() & (h.state == "CT")
    t = h.loc[m, "city"].map(norm)
    h.loc[m, "lat"], h.loc[m, "lon"] = t.map(town.lat_t), t.map(town.lon_t)
    h.loc[m & h.lat.notna(), "coord_source"] = "ct_town_centroid"
m = h.lat.isna() & h.fips.notna()
h.loc[m, "lat"], h.loc[m, "lon"] = h.loc[m, "fips"].map(county_info.lat_c), h.loc[m, "fips"].map(county_info.lon_c)
h.loc[m & h.lat.notna(), "coord_source"] = "county_centroid"

h = h.drop(columns="key")
h.to_parquet("data/interim/hospital_geo.parquet", index=False)

print(f"in-scope hospitals: {len(h)}")
print("county source:", h.fips_source.value_counts(dropna=False).to_dict())
a = h.zcta_agrees.dropna().astype(bool)
print(f"CMS-name county vs ZCTA county agree: {a.mean():.1%} of {len(a)}")
print("RUCC matched:", int(h.rucc_2023.notna().sum()), "| missing by state:", h[h.rucc_2023.isna()].state.value_counts().to_dict())
print("coords:", h.coord_source.value_counts(dropna=False).to_dict())
print("rurality:", h.rurality.value_counts(dropna=False).to_dict())
print("CT cousub file present:", cs is not None)
