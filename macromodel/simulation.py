"""This module implements the core simulation engine for the macroeconomic model.

The simulation handles multiple countries, their interactions through goods markets,
exchange rates, and rest-of-world effects. It provides functionality to:
- Initialize a simulation from preprocessed economic data
- Run time-stepped iterations of the economic model
- Reset the simulation state
- Save and load simulation states
- Track various economic metrics across countries
"""

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import h5py
import numpy as np
from numba import njit

from macro_data import DataWrapper
from macro_data.configuration import CountryDataConfiguration
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.country import Country
from macromodel.country.regional_aggregator import RegionalAggregator
from macromodel.exchange_rates import ExchangeRates
from macromodel.markets.goods_market import GoodsMarket
from macromodel.rest_of_the_world import RestOfTheWorld
from macromodel.timestep import Timestep


@dataclass
class Simulation:
    """A multi-country macroeconomic simulation engine.

    This class orchestrates the simulation of multiple interacting economies, including:
    - Multiple country-level economic models
    - Rest of world interactions
    - Global goods market clearing
    - Exchange rate dynamics

    The simulation can be stepped through time, with each iteration updating all
    economic actors and markets in sequence. Results can be saved for later analysis.

    Attributes:
        countries (dict[str, Country]): Dictionary of country models, keyed by country code
        rest_of_the_world (RestOfTheWorld): Model for rest-of-world economic interactions
        goods_market (GoodsMarket): Global goods market clearing mechanism
        exchange_rates (ExchangeRates): Exchange rate dynamics between countries
        timestep (Timestep): Current simulation timestep
        configuration (SimulationConfiguration): Simulation parameters and settings
        initial_year (int): Starting year of the simulation
        aggregate_country_price_index (float): Aggregate price index across all countries
    """

    countries: dict[str, Country]
    rest_of_the_world: RestOfTheWorld
    goods_market: GoodsMarket
    exchange_rates: ExchangeRates
    timestep: Timestep
    configuration: SimulationConfiguration
    initial_year: int
    aggregate_country_price_index: float = 1.0
    regional_aggregator: Optional[RegionalAggregator] = None
    prehooks: list[Callable] = field(default_factory=list)
    posthooks: list[Callable] = field(default_factory=list)

    @classmethod
    def from_datawrapper(
        cls,
        datawrapper: DataWrapper,
        simulation_configuration: SimulationConfiguration,
    ):
        """Initialize a simulation from preprocessed economic data.

        This method creates a new simulation instance using preprocessed data from a DataWrapper
        object and a simulation configuration. It sets up all countries, markets, and economic
        relationships based on the provided data and configuration.

        Args:
            datawrapper (DataWrapper): Preprocessed economic data for all countries
            simulation_configuration (SimulationConfiguration): Configuration parameters for the simulation

        Returns:
            Simulation: A new simulation instance initialized with the provided data

        Raises:
            ValueError: If a country in the simulation configuration is not found in the data
        """

        data_configuration = datawrapper.configuration
        for country, country_sim_conf in simulation_configuration.country_configurations.items():
            if country not in data_configuration.country_configs:
                raise ValueError(
                    f"Country {country} not found in the data configuration. Please use a valid data configuration."
                )
            if not check_compatibility(data_configuration.country_configs[country], country_sim_conf):  # type: ignore
                datawrapper.synthetic_countries[country].reset_firm_function_dependent(
                    **country_sim_conf.firms.reset_params,
                    zero_initial_debt=False,
                    zero_initial_deposits=False,
                )

        countries_without_row = [c for c in datawrapper.all_country_names if c != "ROW"]
        countries_with_row = datawrapper.all_country_names

        running_multi_country = len(countries_without_row) > 1

        model_dict = {
            country_name: country.synthetic_goods_market.exchange_rates_model
            for country_name, country in datawrapper.synthetic_countries.items()
        }

        emission_factors = datawrapper.emission_factors

        emission_factors = np.array(
            [
                emission_factors["coal"],  # B05a
                emission_factors["gas"],  # B05b
                emission_factors["oil"],  # B05c
                emission_factors["coke_refining"],  # C19
            ]
        )

        exchange_rates = ExchangeRates.from_data(
            exchange_rates_data=datawrapper.exchange_rates,
            exchange_rate_config=simulation_configuration.exchange_rates_configuration,
            initial_year=datawrapper.configuration.year,
            country_names=countries_without_row,
            exchange_rates_model=model_dict,
        )

        countries = {
            country_name: Country.from_pickled_country(
                synthetic_country=datawrapper.synthetic_countries[country_name],
                country_configuration=simulation_configuration.country_configurations[country_name],
                exchange_rates=exchange_rates,
                country_name=country_name,
                all_country_names=countries_with_row,
                industries=datawrapper.industries,
                initial_year=datawrapper.configuration.year,
                t_max=simulation_configuration.t_max,
                running_multiple_countries=running_multi_country,
                emission_factors_usd=emission_factors,
            )
            for country_name in countries_without_row
        }

        row_firm_exo_prices = next(
            (
                datawrapper.synthetic_countries[c].firm_exo_prices
                for c in countries_without_row
                if datawrapper.synthetic_countries[c].firm_exo_prices is not None
            ),
            None,
        )

        rest_of_the_world = RestOfTheWorld.from_pickled_row(
            country_name="ROW",
            all_country_names=countries_with_row,
            n_industries=datawrapper.n_industries,
            synthetic_row=datawrapper.synthetic_rest_of_the_world,
            configuration=simulation_configuration.row_configuration,
            calibration_data_before=datawrapper.calibration_before,
            calibration_data_during=datawrapper.calibration_during,
            firm_exo_prices=row_firm_exo_prices,
            industries=datawrapper.industries,
        )

        goods_market_participants = {
            country_name: country.get_goods_market_participants() for country_name, country in countries.items()
        }

        goods_market_participants["ROW"] = [rest_of_the_world]

        row_index = sorted(countries_with_row).index("ROW")

        goods_market = GoodsMarket.from_data(
            n_industries=datawrapper.n_industries,
            configuration=simulation_configuration.goods_market_configuration,
            goods_market_participants=goods_market_participants,
            origin_trade_proportions=datawrapper.origin_trade_proportions.values,
            destin_trade_proportions=datawrapper.destination_trade_proportions.values,
            row_index=row_index,
        )

        timestep = Timestep(year=datawrapper.configuration.year, month=1, increment=datawrapper.time_unit)

        if simulation_configuration.seed is not None:
            np.random.seed(simulation_configuration.seed)
            set_seed(simulation_configuration.seed)

        aggregator = (
            RegionalAggregator(
                aggregation_structure=datawrapper.aggregation_structure,
            )
            if datawrapper.aggregation_structure
            else None
        )

        return cls(
            countries=countries,
            rest_of_the_world=rest_of_the_world,
            goods_market=goods_market,
            exchange_rates=exchange_rates,
            timestep=timestep,
            configuration=deepcopy(simulation_configuration),
            initial_year=datawrapper.configuration.year,
            regional_aggregator=aggregator,
        )

    def reset(self, configuration: Optional[SimulationConfiguration] = None) -> None:
        """Reset the simulation to its initial state.

        Resets all simulation components (countries, markets, etc.) to their initial states.
        Optionally accepts a new configuration to modify simulation parameters during reset.

        Args:
            configuration (Optional[SimulationConfiguration]): New configuration to use after reset.
                If None, uses the current configuration.
        """

        if configuration is None:
            configuration = self.configuration

        self.timestep = Timestep(year=self.initial_year, month=1)

        self.rest_of_the_world.reset(configuration.row_configuration)
        self.goods_market.reset(configuration.goods_market_configuration)

        self.exchange_rates.reset()

        for country in self.countries.values():
            country.reset(configuration.country_configurations[country.country_name])

        self.configuration = deepcopy(configuration)

        if configuration.seed is not None:
            np.random.seed(configuration.seed)
            set_seed(configuration.seed)

    @property
    def t_max(self):
        """int: Maximum number of timesteps to simulate."""
        return self.configuration.t_max

    @property
    def random_seed(self):
        """Optional[int]: Random seed used for reproducible simulations."""
        return self.configuration.seed

    def run_prehooks(self, year: int, month: int) -> None:
        """Execute all registered pre-hooks before iteration logic.

        Args:
            year (int): Current year of the simulation
            month (int): Current month of the simulation
        """
        for hook in self.prehooks:
            # Warn if month is not a quarter start (1, 4, 7, 10)
            if month not in [1, 4, 7, 10]:
                hook_name = getattr(hook, "__name__", "unknown_hook")
                logging.warning(
                    f"Pre-hook '{hook_name}' called at month {month}, which is not a quarter start. "
                    "The simulation frequency may be quarterly."
                )
            hook(self, year, month)

    def run_posthooks(self, t: int, year: int, month: int) -> None:
        """Execute all registered post-hooks after iteration logic.

        Post-hooks are called after all markets have cleared and metrics are updated,
        allowing inspection of the realized state of the simulation.

        Args:
            t (int): Current timestep index (0-indexed)
            year (int): Current year of the simulation
            month (int): Current month of the simulation
        """
        for hook in self.posthooks:
            hook(self, t, year, month)

    def iterate(self, t: int = 0):
        """Execute one timestep of the simulation.

        Performs a complete iteration of the economic model, including:
        1. Pre-hook execution
        2. Exchange rate updates
        3. Country-level economic processes
        4. Labor market clearing
        5. Housing and credit market clearing
        6. Goods market clearing
        7. Metric updates and recording
        8. Post-hook execution

        Args:
            t (int): Current timestep index (0-indexed), used for logging/debugging
        """
        # Execute pre-hooks before any iteration logic
        self.run_prehooks(self.timestep.year, self.timestep.month)

        # self.exchange_rates.set_current_exchange_rates(current_year=self.timestep.year)

        for ind, country in enumerate(self.countries.values()):
            exchange_rate = self.exchange_rates.get_current_exchange_rates_from_usd_to_lcu(
                country_name=country.country_name,
                current_year=self.timestep.year,
                prev_inflation=country.economy.ts.current("ppi_inflation")[0],
                prev_growth=country.economy.ts.current("total_growth")[0],
            )
            logging.info("Country: %s", country.country_name)
            country.initialisation_phase(exchange_rate_usd_to_lcu=exchange_rate)
            country.estimation_phase()
            country.target_setting_phase()
            country.clear_labour_market()
            country.update_planning_metrics()

        if self.regional_aggregator:
            logging.info("Synchronising central banks across regions")
            self.regional_aggregator.sync_central_banks(self.countries)

        for ind, country in enumerate(self.countries.values()):
            # Clearing the housing and the credit market
            logging.info("Clearing the housing and the credit market")
            country.prepare_housing_market_clearing()
            country.clear_housing_market()
            country.prepare_credit_market_clearing()
            country.clear_credit_market()
            country.process_housing_market_clearing()
            country.process_credit_market_clearing()

            # Prepare goods market clearing
            logging.info("Prepare goods market clearing")
            country.prepare_goods_market_clearing()

        # Prepare goods market clearing
        logging.info("Prepare goods market clearing (ROW)")

        # Prepare goods market clearing
        aggregate_country_production_index = self.production_price_index
        total_real_production = self.total_real_production
        if total_real_production > 0:
            self.aggregate_country_price_index = self.aggregate_nominal_production / total_real_production
        self.rest_of_the_world.update_planning_metrics(
            aggregate_country_production_index=aggregate_country_production_index,
            aggregate_country_price_index=self.aggregate_country_price_index,
        )

        logging.info("Clearing the goods market")
        # Clearing the goods market
        self.goods_market.prepare()
        self.goods_market.clear()
        self.goods_market.record()

        logging.info("Updating metrics")
        # After goods market clearing
        self.rest_of_the_world.record_bought_goods()
        for country in self.countries.values():
            country.update_realised_metrics()
            country.update_population_structure()

        # Execute post-hooks after all metrics are updated
        self.run_posthooks(t, self.timestep.year, self.timestep.month)

        # Next month
        self.timestep.step()

    @property
    def aggregate_nominal_production(self) -> float:
        """float: Total nominal production across all countries in the simulation."""
        return np.sum(
            [
                (
                    self.countries[c].firms.ts.current("price")
                    / self.countries[c].firms.ts.initial("price")
                    * (self.countries[c].firms.ts.current("production") + self.countries[c].firms.ts.prev("inventory"))
                ).sum()
                for c in self.countries.keys()
            ]
        )

    @property
    def total_real_production(self) -> float:
        """float: Total real (quantity) production across all countries."""
        return np.sum(
            [
                (self.countries[c].firms.ts.current("production") + self.countries[c].firms.ts.prev("inventory")).sum()
                for c in self.countries.keys()
            ]
        )

    @property
    def production_price_index(self) -> float:
        """float: Aggregate production price index across all countries."""
        current_production = [self.countries[c].firms.ts.current("production").sum() for c in self.countries.keys()]
        initial_production = [self.countries[c].firms.ts.initial("production").sum() for c in self.countries.keys()]
        return np.sum(current_production) / np.sum(initial_production)

    def run(self) -> None:
        """Run the complete simulation for the configured number of timesteps.

        Executes the simulation from the current state until t_max iterations
        have been completed. Each iteration represents one time period in the model.
        """
        remaining = self.t_max - self.steps_completed
        if remaining > 0:
            self.run_steps(remaining)

    @property
    def steps_completed(self) -> int:
        """Number of :meth:`iterate` calls completed since the initial state."""
        first_country = next(iter(self.countries.values()))
        history = first_country.economy.ts.historic("gdp_output")
        return max(len(history) - 1, 0)

    def run_steps(self, n_steps: int, *, start_t: int | None = None) -> None:
        """Advance the simulation by *n_steps* timesteps from its current state."""
        if n_steps <= 0:
            return
        base_t = self.steps_completed if start_t is None else start_t
        for i in range(n_steps):
            self.iterate(base_t + i)

    def run_until_total_steps(self, total_steps: int) -> None:
        """Run until ``steps_completed == total_steps``."""
        remaining = total_steps - self.steps_completed
        if remaining > 0:
            self.run_steps(remaining)

    def save_random_seed(self, h5_file: h5py.File) -> None:
        """Save the random seed to the HDF5 file metadata.

        Args:
            h5_file (h5py.File): Open HDF5 file to save to
        """
        if self.random_seed:
            h5_file.attrs["random_seed"] = self.random_seed
        else:
            h5_file.attrs["random_seed"] = "no_seed"

    def save_configuration(self, h5_file: h5py.File) -> None:
        """Save the simulation configuration to the HDF5 file metadata.

        Args:
            h5_file (h5py.File): Open HDF5 file to save to
        """
        conf_string = self.configuration.model_dump()
        h5_file.attrs["configuration"] = str(conf_string)

    def save(self, save_dir: Path | str, file_name: str):
        """Save the complete simulation state to an HDF5 file.

        Saves all simulation data including country states, market states,
        configuration, and random seed state to a file for later analysis
        or continuation.

        Args:
            save_dir (Path | str): Directory to save the file in
            file_name (str): Name of the output file
        """
        if isinstance(save_dir, str):
            save_dir = Path(save_dir)
        with h5py.File(save_dir / file_name, "w") as f:
            self.save_random_seed(f)
            self.save_configuration(f)
            # self.exchange_rates.save_to_h5(f)
            self.rest_of_the_world.save_to_h5(f)
            self.goods_market.save_to_h5(f)
            for country in self.countries.values():
                country.save_to_h5(f)

    def shallow_df_dict(self):
        """Create a dictionary of shallow (summary) DataFrames for each country.

        Returns:
            dict: Dictionary mapping country codes to summary DataFrames
        """
        df_dict = {country: self.countries[country].shallow_output() for country in self.countries}
        return df_dict

    def shallow_hdf_save(self, save_dir: Path | str, file_name: str):
        """Save a simplified version of the simulation results to an HDF5 file.

        Saves summary statistics and key metrics for each country, using less
        storage space than a full save.

        Args:
            save_dir (Path | str): Directory to save the file in
            file_name (str): Name of the output file
        """
        if isinstance(save_dir, str):
            save_dir = Path(save_dir)
        for country_name, country in self.countries.items():
            df = country.shallow_output()
            industry_df = country.firms.industries_dataframe
            df.to_hdf(save_dir / file_name, key=country_name, mode="a")
            industry_df.to_hdf(save_dir / file_name, key=f"{country_name}_industries", mode="a")
            # Compact per-industry time series for diagnostics.  Best-effort: a
            # failure here must never break the (convergence-critical) shallow save.
            try:
                for field, field_df in country.firms.industry_timeseries_dataframes().items():
                    field_df.to_hdf(save_dir / file_name, key=f"{country_name}_firms_{field}", mode="a")
            except Exception as exc:  # noqa: BLE001 - diagnostics are non-critical
                logging.getLogger(__name__).warning(
                    "Per-industry diagnostic export failed for %s: %s", country_name, exc
                )
        # Demand decomposition for any good: who buys it, per timestep.  The overshoot
        # investigation needs demand for a good attributed across purchaser classes
        # (firms' intermediate use, firms' capital purchases, household consumption,
        # household investment, exports) -- the aggregate series cannot say which class
        # drives a divergence.
        #
        # UNITS ARE MIXED and every key therefore carries an explicit _real / _nominal
        # suffix.  Firms' series are real amounts; household, government and trade series
        # are nominal LCU and must be deflated by the good's price before being compared
        # with, or added to, the real ones.  This was documented only in a comment here
        # and was duly missed in analysis: deflating the already-real firm series made
        # sector D's firm intermediate demand read +0.1% (Current Measures) and +8.4%
        # (Net-zero) when it is +21.9% and +28.6%, and the purchaser identity came to
        # 79-87% of production instead of ~100%.  With the units applied correctly the
        # identity closes to 99.3-101.0%.  The suffix travels with the data; a comment
        # does not.
        try:
            import pandas as pd

            for country_name, country in self.countries.items():
                cols = list(country.firms.industries)
                for key, arr in (
                    ("firms_intermediate_bought_by_good_real",
                     np.array(country.firms.ts.historic("real_amount_bought_as_intermediate_inputs")).sum(axis=1)),
                    ("firms_capital_bought_by_good_real",
                     np.array(country.firms.ts.historic("real_amount_bought_as_capital_goods")).sum(axis=1)),
                    ("households_consumption_by_good_nominal",
                     np.array(country.households.ts.historic("industry_consumption"))),
                    ("households_investment_by_good_nominal",
                     np.array(country.households.ts.historic("investment")).sum(axis=1)),
                    # Government buys goods too.  Omitting it made the 2020 purchase
                    # total 4.2% short of supply, which biased every growth rate computed
                    # off that base upward -- the identity closes to 1.00 once included.
                    ("government_consumption_by_good_nominal",
                     np.array(country.government_entities.ts.historic("consumption_in_usd"))),
                    ("exports_by_good_nominal", np.array(country.economy.ts.historic("exports"))),
                    ("imports_by_good_nominal", np.array(country.economy.ts.historic("imports"))),
                ):
                    if arr.ndim != 2 or arr.shape[1] != len(cols):
                        continue
                    pd.DataFrame(np.nan_to_num(arr), columns=cols).to_hdf(
                        save_dir / file_name, key=f"{country_name}_{key}", mode="a"
                    )
            # For linkage-owned goods (the energy bundle), also split firms' intermediate
            # purchases by the CONSUMING industry -- the class totals above cannot say
            # whether one linked sector's coefficient path drives an aggregate divergence.
            for country_name, country in self.countries.items():
                owned = getattr(country.firms, "_linkage_owned_pairs", None)
                if not owned:
                    continue
                goods = sorted({j for prs in owned.values() for (_i, j) in prs})
                arr = np.array(country.firms.ts.historic("real_amount_bought_as_intermediate_inputs"))
                if arr.ndim != 3:
                    continue
                industry_idx = np.asarray(country.firms.states["Industry"])
                cols = list(country.firms.industries)
                for j in goods:
                    mat = np.zeros((arr.shape[0], len(cols)))
                    for i in range(len(cols)):
                        sel = industry_idx == i
                        if sel.any():
                            mat[:, i] = np.nan_to_num(arr[:, sel, j]).sum(axis=1)
                    pd.DataFrame(mat, columns=cols).to_hdf(
                        save_dir / file_name,
                        key=f"{country_name}_intermediate_{cols[j]}_by_industry",
                        mode="a",
                    )
        except Exception as exc:  # noqa: BLE001 - diagnostics are non-critical
            logging.getLogger(__name__).warning("Demand-decomposition export failed: %s", exc)

        # Rest-of-the-world sales by industry == the countries' imports by industry.  The
        # shallow summary otherwise carries only an economy-wide Imports total, which
        # cannot say whether a sector is meeting demand domestically or importing it --
        # the central question for the CER electricity linkage.  Best-effort, as above.
        try:
            import pandas as pd

            row_ts = self.rest_of_the_world.ts
            imports_by_industry = pd.DataFrame(np.array(row_ts.historic("exports_real")))
            imports_by_industry.to_hdf(save_dir / file_name, key="row_imports_real", mode="a")
            # ROW's *offered* exports, as distinct from what it actually sells.  The
            # import cap clamps this quantity, so the two series together are what say
            # whether a non-binding cap means "imports are genuinely constrained" or
            # "the cap is anchored above realised trade and has no teeth".
            desired = pd.DataFrame(np.array(row_ts.historic("desired_exports_real")))
            desired.to_hdf(save_dir / file_name, key="row_desired_exports_real", mode="a")
        except Exception as exc:  # noqa: BLE001 - diagnostics are non-critical
            logging.getLogger(__name__).warning("ROW import export failed: %s", exc)

    def get_country_shallow_output(self, country: str):
        """Get summary statistics for a specific country.

        Args:
            country (str): Country code to get data for

        Returns:
            pd.DataFrame: DataFrame containing summary statistics for the country
        """
        return self.countries[country].shallow_output()

    def get_country_gdp_debug_output(self, country: str):
        """Get detailed GDP breakdown for a specific country.

        Args:
            country (str): Country code to get data for

        Returns:
            pd.DataFrame: DataFrame containing detailed GDP breakdown for the country
        """
        return self.countries[country].gdp_debug_output()

    def get_country_gdp_components_df(self, country: str):
        """Get detailed GDP breakdown for a specific country.

        Args:
            country (str): Country code to get data for

        Returns:
            pd.DataFrame: DataFrame containing detailed GDP breakdown for the country
        """
        return self.countries[country].gdp_components_df


def check_compatibility(
    country_data_configuration: CountryDataConfiguration, country_sim_configuration: CountryConfiguration
) -> bool:
    """Check if data and simulation configurations are compatible for a country.

    Verifies that key parameters in the data configuration match those in the
    simulation configuration to ensure consistency in the model.

    Args:
        country_data_configuration (CountryDataConfiguration): Configuration used in data preprocessing
        country_sim_configuration (CountryConfiguration): Configuration for simulation

    Returns:
        bool: True if configurations are compatible, False otherwise
    """
    firm_data_conf = country_data_configuration.firms_configuration

    firm_sim_reset_params = country_sim_configuration.firms.reset_params

    test_cases = [
        firm_data_conf.initial_inventory_to_input_fraction
        == firm_sim_reset_params["initial_inventory_to_input_fraction"],
        firm_data_conf.capital_inputs_utilisation_rate == firm_sim_reset_params["capital_inputs_utilisation_rate"],
        firm_data_conf.intermediate_inputs_utilisation_rate
        == firm_sim_reset_params["intermediate_inputs_utilisation_rate"],
    ]

    return all(test_cases)


@njit
def set_seed(seed: int):
    """Set the random seed for numba-compiled functions.

    Args:
        seed (int): Random seed value
    """
    np.random.seed(seed)
