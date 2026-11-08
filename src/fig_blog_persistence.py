"""Blog figure: each hospital's 2023 ED time against its 2024 ED time (calendar years, OP-18b)."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd

SURF, INK, INK2, GRID, GREY, BLUE = "#ffffff", "#0b0b0b", "#52514e", "#e6e5e1", "#9a9890", "#2a78d6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
t = pd.read_parquet("data/interim/analysis_table.parquet")
w = t[t.year.isin([2023, 2024]) & t.op18b.notna()].pivot_table(index="ccn", columns="year", values="op18b").dropna()
r = np.corrcoef(np.log(w[2023]), np.log(w[2024]))[0, 1]
med_change = (w[2024] - w[2023]).abs().median()
within15 = ((w[2024] - w[2023]).abs() <= 15).mean() * 100

fig, ax = plt.subplots(figsize=(7.5, 6.2), facecolor=SURF); ax.set_facecolor(SURF)
ax.scatter(w[2023], w[2024], s=9, color=GREY, alpha=0.45, linewidths=0)
lim = (50, 450)
ax.plot(lim, lim, color=BLUE, lw=1.6)
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
ticks = [60, 100, 150, 200, 300, 400]
ax.set_xticks(ticks, [str(v) for v in ticks]); ax.set_yticks(ticks, [str(v) for v in ticks])
ax.minorticks_off()
ax.set_xlabel("2023 median minutes in the ER"); ax.set_ylabel("2024 median minutes in the ER")
ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True)
for sp in ax.spines.values(): sp.set_visible(False)
fig.suptitle("An ER's time barely moves from one year to the next", x=0.03, ha="left",
             fontsize=14, fontweight="bold", y=0.975)
fig.text(0.03, 0.885, f"Each dot is one of {len(w):,} US hospitals. Blue line = no change.\n"
         f"Typical change: {med_change:.0f} min. {within15:.0f}% moved 15 minutes or less.", fontsize=10.5,
         color=INK2, linespacing=1.4)
fig.text(0.03, 0.012, "Data: CMS Timely and Effective Care, measure OP-18b (log scales).", fontsize=8.5, color=INK2)
fig.tight_layout(rect=(0, 0.03, 1, 0.885))
fig.savefig("docs/blog/1_persistence_2023_2024.png", dpi=200, facecolor=SURF)
print(f"hospitals {len(w)} | r(log) {r:.3f} | median abs change {med_change:.1f} | within 15 min {within15:.1f}%")
