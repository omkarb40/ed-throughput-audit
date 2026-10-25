"""Download every snapshot in data/manifest.csv into data/raw/.
Resumable (skips files already present), validates each ZIP, rejects HTML responses.
Needs network access to data.cms.gov — run from your own terminal.
"""
import csv, time, zipfile
from pathlib import Path
import requests

RAW = Path("data/raw"); RAW.mkdir(parents=True, exist_ok=True)

def fetch(url: str, dest: Path, tries: int = 3) -> str:
    for attempt in range(1, tries + 1):
        try:
            with requests.get(url, stream=True, timeout=180) as r:
                r.raise_for_status()
                ctype = r.headers.get("content-type", "")
                if "html" in ctype.lower():
                    return f"REJECTED content-type={ctype}"
                tmp = dest.with_suffix(".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.rename(dest)
            bad = zipfile.ZipFile(dest).testzip()
            if bad:
                dest.unlink()
                return f"CORRUPT member={bad}"
            return "ok"
        except Exception as e:
            print(f"   attempt {attempt} failed: {e}")
            time.sleep(5 * attempt)
    return "FAILED"

rows = list(csv.DictReader(open("data/manifest.csv")))
problems = []
for i, r in enumerate(rows, 1):
    dest = RAW / r["url"].split("/")[-1]
    if dest.exists():
        print(f"[{i:2d}/{len(rows)}] {r['snapshot_date']} cached")
        continue
    print(f"[{i:2d}/{len(rows)}] {r['snapshot_date']} downloading...", flush=True)
    status = fetch(r["url"], dest)
    print(f"         {status}")
    if status != "ok":
        problems.append((r["snapshot_date"], status))
    time.sleep(2)  # be polite to a gov server

print(f"\n{len(rows) - len(problems)}/{len(rows)} usable")
for d, s in problems:
    print("  PROBLEM:", d, s)
