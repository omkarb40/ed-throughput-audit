"""S13 figure: % of nearby ED pairs where each signal picks the ED that was faster in 2024, by true difference."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
C = {"last_year": "#2a78d6", "model_A": "#eb6834"}
L = {"last_year": "Last year's published number", "model_A": "Guess from public characteristics (Model A)"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
r = pd.read_csv("reports/13_decision.csv")
order = ["diff_bucket=<15 min", "diff_bucket=15-30", "diff_bucket=30-60", "diff_bucket=>60", "all realistic pairs"]
labels = ["< 15 min", "15–30 min", "30–60 min", "> 60 min", "All pairs"]
fig, ax = plt.subplots(figsize=(9.6, 4.4), facecolor=SURF); ax.set_facecolor(SURF)
x = np.arange(len(order)); w = 0.36
for j, s in enumerate(["last_year", "model_A"]):
    sub = r[r.signal == s].set_index("subset").reindex(order)
    xs = x + (j - 0.5) * w
    ax.bar(xs, sub.pct_correct, width=w - 0.03, color=C[s], label=L[s])
    ax.errorbar(xs, sub.pct_correct, yerr=[sub.pct_correct - sub.pct_lo, sub.pct_hi - sub.pct_correct],
                fmt="none", ecolor=INK, lw=1, capsize=3)
    for xi, v, hi in zip(xs, sub.pct_correct, sub.pct_hi):
        ax.text(xi, hi + 1.5, f"{v:.0f}%", ha="center", fontsize=9, color=INK)
n = r[r.signal == "last_year"].set_index("subset").reindex(order).pairs
ax.set_xticks(x, [f"{l}\n(n={int(k):,})" for l, k in zip(labels, n)])
ax.axhline(50, color=INK2, lw=1, ls=(0, (3, 3))); ax.text(4.62, 51.5, "coin flip", fontsize=8.5, color=INK2, ha="right")
ax.axvline(3.5, color=GRID, lw=1)
ax.set_ylim(0, 112); ax.set_yticks(range(0, 101, 25)); ax.set_ylabel("% of pairs, faster ED picked")
ax.set_xlabel("Actual 2024 difference between the two nearby EDs")
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for sp in ax.spines.values(): sp.set_visible(False)
ax.legend(frameon=False, loc="upper left", fontsize=9, bbox_to_anchor=(0, 1.02))
ax.set_title("Picking the faster of two nearby EDs: last year's number 86%, public profile 64%",
             loc="left", fontsize=11.5, fontweight="bold")
fig.text(0.01, 0.01, "Nearest-neighbour ED pairs within 50 miles, both with a 2024 OP-18b. 95% bootstrap CIs. "
         "Model B forecast scores the same as last year's number (not shown).", fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig("reports/figures/13_decision.png", dpi=180)
print("ok")
