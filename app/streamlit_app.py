"""Nearby ER comparison, built on CMS OP-18b. Reads only the small files in app/data (see src/build_app_data.py)."""
import json
from pathlib import Path
import pandas as pd
import pydeck as pdk
import streamlit as st

DATA = Path(__file__).parent / "data"
st.set_page_config(page_title="Compare nearby ERs", page_icon="🏥", layout="centered")


@st.cache_data
def load():
    h = pd.read_parquet(DATA / "hospitals.parquet")
    nb = pd.read_parquet(DATA / "neighbors.parquet")
    acc = pd.read_csv(DATA / "pick_accuracy.csv")
    meta = json.loads((DATA / "meta.json").read_text())
    return h, nb, acc, meta


h, nb, acc, meta = load()
H = h.set_index("ccn")
WIN = f"{pd.Timestamp(meta['window_start']):%b %Y} to {pd.Timestamp(meta['window_end']):%b %Y}"


def fmt_range(r, lvl=90):
    return f"{r[f'lo{lvl}']:.0f}–{r[f'hi{lvl}']:.0f} min"


def pick_confidence(gap):
    for _, row in acc.iterrows():
        lo, hi = {"under 10 min": (0, 10), "10-20 min": (10, 20), "20-40 min": (20, 40), "over 40 min": (40, 1e9)}[row.bucket]
        if lo < gap <= hi:
            return row.pct_correct, row.bucket, int(row.pairs)
    return None, None, None


st.title("How long do nearby ERs take?")
st.caption(f"Median time patients spent in the emergency department before going home, as published by CMS "
           f"(measure OP-18b) for **{WIN}**. Not a live wait time. [How this was built]({meta['repo']})")
st.warning("This compares hospitals' past performance. It is not a tool for deciding where to seek emergency care. "
           "**In a medical emergency, call 911.**", icon="🚑")

states = sorted(h.state.unique())
c1, c2 = st.columns([1, 3])
state = c1.selectbox("State", states, index=states.index("MA") if "MA" in states else 0)
opts = h[h.state == state].sort_values(["city", "facility_name"])
label = {r.ccn: f"{r.facility_name} · {r.city}" for r in opts.itertuples()}
ccn = c2.selectbox("Emergency department", list(label), format_func=label.get)
r = H.loc[ccn]

st.subheader(r.facility_name)
st.write(f"{r.city}, {r.state} · {r.hospital_type.replace('Hospitals', 'hospital').lower()}")

if r.source == "published":
    a, b = st.columns(2)
    a.metric(f"Published median, {WIN}", f"{r.published:.0f} min")
    b.metric("Likely range for the next 12 months", fmt_range(r), help=(
        "90% range. Built from how much hospitals' numbers moved from 2022 to 2023, and checked on 2024: "
        f"{meta['coverage_90_published_2024']}% of 2024 values fell inside ranges built this way."))
    if r.footnoted:
        st.warning("CMS attached a footnote to this number (often: based on a shorter period than required). "
                   "The range is wider to reflect that.", icon="⚠️")
else:
    if pd.isna(r.last_number_window_end):
        history = f"CMS has not published a number for this ED in any period since {pd.Timestamp(meta['first_window_start']):%Y}."
    else:
        history = (f"The last CMS number was **{r.last_number:.0f} min**, for the 12 months ending "
                   f"{pd.Timestamp(r.last_number_window_end):%b %Y}.")
    if r.source == "older published":
        st.info(f"**CMS publishes no number for this ED** for {WIN}. {history} That older number is shown below, "
                "with a wider range because it is out of date.", icon="ℹ️")
    else:
        st.info(f"**CMS publishes no number for this ED** for {WIN}. {history} Below is an estimate from public facts "
                "about the hospital (type, size, location, county). It is much less precise than a published number.",
                icon="ℹ️")
    st.warning("A missing number can mean low volume, a hospital not reporting, or an ED that has closed. "
               "**Check that this ED is open before relying on it.**", icon="⚠️")
    a, b = st.columns(2)
    if r.source == "older published":
        a.metric(f"Last published median, to {pd.Timestamp(r.last_number_window_end):%b %Y}", f"{r.point:.0f} min")
        b.metric("Likely range now", fmt_range(r), help=(
            "Built from how much hospitals' numbers moved over 2-3 years. In a back-test on 2024, "
            f"{meta['coverage_90_older_backtest']}% of values fell inside ranges built this way (target 90%)."))
    else:
        a.metric("Estimate from hospital profile", f"{r.point:.0f} min")
        b.metric("Likely range", fmt_range(r), help=(
            f"90% range. Checked on 2024: {meta['coverage_90_profile_2024']}% of values fell inside ranges built this way."))

st.markdown("#### Nearest other emergency departments")
mine = nb[nb.ccn == ccn].sort_values("rank")
rows, notes = [], []
for n in mine.itertuples():
    o = H.loc[n.alt_ccn]
    if o.source == "published" and r.source == "published":
        gap = o.published - r.published
        pct, bucket, pairs = pick_confidence(abs(gap))
        if gap == 0:
            verdict = "Same published time"
        else:
            faster = r.facility_name if gap > 0 else o.facility_name
            verdict = f"{'This ED' if gap > 0 else 'That ED'} ({abs(gap):.0f} min lower)"
            notes.append((o.facility_name, faster, abs(gap), pct, pairs))
    else:
        verdict = "Not comparable"
    rows.append({"Emergency department": f"{o.facility_name} ({o.city})", "Miles": round(n.miles, 1),
                 "Median": f"{o.point:.0f} min" + {"published": "", "older published": " (old)", "profile estimate": " (est.)"}[o.source],
                 "Likely range": fmt_range(o), "Lower published time": verdict})
try:  # width="stretch" exists only in newer Streamlit; older versions use use_container_width
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
except TypeError:
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
if notes:
    st.caption("How often the lower published time was really the faster ED the following year, for nearby ED pairs "
               "with a gap this size (2024): " + "; ".join(f"vs {n}: **{pct:.0f}%**" for n, _, _, pct, _ in notes) + ".")

pts = pd.concat([H.loc[[ccn]].assign(kind="selected"), H.loc[mine.alt_ccn].assign(kind="nearby")]).reset_index()
pts["color"] = pts.kind.map({"selected": [42, 120, 214], "nearby": [235, 104, 52]})
pts["label"] = pts.facility_name + " · " + pts.point.round(0).astype(int).astype(str) + " min"
st.pydeck_chart(pdk.Deck(
    layers=[pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_fill_color="color",
                      get_radius=900, radius_min_pixels=7, pickable=True)],
    initial_view_state=pdk.ViewState(latitude=pts.lat.mean(), longitude=pts.lon.mean(), zoom=9),
    tooltip={"text": "{label}"}, map_style=pdk.map_styles.CARTO_LIGHT))
st.caption("Blue: selected ED. Orange: nearest other EDs. Locations are ZIP-code centres, so they are approximate.")

with st.expander("What this number is, and what it is not"):
    st.markdown(f"""
- **What it is.** CMS measure OP-18b: the median time from arrival to leaving the ED for patients who were sent home,
  excluding psychiatric patients and transfers, over 12 months. It includes treatment time, not just waiting.
- **What it is not.** A live or tonight's wait, or advice on where to go. In a medical emergency, call 911.
- **Why compare it at all.** In 2024, for nearby pairs of EDs, the one with the lower number the year before was the
  faster one **86%** of the time. A guess from public facts about the hospital managed 64%.
- **Ranges.** 90% ranges from split conformal prediction, calibrated on 2023 and checked on 2024.
- **Gaps.** {meta['n_no_current']} of {meta['n_eds']:,} EDs listed by CMS have no published number for this period;
  smaller, rural, for-profit EDs and EDs in poorer counties are more likely to be missing.
- **Closures.** CMS's hospital list ({meta['cms_release']}) can include EDs that have since closed. Check before you go.
- **Source.** CMS Provider Data Catalog, Timely and Effective Care, release {meta['cms_release']}. Analysis and code:
  [{meta['repo'].replace('https://', '')}]({meta['repo']}).
""")
