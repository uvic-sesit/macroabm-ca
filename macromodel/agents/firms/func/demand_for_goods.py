from abc import ABC, abstractmethod

import numpy as np


class DemandSetter(ABC):
    """Abstract base class for calculating realized demand for firms' products.

    This class defines strategies for determining actual demand by combining:
    - Realized sales (quantities actually sold in the market)
    - Excess demand (additional quantities that could not be satisfied)

    The total demand calculation helps firms understand their true market position,
    including both fulfilled and unfulfilled demand, which is crucial for:
    - Production planning
    - Capacity decisions
    - Market share analysis
    """

    @abstractmethod
    def compute_demand(
        self,
        sell_real: np.ndarray,
        excess_demand: np.ndarray,
    ) -> np.ndarray:
        """Calculate total realized demand for each firm's products.

        Args:
            sell_real (np.ndarray): Actual quantities sold by each firm
            excess_demand (np.ndarray): Additional quantities demanded but not fulfilled
                due to capacity constraints or stock limitations

        Returns:
            np.ndarray: Total demand for each firm's products, including both
                       fulfilled (sales) and unfulfilled (excess) demand
        """
        pass


class DefaultDemandSetter(DemandSetter):
    """Default implementation of demand calculation.

    This class implements a simple additive strategy that:
    1. Takes actual sales as the base demand
    2. Adds excess demand to represent total market interest
    3. Provides firms with a complete picture of their market position

    The total demand figure represents the maximum quantity that could have
    been sold if all demand could have been satisfied.
    """

    def __init__(self, unmet_demand_weight: float = 1.0) -> None:
        """Initialize the default demand setter.

        Args:
            unmet_demand_weight (float): rho in [0, 1]. Weight firms place on
                unfulfilled demand when forming recorded demand. 1.0 (default)
                reproduces the historical rule exactly. Values below 1.0 discount
                unmet demand for the uncertainty about whether it would persist, and
                directly scale the gain of the
                demand -> target -> input orders -> demand loop.
        """
        self.unmet_demand_weight = unmet_demand_weight

    def compute_demand(
        self,
        sell_real: np.ndarray,
        excess_demand: np.ndarray,
    ) -> np.ndarray:
        """Calculate total demand: sales plus rho-weighted unfulfilled demand.

            demand = sell_real + rho * excess_demand

        rho = 1.0 (default) is the historical rule. This represents the full market
        interest in each firm's products, regardless of whether that demand could be
        satisfied.

        Args:
            sell_real (np.ndarray): Actual quantities sold by each firm
            excess_demand (np.ndarray): Unfulfilled demand quantities

        Returns:
            np.ndarray: Total recorded demand
        """
        return sell_real + self.unmet_demand_weight * excess_demand
