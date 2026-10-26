"""S5 figures: (1) OP_18b reporting status by hospital type and ED volume; (2) observed OP_18b, balanced vs gaps."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

d = pd.read_parquet("data/interim/op18b_status.parquet")
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
COL = {"clean": "#2a78d6", "flagged": "#1baf7a", "suppressed": "#eb6834"}
LBL = {"clean": "Reported", "flagged": "Reported, footnoted", "suppressed": "Suppressed"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK})

def stacked(ax, col, order, labels, title):
    t = pd.crosstab(d[col], d.status, normalize="index").mul(100).reindex(order)
    n = d[col].value_counts().reindex(order)
    left = pd.Series(0.0, index=order)
    for s in ["clean", "flagged", "suppressed"]:
        ax.barh(range(len(order)), t[s], left=left, color=COL[s], height=0.62,
                edgecolor=SURF, linewidth=2, label=LBL[s])
        for i, (v, l) in enumerate(zip(t[s], left)):
            if v >= 6:
                ax.text(l + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontsize=9,
                        color="white" if s != "flagged" else INK)
        left += t[s]
    ax.set_yticks(range(len(order)), [f"{lab}  (n={n[o]:,})" for o, lab in zip(order, labels)])
    ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_xlabel("% of hospital-years"); ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for sp in ax.spines.values(): sp.set_visible(False)

fig, axes = plt.subplots(2, 1, figsize=(9, 6.2), facecolor=SURF, gridspec_kw={"height_ratios": [3, 5]})
for ax in axes: ax.set_facecolor(SURF)
stacked(axes[0], "type", ["Acute Care Hospitals", "Critical Access Hospitals", "Childrens"],
        ["Acute care", "Critical access", "Children's"], "By hospital type")
stacked(axes[1], "edv_cat", ["4 very high", "3 high", "2 medium", "1 low", "missing"],
        ["Very high volume", "High volume", "Medium volume", "Low volume", "Volume not reported"],
        "By ED volume category (same year)")
axes[0].legend(ncol=3, loc="lower left", bbox_to_anchor=(-0.02, 1.13), frameon=False, fontsize=9)
fig.suptitle("Who has a published ED wait time? OP_18b reporting status, 2018–2024 calendar years",
             x=0.02, ha="left", fontsize=12, fontweight="bold", y=0.998)
fig.text(0.02, 0.005, "Source: CMS Timely & Effective Care archives, 28,238 hospital-years. Rural emergency hospitals (n=38) omitted: 100% suppressed.",
         fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.02, 1, 0.985)); fig.savefig("reports/figures/05_reporting_status.png", dpi=180)

obs = d[(d.status != "suppressed") & d.type.isin(["Acute Care Hospitals", "Critical Access Hospitals"])]
yrs = d[d.status != "suppressed"].groupby("ccn").year.nunique()
obs = obs.assign(group=obs.ccn.map(yrs).eq(6).map({True: "All 6 years reported", False: "Gaps in reporting"}))
m = obs.groupby(["type", "group"]).agg(med=("score", "median"), h=("ccn", "nunique")).reset_index()
fig, ax = plt.subplots(figsize=(8, 3.8), facecolor=SURF); ax.set_facecolor(SURF)
types = ["Acute Care Hospitals", "Critical Access Hospitals"]; w = 0.36
for j, (g, c) in enumerate([("All 6 years reported", "#2a78d6"), ("Gaps in reporting", "#eb6834")]):
    sub = m[m.group == g].set_index("type").reindex(types)
    xs = [i + (j - 0.5) * w for i in range(2)]
    ax.bar(xs, sub.med, width=w - 0.02, color=c, label=g, edgecolor=SURF, linewidth=2)
    for x, v, h in zip(xs, sub.med, sub.h):
        ax.text(x, v + 3, f"{v:.0f} min", ha="center", fontsize=10, color=INK)
        ax.text(x, 6, f"{h:,} hosp.", ha="center", fontsize=8, color="white")
ax.set_xticks(range(2), ["Acute care", "Critical access"]); ax.set_ylabel("Median OP_18b (minutes)")
ax.set_ylim(0, 190); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for sp in ax.spines.values(): sp.set_visible(False)
ax.legend(frameon=False, loc="upper right", fontsize=9)
ax.set_title("Dropping hospitals with gaps would remove the faster acute-care EDs",
             loc="left", fontsize=12, fontweight="bold")
fig.text(0.01, 0.01, "Median of reported (non-suppressed) hospital-year scores, CY2018–2024. Hospital counts inside bars.",
         fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig("reports/figures/05_balanced_vs_gaps.png", dpi=180)
print("ok")
