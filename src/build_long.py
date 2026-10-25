"""S2: load all snapshots, verify zero row loss, write long-format Parquet."""
import json
from pathlib import Path
import pandas as pd
from load import load_snapshot

meta = json.load(open("reports/01_schema_by_snapshot.json"))
snaps = [m["snapshot_date"] for m in meta if m.get("member")]
facts_all, dims_all, checks = [], [], []
for d in snaps:
    f, dm, n_src = load_snapshot(d)
    bad_dates = int(f.start_date.isna().sum() + f.end_date.isna().sum())
    ccn_len = f.ccn.str.len().value_counts().to_dict()
    dup_keys = int(f.duplicated(["ccn", "measure_id"]).sum())
    checks.append({"snapshot_date": d, "source_rows": n_src, "loaded_rows": len(f),
                   "match": n_src == len(f), "n_ccn": f.ccn.nunique(),
                   "dup_ccn_measure": dup_keys, "unparsed_dates": bad_dates,
                   "ccn_lengths": json.dumps({str(k): int(v) for k, v in ccn_len.items()})})
    facts_all.append(f); dims_all.append(dm)
    print(d, checks[-1])

facts = pd.concat(facts_all, ignore_index=True)
dims = pd.concat(dims_all, ignore_index=True)
for c in ("ccn", "condition", "measure_id", "measure_name", "footnote", "footnote_codes"):
    facts[c] = facts[c].astype("string")
Path("data/interim").mkdir(parents=True, exist_ok=True)
facts.to_parquet("data/interim/te_long.parquet", index=False)
dims.to_parquet("data/interim/hospital_dims.parquet", index=False)
pd.DataFrame(checks).to_csv("reports/02_load_checks.csv", index=False)
print(f"\nfacts {facts.shape}, dims {dims.shape}")
print("all row counts match:", all(c["match"] for c in checks))
