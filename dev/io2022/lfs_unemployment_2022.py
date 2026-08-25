"""Calibrate the built wrapper's t0 unemployment to LFS 2022, per province.

The synthetic population lands at 7-13% t0 unemployment against LFS 2022 actuals of
4-11%: the build's base-year target lookup picks a stale series value (see the
diagnosis note in the io2022 port doc), and firm-matching pushes some provinces
further above target.  This post-build step reclassifies a seeded random surplus of
UNEMPLOYED individuals to NOT ECONOMICALLY ACTIVE until each province's rate
u = U / (E + U) matches its LFS 2022 annual mean.  Employment, firm matching, output
and wealth are untouched -- only the U pool shrinks, so the participation rate falls
below observed by construction (you cannot match both while employment is pinned by
the IO job count; disclosed trade-off of the "option 2" calibration).

Targets are computed from the same StatCan LFS series the build already ships
(raw_data canadian_inputs/provincial_macro_series.csv, unemployment_rate, mean of the
four 2022 quarters) -- no hand-entered numbers.

KNOWN INCONSISTENCIES LEFT IN PLACE (initialization constants baked before this step,
second-order): social_housing_rent and per-capita unemployment benefits were computed
from the pre-calibration unemployed count.

Scenario note: initial labour-market slack changes the MECHANISM of the NZ-vs-CM
comparison (see the slack-sensitivity record), so runs on an LFS-calibrated pickle are
a different experiment from the uncalibrated ones, not a cleaner version of the same.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_ACTIVE_EMPLOYED = 1
_ACTIVE_UNEMPLOYED = 2
_NOT_ACTIVE = 3


def lfs_2022_targets(raw_data_path: Path) -> dict[str, float]:
    """Per-province LFS 2022 annual-mean unemployment rates from the shipped series."""
    csv = Path(raw_data_path) / "canadian_inputs" / "provincial_macro_series.csv"
    df = pd.read_csv(csv, parse_dates=["date"])
    df = df[(df["date"] >= "2022-01-01") & (df["date"] < "2023-01-01")]
    out = df.groupby("region")["unemployment_rate"].mean().to_dict()
    if not out:
        raise ValueError(f"no 2022 rows in {csv}")
    return out


def apply_lfs_unemployment(data_wrapper, raw_data_path: Path, seed: int = 0) -> None:
    """Reclassify surplus unemployed to inactive so t0 rates match LFS 2022."""
    targets = lfs_2022_targets(raw_data_path)
    rng = np.random.default_rng(seed)
    for province, sc in data_wrapper.synthetic_countries.items():
        if str(province) == "ROW" or str(province) not in targets:
            continue
        target = float(targets[str(province)])
        ind = sc.population.individual_data
        status = ind["Activity Status"].values
        n_employed = int((status == _ACTIVE_EMPLOYED).sum())
        unemployed_idx = np.flatnonzero(status == _ACTIVE_UNEMPLOYED)
        n_unemployed = len(unemployed_idx)
        current = n_unemployed / max(1, n_employed + n_unemployed)
        # target U* solves U*/(E + U*) = target with E fixed.
        target_u = int(round(target / (1.0 - target) * n_employed))
        surplus = n_unemployed - target_u
        if surplus <= 0:
            logger.info(
                "[%s] t0 unemployment %.1f%% already at/below LFS 2022 %.1f%%; unchanged.",
                province, 100 * current, 100 * target,
            )
            continue
        move = rng.choice(unemployed_idx, size=surplus, replace=False)
        ind.iloc[move, ind.columns.get_loc("Activity Status")] = _NOT_ACTIVE
        new_rate = target_u / max(1, n_employed + target_u)
        logger.info(
            "[%s] t0 unemployment %.1f%% -> %.1f%% (LFS 2022 %.1f%%): %d of %d unemployed "
            "reclassified to not-active (employment unchanged at %d).",
            province, 100 * current, 100 * new_rate, 100 * target,
            surplus, n_unemployed, n_employed,
        )
