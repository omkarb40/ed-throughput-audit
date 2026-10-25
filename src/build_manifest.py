"""Write data/manifest.csv: one row per CMS hospital archive snapshot.
Dates transcribed from data.cms.gov/provider-data/archived-data/hospitals on 2026-10-24.
URL pattern confirmed from links on that page.
"""
import csv
from pathlib import Path

BASE = "https://data.cms.gov/provider-data/sites/default/files/dataset-archives/theme/hospitals"

# (snapshot_date, size_mb_shown_on_page, labeled_"Snapshot"_on_page)
SNAPSHOTS = [
    ("2026-09-30", 3,  False), ("2026-08-13", 14, False),
    ("2026-05-13", 14, True),  ("2026-02-25", 14, True),
    ("2025-11-26", 16, True),  ("2025-08-14", 16, True),
    ("2025-04-30", 15, True),  ("2025-02-19", 15, True),
    ("2024-10-30", 15, True),  ("2024-07-31", 14, True),
    ("2024-04-24", 14, True),  ("2024-01-31", 14, True),
    ("2023-11-06", 17, True),  ("2023-10-06", 16, True),
    ("2023-07-06", 16, True),  ("2023-04-06", 16, True),
    ("2023-01-06", 16, True),
    ("2022-10-06", 15, True),  ("2022-07-06", 15, True),
    ("2022-04-06", 16, True),  ("2022-01-06", 16, True),
    ("2021-10-27", 15, True),  ("2021-07-21", 14, True),
    ("2021-04-28", 15, True),  ("2021-03-31", 14, True),
    ("2021-01-27", 15, True),
    ("2020-10-16", 15, True),  ("2020-07-04", 13, True),
    ("2020-05-01", 16, True),  ("2020-01-04", 16, True),
    ("2019-10-31", 17, True),  ("2019-07-31", 22, True),
    ("2019-04-04", 18, True),  ("2019-03-04", 19, True),
]
assert len(SNAPSHOTS) == 34, "count drifted from the page — recheck"

out = Path("data/manifest.csv")
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["snapshot_date", "url", "page_size_mb", "labeled_snapshot"])
    for d, mb, labeled in sorted(SNAPSHOTS):
        w.writerow([d, f"{BASE}/hospitals_{d}.zip", mb, labeled])
print(f"wrote {len(SNAPSHOTS)} rows to {out}")
