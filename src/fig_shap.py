"""S16 figure: mean absolute SHAP per feature for the public-profile model."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK})
s = pd.read_csv("reports/16_shap.csv").head(9)
fig, ax = plt.subplots(figsize=(8.5, 3.9), facecolor=SURF); ax.set_facecolor(SURF)
ax.barh(range(len(s)), s.approx_pct, color="#2a78d6", height=0.6)
for i, v in enumerate(s.approx_pct): ax.text(v + 0.2, i, f"±{v:.1f}%", va="center", fontsize=9)
ax.set_yticks(range(len(s)), s.feature); ax.invert_yaxis(); ax.set_xlim(0, 15)
ax.set_xlabel("Typical effect on predicted ED time (mean |SHAP|, as %)")
ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
for sp in ax.spines.values(): sp.set_visible(False)
ax.set_title("What the public-profile model leans on", loc="left", fontsize=12, fontweight="bold")
fig.text(0.01, 0.01, "Exact TreeSHAP, 2024 hospitals. Describes the fitted model, not causes. Remaining features < 0.5%.",
         fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig("reports/figures/16_shap.png", dpi=180)
print("ok")
