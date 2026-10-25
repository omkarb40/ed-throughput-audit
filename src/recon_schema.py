"""S1: per snapshot, record the T&E file, its columns, row count, and ED measure IDs."""
import csv, io, json, zipfile
from pathlib import Path
import pandas as pd
from locate import find_te_hospital

RAW = Path("data/raw")
out = []
for d in [r["snapshot_date"] for r in csv.DictReader(open("data/manifest.csv"))]:
    z = RAW / f"hospitals_{d}.zip"
    member = find_te_hospital(z)
    if member is None:
        out.append({"snapshot_date": d, "member": None}); continue
    raw = zipfile.ZipFile(z).read(member)
    enc = "utf-8"
    try: raw.decode("utf-8")
    except UnicodeDecodeError: enc = "latin-1"
    df = pd.read_csv(io.BytesIO(raw), dtype=str, encoding=enc, low_memory=False)
    mid = next((c for c in df.columns if c.strip().lower() in ("measure id", "measure_id")), None)
    ids = sorted(df[mid].dropna().unique()) if mid else []
    ed = [i for i in ids if i.upper().startswith(("OP_18", "OP_20", "OP_22", "OP_23", "EDV", "ED_"))]
    out.append({"snapshot_date": d, "member": member, "encoding": enc,
                "rows": len(df), "n_ccn": df[df.columns[0]].nunique(),
                "columns": list(df.columns), "n_measures": len(ids), "ed_measures": ed,
                "all_measures": ids})
Path("reports/01_schema_by_snapshot.json").write_text(json.dumps(out, indent=1))
for r in out:
    if not r.get("member"): print(r["snapshot_date"], "NO T&E FILE"); continue
    print(r["snapshot_date"], r["encoding"], f"rows={r['rows']:6d} ccn={r['n_ccn']:5d} meas={r['n_measures']:3d}", r["ed_measures"])
