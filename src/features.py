"""Lag features built only from calendar years strictly before the target year."""
import numpy as np
import pandas as pd


def add_lag_features(df: pd.DataFrame, col: str = "op18b") -> pd.DataFrame:
    """For each (ccn, year): the most recent prior calendar-year value of `col`, the gap in years
    to it, the count of prior reported years, and the mean of prior log values.
    Rows with no prior reported year get NaN."""
    d = df.sort_values(["ccn", "year"]).copy()
    obs = d[d[col].notna()][["ccn", "year", col]].copy()
    obs["log"] = np.log(obs[col])
    out = []
    for ccn, g in d.groupby("ccn", sort=False):
        o = obs[obs.ccn == ccn]
        for idx, yr in g.year.items():
            prior = o[o.year < yr]
            if prior.empty:
                out.append((idx, np.nan, np.nan, 0, np.nan))
            else:
                last = prior.iloc[-1]
                out.append((idx, last[col], yr - last.year, len(prior), prior.log.mean()))
    f = pd.DataFrame(out, columns=["idx", f"prev_{col}", f"prev_{col}_gap_years",
                                   f"n_prior_{col}", f"prior_mean_log_{col}"]).set_index("idx")
    return d.join(f)
