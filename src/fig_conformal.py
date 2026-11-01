"""S14 figure: 90% interval coverage on 2024 by group, one interval for all vs calibrated per group."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
C = {"marginal": "#9a9890", "mondrian": "#2a78d6"}
L = {"marginal": "One interval width for every hospital", "mondrian": "Calibrated per group"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
r = pd.read_csv("reports/14_coverage.csv")
r = r[(r.forecast == "persistence") & (r.level == 0.9)]
groups = [("all", "All"), ("acute care", "Acute care"), ("critical access", "Critical access"),
          ("rural", "Rural"), ("critical access, last value footnoted", "Critical access,\nlast value footnoted"),
          ("acute care, last value footnoted", "Acute care,\nlast value footnoted")]
fig, ax = plt.subplots(figsize=(9.6, 4.3), facecolor=SURF); ax.set_facecolor(SURF)
x = np.arange(len(groups)); w = 0.18
for j, m in enumerate(["marginal", "mondrian"]):
    sub = r[r.method == m].set_index("group").reindex([g for g, _ in groups])
    xs = x + (j - 0.5) * 2 * w
    ax.scatter(xs, sub.coverage, s=90, color=C[m], label=L[m], zorder=3, edgecolor=SURF, linewidth=2)
    for xi, v, wd in zip(xs, sub.coverage, sub.median_width_min):
        ax.text(xi, v + 0.9, f"{v:.0f}%", ha="center", fontsize=9, color=INK)
n = r[r.method == "marginal"].set_index("group").reindex([g for g, _ in groups]).n
ax.set_xlim(-0.55, 5.55); ax.set_xticks(x, [f"{lab}\n(n={int(k):,})" for (_, lab), k in zip(groups, n)], fontsize=9)
ax.axhline(90, color=INK, lw=1, ls=(0, (3, 3))); ax.text(-0.45, 90.3, "target 90%", fontsize=8.5, color=INK, ha="left")
ax.set_ylim(75, 96); ax.set_ylabel("% of 2024 values inside the interval")
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for sp in ax.spines.values(): sp.set_visible(False)
ax.legend(frameon=False, loc="upper right", fontsize=9, bbox_to_anchor=(1, 1.13), ncol=2)
ax.set_title("90% intervals around last year's number: coverage by group", loc="left", fontsize=12,
             fontweight="bold", pad=24)
fig.text(0.01, 0.01, "Split conformal, calibrated on 2023, tested on 2024. Interval widths in reports/14_intervals.md. "
         "Acute care with a footnoted value: only 24 calibration hospitals.", fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig("reports/figures/14_coverage.png", dpi=180)
print("ok")
