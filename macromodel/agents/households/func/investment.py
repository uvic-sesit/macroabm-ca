"""Household investment behavior implementation.

This module implements household investment decisions through:
- Target investment calculation
- Income-based allocation
- Industry-specific investment
- Tax-adjusted spending
- Price level adjustments

The implementation handles:
- Investment rate application
- Industry allocation weights
- Tax considerations
- Inflation adjustments
- External targets
"""

from abc import ABC, abstractmethod

from typing import Optional

import numpy as np


class HouseholdInvestment(ABC):
    """Abstract base class for household investment behavior.

    Defines interface for computing target investment levels based on:
    - Income and investment rates
    - Industry allocations
    - Price level changes
    - Tax considerations
    """

    def __init__(self):
        pass

    @abstractmethod
    def compute_target_investment(
        self,
        expected_inflation: float,
        current_cpi: float,
        initial_cpi: float,
        income: np.ndarray,
        exogenous_total_investment: np.ndarray,
        current_time: int,
        investment_weights: np.ndarray,
        investment_rate: np.ndarray,
        tau_cf: float,
        good_prices: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Calculate target investment levels.

        Args:
            expected_inflation (float): Expected inflation rate
            current_cpi (float): Current price index
            initial_cpi (float): Initial price index
            income (np.ndarray): Household income
            exogenous_total_investment (np.ndarray): External investment target
            current_time (int): Current period
            investment_weights (np.ndarray): Industry investment shares
            investment_rate (np.ndarray): Investment/income ratios
            tau_cf (float): Capital formation tax rate

        Returns:
            np.ndarray: Target investment by household and industry
        """
        pass


class NoHouseholdInvestment(HouseholdInvestment):
    """Zero investment implementation.

    Returns zero investment for all households and industries.
    Used for scenarios where household investment is not modeled.
    """

    def compute_target_investment(
        self,
        expected_inflation: float,
        current_cpi: float,
        initial_cpi: float,
        income: np.ndarray,
        exogenous_total_investment: np.ndarray,
        current_time: int,
        investment_weights: np.ndarray,
        investment_rate: np.ndarray,
        tau_cf: float,
        good_prices: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Return zero investment targets.

        Args:
            expected_inflation (float): Expected inflation rate
            current_cpi (float): Current price index
            initial_cpi (float): Initial price index
            income (np.ndarray): Household income
            exogenous_total_investment (np.ndarray): External investment target
            current_time (int): Current period
            investment_weights (np.ndarray): Industry investment shares
            investment_rate (np.ndarray): Investment/income ratios
            tau_cf (float): Capital formation tax rate

        Returns:
            np.ndarray: Zero investment array
        """
        return np.zeros((income.shape[0], investment_weights.shape[0]))


class DefaultHouseholdInvestment(HouseholdInvestment):
    """Default implementation of household investment behavior.

    Implements investment decisions based on:
    - Income and investment rates
    - Industry allocation weights
    - Tax adjustments
    """

    def compute_target_investment(
        self,
        expected_inflation: float,
        current_cpi: float,
        initial_cpi: float,
        income: np.ndarray,
        exogenous_total_investment: np.ndarray,
        current_time: int,
        investment_weights: np.ndarray,
        investment_rate: np.ndarray,
        tau_cf: float,
        good_prices: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Calculate target investment using default behavior.

        Determines investment based on:
        - Income-based investment rates
        - Industry allocation weights
        - Tax adjustments

        Args:
            expected_inflation (float): Expected inflation rate
            current_cpi (float): Current price index
            initial_cpi (float): Initial price index
            income (np.ndarray): Household income
            exogenous_total_investment (np.ndarray): External investment target
            current_time (int): Current period
            investment_weights (np.ndarray): Industry investment shares
            investment_rate (np.ndarray): Investment/income ratios
            tau_cf (float): Capital formation tax rate

        Returns:
            np.ndarray: Target investment by household and industry
        """
        nominal = 1.0 / (1 + tau_cf) * np.outer(investment_weights, investment_rate * income).T
        if good_prices is None:
            return nominal

        # REAL targeting.  Without this the rule is a fixed NOMINAL share of income, so
        # the real basket households end up with is whatever that share happens to buy --
        # it has no price response at all.  Measured consequence: the investment basket
        # (62% construction) ran at 89.6% of CPI under Current Measures and 92.4% under
        # Net-zero, so households mechanically bought 24.8% LESS real construction under
        # Net-zero purely because construction was dearer relative to the consumption
        # basket.  That swamped the transition-capital signal by roughly ten to one and
        # inverted the sign on every construction and installation trade in the
        # LabourABM results.
        #
        # Holding the REAL basket proportional to REAL income instead means a dearer
        # investment basket raises households' nominal outlay rather than shrinking what
        # they build.  Scaling by (basket price / CPI), normalised to its own initial
        # value, converts the nominal target accordingly.
        basket_price = float(np.dot(np.asarray(investment_weights, dtype=float),
                                    np.asarray(good_prices, dtype=float)))
        if not np.isfinite(basket_price) or basket_price <= 0.0:
            return nominal
        if not hasattr(self, "_basket_price_0"):
            self._basket_price_0 = basket_price
            self._cpi_0 = float(current_cpi) if current_cpi else 1.0
        cpi_ratio = (float(current_cpi) / self._cpi_0) if self._cpi_0 else 1.0
        if not np.isfinite(cpi_ratio) or cpi_ratio <= 0.0:
            return nominal
        return nominal * (basket_price / self._basket_price_0) / cpi_ratio


class ExogenousHouseholdInvestment(HouseholdInvestment):
    """Exogenous household investment implementation.

    Implements investment decisions based on:
    - External investment targets
    - Price level adjustments
    - Income-based allocation
    - Tax considerations
    """

    def compute_target_investment(
        self,
        expected_inflation: float,
        current_cpi: float,
        initial_cpi: float,
        income: np.ndarray,
        exogenous_total_investment: np.ndarray,
        current_time: int,
        investment_weights: np.ndarray,
        investment_rate: np.ndarray,
        tau_cf: float,
        good_prices: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Calculate target investment using exogenous targets.

        Determines investment based on:
        - External investment targets
        - Price level changes
        - Income-based allocation
        - Tax adjustments

        Args:
            expected_inflation (float): Expected inflation rate
            current_cpi (float): Current price index
            initial_cpi (float): Initial price index
            income (np.ndarray): Household income
            exogenous_total_investment (np.ndarray): External investment target
            current_time (int): Current period
            investment_weights (np.ndarray): Industry investment shares
            investment_rate (np.ndarray): Investment/income ratios
            tau_cf (float): Capital formation tax rate

        Returns:
            np.ndarray: Target investment by household and industry
        """
        target_investment = np.maximum(
            0.0,
            (1.0 / (1 + tau_cf) * np.outer(investment_weights, investment_rate * income).T),
        )
        # exogenous_total_investment is a REAL path ("Real Household Investment"), so it
        # must be converted to nominal at the price of the goods actually bought.  Using
        # CPI instead deflates by the CONSUMPTION basket while households spend on an
        # investment basket that is ~62% construction, so realised real investment comes
        # out as exogenous_real x (CPI / investment_basket_price) rather than
        # exogenous_real.  Measured: the investment basket ran at 89.6% of CPI under
        # Current Measures and 92.4% under Net-zero, so households bought 24.8% less real
        # construction under Net-zero for purely deflator reasons -- swamping the
        # transition-capital signal roughly ten to one and inverting the sign on every
        # construction and installation trade in the LabourABM results.
        #
        # This is a deflator correction, not a behavioural assumption: no elasticity is
        # being chosen, the real path is simply being priced with the right index.
        deflator = current_cpi / initial_cpi
        if good_prices is not None:
            basket_price = float(np.dot(np.asarray(investment_weights, dtype=float),
                                        np.asarray(good_prices, dtype=float)))
            if np.isfinite(basket_price) and basket_price > 0.0:
                if not hasattr(self, "_basket_price_0"):
                    self._basket_price_0 = basket_price
                deflator = basket_price / self._basket_price_0

        return (
            (1 + expected_inflation)
            * deflator
            * 1.0
            / (1 + tau_cf)
            * exogenous_total_investment[current_time]
            * target_investment
            / target_investment.sum()
        )
