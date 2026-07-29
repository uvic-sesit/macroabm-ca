"""Reader for the processed CIMS linkage matrices.

Reads the per-region, per-year ``requested_quantities_*`` and ``investment_*``
CSV files written by :class:`CIMSResultsExtractor
<macro_data.processing.macroabm_cims_data_processing.CIMSResultsExtractor>`
and returns them as labelled DataFrames.  This is the only place the macroABM
side reads processed CIMS data from disk; ``firms.link()`` itself does no I/O.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class CIMSDataReader:
    """Reads processed CIMS linkage CSVs from a directory.

    Args:
        cims_data_path: Directory containing the processed
            ``requested_quantities_{itr}_{year}_{region}.csv`` and
            ``investment_{itr}_{year}_{region}.csv`` files.
    """

    def __init__(self, cims_data_path: str | Path) -> None:
        self.cims_data_path = Path(cims_data_path)

    def get_requested_quantities(self, itr: str, year: int, region: str) -> pd.DataFrame:
        """Return the processed requested-quantities matrix (rows=producing, cols=good)."""
        return self._read_matrix("requested_quantities", itr, year, region)

    def get_investment(self, itr: str, year: int, region: str) -> pd.DataFrame:
        """Return the processed investment matrix (rows=producing, cols=good)."""
        return self._read_matrix("investment", itr, year, region)

    def get_energy_intensity(self, itr: str, year: int, region: str) -> pd.DataFrame:
        """Return the processed energy-intensity matrix (energy per unit output).

        Rows are producing industries, columns are input goods.  Used by the
        intensity-target linkage method.
        """
        return self._read_matrix("energy_intensity", itr, year, region)

    def get_capital_intensity(self, itr: str, year: int, region: str) -> pd.DataFrame:
        """Return the processed capital-intensity matrix (investment per unit output)."""
        return self._read_matrix("capital_intensity", itr, year, region)

    def available(self, itr: str, year: int, region: str) -> bool:
        """True if both processed matrices exist for this iteration/year/region."""
        return self._path("requested_quantities", itr, year, region).exists() and self._path(
            "investment", itr, year, region
        ).exists()

    def intensity_available(self, itr: str, year: int, region: str) -> bool:
        """True if the processed energy-intensity matrix exists for this iteration/year/region."""
        return self._path("energy_intensity", itr, year, region).exists()

    def _path(self, param: str, itr: str, year: int, region: str) -> Path:
        return self.cims_data_path / f"{param}_{itr}_{year}_{region}.csv"

    def _read_matrix(self, param: str, itr: str, year: int, region: str) -> pd.DataFrame:
        return pd.read_csv(self._path(param, itr, year, region), index_col=0)
