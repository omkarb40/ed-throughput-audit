"""S8: leakage-proof splits for the OP_18b calendar-year panel.

Two regimes, both strictly forward in time:

  temporal_split(df)          forecasting (persistence baseline, Model B)
      train: years <= 2022 · validate: 2023 · test: 2024
      The same hospital appears across time on purpose — its past is the input.

  grouped_temporal_split(df)  structural prediction (Model A)
      Hospitals are split into disjoint groups by a stable hash of the CCN (~20% test, ~20% validate).
      Train = train hospitals, years <= 2022. Validate = validation hospitals, 2023. Test = test hospitals, 2024.
      No hospital appears in more than one partition, and no partition sees a later year than the one after it.

Only calendar-year windows are used anywhere, so no two rows share months of data.
"""
import hashlib
import pandas as pd

TRAIN_MAX_YEAR, VAL_YEAR, TEST_YEAR = 2022, 2023, 2024


def hospital_bucket(ccn: str, n: int = 10) -> int:
    """Stable 0..n-1 bucket from the CCN alone: independent of row order, random seeds, and new data."""
    return int(hashlib.md5(ccn.encode()).hexdigest(), 16) % n


def hospital_group(ccn: str) -> str:
    b = hospital_bucket(ccn)
    return "test" if b < 2 else "val" if b < 4 else "train"


def temporal_split(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"train": df[df.year <= TRAIN_MAX_YEAR],
            "val": df[df.year == VAL_YEAR],
            "test": df[df.year == TEST_YEAR]}


def grouped_temporal_split(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    g = df.ccn.map(hospital_group)
    return {"train": df[(g == "train") & (df.year <= TRAIN_MAX_YEAR)],
            "val": df[(g == "val") & (df.year == VAL_YEAR)],
            "test": df[(g == "test") & (df.year == TEST_YEAR)]}
