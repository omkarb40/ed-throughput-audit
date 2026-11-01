"""S15 figure: who has no published 2024 number vs how accurate the number is when it exists."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
C1, C2 = "#eb6834", "#2a78d6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK})
r = pd.read_csv("reports/15_slices.csv")
rows = [("type2", "acute care", "Acute care"), ("type2", "critical access", "Critical access"),
        ("rurality", "metro", "Metro county"), ("rurality", "rural", "Rural county"),
        ("income_q", "Q4 highest", "Richest 25% of counties"), ("income_q", "Q1 lowest", "Poorest 25% of counties"),
        ("ownership_group", "Voluntary non-profit", "Non-profit"), ("ownership_group", "Government", "Government"),
        ("ownership_group", "Proprietary", "For-profit")]
d = pd.DataFrame([{**r[(r.slice == s) & (r.group == g)].iloc[0].to_dict(), "label": lab} for s, g, lab in rows])
fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), facecolor=SURF, sharey=True, gridspec_kw={"wspace": 0.08})
for ax, col, c, title, lim in [(axes[0], "pct_no_2024_number", C1, "No published 2024 number", 20),
                               (axes[1], "persistence_medape", C2, "Typical error of last year's number", 8)]:
    ax.set_facecolor(SURF)
    ax.barh(range(len(d)), d[col], color=c, height=0.6)
    for i, v in enumerate(d[col]): ax.text(v + lim * 0.015, i, f"{v:.1f}%", va="center", fontsize=9)
    ax.set_xlim(0, lim); ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold")
    ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True); ax.tick_params(axis="x", labelsize=8.5)
    for sp in ax.spines.values(): sp.set_visible(False)
    for y in (1.5, 3.5, 5.5): ax.axhline(y, color=GRID, lw=1)
axes[0].set_yticks(range(len(d)), d.label); axes[0].invert_yaxis()
axes[0].set_xlabel("% of listed EDs"); axes[1].set_xlabel("median absolute % error, 2024")
fig.suptitle("Who gets a number varies far more than how accurate it is", x=0.01, ha="left",
             fontsize=12.5, fontweight="bold")
fig.text(0.01, 0.015, "EDs in the 2024 calendar-year panel. Right panel: hospitals with both a 2023 and 2024 value.",
         fontsize=8, color=INK2)
fig.subplots_adjust(left=0.19, right=0.98, top=0.86, bottom=0.17, wspace=0.08); fig.savefig("reports/figures/15_gap_vs_error.png", dpi=180)
print("ok")
