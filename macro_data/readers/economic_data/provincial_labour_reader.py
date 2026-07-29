"""
Optional labour-compensation calibration reader for the Canadian provincial model.

Firms' initial wage bills come from ``industry_vectors["Labour Compensation in LCU"]``, which
is built from the WIOD Socio-Economic Accounts (``raw_data/wiod_sea/wiod_sea.csv``). For
Canada that source is effectively empty -- of 56 industry rows for 2014, exactly **one** is
non-zero ("Fishing and aquaculture") -- so the vector is filled via the
``proxy_country_dict={"CAN": "FRA"}`` proxy from French data that is itself only 4-of-56
populated.

Value added, by contrast, comes from the Canadian provincial IO table and is accurate: the
model's total (~$1.733T annualised) matches StatCan 2014 value added ($1.730T) to 0.17%.
The mismatch therefore lands entirely on the labour side, giving an initial labour share of
**84.4%** against Canada's actual **49.8%** -- firms are loss-making from the first
simulated year, before any scenario mechanism acts, and the model has no margin to absorb
any shock.

This reader supplies the observed Canadian labour share so the wage vector can be rescaled
onto it, preserving the existing within-province industry distribution.

Backward compatible: if the source file is missing the caller keeps the existing behaviour,
so national and non-Canadian runs are unaffected.

Data file
---------
``<raw_data>/3610000101_customizedLayoutData - <year> - processed.csv`` -- the StatCan
supply-use extract that the provincial IO table itself was built from, so numerator and
denominator come from one source and the resulting share is consistent by construction.
Value-added component rows used (column ``Total use``, $ thousands):

===========================  ==============
Wages and salaries              861,052,898
Gross mixed income              227,170,359
Gross operating surplus         557,797,503
Taxes on production              89,918,751
Subsidies on production          -5,597,127
**= Value added**             1,730,342,384
===========================  ==============

giving ``861,052,898 / 1,730,342,384 = 49.8%``. See ``docs/provincial_raw_data.md``
(labour-compensation section) for the full provenance and assumptions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Value-added component rows in the StatCan extract (index labels, column "Total use").
_WAGES_ROW = "Wages and salaries"
_VA_ROWS = (
    "Wages and salaries",
    "Gross mixed income",
    "Gross operating surplus",
    "Taxes on production",
    "Subsidies on production",  # already negative in the source
)
_TOTAL_COLUMN = "Total use"

# Sanity band. Canada's compensation share of GDP has sat in the high-40s/low-50s for
# decades; anything outside this indicates the wrong file, column or units, in which case
# the override is refused rather than silently applied.
_MIN_PLAUSIBLE_SHARE = 0.35
_MAX_PLAUSIBLE_SHARE = 0.70


class ProvincialLabourReader:
    """Observed Canadian labour share, used to calibrate initial firm wage bills."""

    FILENAME_GLOB = "3610000101_customizedLayoutData*processed.csv"

    def __init__(self, labour_share: Optional[float] = None) -> None:
        self._labour_share = labour_share

    @property
    def available(self) -> bool:
        return self._labour_share is not None

    @property
    def labour_share(self) -> Optional[float]:
        """Wages and salaries as a fraction of value added, or ``None`` if unavailable."""
        return self._labour_share

    @classmethod
    def default_path(cls, raw_data_path: Path | str) -> Optional[Path]:
        """Newest matching StatCan supply-use extract at the raw_data root, if any."""
        matches = sorted(Path(raw_data_path).glob(cls.FILENAME_GLOB))
        return matches[-1] if matches else None

    @classmethod
    def from_default(
        cls,
        raw_data_path: Optional[Path | str] = None,
        path: Optional[Path | str] = None,
    ) -> "ProvincialLabourReader":
        """Build from the StatCan extract; a no-op reader when it is absent or unusable."""
        source = Path(path) if path is not None else (
            cls.default_path(raw_data_path) if raw_data_path is not None else None
        )
        if source is None or not source.exists():
            logger.info("No StatCan labour-share source found; keeping existing labour compensation.")
            return cls(None)
        try:
            share = cls._read_labour_share(source)
        except Exception as exc:  # noqa: BLE001 - a calibration input must never break the build
            logger.warning("Could not read labour share from %s: %s", source, exc)
            return cls(None)
        if share is None:
            return cls(None)
        logger.info("Observed Canadian labour share from %s: %.1f%%", source.name, share * 100)
        return cls(share)

    @classmethod
    def _read_labour_share(cls, source: Path) -> Optional[float]:
        frame = pd.read_csv(source, index_col=0, low_memory=False)
        if _TOTAL_COLUMN not in frame.columns:
            logger.warning("%s has no %r column; skipping labour-share override.", source.name, _TOTAL_COLUMN)
            return None
        totals = pd.to_numeric(frame[_TOTAL_COLUMN], errors="coerce")
        missing = [row for row in _VA_ROWS if row not in totals.index or pd.isna(totals[row])]
        if missing:
            logger.warning("%s missing value-added rows %s; skipping override.", source.name, missing)
            return None

        wages = float(totals[_WAGES_ROW])
        value_added = float(sum(totals[row] for row in _VA_ROWS))
        if not np.isfinite(wages) or not np.isfinite(value_added) or value_added <= 0:
            return None

        share = wages / value_added
        if not (_MIN_PLAUSIBLE_SHARE <= share <= _MAX_PLAUSIBLE_SHARE):
            logger.warning(
                "Labour share %.3f from %s is outside the plausible band [%.2f, %.2f]; "
                "refusing to apply it (check the file, column or units).",
                share, source.name, _MIN_PLAUSIBLE_SHARE, _MAX_PLAUSIBLE_SHARE,
            )
            return None
        return share

    def rescale(self, labour_compensation: np.ndarray, value_added: np.ndarray) -> np.ndarray:
        """Scale a labour-compensation vector onto the observed labour share.

        A single scalar is applied across the vector, so the industry distribution is
        preserved and only its level changes.  Returns the input unchanged when no share is
        available or the inputs are unusable.

        Args:
            labour_compensation: per-industry labour compensation to rescale.
            value_added: per-industry value added for the same region, same units.

        Returns:
            The rescaled vector (a copy), or the original when no correction applies.
        """
        if self._labour_share is None:
            return labour_compensation
        lc = np.asarray(labour_compensation, dtype=float)
        va = np.asarray(value_added, dtype=float)
        lc_total = float(np.nansum(lc))
        va_total = float(np.nansum(va))
        if lc_total <= 0 or va_total <= 0 or not np.isfinite(lc_total) or not np.isfinite(va_total):
            return labour_compensation
        target_total = self._labour_share * va_total
        return lc * (target_total / lc_total)
