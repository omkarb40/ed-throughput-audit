"""S5 helper: hospital attributes (type, ownership, emergency services, state) from Hospital General
Information in every snapshot. One row per (snapshot, ccn) plus a 'latest' table per ccn.
"""
import io, json, zipfile
from pathlib import Path
import pandas as pd

RENAME = {"Provider ID": "ccn", "Facility ID": "ccn", "State": "state",
          "Hospital Type": "hospital_type", "Hospital Ownership": "ownership",
          "Emergency Services": "emergency_services", "ZIP Code": "zip"}

def find_gi(z):
    names = [n for n in z.namelist() if n.lower().endswith(".csv") and "__macosx" not in n.lower()]
    hit = [n for n in names if "xubh" in n.lower()] or \
          [n for n in names if "general" in Path(n).name.lower() and "information" in Path(n).name.lower()]
    return hit[0] if hit else None

meta = json.load(open("reports/01_schema_by_snapshot.json"))
frames = []
for d in [m["snapshot_date"] for m in meta if m.get("member")]:
    z = zipfile.ZipFile(f"data/raw/hospitals_{d}.zip")
    m = find_gi(z)
    raw = z.read(m)
    try: text = raw.decode("utf-8")
    except UnicodeDecodeError: text = raw.decode("latin-1")
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False).rename(columns=RENAME)
    df = df[[c for c in set(RENAME.values()) if c in df.columns]].copy()
    df["snapshot_date"] = pd.Timestamp(d)
    frames.append(df)
    print(d, m.split("/")[-1][:60], len(df))

a = pd.concat(frames, ignore_index=True)
for c in ("hospital_type", "ownership", "emergency_services"):
    a[c] = a[c].str.strip()
a.to_parquet("data/interim/hospital_attrs_by_snapshot.parquet", index=False)
latest = a.sort_values("snapshot_date").drop_duplicates("ccn", keep="last")
latest.to_parquet("data/interim/hospital_attrs_latest.parquet", index=False)
print("\nlatest per ccn:", len(latest))
print(latest.hospital_type.value_counts().to_dict())
print(latest.emergency_services.value_counts().to_dict())
