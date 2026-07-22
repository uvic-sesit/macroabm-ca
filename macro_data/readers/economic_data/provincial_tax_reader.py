"""
Optional province-level effective-tax-rate override reader.

Supplies province-specific *effective* corporate income, personal income, and consumption
(sales / VAT) tax rates for the Canadian provincial model. Without this override, all three
rates collapse a :class:`Region` to its ``parent_country`` and every province receives the
same national value: ``read_tau_firm`` returns Canada's single statutory combined corporate
rate, ``read_tau_income`` returns a hard-coded 0.09, and ``get_tau_vat`` returns one national
VAT figure. This reader replaces those with province-specific effective rates derived from the
StatsCan Provincial and Territorial Economic Accounts.

Why effective (not statutory): the model applies a tax rate *flat* (``rate x base``, with no
brackets, deductions, small-business rate or abatement) when it computes government revenue
and firm/household net-of-tax positions, so the scalar it needs is the effective rate.

Backward compatible: if the data file is missing, or a region has no row, the caller keeps
the existing national/proxy behaviour (national and non-Canadian runs are unaffected).

Data file
---------
``<repo_root>/new_raw_data/statcan_provincial/provincial_tax_rates.csv`` with columns:
``region, year, corporate_tax_rate, personal_income_tax_rate, sales_tax_rate`` (decimals). One
row per province x year (2007-2024). See ``docs/provincial_raw_data.md`` (tax section) for the
full provenance and assumptions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


class ProvincialTaxReader:
    """Reader providing optional per-province effective-tax-rate overrides."""

    def __init__(self, table: Optional[pd.DataFrame] = None):
        self._by_region: dict[str, pd.DataFrame] = {}
        if table is not None and not table.empty:
            for region, sub in table.groupby("region"):
                self._by_region[str(region)] = sub.set_index("year").sort_index()

    @property
    def available(self) -> bool:
        return len(self._by_region) > 0

    @classmethod
    def default_path(cls) -> Path:
        return (
            Path(__file__).resolve().parents[3]
            / "new_raw_data"
            / "statcan_provincial"
            / "provincial_tax_rates.csv"
        )

    @classmethod
    def from_default(cls, path: Optional[Path | str] = None) -> "ProvincialTaxReader":
        path = Path(path) if path is not None else cls.default_path()
        if not path.exists():
            return cls(None)
        return cls(pd.read_csv(path))

    def has_region(self, region) -> bool:
        return str(region) in self._by_region

    def _rate(self, region, year: int, column: str) -> Optional[float]:
        key = str(region)
        if key not in self._by_region:
            return None
        sub = self._by_region[key]
        col = sub[column].dropna()
        if col.empty:
            return None
        if year in col.index:
            value = col.loc[year]
        else:  # clamp to the nearest available year
            years = np.asarray(col.index, dtype=float)
            value = col.iloc[int(np.abs(years - year).argmin())]
        return float(value)

    def get_corporate_rate(self, region, year: int) -> Optional[float]:
        """Effective corporate income tax rate for the region/year, or None."""
        return self._rate(region, year, "corporate_tax_rate")

    def get_personal_income_rate(self, region, year: int) -> Optional[float]:
        """Effective personal income tax rate for the region/year, or None."""
        return self._rate(region, year, "personal_income_tax_rate")

    def get_sales_tax_rate(self, region, year: int) -> Optional[float]:
        """Effective consumption (sales / VAT) tax rate for the region/year, or None.

        The model applies ``value_added_tax`` as a flat wedge on final household consumption
        (no staged VAT / input credits), so this effective consumption-tax rate is the correct
        input whether the province levies a retail sales tax (PST) or a VAT-type tax (GST/HST/QST).
        """
        return self._rate(region, year, "sales_tax_rate")
