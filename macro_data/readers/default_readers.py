"""
This module provides centralized data reader management for the macro_data package.
It handles the initialization and coordination of various data readers for different
types of economic data, including ICIO tables, Eurostat data, World Bank indicators,
and more.

The module centers around two main classes:
1. DataPaths: Manages file paths for all data sources
2. DataReaders: Coordinates multiple data readers and provides unified access

Key features:
- Centralized data source management
- Automatic reader initialization
- Data validation and preprocessing
- Exchange rate handling
- Industry aggregation
- Country-specific data processing
"""

import re
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import numpy as np
import pandas as pd

from macro_data.configuration.countries import Country
from macro_data.configuration.region import Region
from macro_data.readers.criticality_data.goods_criticality_reader import (
    GoodsCriticalityReader,
)
from macro_data.readers.economic_data.ecb_reader import ECBReader
from macro_data.readers.economic_data.eurostat_reader import EuroStatReader
from macro_data.readers.economic_data.exchange_rates import ExchangeRatesReader
from macro_data.readers.economic_data.imf_reader import IMFReader
from macro_data.readers.economic_data.oecd_economic_data import OECDEconData
from macro_data.readers.economic_data.ons_reader import ONSReader
from macro_data.readers.economic_data.policy_rates import PolicyRatesReader
from macro_data.readers.policy_data.obps_can_reader import OBPSCANReader
from macro_data.readers.economic_data.provincial_investment_reader import ProvincialInvestmentReader
from macro_data.readers.economic_data.provincial_macro_reader import ProvincialMacroReader
from macro_data.readers.economic_data.provincial_labour_reader import ProvincialLabourReader
from macro_data.readers.economic_data.provincial_tax_reader import ProvincialTaxReader
from macro_data.readers.economic_data.world_bank_reader import WorldBankReader
from macro_data.readers.emission_fraction.emission_fraction_reader import EmissionsFractionReader
from macro_data.readers.emissions.emissions_reader import CH4EmissionsReaderCAN, EmissionsReader
from macro_data.readers.exo_prices.exo_prices_reader import SectorExoPricesReader
from macro_data.readers.icio_sea_matching import (
    add_investment_matrix_to_icio,
    get_investment_fractions,
    match_iot_with_sea,
    reconcile_value_added,
)
from macro_data.readers.io_tables.icio_reader import ICIOReader, split_gfcf_column
from macro_data.readers.io_tables.industries import AGGREGATED_INDUSTRIES
from macro_data.readers.population_data.compustat_banks_reader import (
    CompustatBanksReader,
)
from macro_data.readers.population_data.compustat_firms_reader import (
    CompustatFirmsReader,
)
from macro_data.readers.population_data.hfcs_reader import HFCSReader
from macro_data.readers.socioeconomic_data.wiod_sea_data import WIODSEAReader
from macro_data.readers.util.prune_util import DataFilterWarning


@dataclass
class OBPSPaths:
    """File paths for the Canada Output-Based Pricing System data.

    Attributes:
        rates_path: CSV of carbon price rates by year and jurisdiction.
        policy_path: CSV of per-industry reduction factors and tightening rates.
        policy_elec_path: Optional CSV for electricity-specific tightening rates.
    """

    rates_path: Path
    policy_path: Path
    policy_elec_path: Optional[Path] = None


@dataclass
class DataPaths:
    """Manages file paths for all data sources used in the model.

    This class provides a centralized way to manage and access file paths for
    various data sources, including ICIO tables, Eurostat data, World Bank
    indicators, and more.

    Attributes:
        goods_criticality_path (Path): Path to goods criticality data
        exchange_rates_path (Path): Path to exchange rates data
        eurostat_path (Path): Path to Eurostat data directory
        hfcs_path (Path): Path to Household Finance and Consumption Survey data
        icio_paths (dict[int, Path]): Paths to ICIO tables by year
        icio_pivot_paths (dict[int, Path]): Paths to pivoted ICIO data by year
        wiod_sea_path (Path): Path to WIOD SEA data
        oecd_econ_path (Path): Path to OECD economic data
        oecd_econ_mapping_path (Path): Path to OECD economic data mappings
        policy_rates_path (Path): Path to policy rates data
        country_codes_path (Path): Path to country codes mapping
        imf_path (Path): Path to IMF data
        ons_path (Path): Path to ONS data
        world_bank_path (Path): Path to World Bank data
        ecb_path (Path): Path to ECB data
        compustat_firms_annual_path (Path): Path to annual Compustat firms data
        compustat_firms_quarterly_path (Path): Path to quarterly Compustat firms data
        compustat_banks_path (Path): Path to Compustat banks data
        emissions_path (Path): Path to emissions data
    """

    goods_criticality_path: Path
    exchange_rates_path: Path
    eurostat_path: Path
    hfcs_path: Path
    icio_paths: dict[int, Path]
    icio_pivot_paths: dict[int, Path]
    wiod_sea_path: Path
    oecd_econ_path: Path
    oecd_econ_mapping_path: Path
    policy_rates_path: Path
    country_codes_path: Path
    imf_path: Path
    ons_path: Path
    world_bank_path: Path
    ecb_path: Path
    compustat_firms_annual_path: Path
    compustat_firms_quarterly_path: Path
    compustat_banks_path: Path
    emissions_path: Path
    emissions_fraction_path: Optional[Path] = None
    firm_prices_path: Optional[Path] = None
    ch4_emissions_path: Optional[Path] = None
    obps_path: Optional["OBPSPaths"] = None

    @classmethod
    def default_paths(cls, raw_data_path: Path, icio_years: Iterable[int]):
        """Create default paths for all data sources.

        Args:
            raw_data_path (Path): Base path for raw data
            icio_years (Iterable[int]): Years to include for ICIO data

        Returns:
            DataPaths: Configured paths for all data sources
        """
        return cls(
            goods_criticality_path=raw_data_path / "ihs_markit_goods_criticality" / "UK_2020.csv",
            exchange_rates_path=raw_data_path / "exchange_rates" / "exchange_rates.csv",
            eurostat_path=raw_data_path / "eurostat",
            hfcs_path=raw_data_path / "hfcs",
            icio_paths={year: raw_data_path / "icio" / f"{year}_SML.csv" for year in icio_years},
            icio_pivot_paths={year: raw_data_path / "icio" / f"{year}_SML_P.csv" for year in icio_years},
            wiod_sea_path=raw_data_path / "wiod_sea" / "wiod_sea.csv",
            oecd_econ_path=raw_data_path / "oecd_econ",
            oecd_econ_mapping_path=raw_data_path / "oecd_econ" / "mappings.json",
            policy_rates_path=raw_data_path / "policy_rates" / "bis_cb_policy_rates.csv",
            obps_path=OBPSPaths(
                rates_path=raw_data_path / "policy" / "output_based_price_system_rates.csv",
                policy_path=raw_data_path / "policy" / "output_based_price_system_policy_values_disagg.csv",
                policy_elec_path=raw_data_path / "policy" / "output_based_price_system_policy_values_elec.csv",
            ),
            country_codes_path=raw_data_path / "notation" / "wikipedia-iso-country-codes.csv",
            imf_path=raw_data_path / "imf",
            ons_path=raw_data_path / "ons",
            world_bank_path=raw_data_path / "world_bank",
            ecb_path=raw_data_path / "ecb",
            compustat_firms_annual_path=raw_data_path / "compustat" / "firms_annual.csv",
            compustat_firms_quarterly_path=raw_data_path / "compustat" / "firms_quarterly.csv",
            compustat_banks_path=raw_data_path / "compustat" / "banks.csv",
            emissions_path=raw_data_path / "emissions",
            emissions_fraction_path=raw_data_path / "emission_factors",
            firm_prices_path=raw_data_path / "cims_prices" / "firm_prices.csv",
            ch4_emissions_path=raw_data_path
            / "emission_factors"
            / "EN-GHG_EconSectByGas-CA_Emissions_2014_2023_v4.csv",
        )

    # @classmethod
    # def all_industries(cls, raw_data_path: Path, icio_years: Iterable[int]):
    #     paths = cls.default_paths(raw_data_path, icio_years)
    #     paths.icio_agg_path = raw_data_path / "icio" / "mappings_all_industries.json"
    #     paths.wiod_sea_agg_path = raw_data_path / "wiod_sea" / "mappings_all_industries.json"
    #     return paths


@dataclass
class DataReaders:
    """Centralized management of all data readers for the model.

    This class coordinates multiple data readers and provides unified access to
    various types of economic data. It handles initialization, data validation,
    and preprocessing for all data sources.

    Attributes:
        icio (dict[int, ICIOReader]): ICIO table readers by year
        wiod_sea (WIODSEAReader): WIOD SEA data reader
        oecd_econ (OECDEconData): OECD economic data reader
        world_bank (WorldBankReader): World Bank data reader
        hfcs (dict[str, HFCSReader]): Household Finance and Consumption Survey readers
        eurostat (EuroStatReader): Eurostat data reader
        ons (ONSReader): ONS data reader
        policy_rates (PolicyRatesReader): Policy rates reader
        imf_reader (IMFReader): IMF data reader
        exchange_rates (ExchangeRatesReader): Exchange rates reader
        goods_criticality (GoodsCriticalityReader): Goods criticality reader
        ecb_reader (ECBReader): ECB data reader
        compustat_firms (CompustatFirmsReader): Compustat firms data reader
        compustat_banks (CompustatBanksReader): Compustat banks data reader
        emissions (EmissionsReader): Emissions data reader
        emission_fractions (Optional[EmissionsFractionReader]): Emission fraction data reader
        regions_dict (Optional[dict[Country, list[Region]]]): Regional disaggregation mapping
    """

    icio: dict[int, ICIOReader]
    wiod_sea: WIODSEAReader
    oecd_econ: OECDEconData
    world_bank: WorldBankReader
    hfcs: dict[str, HFCSReader]
    eurostat: EuroStatReader
    ons: ONSReader
    policy_rates: PolicyRatesReader
    imf_reader: IMFReader
    exchange_rates: ExchangeRatesReader
    goods_criticality: GoodsCriticalityReader
    ecb_reader: ECBReader
    compustat_firms: CompustatFirmsReader
    compustat_banks: CompustatBanksReader
    emissions: EmissionsReader
    emission_fractions: Optional[EmissionsFractionReader] = None
    exo_prices: Optional[SectorExoPricesReader] = None
    ch4_emissions: Optional[CH4EmissionsReaderCAN] = None
    obps_can: Optional[OBPSCANReader] = None
    provincial_macro: Optional[ProvincialMacroReader] = None
    provincial_investment: Optional[ProvincialInvestmentReader] = None
    provincial_tax: Optional[ProvincialTaxReader] = None
    provincial_labour: Optional[ProvincialLabourReader] = None
    regions_dict: Optional[dict[Country, list[Region]]] = None

    @classmethod
    def from_raw_data(
        cls,
        raw_data_path: Path | str,
        country_names: list[Country | Region],
        simulation_year: int,
        scale_dict: dict[Country, int],
        industries: list[str],
        aggregate_industries: bool = True,
        imputed_rent_year: int = 2014,
        exog_data_range: Tuple[int, int] = (2010, 2018),
        prune_date: Optional[date] = None,
        force_single_hfcs_survey: bool = False,
        single_icio_survey: bool = False,
        proxy_country_dict: dict[Country, Country] = None,
        use_disagg_can_2014_reader: bool = False,
        use_provincial_can_reader: bool = False,
        regions_dict: dict[Country, list[Region]] = None,
        canadianized_can_households_csv: Optional[Path] = None,
    ):
        if regions_dict:
            all_regions = [region for regions in regions_dict.values() for region in regions]
            country_names = list(set(country_names) - set(all_regions))

        if proxy_country_dict is None:
            proxy_country_dict = {country: country for country in country_names}

        raw_data_path = Path(raw_data_path)
        if single_icio_survey:
            all_years = [simulation_year]
        else:
            all_years = range(exog_data_range[0], exog_data_range[1] + 1)

        datapaths = DataPaths.default_paths(raw_data_path, all_years)

        # The global OECD ICIO ("{year}_SML.csv") is only available in the model in the pre-2021
        # classification (through 2020). For the provincial-CAN build the global table merely
        # scaffolds CAN imputed rent / total output -- the provincial IO table (loaded below)
        # overrides all economics, ROW included -- so when the requested year's SML is missing we
        # fall back to the newest available SML while keeping `year` (exchange rates) intact.
        if use_provincial_can_reader:
            for scaffold_year in list(all_years):
                if datapaths.icio_paths[scaffold_year].exists():
                    continue
                available = sorted(
                    int(m.group(1))
                    for p in (raw_data_path / "icio").glob("*_SML.csv")
                    if (m := re.match(r"(\d{4})_SML\.csv$", p.name))
                )
                candidates = [y for y in available if y <= scaffold_year] or available
                if not candidates:
                    raise FileNotFoundError(
                        f"No global ICIO SML files found under {raw_data_path / 'icio'} to scaffold "
                        f"the provincial {scaffold_year} build."
                    )
                fallback_year = candidates[-1]
                warnings.warn(
                    f"Global ICIO '{scaffold_year}_SML.csv' not found; scaffolding the provincial "
                    f"build off '{fallback_year}_SML.csv' (CAN imputed-rent/total-output scaffold "
                    f"only -- the {scaffold_year} provincial IO table overrides all economics).",
                    DataFilterWarning,
                )
                datapaths.icio_paths[scaffold_year] = raw_data_path / "icio" / f"{fallback_year}_SML.csv"
                datapaths.icio_pivot_paths[scaffold_year] = raw_data_path / "icio" / f"{fallback_year}_SML_P.csv"

        goods_criticality = GoodsCriticalityReader.from_csv(path=datapaths.goods_criticality_path)
        exchange_rates = ExchangeRatesReader.from_csv(path=datapaths.exchange_rates_path)

        eurostat = EuroStatReader(path=datapaths.eurostat_path, country_code_path=datapaths.country_codes_path)

        eu_only = [country for country in country_names if country.is_eu_country]
        proxy_eu = list(proxy_country_dict.values())

        eu_only = list(set(eu_only).union(set(proxy_eu)))

        # Optional province-level GFCF-split override (StatsCan), resolved from the raw_data
        # bundle at <raw_data>/canadian_inputs/. No-op if the file is absent (national/proxy runs).
        provincial_investment = ProvincialInvestmentReader.from_default(raw_data_path=raw_data_path)

        def get_investment_year(year: int, country_names_: Optional[list[Country | Region]] = None):
            if country_names_ is None:
                country_names_ = country_names
            return get_investment_fractions(
                country_names_, eurostat, proxy_country_dict, year, provincial_reader=provincial_investment
            )

        icio = {
            year: ICIOReader.agg_from_csv(
                path=datapaths.icio_paths[year],
                pivot_path=datapaths.icio_pivot_paths[year],
                considered_countries=country_names,
                industries=industries,
                year=year,
                exchange_rates=exchange_rates,
                imputed_rent_fraction=eurostat.get_imputed_rent_fraction(eu_only, imputed_rent_year),
                investment_fractions=get_investment_year(year),
                proxy_country_dict=proxy_country_dict,
                aggregation_type="Aggregate" if aggregate_industries else "All",
            )
            for year in all_years
        }

        total_output = {}
        for country in country_names:
            total_output[country] = icio[simulation_year].get_total_output(country).sum()

        eurostat = EuroStatReader(
            path=datapaths.eurostat_path, country_code_path=datapaths.country_codes_path, total_output=total_output
        )

        proxified = [country if country.is_eu_country else proxy_country_dict[country] for country in country_names]

        # HFCS survey waves are discrete vintages (2010/2014/2017/2021). When the exact
        # simulation-year wave folder is absent, use the nearest available wave <= year (the 2022
        # build uses the HFCS-2021 wave, per the validated-inputs plan).
        hfcs_survey_year = simulation_year
        if not (datapaths.hfcs_path / str(simulation_year)).is_dir():
            available_waves = sorted(
                int(p.name) for p in datapaths.hfcs_path.iterdir() if p.is_dir() and p.name.isdigit()
            )
            eligible = [y for y in available_waves if y <= simulation_year] or available_waves
            if not eligible:
                raise FileNotFoundError(f"No HFCS survey waves found under {datapaths.hfcs_path}.")
            hfcs_survey_year = eligible[-1]
            warnings.warn(
                f"HFCS wave '{simulation_year}' not found; using nearest available wave "
                f"'{hfcs_survey_year}'.",
                DataFilterWarning,
            )

        hfcs = {
            proxy_country: HFCSReader.from_csv(
                country_name=proxy_country,
                country_name_short=proxy_country.to_two_letter_code(),
                hfcs_data_path=datapaths.hfcs_path,
                year=hfcs_survey_year,
                exchange_rates=exchange_rates,
                num_surveys=1 if force_single_hfcs_survey else 5,
            )
            for country_name, proxy_country in zip(country_names, proxified)
        }

        # CAN-2022 Canadianized-household MVP: replace the (French-proxy) household distribution with the
        # validated national Canadian household file, adapted to the model schema. Individuals stay the
        # French skeleton; the reader is flagged cad_native so the EUR->CAD household conversion is skipped
        # (see hfcs_synthetic_population). Explicit + CAN-2022-only; every other build is untouched.
        if canadianized_can_households_csv is not None and Country("CAN") in country_names and simulation_year == 2022:
            from macro_data.readers.population_data.canadianized_household_adapter import (
                build_canadianized_households_df,
            )
            can_proxy = proxy_country_dict.get(Country("CAN"), Country("CAN")) if proxy_country_dict else Country("CAN")
            reader = hfcs[can_proxy]
            # Option 1 (MVP): load the FULL pooled-European individual/member pool so the member skeleton
            # spans the same all-country household ID space as the validated 83,162-household Canadian
            # skeleton -- restores exact household<->individual linkage. Individuals are NOT Canadianized
            # (age/sex/education/composition remain pooled-European HFCS); their employment industry is still
            # reassigned from StatCan 36-10-0489 downstream, and their EUR incomes still convert once.
            all_country = HFCSReader.from_csv(
                country_name=can_proxy,
                country_name_short=can_proxy.to_two_letter_code(),
                hfcs_data_path=datapaths.hfcs_path,
                year=hfcs_survey_year,
                exchange_rates=exchange_rates,
                num_surveys=1 if force_single_hfcs_survey else 5,
                no_country_filter=True,
            )
            reader.individuals_df = all_country.individuals_df
            # carry the linkage + residual columns from the ALL-COUNTRY households frame (same 83,162 IDs)
            reader.households_df = build_canadianized_households_df(
                Path(canadianized_can_households_csv), all_country.households_df
            )
            reader.cad_native = True

        if use_disagg_can_2014_reader:
            # check that only Canada is in the country names
            if country_names != [Country("CAN")]:
                raise ValueError("Only Canada is supported for this reader.")

            if simulation_year != 2014:
                raise ValueError("Only 2014 is supported for this reader.")
            disagg_path = raw_data_path / "icio" / "icio_can_2014_disagg.csv"
            df = pd.read_csv(disagg_path, header=[0, 1], index_col=[0, 1])
            icio[simulation_year].iot = df
            industries = df.loc["ROW"].index.unique()
            if "Household Fixed Capital Formation" not in df["CAN"].columns:
                df = split_gfcf_column(
                    considered_countries=[Country("CAN")],
                    industries=industries,
                    iot=df,
                    investment_fractions=get_investment_year(simulation_year, [Country("CAN")]),
                )
            icio[simulation_year].iot = df
            icio[simulation_year].industries = industries

        if use_provincial_can_reader:
            # check that Canada is in the country names
            if Country("CAN") not in country_names:
                raise ValueError("Canada must be in the country names for this reader.")
            if not regions_dict:
                raise ValueError("Must provide regional disaggregation dictionary.")
            # Provincial IO table by base year: 2014 = legacy 10-province/43-industry custom
            # table; 2022 = OECD-50 / 13-region (incl. YT/NT/NU) compatibility table from the
            # macroabm-io2022 pipeline. Both share the same (region, industry|VA-row) layout.
            provincial_io_files = {
                2014: "icio_2014_can_provinces.csv",
                2022: "icio_2022_can_provinces.csv",
            }
            if simulation_year not in provincial_io_files:
                raise ValueError(
                    f"Provincial Canadian reader supports years {sorted(provincial_io_files)}; "
                    f"got {simulation_year}."
                )
            disagg_path = raw_data_path / "icio" / provincial_io_files[simulation_year]
            df = pd.read_csv(disagg_path, header=[0, 1], index_col=[0, 1])

            df *= 1e6  # Scale to millions

            # The 2022 OECD-50 table carries two final-demand columns the 3-symbol model layout
            # (2014) does not: "Changes in Inventories" and "Direct Purchases Abroad". They are
            # genuine final-demand components (gross capital formation / household final
            # consumption in SNA), so fold them into the model's Fixed Capital Formation and
            # Household Consumption columns and drop the originals -- otherwise C+G+I+X-M falls
            # short of value added by exactly these amounts (the GDP output==expenditure identity
            # in compile_national_accounts_data fails) and, left in place, they would be
            # double-counted by get_trade (which sums all non-industry columns). Verified: the
            # per-region residual goes from +2.6%..+4.8% of VA to 0 after folding.
            fold_final_demand = {
                "Changes in Inventories": "Fixed Capital Formation",
                "Direct Purchases Abroad": "Household Consumption",
            }
            # Snapshot PRE-FOLD "Fixed Capital Formation" before Changes in Inventories are folded in.
            # This is the CAPITAL-TECHNOLOGY composition source (ICIOReader._prefold_capital_composition):
            # ACCOUNTING net investment keeps the fold (and negative cells) for the GDP identity, while
            # the capital-input/productivity/stock/depreciation matrices draw their (non-negative)
            # composition from fixed capital formation only -- inventories must never define capital
            # technology. Taken before the fold so no inventory swing leaks into the composition.
            prefold_fcf_block = df.loc[:, df.columns.get_level_values(1) == "Fixed Capital Formation"].copy()
            icio[simulation_year]._prefold_fcf_block = prefold_fcf_block
            present_extremes = {extra for _, extra in df.columns if extra in fold_final_demand}
            if present_extremes:
                for region in df.columns.get_level_values(0).unique():
                    for extra_col, target_col in fold_final_demand.items():
                        if (region, extra_col) in df.columns and (region, target_col) in df.columns:
                            df[(region, target_col)] = (
                                df[(region, target_col)].fillna(0.0) + df[(region, extra_col)].fillna(0.0)
                            )
                df = df.drop(columns=[c for c in df.columns if c[1] in fold_final_demand])

            column_industries = df.columns.get_level_values(1).unique().tolist()
            row_industries = set(df.index.get_level_values(1).unique())
            shared_labels = [industry for industry in column_industries if industry in row_industries]
            # Accept official OECD-50 codes (C17_18, C24A/B, C301, C302T309, J62_63, R, S, T)
            # as well as legacy codes (B05a/b/c, C24a/b, D01a-e, R_S) so the reader handles both
            # the 2014 custom table and the 2022 OECD-50 table.
            industry_pattern = re.compile(r"^[A-Z]\d{0,3}[A-Za-z]?(?:[_T]\d{2,3}|_[A-Z])?$")
            industries = [industry for industry in shared_labels if industry_pattern.match(industry)]
            if not industries:
                raise ValueError("Provincial ICIO data has no matching industries.")
            icio[simulation_year].industries = industries

            if simulation_year == 2022:
                _floor_empty_provincial_sectors(df, industries, regions_dict)

            all_provinces = []
            for key, value in regions_dict.items():
                all_provinces.extend(value)

            countries_set = set(all_provinces).union(set(country_names)) - set(regions_dict.keys())
            # countries_set = countries_set.union(Country("ROW"))

            countries_and_regions = list(countries_set)

            # df = normalise_iot(
            #     iot=df,
            #     industries=industries,
            #     considered_countries=countries_and_regions,
            #     investment_fractions=get_investment_year(simulation_year, countries_and_regions),
            # )

            industry_cols = df.columns.get_level_values(1).isin(industries)
            non_total_rows = df.index.get_level_values(0) != "TOTAL"

            df.loc[("TOTAL", "Intermediate Inputs"), industry_cols] = df.loc[non_total_rows, industry_cols].sum(axis=0)

            outputs = df.loc[("TOTAL", "Output"), industry_cols].groupby(level=0).sum()

            for large_country, regions in regions_dict.items():
                renorm_output = outputs.loc[regions] / outputs.loc[regions].sum()
                renorm_output = renorm_output.to_dict()

            df.rename(columns={"OUT": "TOTAL"}, level=0, inplace=True)

            df = split_gfcf_column(
                considered_countries=countries_and_regions,
                industries=industries,
                iot=df,
                investment_fractions=get_investment_year(simulation_year, countries_and_regions),
            )

            icio[simulation_year].iot = df.sort_index()
            icio[simulation_year].considered_countries = countries_and_regions

            for large_country, regions in regions_dict.items():
                for region in regions:
                    icio[simulation_year].imputed_rents[region] = (
                        icio[simulation_year].imputed_rents[large_country] * renorm_output[region]
                    )
                del icio[simulation_year].imputed_rents[large_country]

            # country_names = all_countries
        else:
            countries_and_regions = None

        if countries_and_regions is None:
            value_added_dict = {
                country_name: icio[simulation_year].get_value_added_series(country_name)
                * icio[simulation_year].yearly_factor
                for country_name in country_names
            }
        else:
            value_added_dict = {
                country_name: icio[simulation_year].get_value_added_series(country_name)
                * icio[simulation_year].yearly_factor
                for country_name in countries_and_regions
            }
            for key, value in regions_dict.items():
                value_added_dict[key] = sum([value_added_dict[region] for region in value])

        # WIOD SEA coverage ends in 2014; for a later provincial build it is only a scaffold
        # (value added is rescaled to the IO below and capital/compensation are overwritten with
        # the validated series), so read the latest available WIOD year while still reporting
        # `simulation_year`.
        wiod_data_year = None
        if use_provincial_can_reader:
            wiod_year_cols = sorted(
                int(c) for c in pd.read_csv(datapaths.wiod_sea_path, nrows=0).columns if str(c).isdigit()
            )
            if wiod_year_cols and simulation_year not in wiod_year_cols:
                wiod_data_year = max([y for y in wiod_year_cols if y <= simulation_year] or wiod_year_cols)
                warnings.warn(
                    f"WIOD SEA has no '{simulation_year}' column; reading the latest available WIOD "
                    f"year '{wiod_data_year}' as a scaffold (value added rescaled to the IO; capital "
                    f"stock/compensation overwritten with the validated 2022 series).",
                    DataFilterWarning,
                )

        wiod_sea = WIODSEAReader.agg_from_csv(
            path=datapaths.wiod_sea_path,
            year=simulation_year,
            industries=industries,
            exchange_rates=exchange_rates,
            country_names=country_names,
            value_added_dict=value_added_dict,
            aggregation_type="Aggregate" if aggregate_industries else "All",
            regions_dict=regions_dict,
            data_year=wiod_data_year,
        )

        # Inject the validated 2022 province x OECD-50 capital stock / capital compensation BEFORE
        # the SEA<->IO reconciliation, so the validated series act as drop-in replacements for the
        # WIOD scaffold (which does not cover 2022) rather than overwriting the reconciled,
        # GFCF-consistent capital-compensation level that the economy GDP identity depends on.
        if use_provincial_can_reader and simulation_year == 2022:
            inject_can_provincial_socioeconomic_2022(
                sea_reader=wiod_sea,
                regions_dict=regions_dict,
                raw_data_path=raw_data_path,
                industries=wiod_sea.industries,
            )

        reconcile_value_added(
            icio_reader=icio[simulation_year],
            sea_reader=wiod_sea,
            country_names=country_names,
            regions_dict=regions_dict,
        )

        add_investment_matrix_to_icio(
            icio_reader=icio[simulation_year],
            sea_reader=wiod_sea,
            country_names=country_names,
            regions_dict=regions_dict,
        )

        match_iot_with_sea(
            icio_reader=icio[simulation_year],
            sea_reader=wiod_sea,
            country_names=country_names,
            regions_dict=regions_dict,
        )

        oecd_econ = OECDEconData(
            path=datapaths.oecd_econ_path,
            scale_dict=scale_dict,
        )

        policy_rates = PolicyRatesReader(
            path=datapaths.policy_rates_path, country_code_path=datapaths.country_codes_path
        )

        imf_reader = IMFReader.from_data(data_path=datapaths.imf_path, scale_dict=scale_dict)

        ons_reader = ONSReader(path=datapaths.ons_path)

        world_bank = WorldBankReader(path=datapaths.world_bank_path)

        ecb_reader = ECBReader(path=datapaths.ecb_path)

        all_countries = list(set(country_names).union(set(proxy_country_dict.values())))

        compustat_firms = CompustatFirmsReader.from_raw_data(
            year=simulation_year,
            quarter=1,
            countries=all_countries,
            raw_annual_path=datapaths.compustat_firms_annual_path,
            raw_quarterly_path=datapaths.compustat_firms_quarterly_path,
        )

        compustat_banks = CompustatBanksReader.from_raw_data(
            year=simulation_year, quarter=1, raw_quarterly_path=datapaths.compustat_banks_path, countries=all_countries
        )

        if prune_date:
            exchange_rates.prune(prune_date)
            eurostat.prune(prune_date)
            icio = prune_icio_dict(icio, prune_date)
            wiod_sea.prune(prune_date)
            oecd_econ.prune(prune_date)
            policy_rates.prune(prune_date)
            imf_reader.prune(prune_date)
            world_bank.prune(prune_date)

        emissions = EmissionsReader.read_price_data(datapaths.emissions_path)

        emission_fractions = None
        if datapaths.emissions_fraction_path is not None and datapaths.emissions_fraction_path.exists():
            emission_fractions = EmissionsFractionReader.read_fraction_data(datapaths.emissions_fraction_path)

        exo_prices = None
        if datapaths.firm_prices_path is not None and datapaths.firm_prices_path.exists():
            exo_prices = SectorExoPricesReader.read_from_raw_data(datapaths.firm_prices_path)

        ch4_emissions = None
        if datapaths.ch4_emissions_path is not None and datapaths.ch4_emissions_path.exists():
            ch4_emissions = CH4EmissionsReaderCAN.read_data(datapaths.ch4_emissions_path)

        # Optional province-level overrides (StatsCan), resolved from the raw_data bundle at
        # <raw_data>/canadian_inputs/. Each is a no-op if its file is absent, so national/proxy
        # runs (and non-Canadian raw_data bundles) are unaffected. The investment reader is
        # constructed earlier (it feeds the ICIO GFCF split); macro and tax are attached here.
        obps_can = None
        if datapaths.obps_path is not None:
            obps_can = OBPSCANReader.read_from_raw_data(
                rates_path=datapaths.obps_path.rates_path,
                policy_path=datapaths.obps_path.policy_path,
                policy_elec_path=datapaths.obps_path.policy_elec_path,
            )

        provincial_macro = ProvincialMacroReader.from_default(raw_data_path=raw_data_path)
        provincial_tax = ProvincialTaxReader.from_default(raw_data_path=raw_data_path)
        provincial_labour = ProvincialLabourReader.from_default(raw_data_path=raw_data_path)

        # Hand the observed 2022 provincial employer social-contribution rates (loaded onto the SEA
        # reader during the socioeconomic injection) to the OECD reader, whose read_tau_sif is the
        # single source of tau_sif for both the wage decomposition and the firm/ government tax side.
        oecd_econ.can_2022_employer_si_ratio = getattr(wiod_sea, "can_2022_employer_si_ratio", {})

        return cls(
            obps_can=obps_can,
            icio=icio,
            wiod_sea=wiod_sea,
            oecd_econ=oecd_econ,
            world_bank=world_bank,
            hfcs=hfcs,
            eurostat=eurostat,
            ons=ons_reader,
            policy_rates=policy_rates,
            imf_reader=imf_reader,
            exchange_rates=exchange_rates,
            goods_criticality=goods_criticality,
            ecb_reader=ecb_reader,
            compustat_firms=compustat_firms,
            compustat_banks=compustat_banks,
            emissions=emissions,
            emission_fractions=emission_fractions,
            exo_prices=exo_prices,
            ch4_emissions=ch4_emissions,
            provincial_macro=provincial_macro,
            provincial_investment=provincial_investment,
            provincial_tax=provincial_tax,
            provincial_labour=provincial_labour,
            regions_dict=regions_dict,
        )

    @classmethod
    def get_investment_fractions(
        cls,
        country_names: list[Country],
        eurostat: EuroStatReader,
        proxy_country_dict: dict[Country, Country],
        year: int,
    ) -> dict[Country, dict[str, float]]:
        """Calculate investment fractions for each country.

        This method computes the distribution of investment across different sectors
        (firms, households, government) for each country, using either direct data
        for EU countries or proxy data for non-EU countries.

        Args:
            country_names (list[Country]): List of countries to process
            eurostat (EuroStatReader): Eurostat data reader instance
            proxy_country_dict (dict[Country, Country]): Mapping of countries to their proxy countries
            year (int): Reference year for the data

        Returns:
            dict[Country, dict[str, float]]: Investment fractions by country and sector
        """
        investment_fractions = {}
        for country_name in country_names:
            if country_name.is_eu_country:
                investment_fractions[country_name] = eurostat.get_investment_fractions_of_country(
                    country_name, year=year
                )
            else:
                investment_fractions[country_name] = eurostat.get_investment_fractions_of_country(
                    proxy_country_dict[country_name], year=year
                )
        return investment_fractions

    def get_exogenous_data(self, country_name: Country) -> Optional[dict[str, Any]]:
        """Retrieve exogenous economic data for a country.

        This method collects various exogenous economic indicators for a country,
        including inflation, sectoral growth, unemployment rates, and other key
        economic metrics.

        Args:
            country_name (Country): Country to get data for

        Returns:
            Optional[dict[str, Any]]: Dictionary of economic indicators, or None if data is unavailable
        """
        try:
            return {
                "log_inflation": self.world_bank.get_log_inflation(country_name),
                "sectoral_growth": self.eurostat.get_perc_sectoral_growth(country_name),
                "unemployment_rate": self.oecd_econ.get_unemployment_rate(country_name),
                "house_price_index": self.oecd_econ.get_house_price_index(country_name),
                "vacancy_rate": self.oecd_econ.get_vacancy_rate(country_name),
                "total_firm_deposits_and_debt": self.eurostat.get_total_industry_debt_and_deposits(country_name),
            }
        except KeyError:
            return None

    def get_benefits_inflation_data(
        self, country_name: Country, year_min: int, year_max: int, exogenous_data: dict[str, Any]
    ) -> pd.DataFrame:
        """Calculate benefits and inflation data for a country.

        This method processes unemployment benefits, other benefits, and inflation
        data for a country over a specified time period. It interpolates quarterly
        values and merges with inflation and unemployment rate data.

        Args:
            country_name (Country): Country to analyze
            year_min (int): Start year for the analysis
            year_max (int): End year for the analysis
            exogenous_data (dict[str, Any]): Dictionary containing exogenous economic data

        Returns:
            pd.DataFrame: DataFrame containing benefits and inflation data with quarterly frequency
        """
        years = range(year_min, year_max)
        unemp = [
            self.oecd_econ.unemployment_benefits_gdp_pct(country_name, year)
            * self.world_bank.get_current_scaled_gdp(country_name, year)
            for year in years
        ]
        other = [
            self.oecd_econ.all_benefits_gdp_pct(country_name, year)
            * self.world_bank.get_current_scaled_gdp(country_name, year)
            - unemp[i]
            for i, year in enumerate(years)
        ]

        benefits_data = pd.DataFrame(
            data={"Unemployment Benefits": unemp, "Other Total Benefits": other},
            index=pd.DatetimeIndex(
                pd.date_range(
                    start=f"{years[0]}-01-01",
                    end=f"{years[-1] + 1}-01-01",
                    freq="YE",
                )
            ),
        )

        benefits_data = benefits_data.resample("QE").interpolate("linear")
        benefits_data.index = pd.DatetimeIndex([pd.Timestamp(d.year, d.month, 1) for d in benefits_data.index])
        log_inflation = exogenous_data["log_inflation"]["Real CPI Inflation"].copy()
        log_inflation.index = pd.to_datetime(log_inflation.index, format="%Y-%m")
        data = pd.merge_asof(benefits_data, log_inflation, left_index=True, right_index=True)
        unemployment_rate = exogenous_data["unemployment_rate"]["Unemployment Rate"].copy()
        unemployment_rate.index = pd.to_datetime(unemployment_rate.index, format="%Y-%m")
        data = pd.merge_asof(data, unemployment_rate, left_index=True, right_index=True)
        return data

    def get_total_benefits_lcu(self, country_name: Country, year: int) -> float:
        """Calculate total benefits in local currency units.

        This method computes the total benefits (including unemployment and other benefits)
        for a country in its local currency units.

        Args:
            country_name (Country): Country to analyze
            year (int): Reference year

        Returns:
            float: Total benefits in local currency units
        """
        return self.oecd_econ.all_benefits_gdp_pct(country_name, year) * self.world_bank.get_current_scaled_gdp(
            country_name, year
        )

    def get_total_unemployment_benefits_lcu(self, country_name: Country, year: int) -> float:
        """Calculate total unemployment benefits in local currency units.

        This method computes the total unemployment benefits for a country
        in its local currency units.

        Args:
            country_name (Country): Country to analyze
            year (int): Reference year

        Returns:
            float: Total unemployment benefits in local currency units
        """
        return self.oecd_econ.unemployment_benefits_gdp_pct(
            country_name, year
        ) * self.world_bank.get_current_scaled_gdp(country_name, year)

    def get_govt_debt_lcu(self, country: Country, year: int) -> float:
        """Calculate government debt in local currency units.

        This method computes the total government debt for a country
        in its local currency units.

        Args:
            country (Country): Country to analyze
            year (int): Reference year

        Returns:
            float: Government debt in local currency units
        """
        return self.oecd_econ.general_gov_debt(country, year) * self.exchange_rates.from_usd_to_lcu(country, year)

    def get_export_taxes(self, country: Country, year: int) -> float:
        """Calculate export taxes for a country.

        This method computes the total export taxes for a country based on
        its exports and exchange rates.

        Args:
            country (Country): Country to analyze
            year (int): Reference year

        Returns:
            float: Total export taxes
        """
        return (
            self.world_bank.get_lcu_exports(country, year)
            * self.exchange_rates.from_usd_to_lcu(country, year)
            / self.icio[year].get_exports(country).sum()
        )

    def get_national_accounts_growth(self, country: Country) -> pd.DataFrame:
        """Calculate national accounts growth rates.

        This method combines growth rate data from both IMF and OECD sources,
        with IMF data taking precedence for overlapping indicators.

        Args:
            country (Country): Country to analyze

        Returns:
            pd.DataFrame: Combined growth rate data from IMF and OECD sources
        """
        if isinstance(country, Region):
            country = country.parent_country
        imf_growth = self.imf_reader.get_na_growth_rates(country)
        oecd_growth = self.oecd_econ.get_na_growth_rates(country)

        # pick columns of oecd growth not in imf growth
        oecd_growth = oecd_growth[oecd_growth.columns.difference(imf_growth.columns)]

        # merge the two dataframes, ensuring that imf growth has the index
        merged = pd.merge_asof(imf_growth, oecd_growth, left_index=True, right_index=True)
        merged = merged.loc[imf_growth.index]
        return merged

    def expand_weights_by_income(self, year: int, country: str | Country):
        """Expand consumption weights by income quantile.

        This method calculates consumption weights for each industry and income
        quantile, using OECD data for income distribution and ICIO data for
        consumption shares.

        Args:
            year (int): Reference year
            country (str | Country): Country to analyze

        Returns:
            pd.DataFrame: Consumption weights by industry and income quantile
        """
        weights_by_income = self.oecd_econ.get_household_consumption_by_income_quantile(country=country, year=year)
        weights_by_income.index = AGGREGATED_INDUSTRIES
        consumption_shares = self.icio[year].get_consumption_shares_series(country)

        weights_by_income_all = pd.DataFrame(index=consumption_shares.index, columns=weights_by_income.columns)

        dictionary = self.icio[year].get_updated_dictionary()

        for aggregate_industry in AGGREGATED_INDUSTRIES:
            sub_industries = dictionary.get(aggregate_industry, [])
            if not sub_industries:
                continue

            sub_industries = [s_ind for s_ind in sub_industries if s_ind in consumption_shares.index]

            shares = consumption_shares.loc[sub_industries]
            shares /= shares.sum()
            agg_weights = weights_by_income.loc[aggregate_industry]
            sub_weights = pd.DataFrame(
                np.outer(shares.values, agg_weights.values), index=sub_industries, columns=weights_by_income.columns
            )
            weights_by_income_all.loc[sub_industries] = sub_weights

        weights_by_income_all.index = range(weights_by_income_all.shape[0])
        weights_by_income = weights_by_income_all
        return weights_by_income


CAN_2022_EMPTY_SECTOR_FLOOR = 1.0e6  # 1 CAD million (values are absolute after the x1e6 scaling)


def _floor_empty_provincial_sectors(
    df: pd.DataFrame,
    industries: list[str],
    regions_dict: dict[Country, list[Region]],
    floor: float = CAN_2022_EMPTY_SECTOR_FLOOR,
) -> None:
    """Give each genuinely empty (province, sector) cell a negligible, self-consistent presence.

    The finer OECD-50 split leaves exact-zero-output sectors in most provinces (coal B05/B06 in
    NL/PE/NS/NB/MB, many territory sectors). The model builds one firm per sector and its runtime
    production/price dynamics degenerate on exactly-zero output/investment (0/0, inf). This mirrors
    the 2014 table (whose coarser aggregation had no exact-zero sectors) by giving every empty
    sector a tiny output produced from an equal tiny value added and bought as fixed capital
    formation in the same region. Because the output/value-added side and the expenditure/investment
    side each gain the same amount, the GDP output==expenditure identity is preserved.
    """
    output_col = ("TOTAL", "Output")
    output_row = ("TOTAL", "Output")
    va_row = ("TOTAL", "Value Added")
    regions = [region for regions in regions_dict.values() for region in regions]
    floored = 0
    for region in regions:
        fcf_col = (region, "Fixed Capital Formation")
        if fcf_col not in df.columns:
            continue
        for sector in industries:
            cell = (region, sector)
            if cell not in df.index or output_col not in df.columns:
                continue
            current_output = df.at[cell, output_col]
            if pd.notna(current_output) and current_output > 0.0:
                continue
            df.at[cell, output_col] = floor
            if output_row in df.index:
                df.at[output_row, cell] = floor
            if va_row in df.index:
                df.at[va_row, cell] = floor
            existing_fcf = df.at[cell, fcf_col]
            df.at[cell, fcf_col] = (existing_fcf if pd.notna(existing_fcf) else 0.0) + floor
            floored += 1
    if floored:
        warnings.warn(
            f"2022 provincial build: floored {floored} empty (province, sector) cells at "
            f"{floor:g} CAD to keep the per-firm dynamics finite (identity-preserving).",
            DataFilterWarning,
        )


CAN_2022_SOCIOECONOMIC_DIR = "can_2022"
CAN_2022_CAPITAL_STOCK_FILE = "capital_stock_end2021_oecd50_by_province_CADmillions.csv"
CAN_2022_CAPITAL_COMPENSATION_FILE = "capital_compensation_oecd50_by_province_CADmillions.csv"
CAN_2022_EMPLOYMENT_SHARES_FILE = "employment_shares_oecd50_by_province.csv"
CAN_2022_COMPENSATION_FILE = "compensation_of_employees_oecd50_by_province_CADmillions.csv"


def _load_can_2022_compensation_of_employees(
    raw_data_path: Path,
    regions_dict: dict[Country, list[Region]],
    industries: list[str],
) -> tuple[dict[Region, np.ndarray], dict[Region, float]]:
    """Load observed 2022 compensation of employees from the StatCan detail VA breakdown
    (PRM500000 wages_salaries + PRM600000 employers_social_contributions, province x OECD-50, CAD mn).

    Returns:
        (coe_by_region, employer_ratio_by_region)
        * coe_by_region[region]  = TOTAL compensation of employees per sector (wages + employer), x1e6.
          This is the model's ``labour_compensation`` input (== firm-side Total Wages Paid == full firm
          labour cost); ``tau_sif`` only decomposes it into employee wages vs employer contributions.
        * employer_ratio_by_region[region] = sum(employer) / sum(wages) at region level -- the observed
          employer social-contribution rate, used to override ``tau_sif`` so the decomposition matches
          PRM500000 / PRM600000. (firm labour cost = Total Wages * (1+tau_sif) = CoE regardless of the
          rate, so this only re-splits employee income vs employer contributions, not firm cost.)
    """
    path = Path(raw_data_path) / CAN_2022_SOCIOECONOMIC_DIR / CAN_2022_COMPENSATION_FILE
    if not path.exists():
        warnings.warn(
            f"2022 compensation of employees not found at {path}; keeping the residual "
            "VA - GFCF-reconciled capital compensation for the wage bill (observed CoE NOT wired).",
            DataFilterWarning,
        )
        return {}, {}
    df = pd.read_csv(path)
    df["region"] = df["region"].astype(str)
    wages = df.pivot(index="region", columns="oecd", values="wages_salaries")
    employer = df.pivot(index="region", columns="oecd", values="employers_social_contributions")
    coe_by_region: dict[Region, np.ndarray] = {}
    ratio_by_region: dict[Region, float] = {}
    for regions in regions_dict.values():
        for region in regions:
            short_code = str(region).split("_", 1)[-1]
            if short_code not in wages.index:
                continue
            w = wages.loc[short_code].reindex(industries).fillna(0.0).to_numpy(float)
            e = employer.loc[short_code].reindex(industries).fillna(0.0).to_numpy(float)
            coe_by_region[region] = (w + e) * 1e6
            ratio_by_region[region] = float(e.sum() / w.sum()) if w.sum() > 0 else 0.0
    return coe_by_region, ratio_by_region


def _load_can_2022_employment_shares(
    raw_data_path: Path,
    regions_dict: dict[Country, list[Region]],
    industries: list[str],
) -> dict[Region, np.ndarray]:
    """Load validated StatCan 36-10-0489 province x OECD-50 employment shares (sum to 1 per province),
    aligned to the model's ``industries`` order. Returns {region: shares_vector}; regions absent from
    the file are omitted (the caller then keeps the HFCS/output-share allocation for them).
    """
    path = Path(raw_data_path) / CAN_2022_SOCIOECONOMIC_DIR / CAN_2022_EMPLOYMENT_SHARES_FILE
    if not path.exists():
        warnings.warn(
            f"2022 employment shares not found at {path}; keeping the HFCS/output-share employment "
            "allocation (StatCan 36-10-0489 shares NOT wired).",
            DataFilterWarning,
        )
        return {}
    shares_df = pd.read_csv(path, index_col=0)
    shares_df.index = shares_df.index.astype(str)
    out: dict[Region, np.ndarray] = {}
    for regions in regions_dict.values():
        for region in regions:
            short_code = str(region).split("_", 1)[-1]
            if short_code not in shares_df.index:
                continue
            out[region] = shares_df.loc[short_code].reindex(industries).fillna(0.0).to_numpy(float)
    return out


def inject_can_provincial_socioeconomic_2022(
    sea_reader: WIODSEAReader,
    regions_dict: dict[Country, list[Region]],
    raw_data_path: Path,
    industries: list[str],
) -> None:
    """Replace the WIOD scaffold capital stock / capital compensation in the SEA reader with the
    validated 2022 province x OECD-50 StatCan series, as a drop-in for the WIOD values.

    IMPORTANT: this must run BEFORE ``reconcile_value_added`` / ``add_investment_matrix_to_icio`` /
    ``match_iot_with_sea``. Those reconcile SEA "Capital Compensation" to the IO's gross fixed
    capital formation (``_match_country_iot_with_sea`` overwrites it with the investment-matrix
    column sums, and sets "Labour Compensation" = VA - reconciled capital compensation). So the
    validated capital compensation here feeds only the *sectoral investment-allocation pattern*
    (``cap_factors``); the reconciled level (and hence the GDP output==expenditure identity, which
    treats capital cost as investment flow) is preserved. Injecting after ``match`` instead
    over-states gross fixed capital formation (capital compensation >> investment) and breaks the
    economy identity, so labour compensation is deliberately NOT set here.

    Sources (``raw_data_path/can_2022``):
      * capital stock  = StatCan 36-10-0096 geometric end-2021 net non-residential stock
        (opening capital for the 2022 base year), CAD millions -- a genuine level used in
        output/capital-stock productivity.
      * capital compensation = 2022 IO GOS + mixed income + production taxes - subsidies,
        CAD millions, replacing the WIOD ``CAP`` scaffold in the investment allocation.

    Units: SEA fields carry the IO's absolute scale (the provincial IO is x1e6), so CAD-millions
    inputs are x1e6. Capital stock is floored at 1 CAD million (mirrors the WIOD ``max(1.0)``
    floor). Any region absent from the validated files keeps its WIOD scaffold (a warning fires).
    """
    socio_dir = Path(raw_data_path) / CAN_2022_SOCIOECONOMIC_DIR
    capital_stock_path = socio_dir / CAN_2022_CAPITAL_STOCK_FILE
    capital_compensation_path = socio_dir / CAN_2022_CAPITAL_COMPENSATION_FILE

    if not capital_stock_path.exists() or not capital_compensation_path.exists():
        warnings.warn(
            f"2022 provincial socioeconomic inputs not found under {socio_dir}; "
            "falling back to WIOD capital stock / compensation.",
            DataFilterWarning,
        )
        return

    capital_stock_df = pd.read_csv(capital_stock_path, index_col=0)
    capital_stock_df.index = capital_stock_df.index.astype(str)

    capital_comp_long = pd.read_csv(capital_compensation_path)
    capital_comp_wide = capital_comp_long.pivot(index="region", columns="oecd", values="capital_compensation")

    skipped = []
    for _, regions in regions_dict.items():
        for region in regions:
            short_code = str(region).split("_", 1)[-1]
            if short_code not in capital_stock_df.index or short_code not in capital_comp_wide.index:
                skipped.append(str(region))
                continue

            capital_stock = (
                capital_stock_df.loc[short_code].reindex(industries).fillna(0.0).clip(lower=1.0).to_numpy(float)
                * 1e6
            )
            capital_compensation = (
                capital_comp_wide.loc[short_code].reindex(industries).fillna(0.0).clip(lower=0.0).to_numpy(float)
                * 1e6
            )

            sea_reader.set_values_in_usd(region, "Capital Stock", capital_stock)
            sea_reader.set_values_in_usd(region, "Capital Compensation", capital_compensation)

    if skipped:
        warnings.warn(
            f"2022 provincial socioeconomic injection skipped (WIOD fallback) for: {skipped}.",
            DataFilterWarning,
        )

    # Also load the validated StatCan 36-10-0489 employment shares and stash them on the SEA reader.
    # These drive the province x sector EMPLOYED-PERSON structure (headcount), applied to the synthetic
    # population after it is built (see reallocate_employment_by_shares / synthetic_country build). The
    # sector wage bill (SEA Labour Compensation) is unaffected, so wiring these fixes the employment
    # distribution and hence wage/worker and labour productivity, without touching the value-added or
    # GDP-identity reconciliation.
    sea_reader.can_2022_employment_shares = _load_can_2022_employment_shares(
        raw_data_path=raw_data_path,
        regions_dict=regions_dict,
        industries=industries,
    )

    # Load observed 2022 compensation of employees (PRM500000 + PRM600000). This replaces the residual
    # VA - GFCF-capcomp as the firm wage bill (SEA "Labour Compensation"), applied in
    # _match_country_iot_with_sea. The employer/wages ratio overrides tau_sif so the wages vs employer
    # split matches PRM500000/PRM600000. Capital compensation and the GFCF/investment path are untouched.
    coe_by_region, employer_ratio = _load_can_2022_compensation_of_employees(
        raw_data_path=raw_data_path,
        regions_dict=regions_dict,
        industries=industries,
    )
    sea_reader.can_2022_compensation_of_employees = coe_by_region
    sea_reader.can_2022_employer_si_ratio = employer_ratio


def prune_icio_dict(icio_dict: dict[int, Any], prune_date: date):
    """Prune ICIO dictionary to remove data before a specific date.

    This function filters the ICIO dictionary to keep only data from years
    after the specified prune date.

    Args:
        icio_dict (dict[int, Any]): Dictionary of ICIO data by year
        prune_date (date): Date to prune from

    Returns:
        dict[int, Any]: Filtered ICIO dictionary
    """
    # make sure prune date is the year in int format

    icio_dict = {year: icio for year, icio in icio_dict.items() if year >= prune_date.year}

    if not icio_dict:
        warnings.warn(
            f"No ICIO data was kept for date {prune_date}.",
            DataFilterWarning,
        )
    return icio_dict
