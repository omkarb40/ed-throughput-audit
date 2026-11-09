"""Headless app tests: the app renders without errors for every kind of hospital and every state."""
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

APP = "../app/streamlit_app.py"  # resolved relative to this test file
h = pd.read_parquet("app/data/hospitals.parquet")


def run(state, ccn):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.selectbox[0].set_value(state).run()
    at.selectbox[1].set_value(ccn).run()
    return at


@pytest.mark.parametrize("kind", ["published", "footnoted", "older published", "profile estimate"])
def test_each_kind_renders(kind):
    if kind == "footnoted":
        r = h[h.footnoted].iloc[0]
    else:
        r = h[(h.source == kind) & ~h.footnoted].iloc[0]
    at = run(r.state, r.ccn)
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown) + " ".join(str(m.value) for m in at.metric)
    if kind in ("profile estimate", "older published"):
        assert any("publishes no number" in i.value for i in at.info)
        assert any("open before relying" in w.value for w in at.warning), "closure warning missing"
    if kind == "footnoted":
        assert any("footnote" in w.value for w in at.warning), "footnote warning missing"
    assert any("call 911" in w.value for w in at.warning), "emergency warning missing"


def test_every_state_first_hospital():
    at = AppTest.from_file(APP, default_timeout=60).run()
    for st_ in sorted(h.state.unique()):
        at.selectbox[0].set_value(st_).run()
        assert not at.exception, (st_, at.exception)
