"""Canada Output-Based Pricing System (OBPS) policy for the macroeconomic model.

Computes a two-way carbon price signal for each regulated sector based on
emissions relative to an output-based benchmark:

    obps_cost[i] = (emissions[i] - limit[i]) * carbon_price[t]

Sectors emitting above their benchmark incur a positive cost; sectors below
receive a negative cost (rebate). Dividing by production gives a per-unit
marginal tax passed to firms as extra_marginal_taxes_firm in the country's
target-setting phase.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from macro_data.readers.policy_data.obps_can_reader import OBPSCANData


# Federal OBPS applies to facilities emitting >= 50 ktCO2e/yr.  The model resolves
# sectors, not facilities, so this is applied as a LOWER BOUND: a sector-province whose
# entire annual emissions fall below one facility's threshold cannot contain a covered
# facility, so it is not regulated.  It does not exclude sectors that clear the bar in
# aggregate but consist of many small sites -- that would need facility resolution.
#
# It also removes the degenerate benchmarks.  Seven of ten provinces have at least one
# regulated sector with 2014 production of order 1e-4 against a peer median of 1e8 --
# empty cells in the IO table -- and dividing emissions by those produced baseline
# intensities up to 2.5e10 against Alberta's 0.0072, hence emission limits of 1e14 and
# per-unit charges that broke goods-market clearing.  Those sectors emit ~0 and are
# excluded by this rule automatically.
#
# Model emissions are in tonnes CO2e: regulated sectors total ~5.7e8 t/yr against
# Canada's actual ~6.7e8 t/yr, so the statutory figure is used directly.
OBPS_COVERAGE_THRESHOLD_TCO2_PER_YEAR = 50_000.0

# OECD-50 (2022 base) -> 43-scheme fallbacks for the policy-values CSV lookup in
# get_limit.  B06 (merged crude + natural gas extraction) borrows the crude row --
# oil dominates the merged sector's output value; the reduction factor is 0.8 and the
# tightening rate 0.02 across nearly every row, so the choice is second-order.
_POLICY_CODE_ALIASES = {
    "B05": "B05a",
    "B06": "B05c",
    "C17_18": "C17",
    "C24A": "C24a",
    "C24B": "C24b",
    "C301": "C30",
    "C302T309": "C30",
}

@dataclass
class OutputBasedPriceSystemCAN:
    """Canada Output-Based Pricing System policy class.

    Calculates the tax that regulated firms pay on emissions above a
    prescribed output-weighted limit. Reference emission intensities are
    recorded during 2017–2018 and used to set sector-specific limits from
    2019 onwards.

    Attributes:
        country_name: Jurisdiction column to use from the rates CSV.
        industries: Ordered list of all model industry names.
        regulated_industries: Industries subject to OBPS regulation.
        regulated_indices: Array indices into the industries list for each
            regulated industry.
        df_policy: Per-industry reduction factors and tightening rates.
        df_policy_elec: Electricity-specific tightening rates (optional).
        df_rates: Carbon price schedule by year and jurisdiction.
        baseline_emission_intensity: Baseline emission intensity recorded
            over the 2017–2019 reference period and fixed thereafter.
        reference_emission: Cumulative emissions during the reference period.
        reference_production: Cumulative production during the reference period.
        emission_limit: Current period allowable emissions per industry.
        price: Annual carbon price trajectory (indexed from 2014).
        current_t: Current timestep index (incremented by update()).
        current_year: Current calendar year.
    """

    country_name: str
    industries: list[str]
    regulated_industries: list[str]
    regulated_indices: np.ndarray
    df_policy: pd.DataFrame
    df_policy_elec: pd.DataFrame
    df_rates: pd.DataFrame
    baseline_emission_intensity: np.ndarray
    reference_emission: np.ndarray
    reference_production: np.ndarray
    emission_limit: np.ndarray
    price: np.ndarray
    initial_year: int = 2014
    current_t: int = 0
    current_year: int = 2014

    def __init__(
        self,
        country_name: str,
        industries: list[str],
        obps_data: OBPSCANData,
        coverage_threshold_tco2_per_year: float = OBPS_COVERAGE_THRESHOLD_TCO2_PER_YEAR,
        initial_year: int = 2014,
    ):
        """Initialise the OBPS from a loaded OBPSCANData container.

        Args:
            country_name: Jurisdiction code matching a column in obps_data.df_rates.
            industries: Ordered list of all model industry names.
            obps_data: Loaded OBPS CSV data.
        """
        self.country_name = country_name
        self.industries = industries

        # Industries regulated under OBPS (federal schedule)
        self.regulated_industries = [
            "B05a",
            "B05b",
            "B05c",
            "B07",
            "B09",
            "C10T12",
            "C16",
            "C17",
            "C19",
            "C20",
            "C21",
            "C22",
            "C23",
            "C24a",
            "C24b",
            "C29",
            "C30",
            "D01b",
            "D01c",
            # OECD-50 (2022 base) codes -- absent from 43-scheme wrappers, where the
            # existing skip-if-missing behaviour leaves the legacy list untouched.
            "B05",
            "B06",
            "C17_18",
            "C24A",
            "C24B",
            "C301",
            "C302T309",
        ]
        self.regulated_indices = np.array(
            [list(industries).index(ind) for ind in self.regulated_industries if ind in industries]
        )

        skipped = [ind for ind in self.regulated_industries if ind not in industries]
        if skipped:
            logging.warning(
                "OBPS (%s): %d regulated industrie(s) not found in model and will be skipped: %s",
                country_name,
                len(skipped),
                skipped,
            )
        if len(self.regulated_indices) == 0:
            logging.warning(
                "OBPS (%s): none of the regulated industries appear in the model — OBPS will have no effect. "
                "Check that industry codes match.",
                country_name,
            )

        self.coverage_threshold_tco2_per_year = float(coverage_threshold_tco2_per_year)
        self._excluded_logged: set[int] = set()
        # The simulation clock's year zero -- the wrapper's base year.  Previously
        # hardcoded to 2014; a 2022-base run would otherwise sit 8 years behind on the
        # price schedule and tightening arithmetic.
        self.initial_year = int(initial_year)
        self.current_t = 0
        self.current_year = self.initial_year

        n = len(industries)
        self.baseline_emission_intensity = np.zeros(n)
        self.reference_emission = np.zeros(n)
        self.reference_production = np.zeros(n)
        self.emission_limit = np.zeros(n)

        self.df_policy = obps_data.df_policy
        self.df_policy_elec = obps_data.df_policy_elec if obps_data.df_policy_elec is not None else pd.DataFrame()
        self.df_rates = obps_data.df_rates

        self.price_by_year = dict(zip(self.df_rates["Date"], self.df_rates[self.country_name]))

    def compute_obps(
        self,
        use_obps_reg: bool,
        record_obps_reference: bool,
        production: np.ndarray,
        input_em: np.ndarray,
        capital_em: np.ndarray,
        initial_production: np.ndarray | None = None,
    ) -> np.ndarray:
        """Compute per-sector OBPS tax cost.

        Records reference emission intensities during 2017–2019. From 2019
        onwards, computes the signed cost of emissions relative to the
        prescribed limit at the current carbon price.

        Args:
            use_obps_reg: If False, returns a zero array.
            record_obps_reference: If True, accumulate reference period data.
            production: Current-period production per industry.
            input_em: Input-related CO₂e emissions per industry.
            capital_em: Capital-related CO₂e emissions per industry.

        Returns:
            np.ndarray: Signed OBPS cost (dollars) per industry — positive
                when emissions exceed the limit, negative when below it;
                zero for unregulated industries or years before 2019.
        """
        if not use_obps_reg:
            return np.zeros(len(self.industries))

        # Reference production comes from the 2014 IO initialisation (real StatCan data)
        # rather than 2017-18 simulated output.  Modelled output bakes accumulated model
        # drift into a policy benchmark that then governs the whole projection, and makes
        # the benchmark move whenever a macro assumption changes -- so two scenarios
        # differing only in, say, TFP would face different carbon regulation.  Emissions
        # are still accumulated over the statutory 2017-18 window.
        #
        # LATE STARTS (initial_year > 2017, e.g. the 2022-base wrapper): the statutory
        # window predates the simulation, so left alone the baseline stays zero and every
        # regulated tonne would be taxed from t=0 -- a confiscatory misread of the policy.
        # Instead the reference is recorded over the simulation's FIRST year, whose
        # production/emissions are the wrapper's real base-year data (the same
        # initialisation-not-simulation rationale as above), and taxing starts the year
        # after.  For a 2014 start these expressions reduce exactly to the historical
        # (2017, 2018) window / 2019 tax start.
        if self.initial_year <= 2017:
            reference_years: tuple[int, ...] = (2017, 2018)
        else:
            reference_years = (self.initial_year,)
        baseline_year = reference_years[-1]

        if record_obps_reference and self.current_year in reference_years:
            self.reference_emission += input_em + capital_em
            self.reference_production += (
                production if initial_production is None else initial_production
            )

        if self.current_year == baseline_year:
            self.baseline_emission_intensity = np.divide(
                self.reference_emission,
                self.reference_production,
                out=np.zeros_like(self.baseline_emission_intensity),
                where=self.reference_production != 0,
            )

        if self.current_year < max(2019, baseline_year + 1):
            return np.zeros(len(self.industries))

        obps_cost = np.zeros(len(self.industries))
        current_price = self.get_price()
        steps_per_year = 4.0
        for i in self.regulated_indices:
            annual_emissions = (input_em[i] + capital_em[i]) * steps_per_year
            if annual_emissions < self.coverage_threshold_tco2_per_year:
                if i not in self._excluded_logged:
                    self._excluded_logged.add(i)
                    logging.info(
                        "OBPS (%s): %s excluded -- %.4g tCO2e/yr is below the %.0f "
                        "kt/yr facility threshold, so it can hold no covered facility.",
                        self.country_name, self.industries[i], annual_emissions,
                        self.coverage_threshold_tco2_per_year / 1000.0,
                    )
                continue
            if production[i] > 0:
                limit = self.get_limit(i, production[i])
                self.emission_limit[i] = limit
                difference = (input_em[i] + capital_em[i]) - limit
                obps_cost[i] = difference * current_price

        return obps_cost

    def get_limit(self, industry_idx: int, production: float) -> float:
        """Calculate the prescribed emission allowance for an industry.

        Uses the pre-2023 formula (reduction factor only) or the post-2023
        formula (reduction factor × tightening adjustment).

        Args:
            industry_idx: Index into self.industries.
            production: Current period output.

        Returns:
            float: Allowable emissions in tCO₂e.
        """
        industry_name = self.industries[industry_idx]
        row = self.df_policy[self.df_policy["Industry"] == industry_name]
        if row.empty and industry_name in _POLICY_CODE_ALIASES:
            # The policy-values CSV is written in the 43-scheme; OECD-50 codes fall
            # back to their closest legacy row (B06 -> B05c: oil dominates the merged
            # sector's output value).
            row = self.df_policy[self.df_policy["Industry"] == _POLICY_CODE_ALIASES[industry_name]]
        if row.empty:
            return 0.0

        reduction_factor = row["reduction_factor"].values[0]
        B = reduction_factor * self.baseline_emission_intensity[industry_idx]

        if self.current_year < 2023:
            return production * B

        tightening_rate = row["tightening_rate"].values[0]
        return max(0.0, production * (B - B * tightening_rate * (self.current_year - 2022)))

    def get_price(self) -> float:
        """Return the current period carbon price ($/tCO₂e).

        For years not explicitly in the schedule, uses forward-filling: returns
        the price from the last milestone year less than or equal to current_year.
        """
        year = self.current_year
        available_years = sorted(self.price_by_year.keys())

        if year in self.price_by_year:
            return self.price_by_year[year]

        past_years = [y for y in available_years if y <= year]
        if past_years:
            return self.price_by_year[max(past_years)]

        return self.price_by_year[min(available_years)]

    def update(self) -> None:
        """Advance the timestep by one annual period."""
        self.current_t += 1
        self.current_year += 1

    def reset(self) -> None:
        """Reset all internal state for a fresh simulation run.

        Resets time tracking, accumulators, and computed baselines to initial values.
        """
        self.current_t = 0
        self.current_year = self.initial_year
        self.reference_emission = np.zeros(len(self.industries))
        self.reference_production = np.zeros(len(self.industries))
        self.baseline_emission_intensity = np.zeros(len(self.industries))
        self.emission_limit = np.zeros(len(self.industries))
