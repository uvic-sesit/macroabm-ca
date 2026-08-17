"""Household economic agent implementation.

This module implements household economic behavior through:
- Consumption and investment decisions
- Income generation and management
- Wealth accumulation and allocation
- Housing market participation
- Credit market interactions

The implementation handles:
- Household demographics
- Income sources (employment, transfers, rental, financial)
- Consumption patterns
- Investment decisions
- Property ownership
- Financial assets/liabilities
- Debt management
"""

import warnings
from typing import Any, Optional, Tuple

import h5py
import numpy as np
import pandas as pd

from macro_data import SyntheticCountry, SyntheticPopulation
from macro_data.readers.emission_fraction.emission_fraction_reader import EmissionFractions
from macromodel.agents.agent import Agent
from macromodel.agents.banks.banks import Banks
from macromodel.agents.households.household_properties import HouseholdType
from macromodel.agents.households.households_ts import create_households_timeseries
from macromodel.agents.households.utils.create_bundle_matrix import create_bundle_matrix
from macromodel.configurations import HouseholdsConfiguration
from macromodel.markets.credit_market.credit_market import CreditMarket
from macromodel.markets.goods_market.value_type import ValueType
from macromodel.timeseries import TimeSeries
from macromodel.util.function_mapping import functions_from_model, update_functions
from macromodel.util.get_histogram import get_histogram
from macromodel.util.property_mapping import map_to_enum


class Households(Agent):
    """Economic agent representing household sector behavior.

    This class implements household economic decisions through:
    - Income generation (employment, transfers, rental, financial)
    - Consumption allocation across industries
    - Investment in real and financial assets
    - Housing market participation (buying, renting)
    - Credit market interactions (mortgages, loans)
    - Wealth management and allocation

    The implementation considers:
    - Household demographics and composition
    - Income sources and distribution
    - Consumption patterns and preferences
    - Investment strategies
    - Property ownership and rental decisions
    - Financial asset holdings
    - Debt levels and servicing

    Attributes:
        functions (dict): Mapping of function names to implementations
        independents (list): Independent variables for calculations
        consumption_weights (np.ndarray): Industry-specific consumption shares
        consumption_weights_by_income (np.ndarray): Income-based consumption patterns
        investment_weights (np.ndarray): Industry-specific investment shares
        use_consumption_weights_by_income (bool): Whether to use income-based weights
    """

    def __init__(
        self,
        country_name: str,
        all_country_names: list[str],
        n_industries: int,
        functions: dict[str, Any],
        ts: TimeSeries,
        states: dict[str, float | np.ndarray | list[np.ndarray]],
        consumption_weights: np.ndarray,
        consumption_weights_by_income: np.ndarray,
        investment_weights: np.ndarray,
        use_consumption_weights_by_income: bool,
        independents: list[str],
        substitution_bundles: Optional[list] = None,
        emission_fractions: Optional[EmissionFractions] = None,
    ):
        """Initialize household economic agent.

        Args:
            country_name (str): Name of the country
            all_country_names (list[str]): List of all country names
            n_industries (int): Number of industries in the economy
            functions (dict[str, Any]): Function implementations for household behavior
            ts (TimeSeries): Time series data container
            states (dict): State variables and parameters
            consumption_weights (np.ndarray): Industry-specific consumption shares
            consumption_weights_by_income (np.ndarray): Income-based consumption patterns
            investment_weights (np.ndarray): Industry-specific investment shares
            use_consumption_weights_by_income (bool): Whether to use income-based weights
            independents (list[str]): Independent variables for calculations
            substitution_bundles (Optional[list]): Substitution bundle configuration for CES consumption
            emission_fractions (Optional[EmissionFractions]): Per-industry emission fraction multipliers
        """
        n_entities = ts.current("n_households")
        super().__init__(
            country_name,
            all_country_names,
            n_industries,
            n_entities,
            n_entities,
            ts,
            states,
            transactor_settings={
                "Buyer Value Type": ValueType.NOMINAL,
                "Seller Value Type": ValueType.NONE,
                "Buyer Priority": 0,
                "Seller Priority": 0,
            },
        )

        self.functions = functions

        self.independents = independents

        # Set initial values
        self.ts["saving_rates_histogram"] = get_histogram(self.get_saving_rates_by_household(), None)

        self.consumption_weights = consumption_weights
        self.consumption_weights_by_income = consumption_weights_by_income.astype(float)

        self.investment_weights = investment_weights

        self.use_consumption_weights_by_income = use_consumption_weights_by_income

        # Initialize substitution bundles and bundle matrix
        self.substitution_bundles = substitution_bundles if substitution_bundles is not None else []
        if len(self.substitution_bundles) > 0:
            self.bundle_matrix = create_bundle_matrix(np.array(self.substitution_bundles))
        else:
            self.bundle_matrix = None

        self.emission_fractions = emission_fractions

    @classmethod
    def from_pickled_agent(
        cls,
        synthetic_population: SyntheticPopulation,
        synthetic_country: SyntheticCountry,
        configuration: HouseholdsConfiguration,
        country_name: str,
        all_country_names: list[str],
        industries: list[str],
        initial_consumption_by_industry: np.ndarray,
        value_added_tax: float,
        scale: int,
        add_emissions: bool = False,
        emission_fractions: Optional[EmissionFractions] = None,
    ) -> "Households":
        """Create household agent from synthetic data.

        Initializes household agent using:
        - Synthetic population demographics
        - Country-specific parameters
        - Initial consumption/investment patterns
        - Tax rates and scaling factors

        Args:
            synthetic_population (SyntheticPopulation): Synthetic household data
            synthetic_country (SyntheticCountry): Country-specific parameters
            configuration (HouseholdsConfiguration): Household behavior config
            country_name (str): Name of the country
            all_country_names (list[str]): List of all country names
            industries (list[str]): List of industry names
            initial_consumption_by_industry (np.ndarray): Initial consumption
            value_added_tax (float): VAT rate
            scale (int): Scaling factor for histograms
            add_emissions (bool): Whether to track emissions
            emission_fractions (Optional[EmissionFractions]): Per-industry emission fraction multipliers

        Returns:
            Households: Initialized household agent
        """
        individual_ages = synthetic_population.individual_data["Age"].values

        corr_individuals = synthetic_population.household_data["Corresponding Individuals ID"]
        corr_individuals = corr_individuals.rename_axis("Household ID")

        corr_renters = synthetic_population.household_data["Corresponding Renters"]
        corr_renters = corr_renters.rename_axis("Household ID")

        functions = functions_from_model(model=configuration.functions, loc="macromodel.agents.households")

        hh_data = (
            synthetic_population.household_data.drop(
                columns=[
                    "Corresponding Individuals ID",
                    "Corresponding Renters",
                    "Corresponding Additionally Owned Houses ID",
                ]
            )
            .astype(float)
            .rename_axis("Household ID")
        )

        consumption_weights = synthetic_population.consumption_weights

        consumption_weights_by_income = synthetic_population.consumption_weights_by_income.T

        investment_weights = synthetic_population.investment_weights

        # Additional states
        states: dict[str, float | np.ndarray | list[np.ndarray] | Any] = {
            "saving_rates_model": synthetic_population.saving_rates_model,
            "social_transfers_model": synthetic_population.social_transfers_model,
            "wealth_distribution_model": synthetic_population.wealth_distribution_model,
            "average_saving_rate": synthetic_population.household_data["Saving Rate"].mean(),
            "coefficient_fa_income": synthetic_population.coefficient_fa_income,
            "investment_rate": synthetic_population.household_data["Investment Rate"].values,
        }

        # Additional states
        for state_name in [
            "Type",
            "Corresponding Bank ID",
            "Corresponding Inhabited House ID",
            "Corresponding Property Owner",
            "Tenure Status of the Main Residence",
        ]:
            if state_name not in hh_data.columns:
                raise ValueError(f"Missing {state_name} from the data for initialising households.")
            if state_name == "Type":
                states[state_name] = hh_data[state_name].values.flatten()
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter(action="ignore", category=RuntimeWarning)
                    states[state_name] = hh_data[state_name].fillna(-1).values.astype(int).flatten()
                    states[state_name][states[state_name] < 0] = -1

        # TODO: this is set to 0.2 in Sam's code, and transformed somehow into 0.0945. by the time the data is exported
        #  We need to 1. make this a parameters, 2. move this to the macro-data package.
        #  In general, we should think of where to put the piece of code below.

        investment_rate = synthetic_population.household_data["Investment Rate"].values
        # investment_weights = synthetic_country.industry_data["industry_vectors"]["Household Capital Inputs in LCU"]
        # investment_weights = investment_weights.values / investment_weights.values.sum()
        tau_cf = synthetic_country.tax_data.capital_formation_tax
        income = synthetic_population.household_data["Income"].values  # Income is different from Sam's

        initial_investment = pd.DataFrame(
            data=(1.0 / (1 + tau_cf) * np.outer(investment_weights, investment_rate * income).T),
            index=pd.Index(range(len(synthetic_population.household_data))),
            columns=pd.Index(synthetic_country.industries, name="Industry"),
        )

        tau_vat = synthetic_country.tax_data.value_added_tax

        consumption_by_industry_hh = 1 / (1 + tau_vat) * synthetic_population.industry_consumption_before_vat

        if add_emissions:
            consumption_emissions = synthetic_population.household_data["Consumption Emissions"].values
            investment_emissions = synthetic_population.household_data["Investment Emissions"].values
            consumption_emissions_by_good = np.zeros_like(industries, dtype=float)
            investment_emissions_by_good = np.zeros_like(industries, dtype=float)
            consumption_emissions_ch4_by_good = np.zeros_like(industries, dtype=float)
            investment_emissions_ch4_by_good = np.zeros_like(industries, dtype=float)
            coal_consumption_emissions = synthetic_population.household_data["Coal Consumption Emissions"].values
            gas_consumption_emissions = synthetic_population.household_data["Gas Consumption Emissions"].values
            oil_consumption_emissions = synthetic_population.household_data["Oil Consumption Emissions"].values
            refined_products_consumption_emissions = synthetic_population.household_data[
                "Refined Products Consumption Emissions"
            ].values
            coal_investment_emissions = synthetic_population.household_data["Coal Investment Emissions"].values
            gas_investment_emissions = synthetic_population.household_data["Gas Investment Emissions"].values
            oil_investment_emissions = synthetic_population.household_data["Oil Investment Emissions"].values
            refined_products_investment_emissions = synthetic_population.household_data[
                "Refined Products Investment Emissions"
            ].values
        else:
            consumption_emissions = None
            investment_emissions = None
            consumption_emissions_by_good = None
            investment_emissions_by_good = None
            consumption_emissions_ch4_by_good = None
            investment_emissions_ch4_by_good = None
            coal_consumption_emissions = None
            gas_consumption_emissions = None
            oil_consumption_emissions = None
            refined_products_consumption_emissions = None
            coal_investment_emissions = None
            gas_investment_emissions = None
            oil_investment_emissions = None
            refined_products_investment_emissions = None

        ts = create_households_timeseries(
            data=hh_data,
            initial_consumption_by_industry=initial_consumption_by_industry,
            initial_hh_investment=initial_investment.values,
            initial_investment_by_industry=synthetic_population.investment,
            initial_hh_consumption=consumption_by_industry_hh,
            scale=scale,
            vat=value_added_tax,
            tau_cf=tau_cf,
            consumption_emissions=consumption_emissions,
            investment_emissions=investment_emissions,
            consumption_emissions_by_good=consumption_emissions_by_good,
            investment_emissions_by_good=investment_emissions_by_good,
            consumption_emissions_ch4_by_good=consumption_emissions_ch4_by_good,
            investment_emissions_ch4_by_good=investment_emissions_ch4_by_good,
            coal_consumption_emissions=coal_consumption_emissions,
            gas_consumption_emissions=gas_consumption_emissions,
            oil_consumption_emissions=oil_consumption_emissions,
            refined_products_consumption_emissions=refined_products_consumption_emissions,
            coal_investment_emissions=coal_investment_emissions,
            gas_investment_emissions=gas_investment_emissions,
            oil_investment_emissions=oil_investment_emissions,
            refined_products_investment_emissions=refined_products_investment_emissions,
        )

        # Update the household type
        states["Type"] = map_to_enum(states["Type"], HouseholdType)

        # Corresponding individuals
        states["corr_individuals"] = list(corr_individuals.values)

        # Number of adults individuals in the household
        states["Number of Adults"] = np.array(
            [
                np.sum(individual_ages[states["corr_individuals"][hh_id]] >= 18)
                for hh_id in range(ts.current("n_households"))
            ]
        )

        # Corresponding renters
        states["corr_renters"] = [[int(x) for x in sublist if not pd.isna(x)] for sublist in corr_renters]

        use_consumption_weights_by_income = configuration.take_consumption_weights_by_income_quantile

        independents = configuration.functions.saving_rates.parameters["independents"]

        # TODO: corresponding additionally owned houses is not used

        return cls(
            country_name,
            all_country_names,
            len(industries),
            functions,
            ts,
            states,
            consumption_weights,
            consumption_weights_by_income,
            investment_weights,
            use_consumption_weights_by_income,
            independents,
            configuration.substitution_bundles,
            emission_fractions=emission_fractions,
        )

    def reset(self, configuration: HouseholdsConfiguration) -> None:
        """Reset household agent to initial state.

        Updates function implementations based on new configuration.

        Args:
            configuration (HouseholdsConfiguration): New household config
        """
        self.gen_reset()
        update_functions(functions=self.functions, model=configuration.functions, loc="macromodel.agents.households")

    def compute_employee_income(
        self,
        individual_income: np.ndarray,
        corr_households: np.ndarray,
    ) -> np.ndarray:
        """Calculate household income from employment.

        Aggregates individual employment income to household level.

        Args:
            individual_income (np.ndarray): Income by individual
            corr_households (np.ndarray): Individual-household mapping

        Returns:
            np.ndarray: Employment income by household
        """
        return np.bincount(
            corr_households,
            weights=individual_income,
            minlength=self.ts.current("n_households"),
        )

    def compute_expected_social_transfer_income(
        self,
        total_other_social_transfers: float,
        cpi: float,
        expected_inflation: float,
    ) -> np.ndarray:
        """Calculate expected social transfer income.

        Computes expected transfers based on:
        - Total transfer budget
        - Price level changes
        - Inflation expectations

        Args:
            total_other_social_transfers (float): Total transfer budget
            cpi (float): Current price index
            expected_inflation (float): Expected inflation rate

        Returns:
            np.ndarray: Expected transfers by household
        """
        inds = self.independents
        return (
            (1 + expected_inflation)
            * cpi
            * self.functions["social_transfers"].get_social_transfers(
                n_households=self.ts.current("n_households"),
                total_other_social_transfers=total_other_social_transfers,
                current_independents=(
                    np.array([])
                    if len(inds) == 0
                    else np.stack(
                        [self.ts.current(ind.lower()) for ind in inds],
                        axis=1,
                    )
                ),
                initial_independents=(
                    np.array([])
                    if len(inds) == 0
                    else np.stack(
                        [self.ts.initial(ind.lower()) for ind in inds],
                        axis=1,
                    )
                ),
                model=self.states["social_transfers_model"],
            )
        )

    def compute_social_transfer_income(
        self,
        total_other_social_transfers: float,
        cpi: float,
    ) -> np.ndarray:
        """Calculate current social transfer income.

        Computes actual transfers based on:
        - Total transfer budget
        - Current price level

        Args:
            total_other_social_transfers (float): Total transfer budget
            cpi (float): Current price index

        Returns:
            np.ndarray: Current transfers by household
        """
        inds = self.independents
        return cpi * self.functions["social_transfers"].get_social_transfers(
            n_households=self.ts.current("n_households"),
            total_other_social_transfers=total_other_social_transfers,
            current_independents=(
                np.array([])
                if len(inds) == 0
                else np.stack(
                    [self.ts.current(ind.lower()) for ind in inds],
                    axis=1,
                )
            ),
            initial_independents=(
                np.array([])
                if len(inds) == 0
                else np.stack(
                    [self.ts.initial(ind.lower()) for ind in inds],
                    axis=1,
                )
            ),
            model=self.states["social_transfers_model"],
        )

    def compute_rental_income(
        self,
        housing_data: pd.DataFrame,
        income_taxes: float,
    ) -> np.ndarray:
        """Calculate rental income from property ownership.

        Computes after-tax rental income from:
        - Rented properties
        - Current rent levels
        - Tax rates

        Args:
            housing_data (pd.DataFrame): Property market data
            income_taxes (float): Income tax rate

        Returns:
            np.ndarray: Rental income by household
        """
        housing_data_rented_out = housing_data.loc[
            np.logical_and(
                housing_data["Is Owner-Occupied"] == 0,
                housing_data["Corresponding Inhabitant Household ID"] != -1,
            )
        ]
        housing_data_rented_out_grouped = housing_data_rented_out.groupby("Corresponding Owner Household ID")[
            "Rent"
        ].sum()
        rental_income = np.zeros(self.ts.current("n_households"))
        rental_income[housing_data_rented_out_grouped.index.values] = (
            1 - income_taxes
        ) * housing_data_rented_out_grouped.values
        return rental_income

    def compute_expected_income_from_financial_assets(self) -> np.ndarray:
        """Calculate expected income from financial assets.

        Estimates future financial income based on:
        - Asset holdings
        - Return coefficients
        - Historical patterns

        Returns:
            np.ndarray: Expected financial income by household
        """
        return self.functions["financial_assets"].compute_expected_income(
            income_coefficient=self.states["coefficient_fa_income"],
            initial_other_financial_assets=self.ts.initial("wealth_other_financial_assets"),
            current_other_financial_assets=self.ts.current("wealth_other_financial_assets"),
        )

    def compute_income_from_financial_assets(self) -> np.ndarray:
        """Calculate current income from financial assets.

        Computes actual financial income based on:
        - Current asset holdings
        - Realized returns
        - Income coefficients

        Returns:
            np.ndarray: Current financial income by household
        """
        return self.functions["financial_assets"].compute_income(
            income_coefficient=self.states["coefficient_fa_income"],
            initial_other_financial_assets=self.ts.initial("wealth_other_financial_assets"),
            current_other_financial_assets=self.ts.current("wealth_other_financial_assets"),
        )

    def compute_expected_income(self) -> np.ndarray:
        """Calculate total expected income.

        Aggregates expected income from all sources:
        - Employment
        - Social transfers
        - Rental income
        - Financial assets

        Returns:
            np.ndarray: Total expected income by household
        """
        return (
            self.ts.current("expected_income_employee")
            + self.ts.current("expected_income_social_transfers")
            + self.ts.current("income_rental")
            + self.ts.current("expected_income_financial_assets")
        )

    def compute_income(self) -> np.ndarray:
        """Calculate total current income.

        Aggregates current income from all sources:
        - Employment
        - Social transfers
        - Rental income
        - Financial assets

        Returns:
            np.ndarray: Total current income by household
        """
        return (
            self.ts.current("income_employee")
            + self.ts.current("income_social_transfers")
            + self.ts.current("income_rental")
            + self.ts.current("income_financial_assets")
        )

    def get_saving_rates_by_household(self) -> np.ndarray:
        """Calculate household-specific saving rates.

        Determines saving rates based on:
        - Average saving behavior
        - Household characteristics
        - Economic conditions

        Returns:
            np.ndarray: Saving rates by household
        """
        inds = self.independents
        if len(inds) > 0:
            current_independents = np.stack(
                [self.ts.current(ind.lower()) for ind in inds],
                axis=1,
            )
            initial_independents = np.stack(
                [self.ts.initial(ind.lower()) for ind in inds],
                axis=1,
            )
        else:
            current_independents = np.array([])
            initial_independents = np.array([])
        return self.functions["saving_rates"].get_saving_rates(
            n_households=self.ts.current("n_households"),
            average_saving_rate=self.states["average_saving_rate"],
            current_independents=current_independents,
            initial_independents=initial_independents,
            model=self.states["saving_rates_model"],
        )

    def compute_target_consumption(
        self,
        expected_inflation: float,
        current_cpi: float,
        initial_cpi: float,
        exogenous_total_consumption: float,
        per_capita_unemployment_benefits: float,
        tau_vat: float,
        assume_zero_growth: bool,
        income_tax: float = 0.0,
        employee_social_insurance_tax: float = 0.0,
        prices: Optional[np.ndarray] = None,
        initial_prices: Optional[np.ndarray] = None,
        taxes: Optional[np.ndarray] = None,
        initial_taxes: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Calculate target consumption levels.

        Determines desired consumption based on:
        - Income and saving rates
        - Price level changes
        - Benefit levels
        - Growth assumptions
        - Tax rates
        - CES substitution within bundles (if enabled)

        Args:
            expected_inflation (float): Expected inflation rate
            current_cpi (float): Current price index
            initial_cpi (float): Initial price index
            exogenous_total_consumption (float): External consumption target
            per_capita_unemployment_benefits (float): Per person benefits
            tau_vat (float): Value added tax rate
            assume_zero_growth (bool): Whether to assume no growth
            prices (Optional[np.ndarray]): Current prices by industry for CES substitution
            initial_prices (Optional[np.ndarray]): Initial prices by industry for CES substitution
            taxes (Optional[np.ndarray]): Current tax rates by industry for CES substitution
            initial_taxes (Optional[np.ndarray]): Initial tax rates by industry for CES substitution

        Returns:
            np.ndarray: Target consumption by household
        """
        saving_rates = self.get_saving_rates_by_household()
        self.ts.saving_rates_histogram.append(get_histogram(saving_rates, None))

        # Target consumption
        if assume_zero_growth:
            return np.outer(
                self.ts.initial("consumption"),
                self.states["consumption_weights_data"],
            ).astype(float)
        else:
            return self.functions["consumption"].compute_target_consumption(
                expected_inflation=expected_inflation,
                current_cpi=current_cpi,
                initial_cpi=initial_cpi,
                historic_consumption_sum=np.array(self.ts.historic("consumption")),
                saving_rates=saving_rates,
                income=self.ts.current("expected_income"),
                household_benefits=self.states["Number of Adults"] * per_capita_unemployment_benefits
                + self.ts.current("expected_income_social_transfers"),
                consumption_weights=self.consumption_weights,
                consumption_weights_by_income=self.consumption_weights_by_income,
                exogenous_total_consumption=exogenous_total_consumption,
                current_time=len(self.ts.historic("total_consumption")),
                take_consumption_weights_by_income_quantile=self.use_consumption_weights_by_income,
                tau_vat=tau_vat,
                prices=prices,
                initial_prices=initial_prices,
                taxes=taxes,
                initial_taxes=initial_taxes,
                bundle_matrix=self.bundle_matrix,
                income_tax=income_tax,
                employee_social_insurance_tax=employee_social_insurance_tax,
                employee_income=self.ts.current("expected_income_employee"),
                financial_income=self.ts.current("expected_income_financial_assets"),
            )

    def anchor_energy_quantities(
        self,
        targets: dict[int, float],
        prices: dict[int, float],
        max_step: float = 2.0,
        increments: dict[int, float] | None = None,
        energy_indices: list[int] | None = None,
    ) -> None:
        """Pin households' REAL consumption of a good to an external quantity path.

        ``apply_energy_share_increments`` sets a nominal budget weight, which does not
        pin a real quantity once relative prices move -- and under CER's exogenous price
        path they move a long way.  Electricity's real price falls to 74.3% of a CPI the
        model generates itself (CER supplies the electricity price, the model's CPI is
        driven by fossil prices), so households buy roughly 1/0.743 more of it than the
        share implies.  Measured against CER residential: +16.0% vs +1.2% under Current
        Measures and +61.1% vs +5.7% under Net-zero, with the budget share actually
        FALLING 5.6% in the latter.  Setting shares cannot fix that; the target has to be
        the quantity.

        This is the household analogue of ``linkage_owns_coefficients`` for firms: CER
        owns the quantity path, the model owns everything else.

        Args:
            targets: {industry index: desired real quantity as an index on the anchor}.
            prices: {industry index: that good's current price}, to convert the observed
                nominal spend into a real quantity.
            max_step: per-call bound on the weight adjustment.  The correction reads last
                period's realised consumption, so it is one step behind; the bound stops
                a large price jump turning that lag into an overshoot.
            increments: {industry index: change in this good's demand as a SHARE of total
                residential anchor-year energy demand}.  The additive alternative to an
                index, for fuels whose external base-year quantity is too small to divide
                by -- the household counterpart of ``Firms.anchor_energy_quantities``'s
                increments, and see that method for why an index fails there.  Converted
                to model units with households' OWN anchor-year energy consumption:
                ``desired = anchor(j) + delta * total anchor energy``.
            energy_indices: the good indices making up that energy total.  It must be the
                WHOLE energy set the caller's denominator covers, not merely the goods
                being anchored, or the increment changes meaning between the two sides.
                Required for *increments*, ignored otherwise.
        """
        if not (targets or increments) or not prices:
            return
        try:
            nominal = np.asarray(self.ts.current("industry_consumption"), dtype=float).ravel()
        except Exception:  # noqa: BLE001 - before the first step there is nothing to read
            return
        if nominal.size == 0:
            return

        if not hasattr(self, "_energy_quantity_anchor"):
            self._energy_quantity_anchor = {}
        # The correction must be CUMULATIVE and stored, because
        # apply_energy_share_increments rebuilds the weights from their anchor on every
        # milestone.  A per-call multiplier would be discarded by that rebuild and the
        # weight would oscillate between corrected and uncorrected: the correction lands,
        # consumption comes back on target, the next call therefore computes a step of
        # 1.0, the rebuild drops the old factor, and consumption overshoots again.
        if not hasattr(self, "_energy_quantity_multiplier"):
            self._energy_quantity_multiplier = {}
        if not hasattr(self, "_energy_quantity_anchor_total"):
            self._energy_quantity_anchor_total: float | None = None

        weights = np.array(self.consumption_weights, dtype=float, copy=True)
        by_income = np.array(self.consumption_weights_by_income, dtype=float, copy=True)
        n_industries = int(weights.shape[0])

        # One entry per good.  An increment WINS over an index for the same good: the
        # index is precisely what the caller's guard rejected for it.
        specs: dict[int, tuple[str, float]] = {
            int(j): ("index", float(v)) for j, v in targets.items()
        }
        for j, delta in (increments or {}).items():
            specs[int(j)] = ("increment", float(delta))

        def _realised(j: int) -> float | None:
            price = float(prices.get(j, 0.0))
            if j >= nominal.size or price <= 0.0:
                return None
            q = float(nominal[j]) / price
            return q if np.isfinite(q) and q > 0.0 else None

        # Anchors first, so the energy total is captured on the same call as the
        # per-good anchors it is the sum of -- and BEFORE any correction lands, or the
        # increment would be scaled by a denominator this method had already moved.
        # On EVERY call, not only calls carrying an increment: the first increment
        # necessarily arrives a milestone after the first call, because at the anchor
        # year the external level change is zero by construction, and by then the total
        # would no longer be the anchor-year one the increment was derived against.
        if energy_indices:
            for j in [int(k) for k in energy_indices]:
                q = _realised(j)
                if q is not None:
                    self._energy_quantity_anchor.setdefault(j, q)
            if self._energy_quantity_anchor_total is None:
                self._energy_quantity_anchor_total = float(
                    sum(self._energy_quantity_anchor.get(int(k), 0.0) for k in energy_indices)
                )

        for j, (kind, value) in specs.items():
            if not np.isfinite(value) or (kind == "index" and value <= 0.0):
                continue
            realised = _realised(j)
            if realised is None:
                continue
            anchor = self._energy_quantity_anchor.setdefault(j, realised)
            if anchor <= 0.0:
                continue
            if kind == "index":
                desired = anchor * value
            else:
                total = float(self._energy_quantity_anchor_total or 0.0)
                if not np.isfinite(total) or total <= 0.0:
                    continue
                desired = anchor + value * total
            if not np.isfinite(desired) or desired <= 0.0:
                # A negative increment big enough to zero the good out: let the step
                # bound below walk the weight down instead of writing a non-positive one.
                desired = anchor * (1.0 / max_step)
            # `realised` already embeds the multiplier in force last period, so the ratio
            # is the ADDITIONAL factor needed and compounds onto the stored one.
            step = float(min(max(desired / realised, 1.0 / max_step), max_step))
            mult = float(self._energy_quantity_multiplier.get(j, 1.0)) * step
            mult = float(min(max(mult, 1e-3), 1e3))
            self._energy_quantity_multiplier[j] = mult
            weights[j] *= mult
            axes = [a for a, size in enumerate(by_income.shape) if size == n_industries]
            if axes:
                moved = np.moveaxis(by_income, axes[0], 0)
                moved[j] *= mult
                by_income = np.moveaxis(moved, 0, axes[0])

        self.consumption_weights = weights
        self.consumption_weights_by_income = by_income

    def apply_energy_share_increments(
        self,
        increments: dict[int, float],
        relative_prices: dict[int, float] | None = None,
        loss_rates: dict[int, float] | None = None,
    ) -> None:
        """Shift the household budget between energy goods by CER's own share changes.

        Households allocate spending with a FIXED ``consumption_weights`` vector, so
        nothing in the energy linkage reaches them: firms' coefficients follow CER while
        households' fuel mix stays frozen at its base year.  Measured consequence -- real
        household electricity consumption falls 13.5% over 2020-2035 against CER
        residential at +1.2%.

        This is the household analogue of ``additive_intensity`` on the firm side: CER's
        ABSOLUTE change in a fuel's share of residential energy, scaled by the household
        energy budget at the anchor, is added to that good's weight.  Increments across
        fuels sum to ~zero (they are shares of the same total), so the energy block's
        share of the budget is preserved and non-energy weights are untouched; the block
        is renormalised to absorb rounding.  Weights are floored at zero.

        ``consumption_weights`` are NOMINAL budget shares, so a fixed weight buys more
        real quantity as a good becomes relatively cheaper -- measured under CER's
        exogenous prices as household electricity rising +43.1% real against +75.5%
        nominal. CER's shares are PJ shares, i.e. real. Passing ``relative_prices``
        converts the real target to the nominal weight that delivers it
        (``weight ~ real_share x price``), so households buy CER's mix rather than
        whatever the price wedge implies.

        Args:
            increments: {industry index: change in that fuel's share of residential
                energy since the anchor year}.
            relative_prices: {industry index: that good's price relative to its anchor-year
                price}. Omitted => weights are treated as real shares directly (previous
                behaviour).
            loss_rates: {industry index: transmission loss rate}. Applied to the REAL
                share target, before the price conversion -- households must purchase
                more than they consume because some is lost in transmission. Applying it
                to the finished nominal weight instead double-counts against the price
                conversion: measured as household electricity jumping +10.9% -> +35.9%
                from a 7.5% gross-up.
        """
        if not increments and not loss_rates:
            return
        # A fuel with a loss rate but no share increment still needs grossing up, so the
        # index set is the union.  Keying off `increments` alone would drop the loss
        # silently in any region where CER happens to report no residential share change.
        increments = dict(increments or {})
        for j in loss_rates or {}:
            increments.setdefault(int(j), 0.0)
        idx = sorted(increments)
        if not hasattr(self, "_energy_weight_anchor"):
            self._energy_weight_anchor = {
                "flat": np.array(self.consumption_weights, dtype=float, copy=True),
                "by_income": np.array(self.consumption_weights_by_income, dtype=float, copy=True),
            }

        n_industries = int(np.asarray(self.consumption_weights).shape[0])
        for key, target in (
            ("flat", "consumption_weights"),
            ("by_income", "consumption_weights_by_income"),
        ):
            anchor = self._energy_weight_anchor[key]
            current = np.array(anchor, dtype=float, copy=True)
            if anchor.ndim == 1:
                block = float(anchor[idx].sum())
                if block <= 0.0:
                    continue
                for j in idx:
                    real_target = anchor[j] + block * float(increments[j])
                    if relative_prices:
                        real_target *= float(relative_prices.get(j, 1.0))
                    current[j] = max(0.0, real_target)
                new_block = current[idx].sum()
                if new_block > 0.0:
                    current[idx] *= block / new_block
                # Losses are applied AFTER renormalisation.  Inside the loop they would be
                # scaled straight back out, since the block is renormalised to its anchor
                # total -- correct for share increments (fuel shares are of one total),
                # wrong for losses, which legitimately raise energy's share of the budget:
                # households must buy more to consume the same.
                for j in idx:
                    rate = float((loss_rates or {}).get(j, 0.0))
                    if 0.0 < rate < 0.9:
                        current[j] /= 1.0 - rate
            else:
                # The by-income weights are (industries x income quantiles) -- industries
                # are NOT on the last axis.  Locate the industry axis rather than assume
                # it; guessing wrong is an IndexError at best and silent mis-indexing at
                # worst if the two dimensions ever coincide.
                axes = [a for a, size in enumerate(anchor.shape) if size == n_industries]
                if not axes:
                    continue
                ax = axes[0]
                moved = np.moveaxis(current, ax, 0)
                anchor_moved = np.moveaxis(anchor, ax, 0)
                block = anchor_moved[idx].sum(axis=0)
                if not np.any(block > 0.0):
                    continue
                for j in idx:
                    real_target = anchor_moved[j] + block * float(increments[j])
                    if relative_prices:
                        real_target = real_target * float(relative_prices.get(j, 1.0))
                    moved[j] = np.maximum(0.0, real_target)
                new_block = moved[idx].sum(axis=0)
                scale = np.divide(block, new_block, out=np.ones_like(block), where=new_block > 0.0)
                moved[idx] *= scale
                # See the flat-vector branch: after renormalisation, not inside it.
                for j in idx:
                    rate = float((loss_rates or {}).get(j, 0.0))
                    if 0.0 < rate < 0.9:
                        moved[j] = moved[j] / (1.0 - rate)
                current = np.moveaxis(moved, 0, ax)
            setattr(self, target, current)

    def compute_target_investment(
        self,
        expected_inflation: float,
        current_cpi: float,
        initial_cpi: float,
        exogenous_total_investment: float,
        tau_cf: float,
        assume_zero_growth: bool,
        good_prices: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Calculate target investment levels.

        Determines desired investment based on:
        - Income and investment rates
        - Price level changes
        - External targets
        - Growth assumptions
        - Tax rates

        Args:
            expected_inflation (float): Expected inflation rate
            current_cpi (float): Current price index
            initial_cpi (float): Initial price index
            exogenous_total_investment (float): External investment target
            tau_cf (float): Capital formation tax rate
            assume_zero_growth (bool): Whether to assume no growth

        Returns:
            np.ndarray: Target investment by household
        """
        if assume_zero_growth:
            return self.ts.initial("investment").astype(float)
        else:
            return self.functions["investment"].compute_target_investment(
                expected_inflation=expected_inflation,
                current_cpi=current_cpi,
                initial_cpi=initial_cpi,
                income=self.ts.current("expected_income"),
                exogenous_total_investment=exogenous_total_investment,
                current_time=len(self.ts.historic("total_investment")),
                investment_weights=self.investment_weights,
                investment_rate=self.states["investment_rate"],
                tau_cf=tau_cf,
                good_prices=good_prices,
            )

    def prepare_housing_market_clearing(
        self,
        housing_data: pd.DataFrame,
        observed_fraction_value_price: np.ndarray,
        observed_fraction_rent_value: np.ndarray,
        expected_hpi_growth: float,
        assumed_mortgage_maturity: int,
        rental_income_taxes: float,
    ) -> None:
        """Prepare for housing market clearing.

        Sets up housing market participation through:
        - Property demand decisions
        - Price/rent willingness
        - Sale listings
        - Rental offerings

        Args:
            housing_data (pd.DataFrame): Property market data
            observed_fraction_value_price (np.ndarray): Price/value ratios
            observed_fraction_rent_value (np.ndarray): Rent/value ratios
            expected_hpi_growth (float): Expected house price growth
            assumed_mortgage_maturity (int): Mortgage term length
            rental_income_taxes (float): Tax rate on rental income
        """
        if len(housing_data) == 0:
            return

        # Households make decisions on their demand for properties
        (
            max_price_willing_to_pay,
            max_rent_willing_to_pay,
            households_hoping_to_move,
        ) = self.functions["property"].compute_demand(
            housing_data=housing_data,
            household_residence_tenure_status=self.states["Tenure Status of the Main Residence"],
            household_income=self.ts.current("expected_income"),
            household_financial_wealth=self.ts.current("wealth_financial_assets"),
            observed_fraction_value_price=observed_fraction_value_price,
            observed_fraction_rent_value=observed_fraction_rent_value,
            expected_hpi_growth=expected_hpi_growth,
            assumed_mortgage_maturity=assumed_mortgage_maturity,
            rental_income_taxes=rental_income_taxes,
        )
        self.ts.max_price_willing_to_pay.append(max_price_willing_to_pay)
        self.ts.max_rent_willing_to_pay.append(max_rent_willing_to_pay)

        # Set price of properties of households that are hoping to move
        ind_mhr_temp_sale = housing_data["Corresponding Owner Household ID"].isin(households_hoping_to_move)
        housing_data.loc[np.logical_not(ind_mhr_temp_sale), "Sale Price"] = np.nan
        ind_still_on_sale = housing_data["Temporarily for Sale"].copy()
        housing_data["Temporarily for Sale"] = False
        housing_data.loc[ind_mhr_temp_sale, "Temporarily for Sale"] = True
        housing_data.loc[
            np.logical_and(ind_mhr_temp_sale, np.logical_not(ind_still_on_sale)),
            "Sale Price",
        ] = self.functions["property"].compute_initial_sale_price(
            property_values=housing_data.loc[
                np.logical_and(ind_mhr_temp_sale, np.logical_not(ind_still_on_sale)),
                "Value",
            ],
        )
        housing_data.loc[np.logical_and(ind_mhr_temp_sale, ind_still_on_sale), "Sale Price"] = self.functions[
            "property"
        ].compute_updated_sale_price(
            sale_prices=housing_data.loc[
                np.logical_and(ind_mhr_temp_sale, ind_still_on_sale),
                "Sale Price",
            ],
        )

        # Set what's up for rent
        prev_up_for_rent = housing_data["Up for Rent"].values
        now_up_for_rent = np.where(np.isnan(housing_data["Corresponding Inhabitant Household ID"].values))[0]
        newly_up_for_rent = [ind for ind in now_up_for_rent if ind not in prev_up_for_rent]
        housing_data["Up for Rent"] = False
        housing_data.loc[now_up_for_rent, "Up for Rent"] = True
        housing_data["Newly on the Rental Market"] = False
        housing_data.loc[newly_up_for_rent, "Newly on the Rental Market"] = True
        not_newly_up_for_rent = np.logical_and(
            np.logical_not(housing_data["Newly on the Rental Market"]),
            housing_data["Up for Rent"],
        )

        # Calculate rent
        housing_data.loc[housing_data["Newly on the Rental Market"], "Rent"] = self.functions[
            "property"
        ].compute_offered_rent_for_new_properties(
            property_value=housing_data.loc[housing_data["Newly on the Rental Market"], "Value"].values,
            observed_fraction_rent_value=observed_fraction_rent_value,
        )
        housing_data.loc[not_newly_up_for_rent, "Rent"] = self.functions[
            "property"
        ].compute_offered_rent_for_existing_properties(
            current_offered_rent=housing_data.loc[not_newly_up_for_rent, "Rent"].values,
        )

    def update_rent(
        self,
        housing_data: pd.DataFrame,
        historic_inflation: list[np.ndarray],
        exogenous_inflation_before: np.ndarray,
    ) -> None:
        """Update rental prices.

        Adjusts rents based on:
        - Historical inflation
        - External price changes
        - Market conditions

        Args:
            housing_data (pd.DataFrame): Property market data
            historic_inflation (list[np.ndarray]): Past inflation rates
            exogenous_inflation_before (np.ndarray): External inflation
        """
        housing_data["Rent"] = self.functions["property"].compute_rent(
            current_rent=housing_data["Rent"].values,
            historic_inflation=np.concatenate(
                (
                    exogenous_inflation_before,
                    np.array(historic_inflation).flatten(),
                )
            ),
        )

    def process_housing_market_clearing(
        self,
        housing_data: pd.DataFrame,
        social_housing_function: Any,
        current_sales: pd.DataFrame,
        current_unemployment_benefits_by_individual: float,
    ) -> None:
        """Process housing market clearing results.

        Updates housing market outcomes:
        - Rent payments
        - Property purchases
        - Social housing allocation
        - Market transactions

        Args:
            housing_data (pd.DataFrame): Property market data
            social_housing_function (Any): Social housing allocator
            current_sales (pd.DataFrame): Market transactions
            current_unemployment_benefits_by_individual (float): Benefits
        """
        # Calculate rent
        rent_by_household, imputed_rent_by_household = self.compute_rent(
            housing_data=housing_data,
            social_housing_function=social_housing_function,
            current_unemployment_benefits_by_individual=current_unemployment_benefits_by_individual,
        )
        self.ts.rent.append(rent_by_household)
        self.ts.rent_imputed.append(imputed_rent_by_household)

        # Calculate the price paid for property
        price_paid_for_property = np.zeros(self.ts.current("n_households"))
        if len(current_sales) > 0:
            price_paid_for_property[current_sales["buyer_id"].values] = current_sales["price_or_rent"].values
        self.ts.price_paid_for_property.append(price_paid_for_property)

    def compute_rent(
        self,
        housing_data: pd.DataFrame,
        social_housing_function: Any,
        current_unemployment_benefits_by_individual: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Calculate rent payments and imputed rent.

        Determines:
        - Actual rent for renters
        - Social housing rent
        - Imputed rent for owners

        Args:
            housing_data (pd.DataFrame): Property market data
            social_housing_function (Any): Social housing allocator
            current_unemployment_benefits_by_individual (float): Benefits

        Returns:
            tuple[np.ndarray, np.ndarray]: Rent paid and imputed rent
        """
        rent_by_household = np.zeros(self.ts.current("n_households"))
        imputed_rent_by_household = np.zeros(self.ts.current("n_households"))

        # Households in social housing
        ind_social_housing = np.where(self.states["Corresponding Inhabited House ID"] == -1)[0]
        social_housing_rent = social_housing_function.compute_social_housing_rent(
            current_unemployment_benefits_by_individual=current_unemployment_benefits_by_individual,
            current_household_size=self.states["Number of Adults"][ind_social_housing],
        )
        rent_by_household[ind_social_housing] = social_housing_rent
        self.states["Rent paid to Government"] = social_housing_rent.sum()

        # Households renting
        ind_renting = np.all(
            [
                self.states["Tenure Status of the Main Residence"] == 3,
                self.states["Corresponding Inhabited House ID"] != -1,
            ],
            axis=0,
        )

        rent = housing_data.loc[
            self.states["Corresponding Inhabited House ID"][ind_renting],
            "Rent",
        ].values
        rent_by_household[ind_renting] = rent

        # Households owning
        ind_owning = np.all(
            [
                np.isin(self.states["Tenure Status of the Main Residence"], [1, 2, 4]),
                self.states["Corresponding Inhabited House ID"] != -1,
            ],
            axis=0,
        )

        rent = housing_data.loc[
            self.states["Corresponding Inhabited House ID"][ind_owning],
            "Rent",
        ].values
        imputed_rent_by_household[ind_owning] = rent

        return rent_by_household, imputed_rent_by_household

    def compute_target_credit(self, current_sales: pd.DataFrame) -> None:
        """Calculate target credit demand.

        Determines credit needs for:
        - Consumption financing
        - Property purchases
        - Debt management

        Args:
            current_sales (pd.DataFrame): Property transactions
        """
        # Target consumption loans to cover immediate financing gaps
        self.ts.target_consumption_loans.append(
            self.functions["target_credit"].compute_target_consumption_loans(
                target_consumption=self.ts.current("target_consumption"),
                income=self.ts.current("expected_income"),
                rent=self.ts.current("rent"),
                wealth_in_financial_assets=self.ts.current("wealth_financial_assets"),
            )
        )
        self.ts.total_target_consumption_loans.append([self.ts.current("target_consumption_loans").sum()])

        # Mortgages
        target_house_price = np.zeros(self.ts.current("n_households"))
        if len(current_sales) > 0:
            target_house_price[current_sales["buyer_id"].values] = current_sales["price_or_rent"].values
        self.ts.target_mortgage.append(
            self.functions["target_credit"].compute_target_mortgage(
                target_house_price=target_house_price,
                target_consumption=self.ts.current("target_consumption"),
                income=self.ts.current("expected_income"),
                rent=self.ts.current("rent"),
                wealth_in_financial_assets=self.ts.current("wealth_financial_assets"),
            )
        )
        self.ts.total_target_mortgage.append([self.ts.current("target_mortgage").sum()])

    def compute_interest_paid_on_deposits(
        self,
        bank_interest_rate_on_household_deposits: np.ndarray,
        bank_overdraft_rate_on_household_deposits: np.ndarray,
    ) -> np.ndarray:
        """Calculate interest paid on deposits.

        Computes interest flows based on:
        - Deposit balances
        - Interest rates
        - Overdraft conditions

        Args:
            bank_interest_rate_on_household_deposits (np.ndarray): Deposit rates
            bank_overdraft_rate_on_household_deposits (np.ndarray): Overdraft rates

        Returns:
            np.ndarray: Interest paid by household
        """
        return -bank_interest_rate_on_household_deposits[self.states["Corresponding Bank ID"]] * np.maximum(
            0.0, self.ts.current("wealth_deposits")
        ) - bank_overdraft_rate_on_household_deposits[self.states["Corresponding Bank ID"]] * np.minimum(
            0.0, self.ts.current("wealth_deposits")
        )

    def compute_interest_paid(self) -> np.ndarray:
        """Calculate total interest paid.

        Aggregates interest payments on:
        - Deposits
        - Loans
        - Credit facilities

        Returns:
            np.ndarray: Total interest paid by household
        """
        return self.ts.current("interest_paid_on_loans") + self.ts.current("interest_paid_on_deposits")

    def prepare_goods_market_clearing(
        self,
        exchange_rate_usd_to_lcu: float,
    ) -> None:
        """Prepare for goods market clearing.

        Sets up market participation through:
        - Exchange rate adjustment
        - Purchase preparation
        - Sale preparation

        Args:
            exchange_rate_usd_to_lcu (float): USD to local currency rate
        """
        # Exchange rates
        self.set_exchange_rate(exchange_rate_usd_to_lcu)

        # Prepare goods market clearing
        self.prepare_buying_goods()
        self.prepare_selling_goods()

    def prepare_buying_goods(self) -> None:
        """Prepare goods purchase decisions.

        Sets up buying based on:
        - Target consumption
        - Target investment
        - Exchange rates
        """
        self.set_goods_to_buy(
            1.0
            / self.exchange_rate_usd_to_lcu
            * (self.ts.current("target_consumption") + self.ts.current("target_investment"))
        )

    def prepare_selling_goods(self) -> None:
        """Prepare goods sale decisions.

        Sets up selling based on:
        - Available goods
        - Price levels
        """
        self.set_goods_to_sell(np.zeros(self.ts.current("n_households")))
        self.set_prices(np.zeros(self.ts.current("n_households")))

    def update_consumption_and_investment(
        self,
        tau_vat: float,
        tau_cf: float,
        add_emissions: bool = False,
        readjusted_factors: Optional[np.ndarray] = None,
        emitting_indices: Optional[np.ndarray] = None,
        readjusted_factors_ch4: Optional[np.ndarray] = None,
        emitting_indices_ch4: Optional[np.ndarray] = None,
        use_emission_multiplier: bool = False,
        b06_oil_emission_share: Optional[float] = None,
    ) -> None:
        """Update consumption and investment outcomes.

        Records actual:
        - Consumption spending
        - Investment spending
        - Tax payments
        - Emissions data

        Args:
            tau_vat (float): Value added tax rate
            tau_cf (float): Capital formation tax rate
            add_emissions (bool): Whether to track emissions
            readjusted_factors (Optional[np.ndarray]): CO2 emission factors
            emitting_indices (Optional[np.ndarray]): CO2 emitting sector indices
            readjusted_factors_ch4 (Optional[np.ndarray]): CH4 emission factors
            emitting_indices_ch4 (Optional[np.ndarray]): CH4 emitting sector indices
            use_emission_multiplier (bool): Whether to apply industry-specific fraction multipliers
        """

        def _fuel_series(disagg: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            """(col_1, col_2, refined) per the legacy column labelling, scheme-aware.

            Legacy 4-column path: returns columns 1, 2, 3 untouched (their historical
            labels are kept even though the emitting order is B05a, B05b=gas, B05c=oil,
            C19 -- do not silently relabel a legacy export).  Merged 3-column path:
            column 1 is the blended B06; it is split into its exact oil/gas parts with
            oil's emission share of the blend, and the historical label order
            (oil first, gas second) is preserved.
            """
            if disagg.shape[1] == 4:
                return disagg[:, 1], disagg[:, 2], disagg[:, 3]
            share = 0.5 if b06_oil_emission_share is None else float(b06_oil_emission_share)
            return share * disagg[:, 1], (1.0 - share) * disagg[:, 1], disagg[:, 2]

        # Total amount spent
        self.ts.amount_bought.append(self.ts.current("nominal_amount_spent_in_lcu").sum(axis=1))

        # Distribute
        consumption_by_good = np.minimum(
            self.ts.current("nominal_amount_spent_in_lcu"),
            self.ts.current("target_consumption"),
        )

        if add_emissions:
            # Apply per-industry consumption fraction multipliers when enabled.
            # emission_fractions.consumption has shape (1, n_industries); index row 0
            # then select emitting columns to get (n_emitting,) broadcast multipliers.
            if (
                use_emission_multiplier
                and self.emission_fractions is not None
                and self.emission_fractions.consumption is not None
            ):
                cons_fracs = self.emission_fractions.consumption[0, emitting_indices]
                cons_slice = consumption_by_good[:, emitting_indices] * cons_fracs
            else:
                cons_slice = consumption_by_good[:, emitting_indices]

            consumption_emissions = cons_slice @ readjusted_factors
            self.ts.consumption_emissions.append(consumption_emissions)

            consumption_sum = consumption_by_good.sum(axis=0)
            consumption_emissions_by_good = np.zeros(consumption_by_good.shape[1])
            for i in emitting_indices:
                idx = np.where(emitting_indices == i)[0]
                multiplier = (
                    self.emission_fractions.consumption[0, i]
                    if use_emission_multiplier
                    and self.emission_fractions is not None
                    and self.emission_fractions.consumption is not None
                    else 1.0
                )
                consumption_emissions_by_good[i] = (consumption_sum[i] * multiplier * readjusted_factors[idx]).item()
            self.ts.consumption_emissions_by_good.append(consumption_emissions_by_good)

            if emitting_indices_ch4 is not None and readjusted_factors_ch4 is not None:
                consumption_emissions_ch4_by_good = np.zeros(consumption_by_good.shape[1])
                for i in emitting_indices_ch4:
                    idx = np.where(emitting_indices_ch4 == i)[0]
                    consumption_emissions_ch4_by_good[i] = (consumption_sum[i] * readjusted_factors_ch4[idx]).item()
                self.ts.consumption_emissions_ch4_by_good.append(consumption_emissions_ch4_by_good)

            disaggregated_emissions = cons_slice * readjusted_factors
            _oil_c, _gas_c, _ref_c = _fuel_series(disaggregated_emissions)
            self.ts.coal_consumption_emissions.append(disaggregated_emissions[:, 0])
            self.ts.oil_consumption_emissions.append(_oil_c)
            self.ts.gas_consumption_emissions.append(_gas_c)
            self.ts.refined_products_consumption_emissions.append(_ref_c)

        # Consumption
        self.ts.consumption.append(consumption_by_good.sum(axis=1))
        self.ts.total_consumption.append([(1 + tau_vat) * self.ts.current("consumption").sum()])
        self.ts.total_consumption_before_vat.append([self.ts.current("consumption").sum()])
        self.ts.industry_consumption.append(consumption_by_good.sum(axis=0))

        # Investment
        self.ts.investment.append(self.ts.current("nominal_amount_spent_in_lcu") - consumption_by_good)
        if add_emissions:
            inv = self.ts.current("nominal_amount_spent_in_lcu") - consumption_by_good

            # Apply per-industry investment fraction multipliers when enabled.
            if (
                use_emission_multiplier
                and self.emission_fractions is not None
                and self.emission_fractions.investment is not None
            ):
                inv_fracs = self.emission_fractions.investment[0, emitting_indices]
                inv_slice = inv[:, emitting_indices] * inv_fracs
            else:
                inv_slice = inv[:, emitting_indices]

            investment_emissions = inv_slice @ readjusted_factors
            self.ts.investment_emissions.append(investment_emissions)

            inv_sum = inv.sum(axis=0)
            investment_emissions_by_good = np.zeros(inv.shape[1])
            for i in emitting_indices:
                idx = np.where(emitting_indices == i)[0]
                multiplier = (
                    self.emission_fractions.investment[0, i]
                    if use_emission_multiplier
                    and self.emission_fractions is not None
                    and self.emission_fractions.investment is not None
                    else 1.0
                )
                investment_emissions_by_good[i] = (inv_sum[i] * multiplier * readjusted_factors[idx]).item()
            self.ts.investment_emissions_by_good.append(investment_emissions_by_good)

            if emitting_indices_ch4 is not None and readjusted_factors_ch4 is not None:
                investment_emissions_ch4_by_good = np.zeros(inv.shape[1])
                for i in emitting_indices_ch4:
                    idx = np.where(emitting_indices_ch4 == i)[0]
                    investment_emissions_ch4_by_good[i] = (inv_sum[i] * readjusted_factors_ch4[idx]).item()
                self.ts.investment_emissions_ch4_by_good.append(investment_emissions_ch4_by_good)

            disaggregated_emissions = inv_slice * readjusted_factors
            _oil_i, _gas_i, _ref_i = _fuel_series(disaggregated_emissions)
            self.ts.coal_investment_emissions.append(disaggregated_emissions[:, 0])
            self.ts.oil_investment_emissions.append(_oil_i)
            self.ts.gas_investment_emissions.append(_gas_i)
            self.ts.refined_products_investment_emissions.append(_ref_i)
        self.ts.total_investment.append([(1 + tau_cf) * self.ts.current("investment").sum()])
        self.ts.total_investment_before_vat.append([self.ts.current("investment").sum()])
        self.ts.industry_investment.append(self.ts.current("investment").sum(axis=0))

    def update_wealth(self, housing_data: pd.DataFrame, tau_cf: float) -> None:
        """Update household wealth positions.

        Updates:
        - Real asset holdings
        - Financial assets
        - Property values
        - Net wealth position

        Args:
            housing_data (pd.DataFrame): Property market data
            tau_cf (float): Capital formation tax rate
        """
        # Update real wealth
        self.ts.wealth_main_residence.append(
            self.compute_wealth_of_the_main_residence(
                housing_data=housing_data,
            )
        )
        self.ts.total_wealth_main_residence.append([self.ts.current("wealth_main_residence").sum()])
        self.ts.wealth_other_properties.append(
            self.compute_wealth_of_other_properties(
                housing_data=housing_data,
            )
        )
        self.ts.total_wealth_other_properties.append([self.ts.current("wealth_other_properties").sum()])
        self.ts.wealth_other_real_assets.append(self.compute_wealth_of_other_real_assets())
        self.ts.total_wealth_other_real_assets.append([self.ts.current("wealth_other_real_assets").sum()])
        self.ts.wealth_real_assets.append(
            self.ts.current("wealth_main_residence")
            + self.ts.current("wealth_other_properties")
            + self.ts.current("wealth_other_real_assets")
        )

        # New financial wealth
        new_wealth = np.maximum(
            0.0,
            (
                self.ts.current("income")
                - self.ts.current("rent")
                - self.ts.current("nominal_amount_spent_in_lcu").sum(axis=1)
            ),
        )
        (
            new_wealth_in_deposits,
            new_wealth_in_other_financial_assets,
        ) = self.functions["wealth"].distribute_new_wealth(
            new_wealth=new_wealth,
            model=self.states["wealth_distribution_model"],
            ts=self.ts,
        )

        # Used-up financial wealth
        used_up_wealth = -np.minimum(
            0.0,
            (
                self.ts.current("income")
                - self.ts.current("rent")
                - self.ts.current("nominal_amount_spent_in_lcu").sum(axis=1)
            ),
        )
        (
            used_up_wealth_in_deposits,
            used_up_wealth_in_other_financial_assets,
        ) = self.functions["wealth"].use_up_wealth(
            used_up_wealth=used_up_wealth,
            current_wealth_in_deposits=self.ts.current("wealth_deposits"),
            current_wealth_in_other_financial_assets=self.ts.current("wealth_other_financial_assets"),
        )

        # Update other financial assets
        self.ts.wealth_other_financial_assets.append(
            self.compute_wealth_of_other_financial_assets(
                new_wealth_in_other_financial_assets=new_wealth_in_other_financial_assets,
                used_up_wealth_in_other_financial_assets=used_up_wealth_in_other_financial_assets,
            )
        )
        self.ts.total_wealth_other_financial_assets.append([self.ts.current("wealth_other_financial_assets").sum()])

        # Update deposits
        self.ts.wealth_deposits.append(
            self.compute_wealth_in_deposits(
                new_wealth_in_deposits=new_wealth_in_deposits,
                used_up_wealth_in_deposits=used_up_wealth_in_deposits,
                tau_cf=tau_cf,
            )
        )
        self.ts.total_wealth_deposits.append([self.ts.current("wealth_deposits").sum()])

        # Compute total financial assets
        self.ts.wealth_financial_assets.append(
            self.ts.current("wealth_other_financial_assets") + self.ts.current("wealth_deposits")
        )

        # Compute total wealth
        self.ts.wealth.append(self.ts.current("wealth_real_assets") + self.ts.current("wealth_financial_assets"))

    def compute_wealth_of_the_main_residence(self, housing_data: pd.DataFrame) -> np.ndarray:
        """Calculate main residence wealth.

        Determines value of:
        - Owner-occupied housing
        - Primary residences

        Args:
            housing_data (pd.DataFrame): Property market data

        Returns:
            np.ndarray: Main residence value by household
        """
        wealth_of_the_main_residence = np.zeros(self.ts.current("n_households"))
        ind_owning_mhr = np.all(
            [
                np.isin(self.states["Tenure Status of the Main Residence"], [1, 2, 4]),
                self.states["Corresponding Inhabited House ID"] != -1,
            ],
            axis=0,
        )
        wealth_of_the_main_residence[ind_owning_mhr] = housing_data.loc[
            self.states["Corresponding Inhabited House ID"][ind_owning_mhr],
            "Value",
        ].values
        return wealth_of_the_main_residence

    def compute_wealth_of_other_properties(self, housing_data: pd.DataFrame) -> np.ndarray:
        """Calculate other property wealth.

        Determines value of:
        - Investment properties
        - Rental properties
        - Secondary homes

        Args:
            housing_data (pd.DataFrame): Property market data

        Returns:
            np.ndarray: Other property value by household
        """
        wealth_of_other_properties = np.zeros(self.ts.current("n_households"))
        housing_data_not_oo = housing_data.loc[housing_data["Is Owner-Occupied"] == 0]
        housing_data_not_oo_grouped = housing_data_not_oo.groupby("Corresponding Owner Household ID")["Value"].sum()
        wealth_of_other_properties[housing_data_not_oo_grouped.index.values] = housing_data_not_oo_grouped.values
        return wealth_of_other_properties

    def compute_wealth_of_other_real_assets(self) -> np.ndarray:
        """Calculate other real asset wealth.

        Determines value of:
        - Non-property real assets
        - Physical investments
        - Durable goods

        Returns:
            np.ndarray: Other real asset value by household
        """
        return self.functions["wealth"].compute_wealth_in_other_real_assets(
            current_wealth_in_other_real_assets=self.ts.current("wealth_other_real_assets"),
            current_investment_in_other_real_assets=self.ts.current("investment").sum(axis=1),
        )

    def compute_wealth_of_other_financial_assets(
        self,
        new_wealth_in_other_financial_assets: float,
        used_up_wealth_in_other_financial_assets: float,
    ) -> np.ndarray:
        """Calculate other financial asset wealth.

        Updates financial assets based on:
        - New investments
        - Asset usage
        - Market returns

        Args:
            new_wealth_in_other_financial_assets (float): New investments
            used_up_wealth_in_other_financial_assets (float): Used assets

        Returns:
            np.ndarray: Financial asset value by household
        """
        return self.functions["wealth"].compute_wealth_in_other_financial_assets(
            current_wealth_in_other_financial_assets=self.ts.current("wealth_other_financial_assets"),
            new_wealth_in_other_financial_assets=new_wealth_in_other_financial_assets,
            used_up_wealth_in_other_financial_assets=used_up_wealth_in_other_financial_assets,
        )

    def compute_wealth_in_deposits(
        self,
        new_wealth_in_deposits: np.ndarray,
        used_up_wealth_in_deposits: np.ndarray,
        tau_cf: float,
    ) -> np.ndarray:
        """Calculate deposit wealth.

        Updates deposits based on:
        - New savings
        - Withdrawals
        - Interest earned
        - Tax effects

        Args:
            new_wealth_in_deposits (np.ndarray): New deposits
            used_up_wealth_in_deposits (np.ndarray): Used deposits
            tau_cf (float): Capital formation tax rate

        Returns:
            np.ndarray: Deposit value by household
        """
        return self.functions["wealth"].compute_wealth_in_deposits(
            current_wealth_in_deposits=self.ts.current("wealth_deposits"),
            new_wealth_in_deposits=new_wealth_in_deposits,
            used_up_wealth_in_deposits=used_up_wealth_in_deposits,
            current_interest_paid=self.ts.current("interest_paid"),
            price_paid_for_property=self.ts.current("price_paid_for_property"),
            debt_installments=self.ts.current("debt_installments"),
            new_loans=self.ts.current("received_consumption_loans") + self.ts.current("received_mortgages"),
            new_real_wealth=self.ts.current("investment").sum(axis=1),
            tau_cf=tau_cf,
        )

    def compute_debt(self) -> np.ndarray:
        """Calculate total household debt.

        Aggregates debt from:
        - Consumption loans
        - Mortgages
        - Other credit

        Returns:
            np.ndarray: Total debt by household
        """
        self.ts.total_consumption_loan_debt.append([self.ts.current("consumption_loan_debt").sum()])
        self.ts.total_mortgage_debt.append([self.ts.current("mortgage_debt").sum()])
        return self.ts.current("consumption_loan_debt") + self.ts.current("mortgage_debt")

    def compute_net_wealth(self) -> np.ndarray:
        """Calculate household net wealth.

        Determines net position from:
        - Total assets
        - Total liabilities
        - Debt obligations

        Returns:
            np.ndarray: Net wealth by household
        """
        return self.ts.current("wealth") - self.ts.current("debt")

    def handle_insolvency(self, banks: Banks, credit_market: CreditMarket) -> Tuple[float, float, float]:
        """Handle household insolvency cases.

        Processes defaults through:
        - Debt restructuring
        - Asset liquidation
        - Bank interactions

        Args:
            banks (Banks): Banking sector agent
            credit_market (CreditMarket): Credit market interface

        Returns:
            Tuple[float, float, float]: Default outcomes
        """
        return self.functions["insolvency"].handle_insolvency(
            households=self,
            banks=banks,
            credit_market=credit_market,
        )

    def save_to_h5(self, group: h5py.Group):
        """Save household data to HDF5.

        Stores:
        - Time series data
        - State variables
        - Market positions

        Args:
            group (h5py.Group): HDF5 storage group
        """
        self.ts.write_to_h5("households", group)

    def save_consumption_weights(self, group: h5py.Group):
        """Save consumption weight data.

        Stores:
        - Income-based weights
        - Industry allocations
        - Consumption patterns

        Args:
            group (h5py.Group): HDF5 storage group
        """
        group.create_dataset("household_consumption_weights_by_income", data=self.consumption_weights.T)
        group["household_consumption_weights_by_income"].attrs["columns"] = list(range(self.n_industries))

    def total_consumption(self) -> np.ndarray:
        """Get total consumption time series.

        Returns:
            np.ndarray: Aggregate consumption over time
        """
        return self.ts.get_aggregate("total_consumption")

    def consumption_loan_debt(self) -> np.ndarray:
        """Get consumption loan debt time series.

        Returns:
            np.ndarray: Aggregate consumption debt over time
        """
        return self.ts.get_aggregate("consumption_loan_debt")

    def mortgage_debt(self) -> np.ndarray:
        """Get mortgage debt time series.

        Returns:
            np.ndarray: Aggregate mortgage debt over time
        """
        return self.ts.get_aggregate("mortgage_debt")

    def consumption_emissions(self) -> np.ndarray:
        """Get consumption emissions time series.

        Returns:
            np.ndarray: Aggregate consumption emissions over time
        """
        return self.ts.get_aggregate("consumption_emissions")

    def investment_emissions(self) -> np.ndarray:
        """Get investment emissions time series.

        Returns:
            np.ndarray: Aggregate investment emissions over time
        """
        return self.ts.get_aggregate("investment_emissions")

    def disaggregated_consumption_emissions(self, input_name: str) -> np.ndarray:
        """Get disaggregated consumption emissions.

        Args:
            input_name (str): Input category name

        Returns:
            np.ndarray: Category-specific consumption emissions
        """
        return self.ts.get_aggregate(f"{input_name}_consumption_emissions")

    def disaggregated_investment_emissions(self, input_name: str) -> np.ndarray:
        """Get disaggregated investment emissions.

        Args:
            input_name (str): Input category name

        Returns:
            np.ndarray: Category-specific investment emissions
        """
        return self.ts.get_aggregate(f"{input_name}_investment_emissions")
