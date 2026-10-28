"""Shared evaluation for every model in S9+. Inputs are minutes; scoring is done on both scales.

absolute  : errors in minutes, including any nationwide level shift (what a patient would see)
relative  : log errors after removing the median log error across the evaluated rows, i.e. with the
            common level shift taken out; plus Spearman rank correlation (level-invariant)
asymmetry : share of rows under- / over-predicted by more than 15 minutes
CIs       : hospital-level bootstrap, 1,000 resamples, 95% percentile intervals
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

TOL = 15


def point_metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    e = p - y
    le = np.log(p) - np.log(y)
    rel = le - np.median(le)
    return {
        "n": len(y),
        "mae_min": np.mean(np.abs(e)),
        "medae_min": np.median(np.abs(e)),
        "bias_min": np.mean(e),
        "rmse_log": np.sqrt(np.mean(le ** 2)),
        "rel_rmse_log": np.sqrt(np.mean(rel ** 2)),
        "spearman": spearmanr(y, p).statistic if np.ptp(p) > 0 and np.ptp(y) > 0 else np.nan,
        "pct_under_15": 100 * np.mean(e < -TOL),
        "pct_over_15": 100 * np.mean(e > TOL),
    }


def evaluate(df, pred_col, y_col="op18b", n_boot=1000, seed=0):
    d = df[[y_col, pred_col]].dropna()
    pt = point_metrics(d[y_col], d[pred_col])
    rng = np.random.default_rng(seed)
    y, p = d[y_col].to_numpy(), d[pred_col].to_numpy()
    boots = {"mae_min": [], "spearman": [], "rel_rmse_log": []}
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))  # one row per hospital in a single test year -> row = hospital
        m = point_metrics(y[i], p[i])
        for k in boots:
            boots[k].append(m[k])
    for k, v in boots.items():
        pt[f"{k}_lo"], pt[f"{k}_hi"] = np.percentile(v, [2.5, 97.5])
    return pt


def evaluate_by(df, pred_col, by="type", **kw):
    rows = [{"group": "all", **evaluate(df, pred_col, **kw)}]
    for g, sub in df.groupby(by):
        if sub[pred_col].notna().sum() >= 30:
            rows.append({"group": g, **evaluate(sub, pred_col, **kw)})
    return pd.DataFrame(rows)
