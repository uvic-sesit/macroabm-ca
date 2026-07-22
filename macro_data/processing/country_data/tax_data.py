"""Module for handling tax-related data across different countries.

This module provides a structured way to collect and manage various tax rates and related
financial metrics for different countries. It integrates data from multiple sources including
World Bank, OECD, and Eurostat to provide a comprehensive view of a country's tax structure.
"""

from dataclasses import dataclass

from macro_data.configuration.countries import Country
from macro_data.readers import DataReaders

_PROVINCIAL_TAX = None


def _provincial_tax():
    """Lazily load the optional province-level effective-tax-rate override (cached)."""
    global _PROVINCIAL_TAX
    if _PROVINCIAL_TAX is None:
        from macro_data.readers.economic_data.provincial_tax_reader import (
            ProvincialTaxReader,
        )

        _PROVINCIAL_TAX = ProvincialTaxReader.from_default()
    return _PROVINCIAL_TAX


@dataclass
class TaxData:
    """Container for various tax rates and financial metrics for a specific country.

    This class aggregates different types of tax rates and financial metrics that are
    relevant for economic modeling and analysis. It provides both direct tax rates
    (like income and profit taxes) and indirect tax rates (like VAT), as well as
    social insurance contributions and risk premiums.

    Attributes:
        value_added_tax (float): Value Added Tax (VAT) rate.
        export_tax (float): Tax rate applied to exports.
        employer_social_insurance_tax (float): Social insurance tax rate paid by employers.
        employee_social_insurance_tax (float): Social insurance tax rate paid by employees.
        profit_tax (float): Corporate profit tax rate.
        income_tax (float): Personal income tax rate.
        capital_formation_tax (float): Tax rate on capital formation.
        risk_premium (float): Risk premium rate for firms.
    """

    value_added_tax: float
    export_tax: float
    employer_social_insurance_tax: float
    employee_social_insurance_tax: float
    profit_tax: float
    income_tax: float
    capital_formation_tax: float
    risk_premium: float

    @classmethod
    def from_readers(cls, readers: DataReaders, country: Country, year: int):
        """Create a TaxData instance by fetching data from various data readers.

        Args:
            readers (DataReaders): Collection of data readers for accessing different data sources.
            country (Country): Country for which to fetch tax data.
            year (int): Year for which to fetch tax data.

        Returns:
            TaxData: Instance containing tax rates and financial metrics for the specified
                    country and year.

        Note:
            Province-level effective corporate income, personal income, and consumption
            (sales / VAT) tax rates (StatsCan) override the national statutory/proxy rates where
            a provincial data file is present. The override is a no-op for national runs and
            non-Canadian countries, so those paths are unchanged. The sales-tax override targets
            ``value_added_tax`` because the model applies that rate as a flat wedge on final
            household consumption (no staged VAT / input credits), which is mechanically a
            retail sales tax. See ``ProvincialTaxReader`` and ``docs/provincial_raw_data.md``.
        """
        value_added_tax = readers.world_bank.get_tau_vat(country, year)
        profit_tax = readers.oecd_econ.read_tau_firm(country, year)
        income_tax = readers.oecd_econ.read_tau_income(country, year)

        provincial = _provincial_tax()
        if provincial.has_region(country):
            corporate_override = provincial.get_corporate_rate(country, year)
            if corporate_override is not None:
                profit_tax = corporate_override
            income_override = provincial.get_personal_income_rate(country, year)
            if income_override is not None:
                income_tax = income_override
            sales_override = provincial.get_sales_tax_rate(country, year)
            if sales_override is not None:
                value_added_tax = sales_override

        return cls(
            value_added_tax=value_added_tax,
            export_tax=readers.get_export_taxes(country, year),
            employer_social_insurance_tax=readers.oecd_econ.read_tau_sif(country, year),
            employee_social_insurance_tax=readers.oecd_econ.read_tau_siw(country, year),
            profit_tax=profit_tax,
            income_tax=income_tax,
            risk_premium=readers.eurostat.firm_risk_premium(country, year),
            capital_formation_tax=readers.eurostat.taxrate_on_capital_formation(country, year),
        )
