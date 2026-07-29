from abc import ABC, abstractmethod

import numpy as np


class DemandEstimator(ABC):
    """Abstract base class for estimating future demand for firms' products.

    This class defines strategies for projecting future demand based on:
    - Previous period demand
    - Overall economic growth expectations
    - Firm-specific growth estimates

    The estimation process uses two adjustment speeds:
    1. Sectoral: How quickly firms adjust to overall economic growth
    2. Firm-specific: How quickly firms adjust to their individual growth prospects

    Attributes:
        sectoral_growth_adjustment_speed (float): Rate at which firms adjust to overall economic growth
            Values closer to 1 mean faster adjustment to sectoral trends
        firm_growth_adjustment_speed (float): Rate at which firms adjust to firm-specific growth
            Values closer to 1 mean faster adjustment to individual conditions
            Clipped to range [0,1]
    """

    def __init__(
        self,
        sectoral_growth_adjustment_speed: float,
        firm_growth_adjustment_speed: float,
        demand_smoothing: float = 1.0,
    ):
        """Initialize the demand estimator with adjustment speeds.

        Args:
            sectoral_growth_adjustment_speed (float): Speed of adjustment to overall economic growth
            firm_growth_adjustment_speed (float): Speed of adjustment to firm-specific growth
                Will be clipped to range [0,1]
        """
        self.sectoral_growth_adjustment_speed = sectoral_growth_adjustment_speed
        self.firm_growth_adjustment_speed = max(0.0, min(1.0, firm_growth_adjustment_speed))
        self.firm_growth_adjustment_speed = firm_growth_adjustment_speed
        # alpha: adaptive-expectations adjustment speed. 1.0 = no smoothing = the
        # historical rule exactly. See compute_estimated_demand.
        self.demand_smoothing = demand_smoothing
        self._smoothed_demand = None

    @abstractmethod
    def compute_estimated_demand(
        self,
        previous_demand: np.ndarray,
        current_estimated_growth: float,
        estimated_growth_by_firm: np.ndarray,
    ) -> np.ndarray:
        """Calculate estimated future demand for each firm.

        Args:
            previous_demand (np.ndarray): Previous period demand for each firm
            current_estimated_growth (float): Overall economic growth rate estimate
            estimated_growth_by_firm (np.ndarray): Firm-specific growth rate estimates

        Returns:
            np.ndarray: Estimated future demand for each firm
        """
        pass


class DefaultDemandEstimator(DemandEstimator):
    """Default implementation of demand estimation.

    This class implements a demand estimation strategy that:
    1. Starts with previous period demand
    2. Adjusts for overall economic growth at the sectoral adjustment speed
    3. Further adjusts for firm-specific growth at the firm adjustment speed

    The final estimate combines both macro and micro level growth expectations
    in a multiplicative fashion.
    """

    def compute_estimated_demand(
        self,
        previous_demand: np.ndarray,
        current_estimated_growth: float,
        estimated_growth_by_firm: np.ndarray,
    ) -> np.ndarray:
        """Calculate estimated demand using the default strategy.

        Computes future demand as:
        previous_demand * (1 + sectoral_speed * overall_growth) * (1 + firm_speed * firm_growth)

        This formulation allows for:
        - Base demand from previous period
        - Sectoral growth effects with controlled adjustment speed
        - Firm-specific growth effects with controlled adjustment speed

        Args:
            previous_demand (np.ndarray): Previous period demand for each firm
            current_estimated_growth (float): Overall economic growth rate estimate
            estimated_growth_by_firm (np.ndarray): Firm-specific growth rate estimates

        Returns:
            np.ndarray: Estimated future demand for each firm, incorporating both
                       overall economic conditions and firm-specific factors
        """
        # Adaptive expectations (Nerlove): smooth the observed demand before
        # extrapolating it.
        #
        #     D^smooth_t = (1 - alpha) * D^smooth_{t-1} + alpha * previous_demand_t
        #     estimated_demand = (1 + s*g)(1 + f*g_f) * D^smooth_t
        #
        # alpha = 1.0 (default) => D^smooth_t == previous_demand_t, i.e. exactly the
        # historical rule, bit-for-bit.
        #
        # Why this matters here: `previous_demand` is NOT exogenous. Firms are
        # goods-market buyers whose orders are keyed to target_production, which is
        # itself this forecast -- so demand -> target -> input orders -> demand is a
        # closed loop running through the Leontief matrix and the capital accelerator.
        # alpha is one of the few things holding that loop's gain below 1. NOTE a
        # stable AR(1) expectation does NOT imply a stable full system: the eigenvalue
        # (1-alpha) governs the expectation alone, not the loop it sits inside.
        previous_demand = np.asarray(previous_demand, dtype=float)
        if self.demand_smoothing >= 1.0 or self._smoothed_demand is None:
            self._smoothed_demand = previous_demand
        else:
            self._smoothed_demand = (
                1.0 - self.demand_smoothing
            ) * self._smoothed_demand + self.demand_smoothing * previous_demand

        return (
            (1 + self.sectoral_growth_adjustment_speed * current_estimated_growth)
            * (1 + self.firm_growth_adjustment_speed * estimated_growth_by_firm)
            * self._smoothed_demand
        )
