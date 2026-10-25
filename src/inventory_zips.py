"""Offline S1 recon: inventory every ZIP in data/raw/ without network.
Writes reports/03_download_log.csv and reports/01_zip_inventory.csv.
"""
import csv, hashlib, zipfile
from pathlib import Path

RAW = Path("data/raw"); REP = Path("reports"); REP.mkdir(exist_ok=True)
manifest = {r["snapshot_date"]: r for r in csv.DictReader(open("data/manifest.csv"))}

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()

log, members = [], []
for d, m in sorted(manifest.items()):
    p = RAW / f"hospitals_{d}.zip"
    if not p.exists():
        log.append({"snapshot_date": d, "status": "MISSING", "size_mb": 0,
                    "page_size_mb": m["page_size_mb"], "n_files": 0, "sha256": ""})
        continue
    try:
        z = zipfile.ZipFile(p)
        names = z.namelist()
        for n in names:
            members.append({"snapshot_date": d, "member": n,
                            "size_mb": round(z.getinfo(n).file_size / 1e6, 3)})
        status = "ok"
    except zipfile.BadZipFile:
        names, status = [], "BAD_ZIP"
    log.append({"snapshot_date": d, "status": status,
                "size_mb": round(p.stat().st_size / 1e6, 2),
                "page_size_mb": m["page_size_mb"], "n_files": len(names),
                "sha256": sha256(p)})

for name, rows in [("03_download_log.csv", log), ("01_zip_inventory.csv", members)]:
    with open(REP / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

ok = sum(r["status"] == "ok" for r in log)
print(f"{ok}/{len(log)} usable ZIPs; {len(members)} members inventoried")
for r in log:
    print(f"  {r['snapshot_date']}  {r['status']:8s} {r['size_mb']:7.2f} MB  {r['n_files']:3d} files")
