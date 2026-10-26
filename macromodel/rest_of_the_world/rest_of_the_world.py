"""Rest of the World implementation module.

This module implements the Rest of the World (ROW) component that represents
all external economies interacting with the modeled countries. It handles:

1. International Trade:
   - Export supply decisions
   - Import demand behavior
   - Price setting in international markets
   - Currency conversion

2. Economic Integration:
   - Trade flow adjustments
   - Price level convergence
   - Market clearing processes
   - Exchange rate effects

3. Dynamic Behavior:
   - Trade volume forecasting
   - Price adjustment mechanisms
   - Growth and inflation impacts
   - Expectation formation

The ROW component serves as the external sector in the model, providing
closure for international trade and ensuring consistent global accounting.
"""

from functools import reduce
from typing import Any

import h5py
import logging

import numpy as np
import pandas as pd

from macro_data import SyntheticRestOfTheWorld
from macromodel.agents.agent import Agent
from macromodel.configurations import RestOfTheWorldConfiguration
from macromodel.configurations.row_configuration import RestOfTheWorldParameters
from macromodel.markets.goods_market.value_type import ValueType
from macromodel.rest_of_the_world.func.prices import SectorExogenousROWPriceSetter
from macromodel.rest_of_the_world.rest_of_the_world_ts import (
    create_rest_of_the_world_timeseries,
)
from macromodel.timeseries import TimeSeries
from macromodel.util.function_mapping import functions_from_model, update_functions


logger = logging.getLogger(__name__)


class RestOfTheWorld(Agent):
    """Rest of the World economic agent.

    This class represents all external economies as a single agent that trades
    with the modeled countries. It manages international trade flows, price
    setting, and market interactions through:
    - Import and export decisions
    - International price determination
    - Trade flow adjustments
    - Market clearing participation

    Attributes:
        country_name (str): Associated country identifier
        all_country_names (list[str]): All countries in model
        n_industries (int): Number of industrial sectors
        functions (dict[str, Any]): Economic function implementations
        parameters (RestOfTheWorldParameters): Behavioral parameters
        forecasting_window (int): Periods for forecasting
        assume_zero_growth (bool): Whether to assume no growth
        assume_zero_noise (bool): Whether to suppress random variation
        configuration (RestOfTheWorldConfiguration): Model settings
    """

    def __init__(
        self,
        country_name: str,
        all_country_names: list[str],
        n_industries: int,
        n_importers: int,
        n_exporters_by_industry: np.ndarray,
        functions: dict[str, Any],
        ts: TimeSeries,
        parameters: RestOfTheWorldParameters,
        states: dict[str, float | np.ndarray | list[np.ndarray]],
        forecasting_window: int,
        assume_zero_growth: bool,
        assume_zero_noise: bool,
        configuration: RestOfTheWorldConfiguration,
    ):
        """Initialize Rest of the World agent.

        Args:
            country_name (str): Associated country identifier
            all_country_names (list[str]): All countries in model
            n_industries (int): Number of industrial sectors
            n_importers (int): Number of importing agents
            n_exporters_by_industry (np.ndarray): Exporters per industry
            functions (dict[str, Any]): Economic function implementations
            ts (TimeSeries): Time series data
            parameters (RestOfTheWorldParameters): Behavioral parameters
            states (dict): Initial state variables
            forecasting_window (int): Periods for forecasting
            assume_zero_growth (bool): Whether to assume no growth
            assume_zero_noise (bool): Whether to suppress random variation
            configuration (RestOfTheWorldConfiguration): Model settings
        """
        super().__init__(
            country_name=country_name,
            all_country_names=all_country_names,
            n_industries=n_industries,
            n_transactors_sell=int(n_exporters_by_industry.sum()),
            n_transactors_buy=n_importers,
            ts=ts,
            states=states,
            transactor_settings={
                "Buyer Value Type": ValueType.NOMINAL,
                "Seller Value Type": ValueType.REAL,
                "Buyer Priority": 0,
                "Seller Priority": 1,
            },
        )

        self.functions = functions
        self.parameters = parameters
        self.forecasting_window = forecasting_window
        self.assume_zero_growth = assume_zero_growth
        self.assume_zero_noise = assume_zero_noise
        self.configuration = configuration
        # Industry indices whose ROW exports (= domestic imports) are share-capped.
        # Empty by default, so behaviour is unchanged unless set_import_limits() is called.
        self._import_limited_industries: list[int] = []
        # "share" (default) scales the cap by the aggregate production index; "level"
        # freezes imports at their base-year volume.
        self._import_limit_mode: str = "share"

    def set_import_limits(self, industry_indices, *, mode: str = "share") -> None:
        """Cap ROW exports of the given industries so their import *share* cannot grow.

        The rest of the world is an unconstrained residual supplier: whenever domestic
        firms cannot meet demand for a good, ROW fills the gap.  That is realistic for
        tradeable goods but not for ones where the intent is to force the domestic
        sector to build capacity (e.g. electricity under an electrification scenario) --
        there, unconstrained imports silently absorb the entire demand increase and the
        domestic sector never expands.

        Limited industries have their desired real exports clamped to the base-year
        level scaled by the aggregate production index, i.e. imports may still grow with
        the economy but their share of it cannot rise above the base-year share.

        ``mode="level"`` instead freezes imports at their base-year VOLUME, dropping the
        production-index scaling.  For electricity that is the more physical cap:
        cross-border transfer capacity is fixed transmission infrastructure and does not
        grow with GDP, so letting the cap scale with the economy still allows imports to
        roughly double by 2050.  It is also the stricter reading -- if the domestic sector
        cannot build fast enough, the shortfall becomes unmet demand rather than an import.

        Args:
            industry_indices: industry indices to cap; empty/None clears all limits.
            mode: ``"share"`` (default, base-year share) or ``"level"`` (base-year volume).
        """
        mode = str(mode or "share").lower()
        if mode not in ("share", "level"):
            raise ValueError(f"Unknown import limit mode: {mode!r}")
        self._import_limit_mode = mode
        self._import_limited_industries = sorted({int(i) for i in (industry_indices or [])})

    def set_import_supply_reduction(self, reduction_lcu_by_good) -> None:
        """Withdraw a nominal amount (LCU per good) from ROW's supply this step.

        Used to cap the import share of an injected order stream: the hook passes the
        part of those orders that would otherwise be imported above the cap, so domestic
        producers have to supply it. The goods market's additional-ROW backstop is left
        on, so part of the gap can still be refilled at its markup. ``None`` clears it.
        """
        self._import_supply_reduction_lcu = (
            None if reduction_lcu_by_good is None else np.asarray(reduction_lcu_by_good, dtype=float)
        )

    def _apply_import_limits(self, aggregate_country_production_index: float) -> None:
        """Clamp the current desired real exports of import-limited industries in place.

        No-op unless :meth:`set_import_limits` or :meth:`set_import_supply_reduction` has
        been called.  The cap grows with ``aggregate_country_production_index`` so it
        constrains the *share*, not the level.
        """
        reduction = getattr(self, "_import_supply_reduction_lcu", None)
        if not self._import_limited_industries and reduction is None:
            return
        current = np.array(self.ts.current("desired_exports_real"), dtype=float)
        if reduction is not None:
            # Nominal LCU -> real at ROW's latest offered price (before this step's update).
            price = np.asarray(self.ts.current("price_in_lcu"), dtype=float)
            real = np.divide(reduction, price, out=np.zeros_like(reduction), where=price > 0)
            current = np.maximum(current - real, 0.0)
        initial = np.array(self.ts.initial("desired_exports_real"), dtype=float)
        if getattr(self, "_import_limit_mode", "share") == "level":
            # Base-year VOLUME: no scaling with the economy.
            index = 1.0
        else:
            index = float(aggregate_country_production_index)
            if not np.isfinite(index) or index <= 0.0:
                index = 1.0
        for g in self._import_limited_industries:
            if 0 <= g < current.size:
                current[g] = min(current[g], initial[g] * index)
        self.ts.desired_exports_real[-1] = current

    @classmethod
    def from_pickled_row(
        cls,
        country_name: str,
        all_country_names: list[str],
        n_industries: int,
        synthetic_row: SyntheticRestOfTheWorld,
        configuration: RestOfTheWorldConfiguration,
        calibration_data_before: pd.DataFrame,
        calibration_data_during: pd.DataFrame,
        firm_exo_prices=None,
        industries=None,
    ) -> "RestOfTheWorld":
        """Create ROW instance from synthetic data.

        Factory method that constructs a RestOfTheWorld instance using
        synthetic data and calibration information.

        Args:
            country_name (str): Associated country identifier
            all_country_names (list[str]): All countries in model
            n_industries (int): Number of industrial sectors
            synthetic_row (SyntheticRestOfTheWorld): Synthetic ROW data
            configuration (RestOfTheWorldConfiguration): Model settings
            calibration_data_before (pd.DataFrame): Pre-period calibration data
            calibration_data_during (pd.DataFrame): During-period calibration data
            firm_exo_prices: SectorExoPrices container for exogenous sector price
                overrides (optional). Reuses the same CSV as domestic firms.
            industries: Ordered list of industry names, one per industry index,
                used to populate overriden_industries on the ROW price setter.

        Returns:
            RestOfTheWorld: Initialized ROW instance
        """
        functions = functions_from_model(model=configuration.functions, loc="macromodel.rest_of_the_world")

        if (
            isinstance(functions.get("prices"), SectorExogenousROWPriceSetter)
            and firm_exo_prices is not None
            and industries is not None
        ):
            functions["prices"].firm_exo_prices = firm_exo_prices
            functions["prices"].overriden_industries = list(industries)

        data = synthetic_row.row_data.astype(float)
        data.rename_axis("Industry", inplace=True)

        exogenous_real_imports_before = calibration_data_before[("ROW", "Real Imports (Value)")].values
        exogenous_real_exports_before = calibration_data_before[("ROW", "Real Exports (Value)")].values

        exogenous_real_imports_during = calibration_data_during[("ROW", "Real Imports (Value)")].values
        exogenous_real_exports_during = calibration_data_during[("ROW", "Real Exports (Value)")].values

        n_exporters_by_industry = synthetic_row.n_exporters_by_industry
        n_importers = synthetic_row.n_importers

        row_exports_model = synthetic_row.exports_model
        row_imports_model = synthetic_row.imports_model

        ts = create_rest_of_the_world_timeseries(
            data=data,
            n_industries=n_industries,
        )

        states = {
            "row_exports_model": row_exports_model,
            "row_imports_model": row_imports_model,
            "Industry": np.arange(n_industries),
            "number_of_exporters_by_industry": n_exporters_by_industry.astype(int),
            "exogenous_real_imports_before": exogenous_real_imports_before,
            "exogenous_real_imports_during": exogenous_real_imports_during,
            "exogenous_real_exports_before": exogenous_real_exports_before,
            "exogenous_real_exports_during": exogenous_real_exports_during,
        }

        return cls(
            country_name=country_name,
            all_country_names=all_country_names,
            n_industries=n_industries,
            functions=functions,
            ts=ts,
            states=states,
            n_importers=n_importers,
            n_exporters_by_industry=n_exporters_by_industry,
            parameters=configuration.parameters,
            forecasting_window=configuration.forecasting_window,
            assume_zero_growth=configuration.assume_zero_growth,
            assume_zero_noise=configuration.assume_zero_noise,
            configuration=configuration,
        )

    def reset(self, configuration: RestOfTheWorldConfiguration) -> None:
        """Reset ROW state with new configuration.

        Args:
            configuration (RestOfTheWorldConfiguration): New model settings
        """
        self.gen_reset()
        update_functions(
            model=configuration.functions,
            loc="macromodel.rest_of_the_world",
            functions=self.functions,
            force_reset=["imports", "exports"],
        )
        self.parameters = configuration.parameters
        self.forecasting_window = configuration.forecasting_window
        self.assume_zero_growth = configuration.assume_zero_growth
        self.assume_zero_noise = configuration.assume_zero_noise
        self.configuration = configuration

    def estimate_inflation(self, average_country_ppi_inflation: float) -> float:
        """Estimate ROW inflation rate.

        Args:
            average_country_ppi_inflation (float): Average PPI inflation

        Returns:
            float: Estimated ROW inflation rate
        """
        return self.functions["inflation"].compute_inflation(
            average_country_ppi_inflation=average_country_ppi_inflation
        )

    def set_export_demand_index(self, index: "np.ndarray | None") -> None:
        """Target selected industries' PRODUCTION at an external path, via exports.

        ROW's industry composition is otherwise FROZEN: `compute_imports` forecasts an
        aggregate total and splits it by base-year shares, so every industry's exports
        scale as one block and no sector's path can diverge from any other's.

        RESIDUAL TARGETING, and why it is not simply "grow exports by the index".
        Production = domestic absorption + exports. Pinning exports to an external
        PRODUCTION path fails whenever domestic demand is moving: under a deep
        electrification scenario the model's domestic gas demand falls, so exports growing
        in line with production growth still leave production falling. Measured, that
        approach moved gas production only +9.6% against a 38-point gap to CER.

        So exports absorb the residual:

            target_exports = index x base_production  -  domestic_absorption

        which is what an external supply-demand balance does, and the only formulation
        that lets total production track the target while domestic demand stays endogenous.

        `index` is a per-industry multiplier on BASE-YEAR production; entries <= 0 mean
        "not pinned". A no-op when None.
        """
        self._export_demand_index = None if index is None else np.asarray(index, dtype=float)

    def set_export_target_industries(self, industry_indices) -> None:
        """Industries whose index targets EXPORTS directly, not production.

        The default residual formulation targets PRODUCTION and lets exports absorb the
        residual, which is right for oil and gas: CER's export path and its production path
        are the same series, so one index serves both.

        Electricity is the opposite case.  CER has Canada's international electricity
        exports FALLING to 0.892x of the 2014 anchor by 2050 while generation GROWS 2.07x,
        so residual targeting reads the export index as a production target, asks for
        national output at 89% of 2014 minus everything the country consumes, and clamps the
        deeply negative result to zero -- measured: exports to zero and provincial generation
        error worsening from 0.364 to 0.399.  For these industries the index means what it
        says: exports = index x base-year exports, and production stays endogenous.

        Empty by default, so behaviour is unchanged unless this is called.
        """
        self._export_target_industries = {int(i) for i in (industry_indices or [])}

    def set_production_base(self, base_real: "np.ndarray | None") -> None:
        """Base-year REAL production per industry, the level the index multiplies."""
        self._production_base = None if base_real is None else np.asarray(base_real, dtype=float)

    def set_domestic_absorption(self, absorption_real: "np.ndarray | None") -> None:
        """Domestic REAL absorption per industry: production the home economy uses itself.

        Supplied by the simulation, which is the only layer that can see both the
        countries' output and what they consume of it. Lagged one period, which is stable
        and avoids a simultaneity between this target and the market clearing it feeds.
        """
        self._domestic_absorption = None if absorption_real is None else np.asarray(
            absorption_real, dtype=float)

    def set_market_prices(self, prices: "np.ndarray | None") -> None:
        """Countries' production-weighted price per industry, supplied each step.

        Consumed ONLY for industries in :meth:`set_real_terms_export_industries` --
        harmless to supply otherwise.  Lagged one period like absorption.
        """
        self._market_prices = None if prices is None else np.asarray(prices, dtype=float)

    def set_real_terms_export_industries(self, industry_indices) -> None:
        """Industries whose export pin converts at the MARKET's price, not ROW's.

        `desired_imports_in_lcu` is a NOMINAL budget the goods market converts back to
        a real quantity at the market's average price, while ROW's own `price_in_lcu`
        moves every industry by ONE aggregate index. For a pinned industry whose market
        price drifts against that aggregate, the realized real quantity is the target
        times the drift -- measured for D (whose price is exogenously pinned to CER's
        real path, ~0.74x of model CPI by 2050 Net-zero): national D growth 2.35
        against a target consistent with CER's 2.07.

        SELECTIVE BY DESIGN. Converting EVERY pinned industry this way was tried
        (2026-08-13, arm fix1b) and wrecked Net-zero -- the aggregate-indexed nominal
        budgets silently cap the fossil residual export targets (B05b real exports
        9.9bn -> 55.6bn when converted faithfully) and that cap is load-bearing. The
        do-not-rebuild note in _apply_export_demand_index refers to the blanket
        version; this per-industry set exists so D can be corrected without touching
        the fossils. Empty by default, so behaviour is unchanged unless called.
        """
        self._real_terms_export_industries = {int(i) for i in (industry_indices or [])}

    def set_export_price_elasticity(self, industry_indices, epsilon: float | None) -> None:
        """Opt in selected industries to a PRICE-ELASTIC export demand (WTC 2026-10-17).

        ROW's desired imports from the home economy are a NOMINAL budget per industry,
        split from its aggregate import forecast by frozen base-year shares, so a cheaper
        Canadian chemical does not sell more chemicals abroad.  For the industries listed
        here the simulation supplies, each step, a scale M_i = sum_p s_p,i m_p,i, where
        m_p,i = (P_p,i / P_ref,i)^(-epsilon) is province p's relative price change against
        the national production-weighted price (both indexed to their own first-step
        value, so M = 1 at the start and whenever every province moves together) and
        s_p,i the province's lagged share of realised exports.  The budget is multiplied
        by M_i (:meth:`_apply_export_price_elasticity`); the goods market re-divides it
        between provinces with the same m_p,i (clearer.set_row_origin_multipliers).

        Applied to ROW's own import-model budget only: an industry whose export demand
        is a PRODUCTION-mode residual pin (target production minus lagged absorption)
        is skipped with a warning, because that target is itself last period's realised
        exports plus a correction and a multiplier on it would compound every step.
        Empty / None clears the overlay.
        """
        idx = {int(i) for i in (industry_indices or [])}
        if not idx or epsilon is None:
            self._export_price_elasticity = None
        else:
            self._export_price_elasticity = (idx, float(epsilon))
        self._export_elasticity_scale = None
        self._epx_skipped_warned = False

    def set_export_elasticity_scale(self, scale: "np.ndarray | None") -> None:
        """Per-industry multiplier M_i for the price-elastic export demand, supplied each step."""
        self._export_elasticity_scale = None if scale is None else np.asarray(scale, dtype=float)

    def _apply_export_price_elasticity(self) -> None:
        """Multiply the listed industries' desired imports (nominal budget) by M_i."""
        cfg = getattr(self, "_export_price_elasticity", None)
        scale = getattr(self, "_export_elasticity_scale", None)
        if cfg is None or scale is None:
            return
        indices, _eps = cfg
        current = np.array(self.ts.current("desired_imports_in_lcu"), dtype=float)
        if scale.shape != current.shape:
            logger.warning("export price elasticity scale shape %s != %s; not applied.",
                           scale.shape, current.shape)
            return
        prod_pinned = getattr(self, "_last_prod_pinned", None)
        skipped = []
        for i in sorted(indices):
            if not (0 <= i < current.size):
                continue
            if prod_pinned is not None and prod_pinned.shape == current.shape and prod_pinned[i]:
                skipped.append(i)
                continue
            m = scale[i]
            if np.isfinite(m) and m > 0.0:
                current[i] *= m
        if skipped and not getattr(self, "_epx_skipped_warned", False):
            logger.warning(
                "export price elasticity: industries %s are production-mode export pins "
                "(residual targets); the overlay is NOT applied to them.", skipped)
            self._epx_skipped_warned = True
        self.ts.desired_imports_in_lcu[-1] = current

    def set_row_export_elasticity(
        self,
        sigma_by_industry: "dict[int, float] | None",
        *,
        reference: str = "row",
        cap: float = 1.5,
        reference_step: int = 0,
    ) -> None:
        """Opt in selected industries to a REAL-price-elastic export demand (WTC 2026-10-17, doc 5m).

        ``reference_step`` (doc 5r): the overlay is inert (M = 1, no origin factors) until
        ``steps_completed`` reaches it, and the reference prices are captured there instead of
        at the first step, so the baseline's own start-up re-pricing before that step does not
        become an export cut.  0 = the 5m behaviour.

        For each listed industry s the quantity ROW buys from province p becomes

            Q_s,p = Q_s,p_base x (P_s,p / P_world,s) ** (-sigma_s)

        where Q_s,p_base is what the unmodified nominal budget (``compute_imports``, frozen
        base-year sector shares) would have bought from p, P_s,p is the province's
        production-weighted firm price and P_world,s the world price of the good: ROW's own
        offered price for s (``reference="row"``: ``price_in_lcu``, which follows the
        countries' aggregate price index, so a sector that becomes cheaper relative to the
        whole economy sells more abroad in total) or the national production-weighted price
        (``reference="national"``: the 5g form, in which the national purchase cannot grow
        when every province moves together).  Both prices are divided by their own value at
        the first step, so Q = Q_base at equal prices by construction.

        In nominal terms this is a budget multiplier M_s = sum_p s_p (P_s,p / P_world,s)^-sigma
        (s_p the province's lagged share of realised ROW sales of s), supplied each step by the
        simulation (:meth:`set_row_export_elasticity_scale`) and applied in
        :meth:`_apply_row_export_elasticity`, and the same per-province factor on ROW's origin
        shares in the goods market (clearer.set_row_origin_multipliers), so province p's
        quantity moves by (P_s,p / P_world,s)^-sigma relative to the unscaled split.  M_s is
        bounded to [1/cap, cap]: the national ROW purchase of a sector cannot exceed ``cap``
        times (or fall below 1/cap of) its base path.  Production-mode export pins are skipped
        with a warning, as in :meth:`set_export_price_elasticity`.  None / {} clears it.
        """
        sig = {int(i): float(v) for i, v in (sigma_by_industry or {}).items() if float(v) > 0.0}
        ref = str(reference or "row").lower()
        if ref not in ("row", "national"):
            raise ValueError(f"row export elasticity reference must be 'row' or 'national', got {reference!r}")
        cap_f = float(cap) if cap is not None else 1.5
        if not np.isfinite(cap_f) or cap_f < 1.0:
            raise ValueError(f"row export elasticity cap must be >= 1, got {cap!r}")
        step0 = int(reference_step or 0)
        if step0 < 0:
            raise ValueError(f"row export elasticity reference_step must be >= 0, got {reference_step!r}")
        self._row_export_elasticity = (sig, ref, cap_f) if sig else None
        self._row_export_elasticity_reference_step = step0
        self._row_export_elasticity_scale = None
        self._rowe_skipped_warned = False

    def set_row_export_elasticity_scale(self, scale: "np.ndarray | None") -> None:
        """Per-industry budget multiplier M_s for the real-price-elastic export demand, per step."""
        self._row_export_elasticity_scale = None if scale is None else np.asarray(scale, dtype=float)

    def _apply_row_export_elasticity(self) -> None:
        """Multiply the listed industries' desired imports (nominal budget) by the bounded M_s."""
        cfg = getattr(self, "_row_export_elasticity", None)
        scale = getattr(self, "_row_export_elasticity_scale", None)
        if cfg is None or scale is None:
            return
        sigma_by_industry, _ref, cap = cfg
        current = np.array(self.ts.current("desired_imports_in_lcu"), dtype=float)
        if scale.shape != current.shape:
            logger.warning("row export elasticity scale shape %s != %s; not applied.",
                           scale.shape, current.shape)
            return
        prod_pinned = getattr(self, "_last_prod_pinned", None)
        skipped = []
        for i in sorted(sigma_by_industry):
            if not (0 <= i < current.size):
                continue
            if prod_pinned is not None and prod_pinned.shape == current.shape and prod_pinned[i]:
                skipped.append(i)
                continue
            m = scale[i]
            if np.isfinite(m) and m > 0.0:
                # The bound is ROW's: whatever the simulation sends, the national purchase
                # of the sector stays within [1/cap, cap] of its base path.
                current[i] *= float(np.clip(m, 1.0 / cap, cap))
        if skipped and not getattr(self, "_rowe_skipped_warned", False):
            logger.warning(
                "row export elasticity: industries %s are production-mode export pins "
                "(residual targets); the overlay is NOT applied to them.", skipped)
            self._rowe_skipped_warned = True
        self.ts.desired_imports_in_lcu[-1] = current

    def _apply_export_demand_index(self) -> None:
        """Set pinned industries' desired imports to the residual export target."""
        index = getattr(self, "_export_demand_index", None)
        base = getattr(self, "_production_base", None)
        absorption = getattr(self, "_domestic_absorption", None)
        if index is None or base is None or absorption is None:
            return
        current = np.array(self.ts.current("desired_imports_in_lcu"), dtype=float)
        p_now = np.array(self.ts.current("price_in_lcu"), dtype=float)
        shapes = {current.shape, index.shape, base.shape, absorption.shape, p_now.shape}
        if len(shapes) != 1:
            logger.warning("export pinning shape mismatch %s; not applied.", shapes)
            return
        # NOTE (2026-08-13, negative result -- do not rebuild the BLANKET version):
        # converting ALL these real targets at a production-weighted MARKET price
        # instead of ROW's aggregate-indexed `price_in_lcu` was tried to close a
        # relative-price drift in the pinned quantities. A controlled Net-zero pair
        # showed it is much worse: total 2050 production -13.3%, BC to 23%
        # unemployment, generation share-distance 0.161 -> 0.226. ROW's
        # aggregate-indexed nominal budget for the fossil pins is load-bearing under
        # Net-zero, where CER's fossil prices fall relative to the aggregate. The
        # SELECTIVE per-industry conversion below (set_real_terms_export_industries)
        # is the safe form: it touches only the industries explicitly opted in.
        market = getattr(self, "_market_prices", None)
        real_terms = getattr(self, "_real_terms_export_industries", set())
        if real_terms and market is not None and market.shape == p_now.shape:
            usable = np.isfinite(market) & (market > 0.0)
            select = np.zeros(p_now.shape, dtype=bool)
            for i in real_terms:
                if 0 <= int(i) < select.size:
                    select[int(i)] = True
            p_now = np.where(select & usable, market, p_now)
        # Industries whose index is an EXPORT path rather than a production path.
        export_mode = np.zeros(index.shape, dtype=bool)
        for i in getattr(self, "_export_target_industries", set()):
            if 0 <= int(i) < export_mode.size:
                export_mode[int(i)] = True

        priced = np.isfinite(p_now) & (p_now > 0.0)
        prod_pinned = (index > 0.0) & (base > 0.0) & priced & ~export_mode
        # Export-mode needs no production base -- it multiplies base-year EXPORTS instead.
        base_exports_real = np.zeros(index.shape, dtype=float)
        if export_mode.any():
            init_nom = np.array(self.ts.initial("desired_imports_in_lcu"), dtype=float)
            init_p = np.array(self.ts.initial("price_in_lcu"), dtype=float)
            ok = export_mode & np.isfinite(init_p) & (init_p > 0.0) & np.isfinite(init_nom)
            # REAL base-year exports. Deflating by the INITIAL price and re-inflating by the
            # current one below keeps this a real target: the same real/nominal trap the
            # guard at the end of this method was written to catch.
            base_exports_real[ok] = init_nom[ok] / init_p[ok]
        exp_pinned = (index > 0.0) & priced & export_mode & (base_exports_real > 0.0)
        # Remembered for the price-elastic export overlay, which must not multiply a
        # residual (production-mode) target: see set_export_price_elasticity.
        self._last_prod_pinned = prod_pinned

        if not prod_pinned.any() and not exp_pinned.any():
            return

        # Kept as FULL-LENGTH arrays, not compressed to the pinned subset, so the two modes
        # and every diagnostic below index the same way.
        before_all = current.copy()
        target_production = np.zeros(index.shape, dtype=float)
        target_exports_real = np.zeros(index.shape, dtype=float)
        if prod_pinned.any():
            target_production[prod_pinned] = base[prod_pinned] * index[prod_pinned]
            # Exports take whatever the home economy does not. Floored at zero: a target
            # below domestic absorption means the economy already consumes more than the
            # path allows, which is a statement about domestic demand, not a reason for
            # negative exports.
            target_exports_real[prod_pinned] = np.maximum(
                target_production[prod_pinned] - absorption[prod_pinned], 0.0)
            # UNITS: desired_imports_in_lcu is NOMINAL; the real target converts at current
            # prices. Applying a real quantity directly strips every year of inflation.
            current[prod_pinned] = target_exports_real[prod_pinned] * p_now[prod_pinned]
        if exp_pinned.any():
            # EXPORT-TARGETED: the index multiplies base-year REAL exports and production is
            # left endogenous. Deflating the base by the INITIAL price and re-inflating by
            # the current one keeps this a real target.
            target_exports_real[exp_pinned] = (
                base_exports_real[exp_pinned] * index[exp_pinned])
            current[exp_pinned] = target_exports_real[exp_pinned] * p_now[exp_pinned]
        self.ts.desired_imports_in_lcu[-1] = current

        pinned = prod_pinned | exp_pinned
        before = before_all[pinned]

        # DIAGNOSTIC GUARD. Three separate bugs in this feature each produced a clean run
        # with no error and a plausible number: a flag never threaded to its consumer, an
        # index anchored to a different year than the base it multiplied, and a REAL index
        # applied to a NOMINAL series. The last two showed up as demand moving OPPOSITE to
        # its index -- cheap to detect, so it is checked rather than left to the reader.
        after = current[pinned]
        idx = index[pinned]
        contradictory = ((idx > 1.0) & (after < before)) | ((idx < 1.0) & (after > before))
        if contradictory.any():
            where = np.flatnonzero(pinned)[contradictory]
            logger.warning(
                "export pinning moved demand AGAINST its index for industry indices %s -- "
                "index %s, demand %s -> %s. Note this CAN be legitimate under residual "
                "targeting (rising domestic absorption leaves less for export), so check "
                "absorption before assuming a unit or anchor bug.",
                where.tolist(), np.round(idx[contradictory], 4).tolist(),
                np.round(before[contradictory], 1).tolist(),
                np.round(after[contradictory], 1).tolist(),
            )
        # Only meaningful for PRODUCTION-targeted industries: an export-targeted one has no
        # production target for absorption to exceed.
        if prod_pinned.any():
            binding = int(
                (target_production[prod_pinned] - absorption[prod_pinned] <= 0.0).sum())
            if binding:
                logger.warning(
                    "export pinning: %d pinned industries have domestic absorption "
                    "at or above their production target; exports floored at zero.",
                    binding)
        logger.info(
            "export pinning: index %s, target production %s, absorption %s, "
            "export target (real) %s, demand %s -> %s (export-targeted: %s)",
            np.round(idx, 4).tolist(), np.round(target_production[pinned], 1).tolist(),
            np.round(absorption[pinned], 1).tolist(),
            np.round(target_exports_real[pinned], 1).tolist(),
            np.round(before, 1).tolist(), np.round(after, 1).tolist(),
            np.flatnonzero(exp_pinned).tolist(),
        )

    def prepare_buying_goods(
        self,
        aggregate_country_production_index: float,
        aggregate_country_price_index: float,
    ) -> None:
        """Prepare import decisions.

        Determines desired import volumes based on historical data and
        current economic conditions.

        Args:
            aggregate_country_production_index (float): Production level
            aggregate_country_price_index (float): Price level
        """
        historic_total_real_imports = np.concatenate(
            (
                self.states["exogenous_real_imports_before"][-self.forecasting_window :],
                np.sum(
                    np.array(self.ts.historic("imports_in_lcu")) / np.array(self.ts.historic("price_in_lcu")),
                    axis=1,
                ),
            )
        )
        if self.assume_zero_growth:
            self.ts.desired_imports_in_lcu.append(self.ts.initial("desired_imports_in_lcu"))
        else:
            self.ts.desired_imports_in_lcu.append(
                self.functions["imports"].compute_imports(
                    historic_total_real_imports=historic_total_real_imports,
                    historic_total_real_imports_during=self.states["exogenous_real_imports_during"],
                    current_time=len(self.ts.historic("total_exports")),
                    initial_desired_imports=self.ts.initial("desired_imports_in_lcu"),
                    model=self.states["row_imports_model"],
                    aggregate_country_production_index=aggregate_country_production_index,
                    aggregate_country_price_index=aggregate_country_price_index,
                    adjustment_speed=self.parameters.adjustment_speed,
                    assume_zero_noise=self.assume_zero_noise,
                )
            )
        # Pin before converting to USD, so the pinned path flows through everything
        # downstream (USD demand, goods-to-buy, realised exports) unchanged.
        self._apply_export_demand_index()
        # Price-elastic export demand for opted-in industries (after the pin, so a
        # production-mode pin can be recognised and left alone).
        self._apply_export_price_elasticity()
        # Real-price-elastic export demand (doc 5m): the bounded budget multiplier M_s.
        self._apply_row_export_elasticity()
        self.ts.desired_imports_in_usd.append(
            1.0 / self.exchange_rate_usd_to_lcu * self.ts.current("desired_imports_in_lcu")
        )
        assert np.all(self.ts.current("desired_imports_in_usd") >= 0.0)
        self.set_goods_to_buy(
            np.stack(
                [
                    self.ts.current("desired_imports_in_usd") / self.n_transactors_buy
                    for _ in range(self.n_transactors_buy)
                ]
            )
        )

    def prepare_selling_goods(
        self,
        aggregate_country_production_index: float,
        aggregate_country_price_index: float,
    ) -> None:
        """Prepare export decisions.

        Determines desired export volumes and prices based on historical
        data and current economic conditions.

        Args:
            aggregate_country_production_index (float): Production level
            aggregate_country_price_index (float): Price level
        """
        # Set desired exports
        historic_total_real_exports = np.concatenate(
            (
                self.states["exogenous_real_exports_before"][-self.forecasting_window :],
                np.array(self.ts.historic("total_exports")).flatten(),
            )
        )
        if self.assume_zero_growth:
            self.ts.desired_exports_real.append(self.ts.initial("desired_exports_real"))
        else:
            self.ts.desired_exports_real.append(
                self.functions["exports"].compute_exports(
                    historic_total_real_exports=historic_total_real_exports,
                    historic_total_real_exports_during=self.states["exogenous_real_exports_during"],
                    current_time=len(self.ts.historic("total_exports")),
                    initial_desired_exports=self.ts.initial("desired_exports_real"),
                    model=self.states["row_exports_model"],
                    aggregate_country_production_index=aggregate_country_production_index,
                    adjustment_speed=self.parameters.adjustment_speed,
                    assume_zero_noise=self.assume_zero_noise,
                )
            )
        assert np.all(self.ts.current("desired_exports_real") >= 0.0)
        # Cap import-limited industries before the quantities become sellable goods,
        # so the goods market simply sees less ROW supply (no clearing changes needed).
        self._apply_import_limits(aggregate_country_production_index)
        self.set_goods_to_sell(
            np.array(
                reduce(
                    lambda a, b: a + b,
                    (
                        [
                            self.ts.current("desired_exports_real")[industry]
                            / self.states["number_of_exporters_by_industry"][industry]
                        ]
                        * s
                        for industry, s in zip(
                            range(self.n_industries),
                            list(self.states["number_of_exporters_by_industry"]),
                        )
                    ),
                )
            )
        )

        # Set prices
        self.ts.price_in_lcu.append(
            self.functions["prices"].compute_price(
                initial_price=self.ts.initial("price_in_lcu"),
                aggregate_country_price_index=aggregate_country_price_index,
                adjustment_speed=self.parameters.adjustment_speed,
            )
        )
        self.ts.price_in_usd.append(1.0 / self.exchange_rate_usd_to_lcu * self.ts.current("price_in_lcu"))
        assert np.all(self.ts.current("price_in_usd") > 0.0)
        self.ts.price_offered.append(self.ts.current("price_in_usd"))
        self.set_prices(self.ts.current("price_in_usd")[self.states["Industry"]])

        # Seller industries
        self.set_seller_industries(self.states["Industry"])

        # Excess demand
        self.set_maximum_excess_demand(
            self.functions["excess_demand"].set_maximum_excess_demand(
                n_exporters=self.states["number_of_exporters_by_industry"].sum(),
            )
        )

    def prepare_goods_market_clearing(
        self,
        aggregate_country_production_index: float,
        aggregate_country_price_index: float,
    ) -> None:
        """Prepare for goods market clearing.

        Sets up all necessary trade decisions and prices for market clearing.

        Args:
            aggregate_country_production_index (float): Production level
            aggregate_country_price_index (float): Price level
        """
        self.set_exchange_rate(1.0)
        self.prepare_buying_goods(
            aggregate_country_production_index=aggregate_country_production_index,
            aggregate_country_price_index=aggregate_country_price_index,
        )
        self.prepare_selling_goods(
            aggregate_country_production_index=aggregate_country_production_index,
            aggregate_country_price_index=aggregate_country_price_index,
        )

    def update_planning_metrics(
        self,
        aggregate_country_production_index: float,
        aggregate_country_price_index: float,
    ) -> None:
        """Update planning metrics for market participation.

        Args:
            aggregate_country_production_index (float): Production level
            aggregate_country_price_index (float): Price level
        """
        self.prepare_goods_market_clearing(
            aggregate_country_production_index=aggregate_country_production_index,
            aggregate_country_price_index=aggregate_country_price_index,
        )

    def record_bought_goods(self) -> None:
        """Record results of goods market transactions.

        Updates time series with actual trade volumes and values.
        """
        self.ts.exports_real.append(self.ts.current("real_amount_sold"))
        self.ts.total_exports.append([self.ts.current("exports_real").sum()])
        self.ts.imports_in_usd.append(self.ts.current("nominal_amount_spent_in_lcu")[0])
        self.ts.imports_in_lcu.append(self.exchange_rate_usd_to_lcu * self.ts.current("imports_in_usd"))
        self.ts.total_imports.append([self.ts.current("imports_in_lcu").sum()])

    def save_to_h5(self, file: h5py.File) -> None:
        """Save ROW data to HDF5 file.

        Args:
            file (h5py.File): HDF5 file to save to
        """
        group = file.create_group("ROW")
        self.ts.write_to_h5("rest_of_the_world", group)
