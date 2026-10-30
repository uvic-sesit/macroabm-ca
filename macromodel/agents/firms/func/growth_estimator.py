from abc import ABC, abstractmethod

import numpy as np


class GrowthEstimator(ABC):
    """Abstract base class for estimating firm growth rates.

    This class defines strategies for calculating firm-specific growth rates
    based on market conditions including:
    - Price positioning relative to sector averages
    - Supply-demand balance
    - Market share dynamics

    Growth estimates are used to inform:
    - Production planning
    - Capacity decisions
    - Investment strategies
    """

    @abstractmethod
    def compute_growth(
        self,
        prev_average_good_prices: np.ndarray,
        prev_firm_prices: np.ndarray,
        prev_supply: np.ndarray,
        prev_demand: np.ndarray,
        current_firm_sectors: np.ndarray,
        prev_real_unit_costs: "np.ndarray | None" = None,
    ) -> np.ndarray:
        """Calculate growth rates for each firm based on market conditions.

        Determines appropriate growth rates considering:
        - Price competitiveness within sectors
        - Supply-demand imbalances
        - Market positioning

        Args:
            prev_average_good_prices (np.ndarray): Previous period's average
                prices by sector
            prev_firm_prices (np.ndarray): Previous period's prices by firm
            prev_supply (np.ndarray): Previous period's supply by firm
            prev_demand (np.ndarray): Previous period's demand by firm
            current_firm_sectors (np.ndarray): Sector ID for each firm

        Returns:
            np.ndarray: Estimated growth rates by firm
        """
        pass


class DefaultGrowthEstimator(GrowthEstimator):
    """Default implementation of firm growth estimation.

    This class implements a strategy that determines growth based on:
    1. Price position relative to sector average
    2. Supply-demand balance
    3. Market dynamics

    Growth is positive when:
    - Firm price >= sector average AND demand > supply
    - Firm price < sector average AND demand <= supply

    The magnitude of growth/decline is based on the demand/supply ratio.

    ``ignore_price_when_sold_out`` (opt-in, default False, WTC 2026-10-17): a firm that is
    sold out (supply <= demand) grows by demand/supply - 1 whatever its price relative to
    the sector average.  The shipped rule grants growth to a sold-out firm only when its
    price is AT OR ABOVE the sector average, so a firm that is sold out BECAUSE it is
    cheaper than its competitors gets no growth signal at all -- the cost advantage reaches
    its price and its order book and is then discarded here.  The excess-supply branch
    (contract when over-supplied and cheap) is unchanged.

    ``price_advantage_growth`` (opt-in, default 0.0, WTC 2026-10-17, doc 5j): the RELATIVE
    form of the same idea.  A sold-out firm priced BELOW the sector average grows by
    ``k x (average_price / firm_price - 1) x (demand / supply)``: zero at the average
    price, so a firm gets a growth signal only in proportion to how much cheaper than its
    competitors it has become, and the many firms that are merely sold out at the average
    price (the model's normal state under the input-target process, doc 5i) are untouched.
    The dear-and-sold-out branch and the excess-supply branch are the shipped ones.  When
    ``ignore_price_when_sold_out`` is also on it takes precedence (every sold-out firm
    already gets demand/supply - 1).

    ``price_advantage_change_growth`` (opt-in, default 0.0, WTC 2026-10-17, doc 5k) with
    ``price_advantage_window`` (L steps, default 4): the CHANGE-keyed form.  Doc 5j measured
    that the LEVEL of a firm's relative price is not a calibration state (two-thirds of
    firms are cheaper than the sector average AND sold out in the baseline, with a median
    advantage the size of the intertie's own effect), so the level form is not sparse.  This
    form keys on how much the firm's position has IMPROVED over the last L steps:
    ``adv_t = average_price / firm_price - 1`` and
    ``growth = k x max(adv_t - adv_{t-L}, 0) x (demand / supply)`` for a sold-out firm not
    already in the shipped branches (i.e. sold out and priced below the average).  Zero in a
    stationary baseline by construction (a constant advantage, however large, gives nothing),
    an impulse of L steps after a relative price fall in the arm.  The estimator keeps the
    per-firm history of ``adv`` itself: it is called once per step per province with the
    same firm ordering; a changed number of firms resets the history (the first L steps
    after a reset give 0).  Adds to ``price_advantage_growth`` when both are on.

    ``unit_cost_change_growth`` (opt-in, default 0.0, WTC 2026-10-17, doc 5o) with
    ``unit_cost_window`` (L steps, default 4): the OWN-COST-keyed form.  Keyed not on the
    firm's price relative to its competitors but on its own REAL unit cost relative to its
    trailing average: with ``c_t`` the firm's unit cost at the last completed step deflated
    by the province's production-weighted price level (so the baseline's nominal cost
    inflation does not read as a rise), a sold-out firm (supply <= demand, whatever its
    price position) grows by ``k x max(1 - c_t / mean(c_{t-L} .. c_{t-1}), 0) x (demand /
    supply)``.  Fires for exactly the firms whose real unit cost is falling, in proportion
    to the fall; zero for a cost that is flat or rising.  Needs ``prev_real_unit_costs`` to
    be passed to :meth:`compute_growth`; the history is this estimator's own (same reset
    rule as above).  Adds to the other opt-ins when several are on.
    """

    def __init__(
        self,
        ignore_price_when_sold_out: bool = False,
        price_advantage_growth: float = 0.0,
        price_advantage_change_growth: float = 0.0,
        price_advantage_window: int = 4,
        unit_cost_change_growth: float = 0.0,
        unit_cost_window: int = 4,
        price_advantage_symmetric: bool = False,
        price_advantage_deadband: float = 0.0,
        price_advantage_smoothing: float = 0.0,
    ):
        # Noise-robust options for the CHANGE-keyed rule (2026-10-30, epm-wtc doc 3.13).  With
        # the shipped firm price noise (1 % a quarter, a random walk) the 4-quarter change of a
        # firm's advantage is mostly the draws, and max(change, 0) rectifies that symmetric
        # noise into growth (+2-3 % of GDP in a reference run).  ``symmetric``: use the signed
        # change (a falling advantage shrinks the plan), so the draws average out;
        # ``deadband``: ignore |change| below this (and shift by it); ``smoothing``: an
        # exponential average of the advantage (lambda, 0 = raw) before differencing.
        self.price_advantage_symmetric = bool(price_advantage_symmetric)
        self.price_advantage_deadband = max(0.0, float(price_advantage_deadband or 0.0))
        self.price_advantage_smoothing = min(1.0, max(0.0, float(price_advantage_smoothing or 0.0)))
        self._advantage_ema = None
        self.ignore_price_when_sold_out = bool(ignore_price_when_sold_out)
        self.unit_cost_change_growth = max(0.0, float(unit_cost_change_growth))
        self.unit_cost_window = max(1, int(unit_cost_window))
        # Per-firm history of the real unit cost, newest last (doc 5o); length window + 1.
        self._unit_cost_history: list[np.ndarray] = []
        self.price_advantage_growth = max(0.0, float(price_advantage_growth))
        self.price_advantage_change_growth = max(0.0, float(price_advantage_change_growth))
        self.price_advantage_window = max(1, int(price_advantage_window))
        # Per-firm history of the price advantage (average / price - 1), newest last, kept
        # only while the change-keyed rule is on. Length is capped at window + 1.
        self._advantage_history: list[np.ndarray] = []

    def compute_growth(
        self,
        prev_average_good_prices: np.ndarray,
        prev_firm_prices: np.ndarray,
        prev_supply: np.ndarray,
        prev_demand: np.ndarray,
        current_firm_sectors: np.ndarray,
        prev_real_unit_costs: "np.ndarray | None" = None,
    ) -> np.ndarray:
        """Calculate growth rates using the default market-based strategy.

        The method:
        1. Maps sector average prices to firms
        2. Identifies firms with favorable market positions
        3. Calculates growth rates based on demand/supply ratios

        Growth is allowed when either:
        - High price (>= sector avg) and excess demand
        - Low price (< sector avg) and excess supply

        Args:
            prev_average_good_prices (np.ndarray): Previous period's average
                prices by sector
            prev_firm_prices (np.ndarray): Previous period's prices by firm
            prev_supply (np.ndarray): Previous period's supply by firm
            prev_demand (np.ndarray): Previous period's demand by firm
            current_firm_sectors (np.ndarray): Sector ID for each firm

        Returns:
            np.ndarray: Growth rates by firm, where positive values indicate
                expansion and negative values indicate contraction
        """
        average_price_by_firm = prev_average_good_prices[current_firm_sectors]
        firm_growth_rates = np.zeros_like(prev_firm_prices)
        if getattr(self, "ignore_price_when_sold_out", False):
            sold_out = prev_supply <= prev_demand
        else:
            sold_out = np.logical_and(
                prev_supply <= prev_demand,
                prev_firm_prices >= average_price_by_firm,
            )
        ind_canvas = np.logical_or(
            sold_out,
            np.logical_and(
                prev_supply > prev_demand,
                prev_firm_prices < average_price_by_firm,
            ),
        )
        firm_growth_rates[ind_canvas] = (
            np.divide(
                prev_demand[ind_canvas],
                prev_supply[ind_canvas],
                out=np.ones_like(prev_demand[ind_canvas]),
                where=prev_supply[ind_canvas] != 0.0,
            )
            - 1.0
        )
        k = float(getattr(self, "price_advantage_growth", 0.0) or 0.0)
        if k > 0.0:
            # Relative signal: sold out AND cheaper than the sector average, not already
            # granted growth above.  growth = k x (avg / price - 1) x (demand / supply).
            cheap_sold_out = np.logical_and(
                np.logical_and(prev_supply <= prev_demand, prev_firm_prices < average_price_by_firm),
                np.logical_not(ind_canvas),
            )
            if np.any(cheap_sold_out):
                demand_over_supply = np.divide(
                    prev_demand,
                    prev_supply,
                    out=np.ones_like(prev_demand),
                    where=prev_supply != 0.0,
                )
                advantage = np.divide(
                    average_price_by_firm,
                    prev_firm_prices,
                    out=np.ones_like(prev_firm_prices),
                    where=prev_firm_prices > 0.0,
                ) - 1.0
                firm_growth_rates[cheap_sold_out] = (
                    k * np.maximum(advantage[cheap_sold_out], 0.0) * demand_over_supply[cheap_sold_out]
                )
        k_change = float(getattr(self, "price_advantage_change_growth", 0.0) or 0.0)
        if k_change > 0.0:
            # CHANGE-keyed signal (doc 5k): growth = k x max(adv_t - adv_{t-L}, 0) x (d / s)
            # for a sold-out firm priced below the average and not in the shipped branches.
            # The history is this estimator's own: one call per step per province, same firm
            # ordering; a changed n_firms resets it.
            window = max(1, int(getattr(self, "price_advantage_window", 4) or 4))
            advantage_now = np.divide(
                average_price_by_firm,
                prev_firm_prices,
                out=np.ones_like(prev_firm_prices),
                where=prev_firm_prices > 0.0,
            ) - 1.0
            lam = float(getattr(self, "price_advantage_smoothing", 0.0) or 0.0)
            if lam > 0.0:
                ema = getattr(self, "_advantage_ema", None)
                if ema is None or ema.shape != advantage_now.shape:
                    ema = np.array(advantage_now, copy=True)
                else:
                    ema = (1.0 - lam) * ema + lam * advantage_now
                self._advantage_ema = ema
                signal_now = ema
            else:
                signal_now = advantage_now
            history = getattr(self, "_advantage_history", None)
            if history is None or (history and history[-1].shape != signal_now.shape):
                history = []
            history.append(np.array(signal_now, copy=True))
            if len(history) > window + 1:
                del history[: len(history) - (window + 1)]
            self._advantage_history = history
            if len(history) == window + 1:
                change = signal_now - history[0]
                deadband = float(getattr(self, "price_advantage_deadband", 0.0) or 0.0)
                if getattr(self, "price_advantage_symmetric", False):
                    signal = np.where(change > deadband, change - deadband,
                                      np.where(change < -deadband, change + deadband, 0.0))
                else:
                    signal = np.maximum(change - deadband, 0.0)
                cheap_sold_out = np.logical_and(
                    np.logical_and(prev_supply <= prev_demand, prev_firm_prices < average_price_by_firm),
                    np.logical_not(ind_canvas),
                )
                if np.any(cheap_sold_out):
                    demand_over_supply = np.divide(
                        prev_demand,
                        prev_supply,
                        out=np.ones_like(prev_demand),
                        where=prev_supply != 0.0,
                    )
                    firm_growth_rates[cheap_sold_out] += (
                        k_change * signal[cheap_sold_out] * demand_over_supply[cheap_sold_out]
                    )
        k_cost = float(getattr(self, "unit_cost_change_growth", 0.0) or 0.0)
        if k_cost > 0.0 and prev_real_unit_costs is not None:
            # OWN-COST-keyed signal (doc 5o): growth += k x max(1 - c_t / mean(c_{t-L..t-1}), 0)
            # x (d / s) for a sold-out firm, c = real unit cost.  History kept here; a changed
            # n_firms resets it (the first L steps after a reset give 0).
            window = max(1, int(getattr(self, "unit_cost_window", 4) or 4))
            cost_now = np.asarray(prev_real_unit_costs, dtype=float)
            history = getattr(self, "_unit_cost_history", None)
            if history is None or (history and history[-1].shape != cost_now.shape):
                history = []
            history.append(np.array(cost_now, copy=True))
            if len(history) > window + 1:
                del history[: len(history) - (window + 1)]
            self._unit_cost_history = history
            if len(history) == window + 1:
                trailing = np.mean(np.stack(history[:-1]), axis=0)
                fall = np.where(
                    (trailing > 0.0) & np.isfinite(cost_now) & (cost_now > 0.0),
                    1.0 - cost_now / np.where(trailing > 0.0, trailing, 1.0),
                    0.0,
                )
                sold_out_any = prev_supply <= prev_demand
                if np.any(sold_out_any):
                    demand_over_supply = np.divide(
                        prev_demand,
                        prev_supply,
                        out=np.ones_like(prev_demand),
                        where=prev_supply != 0.0,
                    )
                    firm_growth_rates[sold_out_any] += (
                        k_cost * np.maximum(fall[sold_out_any], 0.0) * demand_over_supply[sold_out_any]
                    )
        return firm_growth_rates
