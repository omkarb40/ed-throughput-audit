"""S7 figures: OP_18b distribution by type (log axis); agreement decay with window gap."""
import json
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
C1, C2 = "#2a78d6", "#eb6834"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
def clean(ax):
    ax.set_facecolor(SURF); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for sp in ax.spines.values(): sp.set_visible(False)

t = pd.read_parquet("data/interim/analysis_table.parquet"); y = t[t.op18b.notna()]
fig, ax = plt.subplots(figsize=(9, 4), facecolor=SURF); clean(ax)
bins = np.logspace(np.log10(35), np.log10(1400), 70)
for typ, c, lab in [("Acute Care Hospitals", C1, "Acute care"), ("Critical Access Hospitals", C2, "Critical access")]:
    s = y[y.type == typ].op18b
    ax.hist(s, bins=bins, histtype="step", lw=2, color=c)
    med = s.median(); ax.axvline(med, color=c, lw=1, ls=(0, (3, 3)))
    acute = typ.startswith("Acute")
    ax.text(med * (1.13 if acute else 0.97), 1330, f"{lab}\nmedian {med:.0f} min · n={len(s):,}",
            color=INK, fontsize=9, ha="left" if acute else "right", va="top")
ax.set_xscale("log"); ax.set_xticks([50, 100, 200, 400, 800, 1300], ["50", "100", "200", "400", "800", "1,300"])
ax.set_xlabel("OP_18b, median minutes in ED before leaving (log scale)"); ax.set_ylabel("Hospital-years")
ax.set_title("ED time is right-skewed in minutes and close to symmetric on a log scale", loc="left", fontsize=12, fontweight="bold")
fig.text(0.01, 0.01, "Calendar years 2018, 2019, 2021–2024. Skew: acute 1.78 → −0.02 after log; critical access 1.12 → −0.10.", fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig("reports/figures/07_distribution.png", dpi=180)

ov = pd.DataFrame(json.load(open("reports/07_target_eda.json"))["overlap"])
ov = ov[ov.pairs >= 3]
fig, ax = plt.subplots(figsize=(9, 4), facecolor=SURF); clean(ax)
ax.axvspan(0, 11.5, color="#eeeeec", zorder=0)
ax.text(1, 0.858, "windows share months", fontsize=9, color=INK2)
ax.plot(ov.gap_months, ov.r_log, color=C1, lw=2, marker="o", ms=8, markeredgecolor=SURF, markeredgewidth=2)
for _, r in ov.iterrows():
    ax.text(r.gap_months, r.r_log + 0.006, f"r={r.r_log:.2f}\n{r.median_abs_diff_min:.0f} min", ha="center", fontsize=8.5, color=INK)
ax.set_xticks(ov.gap_months, [f"{int(g)}" for g in ov.gap_months]); ax.set_ylim(0.85, 1.01)
ax.set_xlabel("Months between the end of two 12-month windows"); ax.set_ylabel("Correlation of log OP_18b")
ax.set_title("Overlapping windows almost copy each other; even 3 years apart r ≈ 0.86", loc="left", fontsize=12, fontweight="bold")
fig.text(0.01, 0.01, "Median across window pairs. Labels: correlation and median absolute difference between the two windows' scores. Gaps with ≥3 pairs shown.", fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig("reports/figures/07_window_agreement.png", dpi=180)
print("ok")
