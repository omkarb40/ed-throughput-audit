"""Find the hospital-level Timely and Effective Care CSV inside a CMS snapshot ZIP.
CMS used four naming eras (title w/ spaces, title w/ underscores, foldered, dataset-ID).
Dataset ID yv7e-xc69 / yv7e_xc69 is the stable key; title match is the fallback.
"""
import zipfile
from pathlib import Path

def find_te_hospital(zpath: Path) -> str | None:
    names = [n for n in zipfile.ZipFile(zpath).namelist()
             if n.lower().endswith(".csv") and "__macosx" not in n.lower()]
    by_id = [n for n in names if "yv7e" in n.lower()]
    if by_id:
        return by_id[0]
    by_title = [n for n in names
                if "timely" in Path(n).name.lower() and "hospital" in Path(n).name.lower()
                and "reh" not in Path(n).name.lower()]
    return by_title[0] if len(by_title) == 1 else None
