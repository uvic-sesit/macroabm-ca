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
import pandas as pd
from numba import njit

from macro_data import DataWrapper
from macro_data.configuration import CountryDataConfiguration
from macromodel.agents.agent import Agent
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

        # The goods market reshapes these flat arrays into (country, country, industry) and indexes
        # them positionally in the participant order (== goods_market_participants keys ==
        # countries_with_row). The trade-proportion DataFrames are sort_index()-ed (alphabetical),
        # so taking .values directly would feed the countries in the WRONG order and permute both the
        # origin and destination axes (e.g. sourcing C24B from non-producers). Reindex explicitly to
        # the exact participant order before .values so origin/destination line up with the market's
        # country indexing. This only realigns the array; it does not change any observed trade flow.
        _tp_order = [str(c) for c in countries_with_row]
        _tp_index = pd.MultiIndex.from_product(
            [_tp_order, _tp_order, range(datawrapper.n_industries)],
            names=datawrapper.origin_trade_proportions.index.names,
        )
        _origin_tp = datawrapper.origin_trade_proportions.reindex(_tp_index).to_numpy()
        _destin_tp = datawrapper.destination_trade_proportions.reindex(_tp_index).to_numpy()

        goods_market = GoodsMarket.from_data(
            n_industries=datawrapper.n_industries,
            configuration=simulation_configuration.goods_market_configuration,
            goods_market_participants=goods_market_participants,
            origin_trade_proportions=_origin_tp,
            destin_trade_proportions=_destin_tp,
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

        Args:
            t (int): Current timestep index (0-indexed), used for logging/debugging
        """
        # Execute pre-hooks before any iteration logic
        self.run_prehooks(self.timestep.year, self.timestep.month)

        # Advance the OBPS policy clock to the current calendar year.  The model steps
        # quarterly while the carbon price and benchmark tightening are annual, so this
        # catches the policy up rather than advancing it once per timestep.
        for country in self.countries.values():
            if getattr(country, "obps", None) is not None:
                while country.obps.current_year < self.timestep.year:
                    country.obps.update()

        # self.exchange_rates.set_current_exchange_rates(current_year=self.timestep.year)

        # One national inflation expectation, shared by every province.
        #
        # Each province otherwise forecasts inflation from its OWN prices, and firms pass
        # that straight back into those prices (price_setting_speed_gf = 1.0), so prices ->
        # own PPI -> own expectation -> prices is a closed per-province loop with no anchor.
        # Measured consequence: provincial price LEVELS compound apart, reaching a 3.5x
        # spread by 2050 with 91% of Ontario's industries above 1.5x its Current Measures
        # level while 90% of Saskatchewan's sit below 0.8x -- a province-wide drift with no
        # economic driver, which fed straight into real GDP via the deflator.
        #
        # Sharing the expectation breaks the per-province loop while KEEPING full
        # pass-through, so firms still respond to inflation; they just cannot bootstrap
        # their own province's price level away from everyone else's.
        #
        # Computed from the PREVIOUS step's estimates, which are all available here before
        # any country runs `estimation_phase` this step. That is deliberate: it avoids
        # splitting the country loop below, and reordering that loop would change the RNG
        # draw sequence and therefore every result. A one-quarter lag on an expectation is
        # realistic in any case. Weighted by production, so Ontario counts for more
        # than PEI.
        national_ppi_expectation = None
        if getattr(self, "national_inflation_expectation", False):
            weights, values = [], []
            for _c in self.countries.values():
                try:
                    v = float(np.asarray(_c.economy.ts.current("estimated_ppi_inflation")).ravel()[0])
                    w = float(np.nansum(np.asarray(_c.firms.ts.current("production"), dtype=float)))
                except (KeyError, AttributeError, IndexError, ValueError):
                    continue
                if np.isfinite(v) and np.isfinite(w) and w > 0:
                    values.append(v)
                    weights.append(w)
            if values:
                total = float(np.sum(weights))
                national_ppi_expectation = (
                    float(np.dot(values, weights) / total) if total > 0 else float(np.mean(values))
                )

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
            if national_ppi_expectation is not None:
                # Overrides the province's own estimate for every consumer of it -- prices,
                # wages, planning and government -- rather than prices alone, because a
                # province forecasting one inflation rate for wages and another for prices
                # would be less coherent, not more.
                country.economy.ts.override_current(
                    "estimated_ppi_inflation", [national_ppi_expectation]
                )
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
        # Residual export targeting needs domestic absorption, which only this layer can
        # see: it spans every country's output and the exports ROW took out of it. Supplied
        # with a ONE-PERIOD LAG -- using the current period would make the export target
        # depend on a market clearing that has not happened yet.
        self._update_row_domestic_absorption()
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

    def iter_agents(self):
        """Yield every `Agent` in the simulation, including the rest of the world.

        Walks each country's attributes rather than naming the agent collections, so a
        country gaining an agent type does not silently fall out of the sweep.
        """
        seen = set()
        candidates = [self.rest_of_the_world]
        for country in self.countries.values():
            candidates.extend(vars(country).values())
        for candidate in candidates:
            if isinstance(candidate, Agent) and id(candidate) not in seen:
                seen.add(id(candidate))
                yield candidate

    def set_agent_history_limit(self, limit: int | None) -> None:
        """Cap the goods-market transaction history every agent retains.

        Those per-agent, per-counterparty series are 97.3% of the simulation's memory on
        a long provincial run and nothing reads their history (see `Agent`), so capping
        them makes the footprint flat in the horizon instead of linear.

        `None` restores the default of keeping every step, which is required for
        `save`: a trimmed run cannot write a complete HDF5 export, and callers that
        enable both should be rejected rather than silently write short series.

        Args:
            limit (int | None): Steps to retain, or None for unlimited.  Must be at
                least 2 so `current()` and `prev()` still resolve.

        Raises:
            ValueError: If *limit* is below 2.
        """
        if limit is not None and limit < 2:
            raise ValueError(
                f"history limit must be at least 2 so current() and prev() resolve, got {limit}"
            )
        for agent in self.iter_agents():
            agent.history_limit = limit

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

    def _update_row_domestic_absorption(self) -> None:
        """Real production the home economy keeps, by industry = production - exports.

        A no-op unless a linkage has pinned some industry, so it costs nothing in a normal
        run. Both terms are REAL: `production` is a real quantity and ROW's `exports_real`
        is the real amount it bought, so the difference is what stayed home.
        """
        row = self.rest_of_the_world
        try:
            n = len(next(iter(self.countries.values())).firms.industries)
            production = np.zeros(n)
            price_num = np.zeros(n)
            for country in self.countries.values():
                industry = np.asarray(country.firms.states["Industry"])
                prod = np.asarray(country.firms.ts.current("production"), dtype=float).ravel()
                np.add.at(production, industry, prod)
                price_f = np.asarray(country.firms.ts.current("price"), dtype=float).ravel()
                np.add.at(price_num, industry, prod * price_f)
            # National production-weighted market price per industry.  ROW uses it ONLY
            # for the industries opted in via set_real_terms_export_industries (sector D
            # today); every other pin keeps ROW's aggregate-indexed price, which the
            # fix1b A/B showed is load-bearing for the fossil budgets.
            row.set_market_prices(np.divide(
                price_num, production, out=np.zeros(n), where=production > 0))
            # Base production is captured at the FIRST STEP, unconditionally -- NOT the
            # first time an index arrives. The linkage's first milestone is 2020 while the
            # index is anchored to the simulation start (2014), so capturing it lazily
            # would multiply a 2014-anchored ratio by a 2020 base. That is the same
            # anchor mismatch that already made this feature move demand the wrong way
            # once; both ends are now tied to the simulation start by construction and do
            # not depend on which milestones the linkage happens to write.
            if getattr(row, "_production_base", None) is None:
                row.set_production_base(production.copy())
            if getattr(row, "_export_demand_index", None) is None:
                return
            # Countries' EXPORTS, deflated to real. NOT `row.ts.exports_real`, which is
            # what ROW SELLS to the countries -- their imports. `record_bought_goods` sets
            # it from `real_amount_sold`; the name says exports, the definition does not.
            # Using it overstated absorption ~4x (39.2bn/yr against an actual 10.1bn).
            #
            # HISTORY, so this is not flip-flopped again: this correction was tried once
            # while production was still demand-determined and made results markedly worse
            # (oil +10.4% -> +46.7%, national output 3,933 -> 4,098bn), because a larger
            # export target then inflated production itself. With production driven by
            # `exogenous_fossil_production` that feedback is cut: production is fixed by
            # the external path, so absorption only decides the SPLIT between domestic use
            # and exports. The correction is safe in that configuration and wrong-headed
            # without it.
            exports_real = np.zeros_like(production)
            for country in self.countries.values():
                industry = np.asarray(country.firms.states["Industry"])
                nominal = np.asarray(
                    country.economy.ts.current("exports"), dtype=float).ravel()
                if nominal.shape != production.shape:
                    continue
                prod_f = np.asarray(
                    country.firms.ts.current("production"), dtype=float).ravel()
                price_f = np.asarray(
                    country.firms.ts.current("price"), dtype=float).ravel()
                num = np.zeros_like(production)
                den = np.zeros_like(production)
                np.add.at(num, industry, prod_f * price_f)
                np.add.at(den, industry, prod_f)
                price = np.divide(num, den, out=np.ones_like(num), where=den > 0)
                exports_real += np.divide(nominal, price, out=np.zeros_like(nominal),
                                          where=price > 0)
            row.set_domestic_absorption(np.maximum(production - exports_real, 0.0))
        except Exception as exc:  # noqa: BLE001 - never break the run for a diagnostic input
            logging.getLogger(__name__).warning(
                "Could not compute domestic absorption for export pinning: %s", exc)

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
            # Capital purchases by the INVESTING industry -- i.e. GFCF by sector.
            # `firms_capital_bought_by_good_real` above is indexed by the good BOUGHT and
            # summed over buyers, so it cannot say which sector is doing the investing.
            # That gap made it impossible to answer "how much is being invested in the
            # grid", which is the first question anyone asks of a transition scenario:
            # sector D's own investment simply was not in the file.
            for country_name, country in self.countries.items():
                arr = np.array(country.firms.ts.historic("real_amount_bought_as_capital_goods"))
                if arr.ndim != 3:
                    continue
                industry_idx = np.asarray(country.firms.states["Industry"])
                cols = list(country.firms.industries)
                # sum over the GOOD axis, group by the INVESTING firm's industry
                by_firm = np.nan_to_num(arr).sum(axis=2)
                mat = np.zeros((by_firm.shape[0], len(cols)))
                for t in range(by_firm.shape[0]):
                    np.add.at(mat[t], industry_idx, by_firm[t])
                pd.DataFrame(mat, columns=cols).to_hdf(
                    save_dir / file_name,
                    key=f"{country_name}_firms_gfcf_by_industry_real", mode="a",
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

        # Realised sales split by BUYER country: the origin-destination matrix, per good,
        # per timestep.  Trade proportions and the ROW split only *steer* clearing --
        # they "influence but do not strictly determine actual trade flows" -- so a run
        # that routes electricity geographically cannot be verified from the inputs.
        # It has to be measured on the output side, and nothing here previously carried
        # it: `exports_by_good_nominal` is summed over destinations, and the
        # per-destination series that *does* exist
        # (`economy.ts["exports_before_taxes_to_<c>"]`) is NOMINAL and lives only in the
        # multi-GB full save.
        #
        # REAL, and that is the point.  Cross-province electricity is a quantity claim
        # (CER's GW.h), and the nominal aggregates are dominated by ROW, so a nominal
        # series cannot answer "did province A actually ship electricity to province B".
        #
        # The DOMESTIC destination is included (`dest == country_name`), because the
        # export share is sales-abroad / sales-total and the denominator has to come from
        # the same series -- differencing against `firms_real_amount_sold` instead would
        # silently absorb any book-keeping gap into the domestic cell.  As a corollary,
        # summing these frames across destinations reproduces
        # `<country>_firms_real_amount_sold`, which is the identity check to run first.
        #
        # Every good, not just the linkage-owned ones: the frames are (timesteps x
        # industries) and there are n_countries per country, so the whole matrix is a few
        # MB, and scoping it to today's question would just have to be widened again for
        # the next one (C20 and hydrogen).
        try:
            import pandas as pd

            def _sales_by_destination(agent, cols, key_prefix):
                industry_idx = np.asarray(agent.states["Industry"])
                for dest in agent.all_country_names:
                    hist = agent.ts.historic("real_amount_sold_to_" + dest)
                    mat = np.zeros((len(hist), len(cols)))
                    for t, arr in enumerate(hist):
                        # Row 0 is the pre-simulation initial state and is NaN for every
                        # goods-market series; zero it so the frame is summable, and note
                        # that this makes row 0 a 0 where `firms_real_amount_sold` has NaN.
                        values = np.nan_to_num(np.asarray(arr, dtype=float).ravel())
                        np.add.at(mat[t], industry_idx, values)
                    pd.DataFrame(mat, columns=cols).to_hdf(
                        save_dir / file_name, key=f"{key_prefix}_sales_to_{dest}_real", mode="a"
                    )

            industry_cols = None
            for country_name, country in self.countries.items():
                industry_cols = list(country.firms.industries)
                _sales_by_destination(country.firms, industry_cols, country_name)
            # ROW's row of the same matrix: imports into each province BY SOURCE.
            # `row_imports_real` is summed over destinations, so it cannot say which
            # province the import leakage lands in -- the question the import limits were
            # added to answer.  ROW's seller transactors are per-exporter, not per-industry,
            # so they are aggregated through `states["Industry"]` exactly as firms are.
            if industry_cols is not None:
                _sales_by_destination(self.rest_of_the_world, industry_cols, "row")
        except Exception as exc:  # noqa: BLE001 - diagnostics are non-critical
            logging.getLogger(__name__).warning("Sales-by-destination export failed: %s", exc)

        # Units metadata. Mixed real/nominal units in this file have already caused one
        # round of invalid analysis (firm series are REAL, household/government/trade
        # series are NOMINAL), and the naming is not always a reliable guide -- the "CPI"
        # column is a price LEVEL despite coming from a method called
        # `total_cpi_inflation`. A suffix convention helps but does not cover the
        # per-country summary columns, so the units travel as data.
        try:
            import pandas as pd

            units = [
                # key or column, units, basis, note
                ("*_firms_production", "real", "quantity, base-year prices", "per-industry"),
                ("*_firms_production_nominal", "nominal LCU", "current prices", "production x price"),
                ("*_firms_gva_nominal", "nominal LCU", "current prices", "production x price - intermediate costs"),
                ("*_firms_used_intermediate_inputs_costs", "nominal LCU", "current prices", ""),
                ("*_firms_taxes_paid_on_production", "nominal LCU", "current prices", ""),
                ("*_firms_gfcf_by_industry_real", "real", "quantity, base-year prices", "capital bought BY investing industry"),
                ("*_firms_capital_bought_by_good_real", "real", "quantity, base-year prices", "indexed by good BOUGHT, summed over buyers"),
                ("*_firms_intermediate_bought_by_good_real", "real", "quantity, base-year prices", "indexed by good bought"),
                ("*_firms_price", "index", "price per unit", "production-weighted within industry"),
                ("*_firms_number_of_employees", "count", "headcount", "model units, not literal persons"),
                ("*_firms_total_wage", "nominal LCU", "current prices", ""),
                ("*_households_consumption_by_good_nominal", "nominal LCU", "current prices", "deflate by good price before comparing with real series"),
                ("*_households_investment_by_good_nominal", "nominal LCU", "current prices", "as above"),
                ("*_government_consumption_by_good_nominal", "nominal LCU", "current prices", "as above"),
                ("*_exports_by_good_nominal", "nominal LCU", "current prices", "as above"),
                ("*_imports_by_good_nominal", "nominal LCU", "current prices", "as above"),
                ("*_sales_to_<dest>_real", "real", "quantity, base-year prices",
                 "seller country's realised sales by industry to <dest>; sum over <dest> = *_firms_real_amount_sold"),
                ("row_sales_to_<dest>_real", "real", "quantity, base-year prices",
                 "ROW sales into <dest> by industry; sum over <dest> = row_imports_real"),
                ("row_imports_real", "real", "quantity", "ROW sales by industry"),
                ("row_desired_exports_real", "real", "quantity", "offered, before the import cap"),
                ("<country>", "mixed", "see per-column rows below", "per-country summary frame"),
                ("<country>:GDP Output", "nominal LCU", "current prices", ""),
                ("<country>:GDP Expenditure", "nominal LCU", "current prices", ""),
                ("<country>:GDP Income", "nominal LCU", "current prices", ""),
                ("<country>:GDP Output Real", "real LCU", "CPI-deflated, base = first timestep", "nominal / (cpi/cpi[0])"),
                ("<country>:GDP Expenditure Real", "real LCU", "CPI-deflated, base = first timestep", ""),
                ("<country>:GDP Income Real", "real LCU", "CPI-deflated, base = first timestep", ""),
                ("<country>:CPI", "index", "price LEVEL", "NOT a rate, despite the name"),
                ("<country>:PPI", "index", "price LEVEL", "NOT a rate"),
                ("<country>:CFPI", "index", "price LEVEL", "NOT a rate"),
                ("<country>:CPI Inflation Rate", "rate", "per timestep", "fraction, not percent"),
                ("<country>:PPI Inflation Rate", "rate", "per timestep", "fraction, not percent"),
                ("<country>:Unemployment Rate", "rate", "share of labour force", "fraction, not percent"),
                ("<country>:Central Bank Policy Rate", "rate", "per timestep", "fraction, not percent"),
                ("<country>:Imports", "nominal LCU", "current prices", "economy-wide total"),
                ("<country>:Exports", "nominal LCU", "current prices", "economy-wide total"),
                ("<country>_industries", "mapping", "index -> industry code", "row order matches the column order of every per-industry frame"),
            ]
            pd.DataFrame(units, columns=["key", "units", "basis", "note"]).to_hdf(
                save_dir / file_name, key="series_units", mode="a"
            )
        except Exception as exc:  # noqa: BLE001 - metadata is non-critical
            logging.getLogger(__name__).warning("Units metadata export failed: %s", exc)

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
