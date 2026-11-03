"""Regenerate every report figure from the saved results. Run: PYTHONPATH=src python src/make_figures.py
Each figure script reads only files in reports/ and data/interim/, so this needs no models to be retrained."""
import runpy, sys, time
from pathlib import Path

SCRIPTS = ["fig_suppression", "fig_target", "fig_models", "fig_fe", "fig_decision", "fig_conformal",
           "fig_slices", "fig_shap"]
before = {p: p.stat().st_mtime for p in Path("reports/figures").glob("*.png")}
start = time.time(); failed = []
for s in SCRIPTS:
    try:
        runpy.run_path(f"src/{s}.py", run_name="__main__"); print(f"  {s}: ok")
    except Exception as e:
        failed.append(s); print(f"  {s}: FAILED {e}")
after = sorted(Path("reports/figures").glob("*.png"))
stale = [p.name for p in after if p.stat().st_mtime < start]
print(f"\n{len(after)} figures, {len(after) - len(stale)} regenerated this run")
if stale: print("not regenerated:", stale)
sys.exit(1 if failed or stale else 0)
