"""S11 figure: where the variation in ED time comes from, by hospital type (noise-corrected)."""
import json
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
COL = {"structural": "#2a78d6", "hospital": "#eb6834", "within": "#c9c7c0"}
LBL = {"structural": "Between hospitals, explained by public characteristics",
       "hospital": "Between hospitals, specific to the hospital",
       "within": "Within a hospital, year to year"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK})
runs = {r["label"]: r for r in json.load(open("reports/11_fe_results.json"))}
pops = [("all", "All hospitals"), ("acute care", "Acute care"), ("critical access", "Critical access")]
fig, ax = plt.subplots(figsize=(9, 3.6), facecolor=SURF); ax.set_facecolor(SURF)
for i, (k, lab) in enumerate(pops):
    r = runs[k]; left = 0
    for part, val in [("structural", r["share_total_structural"]), ("hospital", r["share_total_hospital_unexplained"]),
                      ("within", r["share_total_within"])]:
        ax.barh(i, 100 * val, left=left, color=COL[part], height=0.6, edgecolor=SURF, linewidth=2,
                label=LBL[part] if i == 0 else None)
        ax.text(left + 50 * val, i, f"{100 * val:.0f}%", ha="center", va="center", fontsize=10,
                color="white" if part != "within" else INK)
        left += 100 * val
    ax.text(101, i, f"n={r['hospitals']:,}", va="center", fontsize=8.5, color=INK2)
ax.set_yticks(range(3), [p[1] for p in pops]); ax.invert_yaxis(); ax.set_xlim(0, 108)
ax.set_xticks(range(0, 101, 20)); ax.set_xlabel("% of variance in log OP-18b after removing year effects")
for sp in ax.spines.values(): sp.set_visible(False)
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1, frameon=False, fontsize=9)
ax.set_title("Where ED time differences come from", loc="left", fontsize=12, fontweight="bold", pad=62)
fig.text(0.01, 0.01, "Between vs within: random-intercept model (REML). Explained part: 5-fold CV LightGBM on hospital effects. "
         "Years 2018–2024 (no 2020).", fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig("reports/figures/11_variance_sources.png", dpi=180)
print("ok")
