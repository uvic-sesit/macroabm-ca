"""
Optional province-level investment-fraction override reader.

Supplies the province-specific split of gross fixed capital formation (GFCF) across the
Firm / Household / Government institutional sectors. Without this override, the model takes
these fractions from Eurostat and — because Canada is absent from that series — falls back
to **France** for every province (`get_investment_fractions_of_country`), so all ten
provinces receive the same French split. This reader replaces that with StatsCan provincial
data.

Backward compatible: if the data file is missing, or a region has no row, the caller keeps
the existing Eurostat/proxy behaviour. See ``docs/canada/provincial_raw_data.md``.

Data file
---------
``<raw_data>/canadian_inputs/provincial_investment_fractions.csv`` (in the raw_data bundle,
not the model repo) with columns: ``region, year, firm, household, government`` (fractions
sum to 1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


class ProvincialInvestmentReader:
    """Reader providing optional per-province GFCF institutional-split overrides."""

    def __init__(self, table: Optional[pd.DataFrame] = None):
        self._by_region: dict[str, pd.DataFrame] = {}
        if table is not None and not table.empty:
            for region, sub in table.groupby("region"):
                self._by_region[str(region)] = sub.set_index("year").sort_index()

    @property
    def available(self) -> bool:
        return len(self._by_region) > 0

    FILENAME = "provincial_investment_fractions.csv"

    @classmethod
    def default_path(cls, raw_data_path: Path | str) -> Path:
        """``<raw_data>/canadian_inputs/provincial_investment_fractions.csv``."""
        return Path(raw_data_path) / "canadian_inputs" / cls.FILENAME

    @classmethod
    def from_default(
        cls, raw_data_path: Optional[Path | str] = None, path: Optional[Path | str] = None
    ) -> "ProvincialInvestmentReader":
        """Load the fractions, or a no-op reader if the file is absent.

        Pass ``raw_data_path`` (the raw_data bundle root) to resolve the default location, or
        an explicit ``path``. With neither (or if the file is missing), returns a no-op reader.
        """
        if path is None and raw_data_path is not None:
            path = cls.default_path(raw_data_path)
        if path is None:
            return cls(None)
        path = Path(path)
        if not path.exists():
            return cls(None)
        return cls(pd.read_csv(path))

    def has_region(self, region) -> bool:
        return str(region) in self._by_region

    def get_fractions(self, region, year: int) -> Optional[dict[str, float]]:
        """Return {"Firm","Household","Government"} for the region, or None.

        Uses the exact year if present, otherwise the nearest available year (the split is
        only weakly time-varying and the model consumes the base-year value).
        """
        key = str(region)
        if key not in self._by_region:
            return None
        sub = self._by_region[key]
        if year in sub.index:
            row = sub.loc[year]
        else:  # clamp to the nearest available year
            years = np.asarray(sub.index, dtype=float)
            row = sub.iloc[int(np.abs(years - year).argmin())]
        return {"Firm": float(row["firm"]), "Household": float(row["household"]), "Government": float(row["government"])}
