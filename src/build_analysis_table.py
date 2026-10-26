"""S6: one row per in-scope hospital x calendar year, with targets, same-year ED covariates,
hospital attributes, geography, and (if available) ACS county context.
"""
import json, os
import pandas as pd

SCOPE = ["Acute Care Hospitals", "Critical Access Hospitals", "Acute Care - Department of Defense"]
p = pd.read_parquet("data/interim/ed_panel.parquet")
st = pd.read_parquet("data/interim/op18b_status.parquet")
geo = pd.read_parquet("data/interim/hospital_geo.parquet")

base = st[st.type.isin(SCOPE)][["ccn", "year", "score", "status", "is_flagged", "footnote_codes",
                                "edv", "type", "own", "emergency_services", "state"]]
base = base.rename(columns={"score": "op18b", "is_flagged": "op18b_flagged",
                            "footnote_codes": "op18b_footnotes", "own": "ownership_group"})

def same_year(measure, name):
    x = p[(p.measure_id == measure) & p.is_calendar_year][["ccn", "year", "score", "is_flagged"]]
    return x.rename(columns={"score": name, "is_flagged": f"{name}_flagged"})

t = (base.merge(same_year("OP_18c", "op18c"), on=["ccn", "year"], how="left")
         .merge(same_year("OP_22", "op22_lwbs_pct"), on=["ccn", "year"], how="left")
         .merge(geo[["ccn", "fips", "fips_source", "county_ref", "rucc_2023", "rurality",
                     "lat", "lon", "coord_source"]], on="ccn", how="left"))

# ---- ACS (optional until the API key works)
acs_path = "data/external/acs2022_county_profile.json"
acs_ok = False
if os.path.exists(acs_path):
    try:
        raw = json.load(open(acs_path))
        acs = pd.DataFrame(raw[1:], columns=raw[0])
        acs["fips"] = acs.state + acs.county
        acs = acs.rename(columns={"DP05_0001E": "county_pop", "DP03_0062E": "county_median_hh_income",
                                  "DP03_0099PE": "county_pct_uninsured", "DP05_0024PE": "county_pct_65plus"})
        num = ["county_pop", "county_median_hh_income", "county_pct_uninsured", "county_pct_65plus"]
        acs[num] = acs[num].apply(pd.to_numeric, errors="coerce")
        acs[num] = acs[num].mask(acs[num] < 0)  # Census uses large negatives as missing-value sentinels
        t = t.merge(acs[["fips"] + num], on="fips", how="left")
        acs_ok = True
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

t["year"] = t.year.astype(int)
t = t.sort_values(["ccn", "year"]).reset_index(drop=True)
assert not t.duplicated(["ccn", "year"]).any()
t.to_parquet("data/interim/analysis_table.parquet", index=False)

print("analysis_table:", t.shape, "| ACS joined:", acs_ok)
print("hospitals:", t.ccn.nunique(), "| years:", sorted(t.year.unique()))
print("type:", t.drop_duplicates("ccn").type.value_counts().to_dict())
cov = t.notna().mean().mul(100).round(1)
print("non-null % per column:\n", cov.to_string())
