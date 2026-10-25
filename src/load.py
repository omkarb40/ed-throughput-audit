"""S2: load one CMS snapshot's hospital-level Timely & Effective Care file into a tidy frame.

Returns two frames:
  facts : one row per (ccn, measure_id) as published, plus parsed score/dates
  dims  : one row per ccn with name/location as published in that snapshot
Nothing is filtered here. Every source row survives; checks live in build_long.py.
"""
import io, json, zipfile
from pathlib import Path
import pandas as pd
from locate import find_te_hospital

RAW = Path("data/raw")
RENAME = {
    "Provider ID": "ccn", "Facility ID": "ccn",
    "Hospital Name": "facility_name", "Facility Name": "facility_name",
    "Address": "address", "City": "city", "City/Town": "city", "State": "state",
    "ZIP Code": "zip", "County Name": "county", "County/Parish": "county",
    "Phone Number": "phone", "Telephone Number": "phone",
    "Condition": "condition", "Measure ID": "measure_id", "Measure Name": "measure_name",
    "Score": "score_raw", "Sample": "sample_raw", "Footnote": "footnote",
    "Measure Start Date": "start_date", "Start Date": "start_date",
    "Measure End Date": "end_date", "End Date": "end_date",
}
FACT_COLS = ["ccn", "condition", "measure_id", "measure_name", "score_raw", "sample_raw",
             "footnote", "start_date", "end_date"]
DIM_COLS = ["ccn", "facility_name", "address", "city", "state", "zip", "county"]


def _codes(fn: str):
    import re
    head = fn.split(" - ")[0]
    codes = sorted({int(c) for c in re.findall(r"\d+", head)})
    return ",".join(map(str, codes)) if codes else pd.NA


def read_snapshot(snapshot_date: str) -> tuple[pd.DataFrame, int]:
    z = RAW / f"hospitals_{snapshot_date}.zip"
    member = find_te_hospital(z)
    if member is None:
        raise FileNotFoundError(f"no T&E hospital file in {z.name}")
    raw = zipfile.ZipFile(z).read(member)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    # source row count independent of pandas: physical CSV records via csv module
    import csv
    n_source = sum(1 for _ in csv.reader(io.StringIO(text))) - 1
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    unknown = set(df.columns) - set(RENAME)
    if unknown:
        raise ValueError(f"{snapshot_date}: unmapped columns {unknown}")
    return df.rename(columns=RENAME), n_source


def load_snapshot(snapshot_date: str):
    df, n_source = read_snapshot(snapshot_date)
    df = df.apply(lambda s: s.str.strip())
    df["snapshot_date"] = pd.Timestamp(snapshot_date)

    facts = df[["snapshot_date"] + FACT_COLS].copy()
    facts["score"] = pd.to_numeric(facts.score_raw, errors="coerce")
    facts["sample"] = pd.to_numeric(facts.sample_raw, errors="coerce")
    for c in ("start_date", "end_date"):
        facts[c] = pd.to_datetime(facts[c], format="%m/%d/%Y", errors="coerce")
    facts["footnote"] = facts.footnote.replace("", pd.NA)
    # CMS writes footnotes either as bare codes ("3, 29") or "5 - Results are not...".
    # Normalize to a sorted comma-separated code list; the text lives in the data dictionary.
    facts["footnote_codes"] = facts.footnote.map(_codes, na_action="ignore")
    facts["is_flagged"] = facts.footnote.notna()  # includes one "***" with no code (521348, 2021-10-27)

    dims = df[["snapshot_date"] + DIM_COLS].drop_duplicates("ccn")
    return facts, dims, n_source
