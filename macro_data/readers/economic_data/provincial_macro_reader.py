"""
Optional province-level macro override reader.

This reader supplies province-specific macroeconomic time series for the Canadian
provincial model, replacing the national (or proxy) series that the standard readers
return for every province. It exists because the economic readers
(``world_bank``, ``oecd``, ``imf``, ``eurostat`` ...) all collapse a :class:`Region`
to its ``parent_country`` before looking up data, so without an override every
province receives the *same* national CPI / unemployment / house-price / vacancy path.

Design goals
------------
- **Backward compatible.** If the data file is missing, or a region has no provincial
  row, every lookup returns ``None`` and the caller keeps the existing national/proxy
  behaviour. National (non-provincial) runs are completely unaffected.
- **Blend, don't clobber.** :meth:`override` substitutes provincial values only where
  they exist and keeps the national series everywhere else (e.g. pre-1998 history, or
  vacancy before the JVWS starts in 2015).
- **Single tidy source.** All provincial data lives in one processed CSV so it is easy
  to inspect, QA and document, rather than being scattered across the heterogeneous
  raw international files.

Data file
---------
``<repo_root>/new_raw_data/statcan_provincial/provincial_macro_series.csv`` with columns:
``region, date, cpi_inflation, unemployment_rate, hpi_nominal_growth, vacancy_rate``.

- ``region``            model region code (e.g. ``CAN_AB``)
- ``date``              quarter-start ``Timestamp`` (months 1/4/7/10)
- ``cpi_inflation``     quarter-over-quarter change of the quarterly-average all-items CPI (decimal)
- ``unemployment_rate`` quarterly-average unemployment rate (decimal, i.e. percent / 100)
- ``hpi_nominal_growth`` quarter-over-quarter change of the quarterly-average New Housing Price Index (decimal)
- ``vacancy_rate``      quarterly-average job vacancy rate (decimal); NaN before 2015

See ``docs/canada/provincial_raw_data.md`` for the full provenance and processing notes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

# columns of the tidy panel that map onto model series
SERIES_COLUMNS = ("cpi_inflation", "unemployment_rate", "hpi_nominal_growth", "vacancy_rate")


class ProvincialMacroReader:
    """Reader that provides optional per-province macro overrides.

    Attributes:
        available (bool): whether any provincial data was loaded.
    """

    def __init__(self, panel: Optional[pd.DataFrame] = None):
        self._by_region: dict[str, pd.DataFrame] = {}
        if panel is not None and not panel.empty:
            for region, sub in panel.groupby("region"):
                self._by_region[str(region)] = sub.set_index("date").sort_index()

    @property
    def available(self) -> bool:
        return len(self._by_region) > 0

    @classmethod
    def default_path(cls) -> Path:
        """Resolve the default provincial data file relative to the repository root.

        ``.../macro_data/readers/economic_data/provincial_macro_reader.py``
        -> parents[3] is the repository root that also contains ``new_raw_data``.
        """
        return (
            Path(__file__).resolve().parents[3]
            / "new_raw_data"
            / "statcan_provincial"
            / "provincial_macro_series.csv"
        )

    @classmethod
    def from_default(cls, path: Optional[Path | str] = None) -> "ProvincialMacroReader":
        """Load the provincial panel, or an empty (no-op) reader if the file is absent."""
        path = Path(path) if path is not None else cls.default_path()
        if not path.exists():
            return cls(None)
        panel = pd.read_csv(path, parse_dates=["date"])
        return cls(panel)

    def has_region(self, region) -> bool:
        return str(region) in self._by_region

    def get_series(self, region, column: str) -> Optional[pd.Series]:
        """Return the (non-null) provincial series for ``region``/``column`` or ``None``."""
        key = str(region)
        if key not in self._by_region or column not in SERIES_COLUMNS:
            return None
        series = self._by_region[key][column].dropna()
        return series if not series.empty else None

    def override(self, region, column: str, national: pd.Series) -> pd.Series:
        """Blend the provincial series over a national series.

        Provincial values are substituted wherever they exist; the national series is
        retained elsewhere. The returned index is the union of both, so provincial
        dates outside the national coverage (e.g. 2022+) are not dropped.
        """
        provincial = self.get_series(region, column)
        if provincial is None:
            return national
        index = national.index.union(provincial.index)
        combined = national.reindex(index)
        provincial = provincial.reindex(index)
        mask = provincial.notna()
        combined[mask] = provincial[mask]
        return combined
