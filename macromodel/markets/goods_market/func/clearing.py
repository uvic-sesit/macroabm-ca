"""Market clearing implementations for the goods market.

This module provides different strategies for clearing the goods market, matching
buyers with sellers while respecting various constraints and priorities. It implements
multiple clearing mechanisms:

1. Default Clearing:
   - Random matching with priority weights
   - Supply chain persistence
   - Excess demand handling

2. Pro-rata Clearing:
   - Proportional allocation based on demands
   - Aggregate supply/demand balancing

3. Water Bucket Clearing:
   - Network flow based allocation
   - Trade proportion preservation
   - Priority-based routing

Each clearing mechanism can be configured to handle:
- Domestic vs international trade preferences
- Supply chain relationships
- Price and quantity adjustments
- Priority-based allocation
- Minimum fill rates
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple

import logging

import numpy as np

from macromodel.agents.agent import Agent
from macromodel.markets.goods_market.func.lib_default import (
    check_buyers_left,
    check_sellers_left,
    clean_rounding_errors,
    get_random_buyer,
    get_random_seller,
    handle_hypothetical_transaction,
    handle_transaction,
    update_supply_chain,
)
from macromodel.markets.goods_market.func.lib_pro_rata import (
    collect_buyer_info,
    collect_seller_info,
)
from macromodel.markets.goods_market.func.lib_water_bucket import (
    clear_water_bucket,
    fill_buckets,
    get_buyer_priorities,
    get_seller_priorities_deterministic,
    get_seller_priorities_stochastic,
    get_trade_proportions,
)
from macromodel.markets.goods_market.value_type import ValueType

_rf_log = logging.getLogger(__name__)


class GoodsMarketClearer(ABC):
    """Abstract base class for goods market clearing mechanisms.

    This class defines the interface and common functionality for all market
    clearing implementations. It handles the matching of buyers and sellers
    while respecting various economic constraints and preferences.

    The clearing process follows these general steps:
    1. Preparation of market participants
    2. Collection of supply and demand information
    3. Execution of clearing algorithm
    4. Recording of transactions

    Attributes:
        real_country_prioritisation (float): Weight given to real countries vs ROW [0,1]
        prio_high_prio_buyers (bool): Whether to prioritize high-priority buyers
        prio_high_prio_sellers (bool): Whether to prioritize high-priority sellers
        prio_domestic_sellers (bool): Whether to prioritize domestic sellers
        probability_keeping_previous_seller (float): Chance to maintain supply chains
        price_temperature (float): Price sensitivity parameter
        trade_temperature (float): Trade flow sensitivity parameter
        seller_selection_distribution_type (str): Method for selecting sellers
        seller_minimum_fill (float): Minimum order fill rate for sellers
        buyer_minimum_fill_macro (float): Minimum fill rate for macro buyers
        buyer_minimum_fill_micro (float): Minimum fill rate for micro buyers
        deterministic (bool): Whether to use deterministic matching
        consider_trade_proportions (bool): Whether to use historical trade patterns
        consider_buyer_priorities (bool): Whether to consider buyer priorities
        additionally_available_factor (float): Extra capacity factor
        price_markup (float): Price adjustment factor
        remedy_rounding_errors (bool): Whether to fix rounding errors
        allow_additional_row_exports (bool): Whether to allow extra ROW exports
    """

    def __init__(
        self,
        real_country_prioritisation: float,
        prio_high_prio_buyers: bool,
        prio_high_prio_sellers: bool,
        prio_domestic_sellers: bool,
        probability_keeping_previous_seller: float,
        price_temperature: float,
        trade_temperature: float,
        seller_selection_distribution_type: str,
        seller_minimum_fill: float,
        buyer_minimum_fill_macro: float,
        buyer_minimum_fill_micro: float,
        deterministic: bool,
        consider_trade_proportions: bool,
        consider_buyer_priorities: bool,
        additionally_available_factor: float,
        price_markup: float,
        remedy_rounding_errors: bool = True,
        allow_additional_row_exports: bool = True,
    ):
        """Initialize market clearer with configuration parameters.

        Args:
            real_country_prioritisation (float): Weight for real countries [0,1]
            prio_high_prio_buyers (bool): Prioritize high-priority buyers
            prio_high_prio_sellers (bool): Prioritize high-priority sellers
            prio_domestic_sellers (bool): Prioritize domestic sellers
            probability_keeping_previous_seller (float): Supply chain persistence
            price_temperature (float): Price sensitivity
            trade_temperature (float): Trade sensitivity
            seller_selection_distribution_type (str): Seller selection method
            seller_minimum_fill (float): Minimum seller fill rate
            buyer_minimum_fill_macro (float): Minimum macro buyer fill
            buyer_minimum_fill_micro (float): Minimum micro buyer fill
            deterministic (bool): Use deterministic matching
            consider_trade_proportions (bool): Use trade patterns
            consider_buyer_priorities (bool): Use buyer priorities
            additionally_available_factor (float): Extra capacity
            price_markup (float): Price adjustment
            remedy_rounding_errors (bool): Fix rounding errors
            allow_additional_row_exports (bool): Allow extra ROW exports
        """
        # Ensure prioritisation is between 0 and 1
        self.real_country_prioritisation = max(0.0, min(1.0, real_country_prioritisation))
        self.real_country_prioritisation = real_country_prioritisation

        # Priority flags
        self.prio_high_prio_buyers = prio_high_prio_buyers
        self.prio_high_prio_sellers = prio_high_prio_sellers
        self.prio_domestic_sellers = prio_domestic_sellers

        # Market behavior parameters
        self.probability_keeping_previous_seller = probability_keeping_previous_seller
        self.price_temperature = price_temperature
        self.trade_temperature = trade_temperature
        self.seller_selection_distribution_type = seller_selection_distribution_type

        # Fill rate requirements
        self.seller_minimum_fill = seller_minimum_fill
        self.buyer_minimum_fill_macro = buyer_minimum_fill_macro
        self.buyer_minimum_fill_micro = buyer_minimum_fill_micro

        # Market clearing behavior flags
        self.deterministic = deterministic
        self.consider_trade_proportions = consider_trade_proportions
        self.consider_buyer_priorities = consider_buyer_priorities

        # Additional parameters
        self.additionally_available_factor = additionally_available_factor
        self.price_markup = price_markup
        self.remedy_rounding_errors = remedy_rounding_errors
        self.allow_additional_row_exports = allow_additional_row_exports
        # Industries excluded from the additional-ROW-exports backstop.  That backstop
        # adds to ROW's "Real Amount sold" without reference to "Initial Goods", so
        # capping ROW's desired exports (RestOfTheWorld.set_import_limits) does not bind
        # unless the backstop is suppressed for the same industries.  Empty by default,
        # so behaviour is unchanged unless set_import_limited_industries() is called.
        self._import_limited_industries: set[int] = set()
        # Per-industry external origin shares for ROW's purchases; see
        # set_row_split_override().  Empty by default.
        self._row_split_override: dict[int, np.ndarray] = {}
        self._row_split_strict: bool = False
        # Industries whose origin shares are NOT price-adjusted when trade_temperature > 0
        # (their default / externally written shares are used as they are); see
        # set_trade_temperature_neutral_industries().  Empty by default.
        self._trade_temperature_neutral_industries: set[int] = set()
        # Reference prices for the temperature term, taken at the first clearing: each
        # origin's price is divided by its own reference before exp(-T p), so the shares
        # respond to RELATIVE PRICE CHANGES from the calibrated split, not to level
        # differences between origins. Needed because ROW's offered price carries the
        # data's exchange rate (Price in LCU = rate x 1.0, ~1.3-1.5x the provinces' 1.0
        # index), which exp(-T p) would otherwise read as a 30-50% import premium.
        self._tp_reference_prices: np.ndarray | None = None
        self._row_split_signal: float = 0.0
        # Per-origin multipliers on ROW's DEFAULT origin shares, {country_name: array over
        # industries}; see set_row_origin_multipliers().  Empty by default.
        self._row_origin_multipliers: dict[str, np.ndarray] = {}
        # Fraction of each origin's unfilled DIRECTED orders booked as its sellers' excess
        # demand; see set_origin_shortfall_signal().  0.0 = shipped behaviour.
        self._origin_shortfall_signal: float = 0.0
        # Relative form of the signal: only the orders the PRICE-ADJUSTED origin shares
        # moved toward an origin beyond its DEFAULT share count (doc 5j).
        self._origin_shortfall_relative: bool = False
        # Last step's booked shortfall per (origin, industry), for diagnostics.
        self.last_origin_shortfall: np.ndarray | None = None
        # Industries whose ROW buyers are served BEFORE the domestic pair passes; see
        # set_row_first_industries().  Empty = shipped order (ROW is the last destination).
        self._row_first_industries: list[int] = []
        self._rf_calls: int = 0
        # ROW's open order at the world price for the listed industries (doc 5t); see
        # set_row_world_price_demand().  None = shipped behaviour.
        self._row_world_price_industries: list[int] = []
        self._row_world_price_shares: dict[str, np.ndarray] | None = None
        self._row_world_price_order: str = "before_pool"
        # How ROW's ORDINARY (budgeted) demand for the listed industries reaches the origins
        # (doc 5u): "pool" = the shipped pool, after the world-price pass; "presplit" = split
        # by each origin's remaining supply BEFORE the world-price pass.
        self._row_world_price_ordinary: str = "pool"
        self._rwp_calls: int = 0
        self.last_row_world_price_sales: np.ndarray | None = None
        self.last_row_ordinary_presplit: np.ndarray | None = None
        self._rwp_unfilled: np.ndarray | None = None

    def set_row_world_price_demand(self, industry_indices, shares_by_country, order: str = "before_pool",
                                   ordinary: str = "pool") -> None:
        """ROW buys a share of each listed seller's supply at the seller's price (doc 5t).

        ROW is a NOMINAL buyer with a budget per industry that no supply can enlarge, and with
        the default ``real_country_prioritisation`` it buys provincial goods only in the pool,
        out of what the domestic pair passes left.  A trade-exposed price-taker faces the
        opposite: the world market takes whatever extra it supplies at the world price.  With
        this on, for the listed industries a pre-pass runs before the domestic pair passes:
        for each origin c and industry g ROW places an EXTRA order, on top of its budget, for

            X_c,g = sum_i a_i x supply_i      (sellers i of g in c; ``shares_by_country[c][i]``)

        at the origin's supply-weighted price, which with the price-taker peg is the national
        (world) path.  The order is open-ended in that ROW's budget is raised by exactly what
        it buys; what it does not buy is withdrawn, so ROW's own budget is unchanged for the
        pool.  The origin's domestic destination shares of g are scaled by (1 - sold / supply)
        so the domestic pair passes share the rest without loop-order effects.  The firm's
        recorded demand (sales + excess demand) includes ROW's purchase, so a plan lifted
        above what the domestic market re-orders is re-ordered by ROW.  The caller sets the
        shares each step (a_i in [0, 1], one per seller row of the province's firms; zero or
        absent = no order); all zero = the shipped clearing exactly.

        ``order``: ``"first"`` runs the pass BEFORE the domestic pair passes, with the origin's
        domestic destination shares scaled to what ROW left (the domestic buyers then lose that
        supply and refill it from other provinces through the pool and the excess-demand
        distribution); ``"before_pool"`` (default) runs it AFTER the domestic pair passes and
        BEFORE the unconstrained pool, on what the domestic pair passes left, and books the
        part of ROW's order the origin could not fill as excess demand on its sellers of the
        good (after the global excess distribution, which assigns rather than adds), so the
        firm's recorded demand carries the whole order and its plan grows into it while the
        domestic destinations keep their calibrated shares.

        ``ordinary`` (doc 5u): ``"pool"`` (default) leaves ROW's own budget for the listed
        industries to the unconstrained pool, which splits it by the origins' REMAINING supply,
        i.e. after the world-price pass has taken its share: the more ROW buys of an origin at
        the world price, the less of its ordinary budget lands there.  ``"presplit"`` (order
        ``"before_pool"`` only) clears ROW's ordinary demand for the listed industries origin
        by origin BEFORE the world-price pass, each origin getting what the pool would have
        given it, so the world-price order is added to the origin's ordinary ROW sales instead
        of re-dividing them (see ``_row_ordinary_presplit``).
        """
        o = str(order or "before_pool").lower()
        if o not in ("first", "before_pool"):
            raise ValueError(f"row world-price order must be 'first' or 'before_pool', got {order!r}")
        ordn = str(ordinary or "pool").lower()
        if ordn not in ("pool", "presplit"):
            raise ValueError(f"row world-price ordinary must be 'pool' or 'presplit', got {ordinary!r}")
        if ordn == "presplit" and o != "before_pool":
            raise ValueError("row world-price ordinary = 'presplit' needs order 'before_pool'")
        self._row_world_price_order = o
        self._row_world_price_ordinary = ordn
        self._row_world_price_industries = sorted({int(i) for i in (industry_indices or [])})
        if not shares_by_country:
            self._row_world_price_shares = None
            return
        self._row_world_price_shares = {
            str(k): np.clip(np.nan_to_num(np.asarray(v, dtype=float)), 0.0, 1.0)
            for k, v in shares_by_country.items()
        }

    def set_row_first_industries(self, industry_indices, mode: str = "all") -> None:
        """Serve ROW's directed orders for these industries before any domestic buyer (doc 5r).

        In the trade-proportion passes each origin c1 is cleared against destinations in
        order, ROW last, and each pass offers at most ``destin_share[c1, d] x initial
        supply``: ROW's demand directed at c1 (``origin_share[c1, ROW] x ROW's demand``,
        which the export overlays scale up for a cheaper origin) is capped by c1's
        calibrated ROW share of its own output, and what a sold-out origin cannot fill goes
        to the pool and is filled by whoever has slack.  With this on, for the listed
        industries a pre-pass runs before the pair loop: each origin offers ALL its supply
        to ROW's directed orders (buyer side still ``min(origin_share x initial,
        remaining)``), and the regular c1 -> ROW pass skips them, so ROW's orders at an
        origin are filled first and the domestic destinations share what is left.  None or
        [] restores the shipped order.

        ``mode``: ``"all"`` (above) or ``"share"``: the pre-pass offers ROW only the origin's
        (price-adjusted) ROW destination share times the export overlays' factor for that
        origin (``set_row_origin_multipliers``; 1 when no overlay is on), capped at all of
        its supply.  At factor 1 this is the shipped allocation; a cheaper origin whose
        overlay factor rose ships ROW that much more of its output, first.  "all" starved
        the domestic users of the listed goods and collapsed the WTC baseline (doc 5r).
        With the default ``real_country_prioritisation`` (10, clipped to 1) the prioritised
        ROW destination share is ZERO, so "share" is the shipped clearing exactly: provinces
        sell to ROW only in the pool, out of what the domestic pair passes left.
        ``"calibrated"``: the pre-pass offers ROW the CALIBRATED (IO, pre-prioritisation)
        ROW destination share times the overlay factor, and the origin's domestic destination
        shares for these industries are scaled by (1 - that share), so the caps still sum to
        the origin's supply and the domestic destinations' loop order does not matter.
        """
        m = str(mode or "all").lower()
        if m not in ("all", "share", "calibrated"):
            raise ValueError(f"row-first mode must be 'all', 'share' or 'calibrated', got {mode!r}")
        self._row_first_industries = sorted({int(i) for i in (industry_indices or [])})
        self._row_first_mode = m

    def set_origin_shortfall_signal(self, fraction: float, relative: bool = False) -> None:
        """Book orders directed at an origin that it could not fill as its excess demand.

        In the trade-proportion passes each buyer's demand is split across origins by the
        (price-adjusted) origin shares, so a cheaper origin is DIRECTED more orders.  If it
        cannot fill them, the remainder goes to the unconstrained pool and is filled from
        whichever province has slack, and the global excess-demand distribution afterwards
        assigns what is still unmet by SUPPLY share.  The origin that was asked and could
        not deliver therefore never sees those orders, its demand estimate reads only what
        it sold, and its plan cannot grow (WTC 2026-10-17, doc 5i).

        With ``fraction`` > 0, after the pool and the global distribution, each origin's
        sellers of good g receive ``fraction x max(directed_g - sold_g, 0)`` as additional
        real excess demand, where directed_g is the real demand the passes directed at the
        origin (summed over destinations, converted at the origin's price) and sold_g its
        realised real sales of g this step (pool backfill included, so an origin that ended
        up selling more than was directed at it gets nothing).  Spread over the origin's
        sellers in proportion to their initial supply.  Damp it (0.5): the same signal at
        1.0 for the ROW split over-invested Ontario's electricity (arm S3, 2026-08).

        ``relative`` (WTC 2026-10-17, doc 5j): with most firms sold out, most origins have
        directed orders they did not fill in every pass, so the absolute form above is an
        economy-wide expansion (doc 5i).  The relative form books only the orders that the
        PRICE-ADJUSTED origin shares moved toward the origin beyond its DEFAULT (calibrated
        IO) share: directed_excess_g = sum over destinations d of
        max(share_adjusted[origin, d, g] - share_default[origin, d, g], 0) x d's initial
        demand for g (real, at the origin's price), and the booking is
        ``fraction x min(directed_excess_g, max(directed_g - sold_g, 0))``.  Zero wherever
        the shares sit at their defaults, so the baseline is untouched by construction up
        to its own relative-price drift, and only an origin that became cheaper (and was
        therefore asked for more than its calibrated share) sees the orders it missed.
        """
        self._origin_shortfall_signal = max(0.0, min(1.0, float(fraction)))
        self._origin_shortfall_relative = bool(relative)

    def set_row_origin_multipliers(self, multipliers_by_country) -> None:
        """Scale the default origin shares of ROW's purchases, per origin and industry.

        Used by the price-elastic export overlay (WTC 2026-10-17): province p's default
        share of ROW's purchases of good g is multiplied by m_p,g before the temperature
        adjustment and the renormalisation in ``get_trade_proportions``, so ROW's demand
        is re-divided toward origins whose relative price fell.  The ROW total is set
        upstream (RestOfTheWorld.set_export_elasticity_scale); this only moves the split.
        Only ROW as DESTINATION is touched; the provinces' purchases are unaffected.
        Passing None or {} clears it.
        """
        cleaned: dict[str, np.ndarray] = {}
        for name, arr in (multipliers_by_country or {}).items():
            a = np.asarray(arr, dtype=float).copy()
            a[~np.isfinite(a) | (a <= 0.0)] = 1.0
            cleaned[str(name)] = a
        self._row_origin_multipliers = cleaned

    def set_row_split_override(self, shares_by_industry, *, strict: bool = False,
                               signal_shortfall: float = 0.0) -> None:
        """Route ROW's demand for SPECIFIC industries to externally supplied origin shares.

        Unlike an all-industry base-year anchor -- rejected twice for destabilising
        scenarios that move production geography -- this takes
        {industry_index: shares_over_countries} for a chosen few
        industries, and the shares may be updated per year by the caller.  Built for
        sector D: ROW's electricity purchases (international interchange plus
        hydrogen-electrolysis load) belong in the provinces CER says export and make
        hydrogen, not wherever the pool finds slack.  Shares are normalised here; the
        entry for ROW's own position must be 0.  Passing None or {} disables it.

        As a pure first-pass hint the split does NOT bind: the pool backfills whatever an
        origin could not supply, from whichever province has slack.  Measured (S2 pair,
        2026-08-13): Ontario delivered 0.8% of ROW's D demand against a 24.2% anchored
        share -- its supply is fully committed domestically by the time the anchored pass
        runs -- while Quebec delivered 31% against 15.6% and Manitoba 11.5% against 4.4%.
        Two opt-ins close the loop:

        - ``strict``: ROW's demand for an override industry that its anchored origins
          cannot fill is WITHDRAWN, not pooled. Realised exports may run under the index
          while origins grow in; without it the split is decorative for any origin whose
          supply is domestically committed.
        - ``signal_shortfall``: the FRACTION (0..1) of each origin's unfilled allocation
          booked as REAL excess demand on that origin's sellers of that industry (after
          the global excess-demand distribution, which would otherwise hand the signal
          to whichever province has spare supply -- the same defect the split corrects,
          one step earlier). This is what lets an origin PLAN for the order book it
          keeps missing: demand estimation reads recorded excess demand. DAMP IT:
          measured at 1.0 (arm S3), Ontario -- under-filled for 20 straight years --
          over-invested past its share (generation ratio 1.52 vs CER, growth 2.48 vs
          2.05) and its cheapened electricity inflated its own demand; 0.0 (arm S4)
          leaves the origin blind and exports permanently under-run.
        """
        cleaned: dict[int, np.ndarray] = {}
        for g, shares in (shares_by_industry or {}).items():
            arr = np.asarray(shares, dtype=float).copy()
            arr[~np.isfinite(arr)] = 0.0
            arr[arr < 0.0] = 0.0
            total = float(arr.sum())
            if total > 0.0:
                cleaned[int(g)] = arr / total
        self._row_split_override = cleaned
        self._row_split_strict = bool(strict)
        self._row_split_signal = max(0.0, min(1.0, float(signal_shortfall)))

    def set_trade_temperature_neutral_industries(self, industry_indices) -> None:
        """Exclude industries from the price adjustment of the origin trade shares.

        ``get_trade_proportions`` scales every origin's share by
        exp(-trade_temperature x price); for the industries listed here every origin is
        given the same price instead, so the factor cancels in the normalisation and the
        default (or externally written) origin shares pass through unchanged.  Used for
        sectors whose prices are exogenous paths and whose origin split is set elsewhere
        (electricity under the COPPER import shares, CIMS-pinned fuels).

        Args:
            industry_indices: industry indices to exclude; empty/None clears the set.
        """
        self._trade_temperature_neutral_industries = {int(i) for i in (industry_indices or [])}

    def set_domestic_only_industries(self, industry_indices) -> None:
        """Make industries non-tradable: every participant buys them only from itself.

        After the price adjustment, the origin shares of these goods are set to the identity
        (buyer c sources 100% from origin c) and the destination shares likewise (origin c
        sells 100% to c). Intended for real estate (imputed rent), whose interprovincial
        "exports" in the IO table are an accounting split, not a market that can crowd a
        small province's capacity-constrained supplier out (WTC Atlantic PEI artefact, doc 5x).
        Empty/None clears the set; shipped behaviour is unchanged unless this is called.
        """
        self._domestic_only_industries = {int(i) for i in (industry_indices or [])}

    def set_import_limited_industries(self, industry_indices) -> None:
        """Exclude industries from the additional-ROW-exports backstop.

        Args:
            industry_indices: industry indices to exclude; empty/None clears the set.
        """
        self._import_limited_industries = {int(i) for i in (industry_indices or [])}

    @staticmethod
    def prepare(goods_market_participants: dict[str, list[Agent]]) -> None:
        """Prepare market participants for clearing.

        Calls prepare() on all market participants to initialize their
        trading states for the current period.

        Args:
            goods_market_participants (dict[str, list[Agent]]): Market participants by country
        """
        for country_name in goods_market_participants.keys():
            for transactor in goods_market_participants[country_name]:
                transactor.prepare()

    @staticmethod
    def collect_all_supply_and_demand(
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        buyer_high_prio_only: bool = False,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Collect aggregate supply and demand data.

        Gathers total supply and demand information across all industries and
        participants, optionally filtering for high-priority buyers only.

        Args:
            goods_market_participants (dict[str, list[Agent]]): Market participants
            n_industries (int): Number of industries
            buyer_high_prio_only (bool): Whether to only include high-priority buyers

        Returns:
            tuple[np.ndarray, np.ndarray]: Aggregate nominal supply and demand arrays
        """
        # Collect seller (supply) information
        (
            total_real_supply,
            aggr_real_supply,
            total_nominal_supply,
            aggr_nominal_supply,
            average_goods_price,
        ) = collect_seller_info(
            goods_market_participants=goods_market_participants,
            n_industries=n_industries,
        )

        # Collect buyer (demand) information
        (
            total_real_demand,
            aggr_real_demand,
            total_nominal_demand,
            aggr_nominal_demand,
        ) = collect_buyer_info(
            goods_market_participants=goods_market_participants,
            average_price=average_goods_price,
            n_industries=n_industries,
            high_prio_only=buyer_high_prio_only,
        )

        return aggr_nominal_supply, aggr_nominal_demand

    @abstractmethod
    def clear(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        default_origin_trade_proportions: np.ndarray,
        default_destin_trade_proportions: np.ndarray,
        buyer_priorities: dict[str, np.ndarray],
        previous_supply_chain: dict[int, dict[Agent, dict[int, list[Tuple[Agent, int]]]]],
        current_supply_chain: dict[int, dict[Agent, dict[int, list[Tuple[Agent, int]]]]],
        row_index: int = -1,
    ) -> None:
        """Execute market clearing algorithm.

        Abstract method that must be implemented by concrete clearers to match
        buyers with sellers and execute transactions.

        Args:
            goods_market_participants (dict[str, list[Agent]]): Market participants
            n_industries (int): Number of industries
            default_origin_trade_proportions (np.ndarray): Historical origin shares
            default_destin_trade_proportions (np.ndarray): Historical destination shares
            buyer_priorities (dict[str, np.ndarray]): Buyer priority rankings
            previous_supply_chain (dict): Previous period's supply chain
            current_supply_chain (dict): Current period's supply chain
            row_index (int): Rest of World index. Defaults to -1.
        """
        pass

    @staticmethod
    def record(goods_market_participants: dict[str, list[Agent]]) -> None:
        """Record market clearing outcomes.

        Calls record() on all market participants to save their final
        trading positions for the current period.

        Args:
            goods_market_participants (dict[str, list[Agent]]): Market participants
        """
        for country_name in goods_market_participants.keys():
            for transactor in goods_market_participants[country_name]:
                transactor.record()


class NoGoodsMarketClearer(GoodsMarketClearer):
    """Null implementation of market clearing.

    This implementation does nothing during clearing, effectively creating
    a market with no transactions. Useful for testing and debugging.
    """

    def clear(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        default_origin_trade_proportions: np.ndarray,
        default_destin_trade_proportions: np.ndarray,
        buyer_priorities: dict[str, np.ndarray],
        previous_supply_chain: dict[int, dict[Agent, dict[int, list[Tuple[Agent, int]]]]],
        current_supply_chain: dict[int, dict[Agent, dict[int, list[Tuple[Agent, int]]]]],
        row_index: int = -1,
    ) -> None:
        """No-op implementation of market clearing.

        Args:
            goods_market_participants (dict[str, list[Agent]]): Unused
            n_industries (int): Unused
            default_origin_trade_proportions (np.ndarray): Unused
            default_destin_trade_proportions (np.ndarray): Unused
            buyer_priorities (dict[str, np.ndarray]): Unused
            previous_supply_chain (dict): Unused
            current_supply_chain (dict): Unused
            row_index (int): Unused
        """
        pass


class DefaultGoodsMarketClearer(GoodsMarketClearer):
    """Default implementation of market clearing.

    This implementation uses a random matching algorithm with priorities and
    constraints. For each industry, it:
    1. Matches buyers and sellers based on priorities and preferences
    2. Executes transactions and updates supply chains
    3. Handles excess demand through additional matching rounds
    4. Maintains supply chain relationships where possible
    """

    def clear(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        default_origin_trade_proportions: np.ndarray,
        default_destin_trade_proportions: np.ndarray,
        buyer_priorities: dict[str, np.ndarray],
        previous_supply_chain: dict[int, dict[Agent, dict[int, list[Tuple[Agent, int]]]]],
        current_supply_chain: dict[int, dict[Agent, dict[int, list[Tuple[Agent, int]]]]],
        row_index: int = -1,
    ) -> None:
        """Execute the default market clearing algorithm.

        Processes each industry sequentially, matching buyers with sellers
        until either supply or demand is exhausted. Then handles any
        remaining excess demand.

        Args:
            goods_market_participants (dict[str, list[Agent]]): Market participants
            n_industries (int): Number of industries
            default_origin_trade_proportions (np.ndarray): Historical origin shares
            default_destin_trade_proportions (np.ndarray): Historical destination shares
            buyer_priorities (dict[str, np.ndarray]): Buyer priority rankings
            previous_supply_chain (dict): Previous period's supply chain
            current_supply_chain (dict): Current period's supply chain
            row_index (int): Rest of World index

        Note:
            The clearing process for each industry follows these steps:
            1. Check for active buyers and sellers
            2. Match buyers and sellers considering:
               - Priorities and preferences
               - Previous supply chain relationships
               - Price and trade sensitivities
            3. Execute transactions and update supply chains
            4. Handle excess demand if any remains
        """
        # Process each industry separately
        for g in range(n_industries):
            # Check if there are any buyers or sellers left
            if (
                not check_buyers_left(
                    industry=g,
                    goods_market_participants=goods_market_participants,
                    field="Remaining Goods",
                )
            ) or (
                not check_sellers_left(
                    industry=g,
                    goods_market_participants=goods_market_participants,
                    field="Remaining Goods",
                )
            ):
                continue

            # Main clearing loop: match buyers and sellers until no more matches possible
            while True:
                # Select a random buyer based on priorities and preferences
                buyer, buyer_ind = get_random_buyer(
                    industry=g,
                    goods_market_participants=goods_market_participants,
                    real_country_prioritisation=self.real_country_prioritisation,
                    prio_high_prio=self.prio_high_prio_buyers,
                    field="Remaining Goods",
                )

                # Select a seller considering:
                # - Previous supply chain relationships
                # - Price competitiveness
                # - Domestic vs international preferences
                seller, seller_ind = get_random_seller(
                    industry=g,
                    goods_market_participants=goods_market_participants,
                    chosen_buyer=buyer,
                    chosen_buyer_ind=buyer_ind,
                    previous_supply_chain=previous_supply_chain,
                    real_country_prioritisation=self.real_country_prioritisation,
                    prio_high_prio_sellers=self.prio_high_prio_sellers,
                    prio_domestic_sellers=self.prio_domestic_sellers,
                    probability_keeping_previous_seller=self.probability_keeping_previous_seller,
                    price_temperature=self.price_temperature,
                    field="Remaining Goods",
                    distribution_type=self.seller_selection_distribution_type,
                )

                # Execute the transaction between matched buyer and seller
                handle_transaction(
                    industry=g,
                    buyer=buyer,
                    buyer_ind=buyer_ind,
                    seller=seller,
                    seller_ind=seller_ind,
                )

                # Record the transaction in the supply chain
                update_supply_chain(
                    current_supply_chain=current_supply_chain,
                    industry=g,
                    buyer=buyer,
                    buyer_ind=buyer_ind,
                    seller=seller,
                    seller_ind=seller_ind,
                )

                # Check if we've exhausted either supply or demand
                if (
                    not check_buyers_left(
                        industry=g,
                        goods_market_participants=goods_market_participants,
                        field="Remaining Goods",
                    )
                ) or (
                    not check_sellers_left(
                        industry=g,
                        goods_market_participants=goods_market_participants,
                        field="Remaining Goods",
                    )
                ):
                    break

            # Handle excess demand after main clearing
            # Copy remaining demand to excess demand field
            for country_name in goods_market_participants.keys():
                for transactor in goods_market_participants[country_name]:
                    if transactor.transactor_buyer_states["Value Type"] != ValueType.NONE:
                        transactor.transactor_buyer_states["Remaining Excess Goods"] = (
                            transactor.transactor_buyer_states["Remaining Goods"].copy()
                        )

            # Try to satisfy excess demand if possible
            while check_buyers_left(
                industry=g,
                goods_market_participants=goods_market_participants,
                field="Remaining Excess Goods",
            ):
                if not check_sellers_left(
                    industry=g,
                    goods_market_participants=goods_market_participants,
                    field="Remaining Goods",
                ):
                    break

                # Get a random buyer
                buyer, buyer_ind = get_random_buyer(
                    industry=g,
                    goods_market_participants=goods_market_participants,
                    real_country_prioritisation=self.real_country_prioritisation,
                    prio_high_prio=self.prio_high_prio_buyers,
                    field="Remaining Excess Goods",
                )

                # Get a random seller
                seller, seller_ind = get_random_seller(
                    industry=g,
                    goods_market_participants=goods_market_participants,
                    chosen_buyer=buyer,
                    chosen_buyer_ind=buyer_ind,
                    previous_supply_chain=previous_supply_chain,
                    real_country_prioritisation=self.real_country_prioritisation,
                    prio_high_prio_sellers=self.prio_high_prio_sellers,
                    prio_domestic_sellers=self.prio_domestic_sellers,
                    probability_keeping_previous_seller=self.probability_keeping_previous_seller,
                    price_temperature=self.price_temperature,
                    field="Remaining Excess Goods",
                    distribution_type=self.seller_selection_distribution_type,
                )

                # Handle hypothetical transaction
                handle_hypothetical_transaction(
                    industry=g,
                    buyer=buyer,
                    buyer_ind=buyer_ind,
                    seller=seller,
                    seller_ind=seller_ind,
                )

        # Clean up
        if self.remedy_rounding_errors:
            clean_rounding_errors(goods_market_participants=goods_market_participants)


class WaterBucketGoodsMarketClearer(GoodsMarketClearer):
    """Network flow-based market clearing implementation using the water bucket algorithm.

    This implementation models market clearing as a network flow problem, where supply
    and demand are distributed through the network like water flowing through buckets.
    The algorithm:

    1. Trade Flow Management:
       - Uses origin and destination trade proportions to guide flows
       - Adjusts flows based on price differentials between countries
       - Maintains historical trade relationships while allowing for adaptation

    2. Priority-Based Allocation:
       - Handles high-priority buyers (e.g., critical industries) first
       - Supports both deterministic and stochastic seller selection
       - Allows for domestic market preference

    3. Multi-Stage Clearing:
       - First clears according to trade proportions if enabled
       - Then performs general clearing for remaining supply/demand
       - Finally handles excess demand and additional ROW exports

    4. Price Sensitivity:
       - Incorporates price differences in seller selection
       - Adjusts trade flows based on price competitiveness
       - Applies markups for additional ROW exports

    Key Features:
    - Network flow optimization for efficient allocation
    - Support for minimum fill rates for both buyers and sellers
    - Flexible priority system for critical market participants
    - Sophisticated handling of international trade flows
    - Robust excess demand management
    """

    def clear(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        default_origin_trade_proportions: np.ndarray,
        default_destin_trade_proportions: np.ndarray,
        buyer_priorities: dict[str, np.ndarray],
        previous_supply_chain: dict[int, dict[Agent, dict[int, list[Tuple[Agent, int]]]]],
        current_supply_chain: dict[int, dict[Agent, dict[int, list[Tuple[Agent, int]]]]],
        row_index: int = -1,
    ) -> None:
        """Execute the water bucket market clearing algorithm.

        This method implements a sophisticated market clearing mechanism that models
        trade flows like water flowing through a network of buckets. It operates in
        multiple stages to ensure efficient and fair allocation of resources.

        Args:
            goods_market_participants: Dict mapping country names to lists of trading agents
            n_industries: Number of industries in the model
            default_origin_trade_proportions: Historical proportions of trade flows from origin
                countries, shape (n_countries, n_countries, n_industries)
            default_destin_trade_proportions: Historical proportions of trade flows to destination
                countries, shape (n_countries, n_countries, n_industries)
            buyer_priorities: Dict mapping country names to priority arrays for buyers
            previous_supply_chain: Previous period's supply chain relationships
            current_supply_chain: Current period's supply chain relationships
            row_index: Index for Rest of World in the country arrays

        Algorithm Stages:
        1. Price Collection:
           - Gathers average prices by country and industry
           - Handles missing prices using ROW averages
           - Ensures positive prices for all industries

        2. Trade Proportion-Based Clearing:
           - If enabled, first clears according to historical trade patterns
           - Adjusts proportions based on price competitiveness
           - Processes each country pair sequentially

        3. General Clearing:
           - Clears remaining supply and demand without trade constraints
           - Uses price-weighted matching for efficiency

        4. Excess Demand Handling:
           - Processes any remaining excess demand
           - Applies water bucket algorithm for fair distribution

        5. Additional ROW Exports:
           - If enabled, allows extra purchases from ROW
           - Applies price markup for additional exports
           - Prioritizes critical industries
        """
        n_countries = len(goods_market_participants.keys())

        # Calculate average prices by country and industry
        average_prices_by_country = np.zeros((n_countries + 1, n_industries))
        for ind, country_name in enumerate(goods_market_participants.keys()):
            for gmp in goods_market_participants[country_name]:
                if gmp.transactor_settings["Seller Value Type"] != ValueType.NONE:
                    average_prices_by_country[ind] = gmp.ts.current("price_offered")
                    break
        (
            _,
            _,
            _,
            _,
            average_prices_by_country[-1],
        ) = collect_seller_info(
            goods_market_participants=goods_market_participants,
            n_industries=n_industries,
        )
        assert np.all(average_prices_by_country[0:-1] > 0.0)

        # Real demand directed at each origin by the trade-proportion passes (origin
        # shortfall signal); stays None unless the signal is on.
        directed_demand = None
        # Relative form: real demand the price-adjusted shares moved toward each origin
        # beyond its default share (see set_origin_shortfall_signal); None unless on.
        directed_excess = None
        shortfall_relative = bool(getattr(self, "_origin_shortfall_relative", False))

        # Clear markets using trade proportions if enabled
        if self.consider_trade_proportions:
            # Get price-adjusted trade proportions
            # ROW's destination share, either frozen (default) or scaled to its own
            # current demand.  Done HERE rather than inside get_trade_proportions because
            # that function is numba-compiled and cannot take an optional array.  Passing
            # real_country_prioritisation=0.0 makes its own ROW line `(1 - 0) * share`,
            # i.e. a pass-through of whatever we put in.
            tp_prices = average_prices_by_country
            # The calibrated (IO) origin shares, before the export overlay scales ROW's
            # column: the reference for the relative shortfall signal below.
            default_origin_unscaled = default_origin_trade_proportions
            # Price-elastic export overlay: scale ROW's default origin shares per origin
            # (copy: the market's state array must not accumulate the multipliers).
            row_mult = getattr(self, "_row_origin_multipliers", None)
            if row_mult and row_index >= 0:
                names = list(goods_market_participants.keys())
                scaled = default_origin_trade_proportions.copy()
                for name, m in row_mult.items():
                    if name in names and m.shape[0] == scaled.shape[2]:
                        scaled[names.index(name), row_index, :] *= m
                default_origin_trade_proportions = scaled
            if self.trade_temperature != 0.0:
                ref = getattr(self, "_tp_reference_prices", None)
                if ref is None:
                    ref = average_prices_by_country.copy()
                    ref[~(ref > 0.0)] = 1.0
                    self._tp_reference_prices = ref
                # Relative price index per origin (1.0 at the first clearing).
                tp_prices = average_prices_by_country / ref
                neutral = getattr(self, "_trade_temperature_neutral_industries", None)
                if neutral:
                    # Same price for every origin in these industries -> exp(-T p) cancels.
                    for g in neutral:
                        tp_prices[:, g] = 1.0
            origin_trade_proportions, destin_trade_proportions = get_trade_proportions(
                n_countries=n_countries,
                default_origin_trade_proportions=default_origin_trade_proportions,
                default_destin_trade_proportions=default_destin_trade_proportions,
                average_prices_by_country=tp_prices,
                temperature=self.trade_temperature,
                real_country_prioritisation=self.real_country_prioritisation,
                row_index=row_index,
            )
            dom_only = getattr(self, "_domestic_only_industries", None)
            if dom_only:
                # Non-tradable goods (doc 5x): each participant buys from and sells to itself.
                eye = np.eye(origin_trade_proportions.shape[0])
                for g in dom_only:
                    if 0 <= g < origin_trade_proportions.shape[2]:
                        origin_trade_proportions[:, :, g] = eye
                        destin_trade_proportions[:, :, g] = eye
            if self._origin_shortfall_signal > 0.0 and shortfall_relative:
                directed_excess = self._directed_excess_beyond_default(
                    goods_market_participants=goods_market_participants,
                    n_industries=n_industries,
                    origin_trade_proportions=origin_trade_proportions,
                    default_origin_trade_proportions=default_origin_unscaled,
                    average_prices_by_country=average_prices_by_country,
                    row_index=row_index,
                )
            # Optional buyer-specific origin shares: per-buyer multipliers on these
            # price-adjusted proportions, used by the pair passes below.
            buyer_sourcing = getattr(self, "buyer_sourcing", None)
            if buyer_sourcing is not None:
                buyer_sourcing.prepare(
                    goods_market_participants=goods_market_participants,
                    origin_tp=origin_trade_proportions,
                    default_origin_tp=default_origin_trade_proportions,
                )

            # ROW-first pre-pass for the listed industries (doc 5r; see
            # set_row_first_industries): each origin offers ROW all its supply ("all"), its
            # overlay-scaled (prioritised) ROW share ("share"), or its CALIBRATED ROW share x
            # the overlay factor ("calibrated"; the domestic destination shares are scaled to
            # the remainder), and the pair loop below then skips c1 -> ROW for them.
            pair_origin_tp = origin_trade_proportions
            pair_destin_tp = destin_trade_proportions
            row_first = getattr(self, "_row_first_industries", None)
            if row_first and row_index >= 0:
                gs = np.asarray([g for g in row_first if 0 <= g < n_industries], dtype=int)
                rf_mode = getattr(self, "_row_first_mode", "all")
                names_rf = list(goods_market_participants.keys())
                row_mult_rf = getattr(self, "_row_origin_multipliers", None) or {}
                first_origin = np.zeros_like(origin_trade_proportions)
                first_destin = np.zeros_like(destin_trade_proportions)
                pair_origin_tp = np.array(origin_trade_proportions, copy=True)
                if rf_mode == "calibrated":
                    pair_destin_tp = np.array(destin_trade_proportions, copy=True)
                for c1 in range(n_countries):
                    if c1 == row_index or gs.size == 0:
                        continue
                    first_origin[c1, row_index, gs] = origin_trade_proportions[c1, row_index, gs]
                    m_c1 = row_mult_rf.get(names_rf[c1])
                    f = np.asarray(m_c1, dtype=float)[gs] if m_c1 is not None else np.ones(gs.size)
                    if rf_mode == "share":
                        first_destin[c1, row_index, gs] = np.minimum(
                            np.nan_to_num(destin_trade_proportions[c1, row_index, gs]) * f, 1.0)
                    elif rf_mode == "calibrated":
                        # The calibrated (IO) ROW destination share, before the real-country
                        # prioritisation zeroes it in get_trade_proportions.
                        s_row = np.minimum(np.nan_to_num(np.asarray(
                            default_destin_trade_proportions[c1, row_index, gs], dtype=float)) * f, 1.0)
                        first_destin[c1, row_index, gs] = s_row
                        for c2 in range(n_countries):
                            if c2 != row_index:
                                pair_destin_tp[c1, c2, gs] = pair_destin_tp[c1, c2, gs] * (1.0 - s_row)
                    else:
                        first_destin[c1, row_index, gs] = 1.0
                    pair_origin_tp[c1, row_index, gs] = 0.0
                for c1 in range(n_countries):
                    if c1 == row_index or not np.any(first_origin[c1, row_index] > 0.0):
                        continue
                    directed_pair = self.perform_clearing(
                        goods_market_participants=goods_market_participants,
                        n_industries=n_industries,
                        average_prices_by_country=average_prices_by_country,
                        buyer_priorities=buyer_priorities,
                        start_country=c1,
                        end_country=row_index,
                        origin_trade_proportions=first_origin,
                        destin_trade_proportions=first_destin,
                    )
                    if self._origin_shortfall_signal > 0.0:
                        if directed_demand is None:
                            directed_demand = np.zeros((n_countries, n_industries))
                        directed_demand[c1] += np.nan_to_num(directed_pair)
                    # Diagnostic (doc 5r): ROW's directed real orders at the origin, the shipped
                    # seller cap (prioritised ROW share x initial supply) and this mode's cap.
                    if getattr(self, "_rf_calls", 0) % 16 == 0 and names_rf[c1][-2:] in ("AB", "BC", "NB"):
                        init = np.zeros(n_industries)
                        for t in goods_market_participants[names_rf[c1]]:
                            if t.transactor_seller_states["Value Type"] == ValueType.REAL:
                                np.add.at(init, np.asarray(t.transactor_seller_states["Industries"]),
                                          np.nan_to_num(np.asarray(t.transactor_seller_states["Initial Goods"], dtype=float)))
                        dp = np.nan_to_num(np.asarray(directed_pair, dtype=float))
                        _rf_log.info(
                            "row-first %s (%s) call %d: industry: (directed, shipped cap, cap) %s",
                            names_rf[c1], rf_mode, getattr(self, "_rf_calls", 0),
                            {int(g): (round(float(dp[g]), 1), round(float(destin_trade_proportions[c1, row_index, g] * init[g]), 1),
                                      round(float(first_destin[c1, row_index, g] * init[g]), 1)) for g in gs})
                self._rf_calls = getattr(self, "_rf_calls", 0) + 1

            # ROW's open order at the world price for the listed industries (doc 5t; see
            # set_row_world_price_demand), before the domestic pair passes.
            rwp_shares = getattr(self, "_row_world_price_shares", None)
            rwp_gs = [g for g in getattr(self, "_row_world_price_industries", []) if 0 <= g < n_industries]
            if rwp_shares and rwp_gs and row_index >= 0 and self._row_world_price_order == "first":
                pair_destin_tp = self._row_world_price_prepass(
                    goods_market_participants=goods_market_participants,
                    n_industries=n_industries,
                    average_prices_by_country=average_prices_by_country,
                    buyer_priorities=buyer_priorities,
                    pair_destin_tp=pair_destin_tp,
                    shares=rwp_shares,
                    gs=rwp_gs,
                    row_index=row_index,
                )

            # Clear each country pair using trade proportions
            for c1 in range(n_countries):
                for c2 in range(n_countries):
                    directed_pair = self.perform_clearing(
                        goods_market_participants=goods_market_participants,
                        n_industries=n_industries,
                        average_prices_by_country=average_prices_by_country,
                        buyer_priorities=buyer_priorities,
                        start_country=c1,
                        end_country=c2,
                        origin_trade_proportions=pair_origin_tp,
                        destin_trade_proportions=pair_destin_tp,
                    )
                    # Real demand the passes DIRECTED at origin c1 (all destinations), for
                    # the shortfall signal booked after the pool; see
                    # set_origin_shortfall_signal.
                    if self._origin_shortfall_signal > 0.0 and c1 != row_index:
                        if directed_demand is None:
                            directed_demand = np.zeros((n_countries, n_industries))
                        directed_demand[c1] += np.nan_to_num(directed_pair)

        # ROW split override: bilateral province -> ROW passes on externally supplied
        # origin shares, BEFORE the unconstrained pool below.  Buyer-side proportions
        # apply to ROW's INITIAL demand (collect_buyer_info takes
        # min(share x initial, remaining)), so each origin is capped at its share of
        # ROW's demand and the passes do not compound; whatever an origin cannot fill
        # stays in ROW's remaining demand and clears in the pool as it always did,
        # keeping the level residual.
        split_shortfalls: dict[tuple[int, int], float] = {}
        if self._row_split_override and row_index >= 0:
            anchor_shares = np.zeros(
                (n_countries, default_origin_trade_proportions.shape[2])
            )
            for g_over, shares_over in self._row_split_override.items():
                if 0 <= int(g_over) < anchor_shares.shape[1] and len(shares_over) == n_countries:
                    anchor_shares[:, int(g_over)] = shares_over
                    anchor_shares[row_index, int(g_over)] = 0.0
            anchor_origin = np.zeros_like(default_origin_trade_proportions)
            anchor_destin = np.zeros_like(default_destin_trade_proportions)
            for c1 in range(n_countries):
                if c1 == row_index:
                    continue
                anchor_origin[c1, row_index] = anchor_shares[c1]
                # The seller side offers everything it still has to ROW in this pass;
                # the buyer-side share above is what limits the actual flow.
                anchor_destin[c1, row_index] = np.where(anchor_shares[c1] > 0.0, 1.0, 0.0)
            row_name = list(goods_market_participants.keys())[row_index]

            def _row_buyer_sum(g: int, field: str) -> float:
                total = 0.0
                for _tr in goods_market_participants[row_name]:
                    if _tr.transactor_buyer_states["Value Type"] != ValueType.NONE:
                        total += float(_tr.transactor_buyer_states[field][:, g].sum())
                return total

            override_gs = sorted(self._row_split_override)
            row_initial = {g: _row_buyer_sum(g, "Initial Goods") for g in override_gs}
            for c1 in range(n_countries):
                if c1 == row_index or not np.any(anchor_shares[c1] > 0.0):
                    continue
                before = {g: _row_buyer_sum(g, "Remaining Goods") for g in override_gs}
                self.perform_clearing(
                    goods_market_participants=goods_market_participants,
                    n_industries=n_industries,
                    average_prices_by_country=average_prices_by_country,
                    buyer_priorities=buyer_priorities,
                    start_country=c1,
                    end_country=row_index,
                    origin_trade_proportions=anchor_origin,
                    destin_trade_proportions=anchor_destin,
                )
                # Shortfall bookkeeping for the override industries: what this origin
                # was allocated but could not supply.  In ROW's own units (nominal for
                # a NOMINAL buyer); converted at the origin's price when signalled.
                for g in override_gs:
                    allocated = min(anchor_shares[c1, g] * row_initial[g], before[g])
                    cleared = before[g] - _row_buyer_sum(g, "Remaining Goods")
                    short = allocated - cleared
                    if short > 0.0:
                        split_shortfalls[(c1, g)] = split_shortfalls.get((c1, g), 0.0) + short

            # STRICT split: demand the anchored origins could not fill is withdrawn,
            # not pooled.  Without this the pool re-runs the defect the split exists to
            # fix -- whichever province has slack captures the sale (Manitoba).
            if self._row_split_strict and override_gs:
                for _tr in goods_market_participants[row_name]:
                    if _tr.transactor_buyer_states["Value Type"] != ValueType.NONE:
                        for g in override_gs:
                            _tr.transactor_buyer_states["Remaining Goods"][:, g] = 0.0

        # ROW's open world-price order, after the domestic pair passes and before the pool
        # (doc 5t, order "before_pool"); the unfilled part is booked below.
        self._rwp_unfilled = None
        self._row_presplit_held = None
        rwp_shares = getattr(self, "_row_world_price_shares", None)
        rwp_gs = [g for g in getattr(self, "_row_world_price_industries", []) if 0 <= g < n_industries]
        if (rwp_shares and rwp_gs and row_index >= 0
                and getattr(self, "_row_world_price_order", "before_pool") == "before_pool"):
            # ROW's ordinary budget for these industries, split as the pool would split it
            # before the world-price pass takes its share (doc 5u).
            if getattr(self, "_row_world_price_ordinary", "pool") == "presplit":
                self._row_ordinary_presplit(
                    goods_market_participants=goods_market_participants,
                    n_industries=n_industries,
                    average_prices_by_country=average_prices_by_country,
                    buyer_priorities=buyer_priorities,
                    gs=rwp_gs,
                    row_index=row_index,
                )
            self._row_world_price_prepass(
                goods_market_participants=goods_market_participants,
                n_industries=n_industries,
                average_prices_by_country=average_prices_by_country,
                buyer_priorities=buyer_priorities,
                pair_destin_tp=None,
                shares=rwp_shares,
                gs=rwp_gs,
                row_index=row_index,
                book_unfilled=True,
            )

        # Non-tradable goods (doc 5x): what a participant's own sellers could not supply is held
        # out of the unconstrained pool (which would otherwise fill it from any province with
        # slack) and restored afterwards, so it is still recorded as excess demand.
        dom_held = []
        dom_only = getattr(self, "_domestic_only_industries", None)
        if dom_only:
            dom_gs = np.asarray(sorted(g for g in dom_only if 0 <= g < n_industries), dtype=int)
            if dom_gs.size:
                for _name, transactors in goods_market_participants.items():
                    for t in transactors:
                        rem = t.transactor_buyer_states["Remaining Goods"]
                        dom_held.append((t, np.array(rem[:, dom_gs], dtype=float, copy=True), dom_gs))
                        rem[:, dom_gs] = 0.0
        # Clear remaining supply and demand without trade proportion constraints
        self.perform_clearing(
            goods_market_participants=goods_market_participants,
            n_industries=n_industries,
            average_prices_by_country=average_prices_by_country,
            buyer_priorities=buyer_priorities,
        )
        for t, h, gs_d in dom_held:
            t.transactor_buyer_states["Remaining Goods"][:, gs_d] += h
        # ROW's ordinary demand the presplit could not fill (doc 5u) rejoins its remaining
        # demand after the pool, for the excess-demand step.
        if getattr(self, "_row_presplit_held", None) is not None:
            gs_h, held = self._row_presplit_held
            for t, h in held:
                t.transactor_buyer_states["Remaining Goods"][:, gs_h] += h
            self._row_presplit_held = None

        # Handle any remaining excess demand
        self.distribute_excess_demand_water_bucket(
            goods_market_participants=goods_market_participants,
            n_industries=n_industries,
        )

        # ROW's unfilled world-price orders, booked on the origin's sellers AFTER the global
        # distribution (which assigns by supply share): the order book the firm missed.
        if self._rwp_unfilled is not None and np.any(self._rwp_unfilled > 0.0):
            names_u = list(goods_market_participants.keys())
            for c, g in zip(*np.nonzero(self._rwp_unfilled > 0.0)):
                short = float(self._rwp_unfilled[c, g])
                sellers = [t for t in goods_market_participants[names_u[c]]
                           if t.transactor_seller_states["Value Type"] == ValueType.REAL]
                total = 0.0
                for t in sellers:
                    ind = np.asarray(t.transactor_seller_states["Industries"]) == g
                    total += float(np.nan_to_num(np.asarray(t.transactor_seller_states["Initial Goods"], dtype=float))[ind].sum())
                for t in sellers:
                    ind = np.asarray(t.transactor_seller_states["Industries"]) == g
                    n_rows = int(ind.sum())
                    if not n_rows:
                        continue
                    init_t = np.nan_to_num(np.asarray(t.transactor_seller_states["Initial Goods"], dtype=float))[ind]
                    w = init_t / total if total > 0.0 else np.full(n_rows, 1.0 / n_rows)
                    t.transactor_seller_states["Real Excess Demand"][ind] += short * w

        # Route the anchored-pass shortfalls to their origins as excess demand, AFTER
        # the global distribution above (which ASSIGNS rather than adds, and would hand
        # the signal to whichever province has spare supply -- the defect the split
        # corrects).  This is the order book an origin keeps missing: demand estimation
        # reads recorded excess demand, so the origin plans and invests into its share.
        if self._row_split_signal and split_shortfalls:
            names = list(goods_market_participants.keys())
            for (c1, g), nominal in split_shortfalls.items():
                if nominal <= 0.0:
                    continue
                price = float(average_prices_by_country[c1][g])
                if not np.isfinite(price) or price <= 0.0:
                    price = float(average_prices_by_country[-1][g])
                if not np.isfinite(price) or price <= 0.0:
                    continue
                real_short = (nominal / price) * self._row_split_signal
                for transactor in goods_market_participants[names[c1]]:
                    if transactor.transactor_seller_states["Value Type"] == ValueType.REAL:
                        ind = transactor.transactor_seller_states["Industries"] == g
                        n_rows = int(ind.sum())
                        if n_rows:
                            transactor.transactor_seller_states["Real Excess Demand"][ind] += (
                                real_short / n_rows
                            )

        # Origin shortfall signal: orders DIRECTED at a province that it did not fill, booked
        # on its sellers AFTER the pool and the global distribution (which assign by supply
        # share and would otherwise hand the signal to whoever had slack).  See
        # set_origin_shortfall_signal.  Sold = initial supply - remaining supply, so the
        # pool's backfill through this origin counts as filled.
        if self._origin_shortfall_signal > 0.0 and directed_demand is not None:
            names = list(goods_market_participants.keys())
            booked = np.zeros((n_countries, n_industries))
            for c1, name in enumerate(names):
                if c1 == row_index or not np.any(directed_demand[c1] > 0.0):
                    continue
                sellers = [
                    t for t in goods_market_participants[name]
                    if t.transactor_seller_states["Value Type"] == ValueType.REAL
                ]
                if not sellers:
                    continue
                sold = np.zeros(n_industries)
                initial = np.zeros(n_industries)
                for t in sellers:
                    ind_g = np.asarray(t.transactor_seller_states["Industries"])
                    init_t = np.nan_to_num(np.asarray(t.transactor_seller_states["Initial Goods"], dtype=float))
                    rem_t = np.nan_to_num(np.asarray(t.transactor_seller_states["Remaining Goods"], dtype=float))
                    np.add.at(sold, ind_g, np.maximum(init_t - rem_t, 0.0))
                    np.add.at(initial, ind_g, init_t)
                short = np.maximum(directed_demand[c1] - sold, 0.0)
                if shortfall_relative:
                    # Relative form: only what the price-adjusted shares moved toward this
                    # origin beyond its default share can be booked (doc 5j).
                    if directed_excess is None:
                        continue
                    short = np.minimum(short, np.maximum(directed_excess[c1], 0.0))
                short = short * self._origin_shortfall_signal
                booked[c1] = short
                for g in np.flatnonzero(short > 0.0):
                    for t in sellers:
                        ind = t.transactor_seller_states["Industries"] == g
                        n_rows = int(ind.sum())
                        if not n_rows:
                            continue
                        init_t = np.nan_to_num(np.asarray(t.transactor_seller_states["Initial Goods"], dtype=float))[ind]
                        if initial[g] > 0.0:
                            weights = init_t / initial[g]
                        else:
                            weights = np.full(n_rows, 1.0 / n_rows)
                        t.transactor_seller_states["Real Excess Demand"][ind] += short[g] * weights
            self.last_origin_shortfall = booked

        # Allow additional ROW exports if enabled
        if self.allow_additional_row_exports and self.additionally_available_factor > 0.0:
            self.handle_additional_row_exports(
                goods_market_participants=goods_market_participants,
                n_industries=n_industries,
            )


    def _row_world_price_prepass(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        average_prices_by_country: np.ndarray,
        buyer_priorities: dict[str, np.ndarray],
        pair_destin_tp: np.ndarray,
        shares: dict[str, np.ndarray],
        gs: list[int],
        row_index: int,
        book_unfilled: bool = False,
    ) -> np.ndarray:
        """Clear ROW's extra world-price orders (doc 5t); returns the pair passes' destin shares.

        Order "first": on the origin's whole supply, before the pair passes, and the domestic
        destination shares are scaled to what is left.  Order "before_pool"
        (``book_unfilled``): on what the pair passes left (the seller cap, share x initial
        supply, is bounded by the remaining supply in collect_seller_info); the unfilled part
        is stored in ``self._rwp_unfilled`` for booking as excess demand after the global
        distribution.
        """
        names = list(goods_market_participants.keys())
        n_countries = len(names)
        gs_arr = np.asarray(gs, dtype=int)
        want = np.zeros((n_countries, n_industries))
        supply = np.zeros((n_countries, n_industries))
        value = np.zeros((n_countries, n_industries))

        def _remaining(c: int) -> np.ndarray:
            rem = np.zeros(n_industries)
            for t in goods_market_participants[names[c]]:
                st = t.transactor_seller_states
                if st["Value Type"] == ValueType.REAL:
                    np.add.at(rem, np.asarray(st["Industries"]),
                              np.nan_to_num(np.asarray(st["Remaining Goods"], dtype=float)))
            return rem

        for c, name in enumerate(names):
            a = shares.get(name)
            if c == row_index or a is None or not np.any(a > 0.0):
                continue
            for t in goods_market_participants[name]:
                st = t.transactor_seller_states
                if st["Value Type"] != ValueType.REAL:
                    continue
                ind = np.asarray(st["Industries"])
                if a.shape[0] != ind.shape[0]:
                    continue
                init = np.nan_to_num(np.asarray(st["Initial Goods"], dtype=float))
                pr = np.nan_to_num(np.asarray(st["Prices"], dtype=float))
                sel = np.isin(ind, gs_arr)
                np.add.at(want[c], ind[sel], (a * init)[sel])
                np.add.at(supply[c], ind[sel], init[sel])
                np.add.at(value[c], ind[sel], (pr * init)[sel])
        sold = np.zeros((n_countries, n_industries))
        self.last_row_world_price_sales = sold
        if not np.any(want > 0.0):
            return pair_destin_tp
        price = np.divide(value, supply, out=np.zeros_like(value), where=supply > 0.0)
        nominal = want * price
        add = nominal.sum(axis=0)
        row_buyers = [
            t for t in goods_market_participants[names[row_index]]
            if t.transactor_buyer_states["Value Type"] != ValueType.NONE
        ]
        n_rows = sum(int(t.transactor_buyer_states["Initial Goods"].shape[0]) for t in row_buyers)
        if n_rows == 0:
            return pair_destin_tp
        extra_row = add / n_rows
        orig_init = [np.array(t.transactor_buyer_states["Initial Goods"], dtype=float, copy=True) for t in row_buyers]
        orig_rem = [np.array(t.transactor_buyer_states["Remaining Goods"], dtype=float, copy=True) for t in row_buyers]
        for t in row_buyers:
            t.transactor_buyer_states["Initial Goods"][:, gs_arr] += extra_row[gs_arr]
            t.transactor_buyer_states["Remaining Goods"][:, gs_arr] += extra_row[gs_arr]
        row_init_total = np.zeros(n_industries)
        for t in row_buyers:
            row_init_total += np.asarray(t.transactor_buyer_states["Initial Goods"], dtype=float).sum(axis=0)
        first_origin = np.zeros((n_countries, n_countries, n_industries))
        first_destin = np.zeros((n_countries, n_countries, n_industries))
        for c in range(n_countries):
            if c == row_index or not np.any(want[c] > 0.0):
                continue
            first_origin[c, row_index, gs_arr] = np.divide(
                nominal[c, gs_arr], row_init_total[gs_arr],
                out=np.zeros(gs_arr.size), where=row_init_total[gs_arr] > 0.0)
            first_destin[c, row_index, gs_arr] = np.minimum(np.divide(
                want[c, gs_arr], supply[c, gs_arr],
                out=np.zeros(gs_arr.size), where=supply[c, gs_arr] > 0.0), 1.0)
            before = _remaining(c)
            self.perform_clearing(
                goods_market_participants=goods_market_participants,
                n_industries=n_industries,
                average_prices_by_country=average_prices_by_country,
                buyer_priorities=buyer_priorities,
                start_country=c,
                end_country=row_index,
                origin_trade_proportions=first_origin,
                destin_trade_proportions=first_destin,
            )
            sold[c] = np.maximum(before - _remaining(c), 0.0)
        # Withdraw the part of the extra budget ROW did not spend: its own budget reaches the
        # pool unchanged.
        for t, oi, orr in zip(row_buyers, orig_init, orig_rem):
            rem_now = np.asarray(t.transactor_buyer_states["Remaining Goods"], dtype=float)
            spent = orr[:, gs_arr] + extra_row[gs_arr] - rem_now[:, gs_arr]
            t.transactor_buyer_states["Remaining Goods"][:, gs_arr] = np.minimum(orr[:, gs_arr], rem_now[:, gs_arr])
            t.transactor_buyer_states["Initial Goods"][:, gs_arr] = oi[:, gs_arr] + np.clip(
                spent, 0.0, extra_row[gs_arr])
        if book_unfilled:
            self._rwp_unfilled = np.maximum(want - sold, 0.0)
        # The domestic pair passes share what ROW left (order "first").
        frac = np.divide(sold, supply, out=np.zeros_like(sold), where=supply > 0.0)
        if pair_destin_tp is not None and np.any(frac > 0.0):
            pair_destin_tp = np.array(pair_destin_tp, copy=True)
            for c in range(n_countries):
                if c == row_index or not np.any(frac[c] > 0.0):
                    continue
                for c2 in range(n_countries):
                    if c2 != row_index:
                        pair_destin_tp[c, c2, gs_arr] = pair_destin_tp[c, c2, gs_arr] * (1.0 - frac[c, gs_arr])
        if self._rwp_calls % 16 == 0:
            for c, name in enumerate(names):
                if name[-2:] in ("AB", "BC") and np.any(want[c] > 0.0):
                    _rf_log.info(
                        "row world-price %s call %d: industry: (ordered, bought, supply) %s",  # unfilled = ordered - bought
                        name, self._rwp_calls,
                        {int(g): (round(float(want[c, g]), 2), round(float(sold[c, g]), 2),
                                  round(float(supply[c, g]), 1)) for g in gs_arr})
        self._rwp_calls += 1
        return pair_destin_tp

    def _row_ordinary_presplit(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        average_prices_by_country: np.ndarray,
        buyer_priorities: dict[str, np.ndarray],
        gs: list[int],
        row_index: int,
    ) -> None:
        """Clear ROW's ordinary demand for ``gs`` origin by origin, as the pool would (doc 5u).

        The unconstrained pool sells each origin c the share S_c / max(sum S, D) of every
        buyer's remaining demand (S_c the origin's remaining real supply, D all buyers'
        remaining real demand at the pool's average price): S_c / sum S of it when supply
        exceeds demand, all of S_c pro rata to demand when it does not.  Run before the
        world-price pass, this gives ROW from every origin (ROW's own sellers included)

            q_c = S_c x D_ROW / max(sum S, D)

        of its remaining ordinary demand D_ROW, on the supply the world-price pass has not yet
        taken, charged at the pool's average price p (the pool charges every buyer p), so ROW's
        nominal spend is the pool's: sum_c q_c x p = D_ROW x p.  With no world-price order every origin's total sales are the pool's (the
        domestic remainder then meets supply in the same proportions); with one, the order
        comes on top of the origin's ordinary ROW sales instead of re-dividing them toward
        origins with more left.  Buyer-side origin share = q_c x p / ROW's initial budget;
        the seller side offers all the origin has left, as in the pool.

        The passes draw seller and buyer orderings from numpy's and numba's random streams; both
        states are restored afterwards, so the run stays on the shipped stream (otherwise the
        presplit, which runs from step 0, makes the baseline a different draw).
        """
        np_state = np.random.get_state()
        nb_ptr = nb_state = None
        try:
            from numba import _helperlib
            nb_ptr = _helperlib.rnd_get_np_state_ptr()
            nb_state = _helperlib.rnd_get_state(nb_ptr)
        except Exception:  # numba internals unavailable: the draw shifts, nothing else changes
            nb_ptr = None
        try:
            self._row_ordinary_presplit_passes(
                goods_market_participants=goods_market_participants,
                n_industries=n_industries,
                average_prices_by_country=average_prices_by_country,
                buyer_priorities=buyer_priorities,
                gs=gs,
                row_index=row_index,
            )
        finally:
            np.random.set_state(np_state)
            if nb_ptr is not None:
                _helperlib.rnd_set_state(nb_ptr, nb_state)

    def _row_ordinary_presplit_passes(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        average_prices_by_country: np.ndarray,
        buyer_priorities: dict[str, np.ndarray],
        gs: list[int],
        row_index: int,
    ) -> None:
        names = list(goods_market_participants.keys())
        n_countries = len(names)
        gs_arr = np.asarray(gs, dtype=int)
        total_rs, aggr_rs, _, _, p_pool = collect_seller_info(
            goods_market_participants=goods_market_participants,
            n_industries=n_industries,
        )
        p_pool = np.array(p_pool, dtype=float, copy=True)
        bad = ~(np.isfinite(p_pool) & (p_pool > 0.0))
        p_pool[bad] = average_prices_by_country[-1][bad]
        total_rd, aggr_rd, _, _ = collect_buyer_info(
            goods_market_participants=goods_market_participants,
            average_price=p_pool,
            n_industries=n_industries,
        )
        d_row = np.nan_to_num(np.asarray(total_rd[names[row_index]], dtype=float))
        denom = np.maximum(np.nan_to_num(aggr_rs), np.nan_to_num(aggr_rd))
        row_buyers = [
            t for t in goods_market_participants[names[row_index]]
            if t.transactor_buyer_states["Value Type"] != ValueType.NONE
        ]
        planned = np.zeros((n_countries, n_industries))
        bought = np.zeros((n_countries, n_industries))
        self.last_row_ordinary_presplit = None
        if not row_buyers or not np.any(d_row[gs_arr] > 0.0):
            return
        row_init_total = np.zeros(n_industries)
        for t in row_buyers:
            row_init_total += np.asarray(t.transactor_buyer_states["Initial Goods"], dtype=float).sum(axis=0)
        origin_tp = np.zeros((n_countries, n_countries, n_industries))
        destin_tp = np.zeros((n_countries, n_countries, n_industries))
        # Every pass charges the pool's price, so ROW's nominal spend per origin is the pool's.
        price_gs = np.full(n_industries, np.nan)
        price_gs[gs_arr] = p_pool[gs_arr]
        for c, name in enumerate(names):
            s_c = np.nan_to_num(np.asarray(total_rs[name], dtype=float))
            q = np.zeros(n_industries)
            q[gs_arr] = np.divide(s_c[gs_arr] * d_row[gs_arr], denom[gs_arr],
                                  out=np.zeros(gs_arr.size), where=denom[gs_arr] > 0.0)
            if not np.any(q > 0.0):
                continue
            origin_tp[c, row_index, gs_arr] = np.divide(
                q[gs_arr] * p_pool[gs_arr], row_init_total[gs_arr],
                out=np.zeros(gs_arr.size), where=row_init_total[gs_arr] > 0.0)
            # The origin offers all it has left, as in the pool; ROW's q_c limits the flow.
            destin_tp[c, row_index, gs_arr] = np.where(q[gs_arr] > 0.0, 1.0, 0.0)
            before = s_c.copy()
            self.perform_clearing(
                goods_market_participants=goods_market_participants,
                n_industries=n_industries,
                average_prices_by_country=average_prices_by_country,
                buyer_priorities=buyer_priorities,
                start_country=c,
                end_country=row_index,
                origin_trade_proportions=origin_tp,
                destin_trade_proportions=destin_tp,
                price_override=price_gs,
            )
            after = np.zeros(n_industries)
            for t in goods_market_participants[name]:
                st = t.transactor_seller_states
                if st["Value Type"] == ValueType.REAL:
                    np.add.at(after, np.asarray(st["Industries"]),
                              np.nan_to_num(np.asarray(st["Remaining Goods"], dtype=float)))
            planned[c] = q
            bought[c] = np.maximum(before - after, 0.0)
        self.last_row_ordinary_presplit = bought
        # What ROW could not get (the shortage case: the pool would have rationed it once, pro
        # rata, as above) is held out of the pool so it does not compete a second time for
        # the domestic buyers' share; ``clear`` restores it after the pool, so it is still
        # recorded as excess demand.
        held = []
        for t in row_buyers:
            rem = t.transactor_buyer_states["Remaining Goods"]
            held.append((t, np.array(rem[:, gs_arr], dtype=float, copy=True)))
            rem[:, gs_arr] = 0.0
        self._row_presplit_held = (gs_arr, held)
        if self._rwp_calls % 16 == 0:
            for c, name in enumerate(names):
                if (name[-2:] in ("AB", "BC") or c == row_index) and np.any(planned[c] > 0.0):
                    _rf_log.info(
                        "row ordinary presplit %s call %d: industry: (planned, bought) %s",
                        name, self._rwp_calls,
                        {int(g): (round(float(planned[c, g]), 2), round(float(bought[c, g]), 2)) for g in gs_arr})

    @staticmethod
    def _directed_excess_beyond_default(
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        origin_trade_proportions: np.ndarray,
        default_origin_trade_proportions: np.ndarray,
        average_prices_by_country: np.ndarray,
        row_index: int,
    ) -> np.ndarray:
        """Real demand the price-adjusted origin shares moved toward each origin beyond
        its default share, summed over destinations (relative origin shortfall signal,
        doc 5j).

        For origin o and good g: sum over destinations d of
        max(share_adj[o, d, g] - share_def[o, d, g], 0) x initial demand of d's buyers for
        g, with NOMINAL buyers (ROW) converted at o's average offered price.  The default
        shares are renormalised per (destination, good) so both share arrays sum to one
        over origins.  ROW as an origin is left at zero.
        """
        names = list(goods_market_participants.keys())
        n_countries = len(names)
        init_real = np.zeros((n_countries, n_industries))
        init_nom = np.zeros((n_countries, n_industries))
        for c2, name in enumerate(names):
            for t in goods_market_participants[name]:
                vt = t.transactor_buyer_states["Value Type"]
                if vt == ValueType.NONE:
                    continue
                init = np.nan_to_num(np.asarray(t.transactor_buyer_states["Initial Goods"], dtype=float))
                if init.ndim == 1:
                    init = init[None, :]
                if vt == ValueType.REAL:
                    init_real[c2] += init.sum(axis=0)
                elif vt == ValueType.NOMINAL:
                    init_nom[c2] += init.sum(axis=0)
        default = np.nan_to_num(np.asarray(default_origin_trade_proportions, dtype=float)).copy()
        denom = default.sum(axis=0)  # (c2, g)
        safe = np.where(denom > 0.0, denom, 1.0)
        default = default / safe[None, :, :]
        adjusted = np.nan_to_num(np.asarray(origin_trade_proportions, dtype=float))
        dshare = np.maximum(adjusted - default, 0.0)  # (c1, c2, g)
        out = np.zeros((n_countries, n_industries))
        row_price = np.asarray(average_prices_by_country[-1], dtype=float)
        for c1 in range(n_countries):
            if c1 == row_index:
                continue
            price = np.asarray(average_prices_by_country[c1], dtype=float).copy()
            bad = ~np.isfinite(price) | (price <= 0.0)
            price[bad] = row_price[bad]
            real_from_nominal = np.divide(
                init_nom, price[None, :], out=np.zeros_like(init_nom), where=price[None, :] > 0.0,
            )
            out[c1] = (dshare[c1] * (init_real + real_from_nominal)).sum(axis=0)
        return out

    def perform_clearing(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
        average_prices_by_country: np.ndarray,
        buyer_priorities: dict[str, np.ndarray],
        start_country: Optional[int] = None,
        end_country: Optional[int] = None,
        origin_trade_proportions: Optional[np.ndarray] = None,
        destin_trade_proportions: Optional[np.ndarray] = None,
        price_override: Optional[np.ndarray] = None,
    ) -> None:
        """Execute market clearing for a specific pair of countries or all countries.

        This method implements the core water bucket clearing algorithm, either for
        a specific country pair or for all countries. It handles both trade
        proportion-based clearing and general clearing.

        Args:
            goods_market_participants: Dict mapping country names to lists of trading agents
            n_industries: Number of industries in the model
            average_prices_by_country: Average prices by country and industry
            buyer_priorities: Dict mapping country names to priority arrays for buyers
            start_country: Optional index of origin country for bilateral clearing
            end_country: Optional index of destination country for bilateral clearing
            origin_trade_proportions: Optional trade proportions from origin countries
            destin_trade_proportions: Optional trade proportions to destination countries
            price_override: Optional price per industry used instead of the pass's own
                average seller price where finite and positive (doc 5u: the ROW presplit
                charges the pool's price, as the pool would)

        The clearing process:
        1. Extracts relevant trade proportions for the country pair if specified
        2. Collects supply information considering trade proportions
        3. Collects demand information considering trade proportions
        4. Executes the water bucket clearing algorithm with:
           - Price-based seller selection
           - Priority-based buyer allocation
           - Minimum fill rate guarantees
           - Supply chain persistence
        """
        # Extract relevant trade proportions for the country pair
        if origin_trade_proportions is None or destin_trade_proportions is None:
            current_origin_trade_proportions = None
            current_destin_trade_proportions = None
        else:
            current_origin_trade_proportions = origin_trade_proportions[start_country, end_country]
            current_destin_trade_proportions = destin_trade_proportions[start_country, end_country]

        # Collect supply information
        (
            total_real_supply,
            aggr_real_supply,
            _,
            _,
            emp_goods_prices,
        ) = collect_seller_info(
            goods_market_participants=goods_market_participants,
            n_industries=n_industries,
            from_country=start_country,
            trade_proportions=current_destin_trade_proportions,
        )

        # Handle missing prices using country or ROW averages
        if start_country is None:
            emp_goods_prices[np.isnan(emp_goods_prices)] = average_prices_by_country[-1][np.isnan(emp_goods_prices)]
            emp_goods_prices[emp_goods_prices == 0.0] = average_prices_by_country[-1][emp_goods_prices == 0.0]
        else:
            emp_goods_prices[np.isnan(emp_goods_prices)] = average_prices_by_country[start_country][
                np.isnan(emp_goods_prices)
            ]
            emp_goods_prices[emp_goods_prices == 0.0] = average_prices_by_country[start_country][
                emp_goods_prices == 0.0
            ]
            emp_goods_prices[emp_goods_prices == 0.0] = average_prices_by_country[-1][emp_goods_prices == 0.0]
        if price_override is not None:
            use = np.isfinite(price_override) & (price_override > 0.0)
            emp_goods_prices[use] = price_override[use]

        # Collect demand information
        (
            total_real_demand,
            aggr_real_demand,
            _,
            _,
        ) = collect_buyer_info(
            goods_market_participants=goods_market_participants,
            average_price=emp_goods_prices,
            n_industries=n_industries,
            to_country=end_country,
            trade_proportions=current_origin_trade_proportions,
            from_country=start_country,
        )

        # Execute water bucket clearing
        clear_water_bucket(
            goods_market_participants=goods_market_participants,
            buyer_priority=buyer_priorities,
            n_industries=n_industries,
            total_real_supply=total_real_supply,
            aggr_real_supply=aggr_real_supply,
            average_goods_price=emp_goods_prices,
            total_real_demand=total_real_demand,
            aggr_real_demand=aggr_real_demand,
            from_country=start_country,
            to_country=end_country,
            origin_trade_proportions=current_origin_trade_proportions,
            destin_trade_proportions=current_destin_trade_proportions,
            price_temperature=self.price_temperature,
            distribution_type=self.seller_selection_distribution_type,
            seller_minimum_fill=self.seller_minimum_fill,
            buyer_minimum_fill_macro=self.buyer_minimum_fill_macro,
            buyer_minimum_fill_micro=self.buyer_minimum_fill_micro,
            deterministic=self.deterministic,
            consider_buyer_priorities=self.consider_buyer_priorities,
        )
        # The real demand this pass directed at `start_country` (share-capped, converted at
        # the origin's prices); consumed by the origin shortfall signal in `clear`.
        return aggr_real_demand

    def distribute_excess_demand_water_bucket(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
    ) -> None:
        """Distribute excess demand using the water bucket algorithm.

        This method handles any remaining excess demand after the main clearing
        rounds. It uses the water bucket algorithm to fairly distribute remaining
        supply to excess demand.

        Args:
            goods_market_participants: Dict mapping country names to lists of trading agents
            n_industries: Number of industries in the model

        The distribution process:
        1. Collects initial supply and excess demand information
        2. For each industry with both supply and excess demand:
           a. Calculates allocation based on supply shares
           b. Adjusts for real country prioritization
           c. Distributes using the water bucket algorithm with:
              - Price-based seller selection
              - Minimum fill rate guarantees
              - Priority-based allocation
        """
        # Collect initial values
        _, _, total_nominal_supply, aggr_nominal_supply, average_price = collect_seller_info(
            goods_market_participants=goods_market_participants,
            n_industries=n_industries,
            use_initial=True,
        )
        _, excess_real_demand, _, _ = collect_buyer_info(
            goods_market_participants=goods_market_participants,
            average_price=average_price,
            n_industries=n_industries,
        )

        # Distribute excess demand by industry
        for g in range(n_industries):
            if aggr_nominal_supply[g] == 0.0 or excess_real_demand[g] == 0.0:
                continue

            # Calculate allocation based on supply shares
            current_alloc = np.array(
                [
                    excess_real_demand[g] * total_nominal_supply[country_name][g] / aggr_nominal_supply[g]
                    for country_name in goods_market_participants.keys()
                ]
            )
            # Adjust ROW allocation based on real country prioritization
            current_alloc[-1] *= 1 - max(0.0, min(1.0, self.real_country_prioritisation))
            if current_alloc.sum() == 0.0:
                continue
            current_alloc *= excess_real_demand[g] / current_alloc.sum()

            # Distribute to each country
            for country_ind, country_name in enumerate(goods_market_participants.keys()):
                for transactor in goods_market_participants[country_name]:
                    if transactor.transactor_seller_states["Value Type"] == ValueType.REAL:
                        ind = transactor.transactor_seller_states["Industries"] == g
                        if self.deterministic:
                            _, seller_priorities = get_seller_priorities_deterministic(
                                productions=transactor.transactor_seller_states["Initial Goods"][ind],
                                prices=transactor.transactor_seller_states["Prices"][ind],
                                price_temperature=self.price_temperature,
                                distribution_type=self.seller_selection_distribution_type,
                            )
                        else:
                            _, seller_priorities = get_seller_priorities_stochastic(
                                productions=transactor.transactor_seller_states["Initial Goods"][ind],
                                prices=transactor.transactor_seller_states["Prices"][ind],
                                price_temperature=self.price_temperature,
                                distribution_type=self.seller_selection_distribution_type,
                            )
                        transactor.transactor_seller_states["Real Excess Demand"][ind] = fill_buckets(
                            capacities=transactor.transactor_seller_states["Remaining Excess Goods"][ind],
                            fill_amount=current_alloc[country_ind],
                            priorities=seller_priorities,
                            minimum_fill=self.seller_minimum_fill,
                        )

    def handle_additional_row_exports(
        self,
        goods_market_participants: dict[str, list[Agent]],
        n_industries: int,
    ) -> None:
        """Handle additional exports from Rest of World.

        This method allows for additional purchases from ROW beyond the normal
        clearing process, typically used to handle supply shortages in critical
        industries.

        Args:
            goods_market_participants: Dict mapping country names to lists of trading agents
            n_industries: Number of industries in the model

        The process:
        1. Collects initial ROW export capacity and high-priority demand
        2. Applies price markup to ROW exports
        3. Distributes additional exports:
           a. Proportionally to country demand
           b. Only to high-priority buyers
           c. With minimum fill rate guarantees
        4. Updates both buyer and seller states
        """
        # Collect initial ROW exports and high-priority demand
        _, aggr_real_supply, _, _, average_price = collect_seller_info(
            goods_market_participants={"ROW": goods_market_participants["ROW"]},
            n_industries=n_industries,
            use_initial=True,
        )
        # Apply price markup
        average_price *= 1 + self.price_markup
        additional_real_demand_by_country, additional_real_demand, _, _ = collect_buyer_info(
            goods_market_participants=goods_market_participants,
            average_price=average_price,
            n_industries=n_industries,
            high_prio_only=True,
            exclude_row=True,
        )

        # Distribute additional exports by industry
        for g in range(n_industries):
            if aggr_real_supply[g] == 0.0 or additional_real_demand[g] == 0.0:
                continue
            # Import-limited industries must meet unmet demand domestically rather than
            # from ROW's residual backstop -- otherwise the cap on desired exports is
            # refilled here and has no effect.
            if g in self._import_limited_industries or g in (getattr(self, "_domestic_only_industries", None) or ()):
                continue

            # Process each country's high-priority buyers
            for country_name in goods_market_participants.keys():
                if country_name == "ROW":
                    continue

                # Calculate country's supply allocation
                country_supply = (
                    self.additionally_available_factor
                    * aggr_real_supply.sum()
                    * additional_real_demand_by_country[country_name].sum()
                    / additional_real_demand.sum()
                    * additional_real_demand_by_country[country_name][g]
                    / additional_real_demand_by_country[country_name].sum()
                )
                if country_supply == 0.0:
                    continue

                # Distribute to high-priority buyers
                for transactor in goods_market_participants[country_name]:
                    if transactor.transactor_buyer_states["Priority"] == 1:
                        # Get buyer priorities
                        buyer_priorities = get_buyer_priorities(
                            n_buyers=transactor.transactor_buyer_states["Remaining Goods"].shape[0]
                        )
                        # Allocate additional supply
                        real_amount_bought = fill_buckets(
                            capacities=transactor.transactor_buyer_states["Remaining Goods"][:, g],
                            fill_amount=country_supply,
                            priorities=buyer_priorities,
                            minimum_fill=self.buyer_minimum_fill_micro,
                        )
                        if np.sum(real_amount_bought) == 0.0:
                            continue

                        # Update buyer states
                        transactor.transactor_buyer_states["Real Amount bought"][:, g] += real_amount_bought
                        transactor.transactor_buyer_states["Real Amount bought from ROW"][:, g] += real_amount_bought
                        transactor.transactor_buyer_states["Nominal Amount spent"][:, g] += (
                            average_price[g] * real_amount_bought
                        )
                        transactor.transactor_buyer_states["Nominal Amount spent on Goods from ROW"][:, g] += (
                            average_price[g] * real_amount_bought
                        )
                        transactor.transactor_buyer_states["Remaining Goods"][:, g] -= real_amount_bought

                        # Update ROW seller states
                        ind = goods_market_participants["ROW"][0].transactor_seller_states["Industries"] == g
                        goods_market_participants["ROW"][0].transactor_seller_states["Real Amount sold"][ind] += (
                            real_amount_bought.sum() / np.sum(ind)
                        )
                        goods_market_participants["ROW"][0].transactor_seller_states[
                            "Real Amount sold to " + country_name
                        ][ind] += real_amount_bought.sum() / np.sum(ind)
                        goods_market_participants["ROW"][0].transactor_seller_states["Remaining Goods"][ind] -= (
                            real_amount_bought.sum() / np.sum(ind)
                        )
