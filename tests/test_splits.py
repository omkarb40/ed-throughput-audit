"""S8 split integrity tests. Run: PYTHONPATH=src python3 -m pytest tests -q"""
import numpy as np
import pandas as pd
import pytest
from splits import (TEST_YEAR, TRAIN_MAX_YEAR, VAL_YEAR, grouped_temporal_split,
                    hospital_group, temporal_split)
from features import add_lag_features


@pytest.fixture(scope="module")
def df():
    t = pd.read_parquet("data/interim/analysis_table.parquet")
    return t[t.op18b.notna()].reset_index(drop=True)


def test_temporal_split_is_forward_only(df):
    s = temporal_split(df)
    assert s["train"].year.max() <= TRAIN_MAX_YEAR < VAL_YEAR
    assert set(s["val"].year) == {VAL_YEAR} and set(s["test"].year) == {TEST_YEAR}


def test_grouped_split_has_disjoint_hospitals(df):
    s = grouped_temporal_split(df)
    tr, va, te = (set(s[k].ccn) for k in ("train", "val", "test"))
    assert not (tr & te), "hospital in both train and test"
    assert not (tr & va) and not (va & te)


def test_grouped_split_is_forward_only(df):
    s = grouped_temporal_split(df)
    assert s["train"].year.max() < s["val"].year.min() <= s["val"].year.max() < s["test"].year.min()


def test_hospital_assignment_is_stable_and_order_free(df):
    a = df.ccn.map(hospital_group)
    b = df.sample(frac=1, random_state=7).ccn.map(hospital_group).reindex(df.index)
    assert (a == b).all()
    assert hospital_group("220071") == hospital_group("220071")


def test_group_proportions_are_reasonable(df):
    share = df.drop_duplicates("ccn").ccn.map(hospital_group).value_counts(normalize=True)
    assert 0.15 < share["test"] < 0.25 and 0.15 < share["val"] < 0.25


def test_lag_features_never_use_target_or_future_year(df):
    f = add_lag_features(df)
    has = f[f.prev_op18b.notna()]
    assert (has.prev_op18b_gap_years >= 1).all()
    # brute-force check on a sample: prior mean equals mean of strictly earlier years
    for ccn in has.ccn.drop_duplicates().sample(200, random_state=0):
        g = f[f.ccn == ccn].sort_values("year")
        for _, r in g.iterrows():
            prior = g[(g.year < r.year)].op18b.dropna()
            if prior.empty:
                assert np.isnan(r.prior_mean_log_op18b)
            else:
                assert np.isclose(r.prior_mean_log_op18b, np.log(prior).mean())
                assert r.prev_op18b == prior.iloc[-1]


def test_lag_feature_ignores_suppressed_years():
    toy = pd.DataFrame({"ccn": ["X"] * 4, "year": [2018, 2019, 2021, 2022],
                        "op18b": [100.0, np.nan, 120.0, 130.0]})
    f = add_lag_features(toy).set_index("year")
    assert f.loc[2021, "prev_op18b"] == 100.0 and f.loc[2021, "prev_op18b_gap_years"] == 3
    assert f.loc[2022, "prev_op18b"] == 120.0 and f.loc[2018, "n_prior_op18b"] == 0
