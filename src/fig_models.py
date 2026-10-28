"""S10 figure: test-year MAE for every baseline and model, with 95% CIs."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
BASE, MODEL = "#9a9890", "#2a78d6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK})
b = pd.read_csv("reports/09_baselines.csv"); m = pd.read_csv("reports/10_models.csv")
b = b[(b.part == "test") & (b.group == "all")].set_index("baseline")
m = m[(m.subset == "all") & (m.group == "all")].set_index("model")
rows = [("National type median", b.loc["B2"], BASE, "unseen hospitals"),
        ("State × type median", b.loc["B1"], BASE, "unseen hospitals"),
        ("Model A without volume", m.loc["A_no_volume"], MODEL, "unseen hospitals"),
        ("Model A (structure)", m.loc["A"], MODEL, "unseen hospitals"),
        ("Last year's value", b.loc["B0"], BASE, "same hospitals, next year"),
        ("Model B (forecast)", m.loc["B"], MODEL, "same hospitals, next year")]
fig, ax = plt.subplots(figsize=(9, 4.4), facecolor=SURF); ax.set_facecolor(SURF)
for i, (lab, r, c, _) in enumerate(rows):
    ax.barh(i, r.mae_min, color=c, height=0.6)
    ax.errorbar(r.mae_min, i, xerr=[[r.mae_min - r.mae_min_lo], [r.mae_min_hi - r.mae_min]],
                color=INK, lw=1, capsize=3)
    ax.text(r.mae_min_hi + 0.6, i, f"{r.mae_min:.1f} min · ρ {r.spearman:.2f}", va="center", fontsize=9)
ax.set_yticks(range(len(rows)), [r[0] for r in rows]); ax.invert_yaxis()
ax.axhline(3.5, color=GRID, lw=1)
ax.text(44, 2.5, "Hospitals never\nseen in training", fontsize=8.5, color=INK2, va="center", ha="right")
ax.text(44, 5, "Same hospitals,\nforecast 2024", fontsize=8.5, color=INK2, va="center", ha="right")
ax.set_xlim(0, 44); ax.set_xticks(range(0, 36, 5)); ax.set_xlabel("Mean absolute error, 2024 (minutes), with 95% CI")
ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
for sp in ax.spines.values(): sp.set_visible(False)
ax.set_title("Structure closes a fifth of the gap. Knowing the hospital closes the rest.",
             loc="left", fontsize=12, fontweight="bold")
fig.text(0.01, 0.01, "Grey = baseline, blue = model. ρ = Spearman rank correlation with actual 2024 OP-18b.",
         fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig("reports/figures/10_model_comparison.png", dpi=180)
print("ok")
