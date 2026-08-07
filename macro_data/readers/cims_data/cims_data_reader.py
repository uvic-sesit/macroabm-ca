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

    def get_generation_capacity(self, itr: str, year: int, region: str) -> pd.DataFrame:
        """Return the power-sector capacity index (one column, indexed by industry)."""
        return self._read_matrix("generation_capacity", itr, year, region)

    def get_transition_capital(self, itr: str, year: int, region: str) -> pd.DataFrame:
        """Return the fuel-switching capital uplift (capital good x consuming sector)."""
        return self._read_matrix("transition_capital", itr, year, region)

    def get_investment_tax_credit(self, itr: str, year: int, region: str) -> pd.DataFrame:
        """Investment tax credit accruing to each industry, $ per year (linkage-supplied)."""
        return self._read_matrix("investment_tax_credit", itr, year, region)

    def investment_tax_credit_available(self, itr: str, year: int, region: str) -> bool:
        return self._path("investment_tax_credit", itr, year, region).exists()

    def get_export_demand_index(self, itr: str, year: int, region: str) -> pd.DataFrame:
        """Per-industry multiplier on base-year ROW export demand (linkage-supplied)."""
        return self._read_matrix("export_demand_index", itr, year, region)

    def export_demand_index_available(self, itr: str, year: int, region: str) -> bool:
        """True when the linkage wrote an export-demand index for this region/year."""
        return self._path("export_demand_index", itr, year, region).exists()

    def transition_capital_available(self, itr: str, year: int, region: str) -> bool:
        """True if the processed transition-capital table exists."""
        return self._path("transition_capital", itr, year, region).exists()

    def get_electricity_own_use(self, itr: str, year: int, region: str) -> pd.DataFrame:
        """Return the power sector's own-use (transmission loss) rate by industry."""
        return self._read_matrix("electricity_own_use", itr, year, region)

    def own_use_available(self, itr: str, year: int, region: str) -> bool:
        """True if the processed own-use table exists."""
        return self._path("electricity_own_use", itr, year, region).exists()

    def capacity_available(self, itr: str, year: int, region: str) -> bool:
        """True if the processed capacity index exists for this iteration/year/region."""
        return self._path("generation_capacity", itr, year, region).exists()

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
