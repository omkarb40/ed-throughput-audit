"""S1: per snapshot, OP_18b/OP_22 collection window, coverage, suppression, and duplicate detection."""
import hashlib, io, json, zipfile
from pathlib import Path
import pandas as pd
from locate import find_te_hospital

RENAME = {"Provider ID": "ccn", "Facility ID": "ccn", "Measure ID": "measure_id",
          "Measure Name": "measure_name", "Score": "score", "Sample": "sample",
          "Footnote": "footnote", "Measure Start Date": "start_date", "Start Date": "start_date",
          "Measure End Date": "end_date", "End Date": "end_date"}
meta = json.load(open("reports/01_schema_by_snapshot.json"))
rows, names = [], {}
for m in meta:
    if not m.get("member"): continue
    d = m["snapshot_date"]
    raw = zipfile.ZipFile(f"data/raw/hospitals_{d}.zip").read(m["member"])
    df = pd.read_csv(io.BytesIO(raw), dtype=str, encoding=m["encoding"]).rename(columns=RENAME)
    for mid in ["OP_18a", "OP_18b", "OP_18c", "OP_18d", "OP_22"]:
        s = df[df.measure_id == mid]
        if s.empty: continue
        names.setdefault(mid, set()).update(s.measure_name.unique())
        num = pd.to_numeric(s.score, errors="coerce")
        fp = hashlib.md5(pd.util.hash_pandas_object(
            s[["ccn", "score"]].sort_values("ccn").reset_index(drop=True), index=False).values).hexdigest()[:10]
        rows.append({"snapshot": d, "measure": mid,
                     "window": f"{s.start_date.mode()[0]} to {s.end_date.mode()[0]}",
                     "n_rows": len(s), "n_numeric": int(num.notna().sum()),
                     "pct_suppressed": round(100 * num.isna().mean(), 1),
                     "median": num.median(), "fingerprint": fp})
out = pd.DataFrame(rows)
out.to_csv("reports/01_op18_by_snapshot.csv", index=False)
pd.set_option("display.width", 200)
print(out[out.measure == "OP_18b"].to_string(index=False))
print()
print(out[out.measure == "OP_22"][["snapshot", "window", "n_numeric", "pct_suppressed", "median"]].to_string(index=False))
print()
for k, v in names.items(): print(k, "->", v)
