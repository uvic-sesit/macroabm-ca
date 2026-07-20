from abc import ABC, abstractmethod

import numpy as np

from macromodel.util.clamps import clamp_towards as _clamp_towards


class DesiredLabourSetter(ABC):
    """Abstract base class for determining firms' desired labor inputs.

    This class defines strategies for calculating optimal labor demand based on:
    - Production targets
    - Input constraints (intermediate and capital)
    - Complementarity between labor and other inputs

    The labor demand calculation considers the interaction between different
    factors of production, with configurable weights for:
    - Intermediate input constraints (materials, supplies)
    - Capital input constraints (machinery, equipment)

    Attributes:
        consider_intermediate_inputs (float): Weight given to intermediate input constraints
            Clipped to range [0,1], where higher values mean stronger complementarity
        consider_capital_inputs (float): Weight given to capital input constraints
            Clipped to range [0,1], where higher values mean stronger complementarity
    """

    def __init__(
        self,
        consider_intermediate_inputs: float,
        consider_capital_inputs: float,
    ) -> None:
        """Initialize the desired labor setter with input consideration weights.

        Args:
            consider_intermediate_inputs (float): Weight for intermediate input constraints
                Will be clipped to range [0,1]
            consider_capital_inputs (float): Weight for capital input constraints
                Will be clipped to range [0,1]
        """
        self.consider_intermediate_inputs = max(0.0, min(1.0, consider_intermediate_inputs))
        self.consider_capital_inputs = max(0.0, min(1.0, consider_capital_inputs))

    @abstractmethod
    def compute_desired_labour(
        self,
        current_target_production: np.ndarray,
        current_limiting_intermediate_inputs: np.ndarray,
        current_limiting_capital_inputs: np.ndarray,
    ) -> np.ndarray:
        """Calculate desired labor inputs for each firm.

        Args:
            current_target_production (np.ndarray): Target production levels
            current_limiting_intermediate_inputs (np.ndarray): Production constraints
                from intermediate input availability
            current_limiting_capital_inputs (np.ndarray): Production constraints
                from capital input availability

        Returns:
            np.ndarray: Desired labor inputs for each firm
        """
        pass


class DefaultDesiredLabourSetter(DesiredLabourSetter):
    """Default implementation of desired labor calculation.

    This class implements a labor demand strategy that:
    1. Starts with target production levels
    2. Adjusts for intermediate input constraints
    3. Further adjusts for capital input constraints

    The adjustments reflect the complementarity between labor and other
    inputs in the production process, ensuring labor demand is consistent
    with available complementary factors of production.
    """

    def compute_desired_labour(
        self,
        current_target_production: np.ndarray,
        current_limiting_intermediate_inputs: np.ndarray,
        current_limiting_capital_inputs: np.ndarray,
    ) -> np.ndarray:
        """Calculate desired labor using the default adjustment strategy.

        Adjusts target production downward based on input constraints:
        1. First considers intermediate input limitations with configured weight
        2. Then considers capital input limitations with configured weight
        The final value represents feasible labor demand given input constraints.

        Args:
            current_target_production (np.ndarray): Initial production targets
            current_limiting_intermediate_inputs (np.ndarray): Intermediate input constraints
            current_limiting_capital_inputs (np.ndarray): Capital input constraints

        Returns:
            np.ndarray: Adjusted labor demand accounting for input complementarities
        """
        # NOTE: uses the same inf-safe clamp as TargetProductionSetter. The naive form
        # `target + w*(limit - target)` evaluates 0.0 * inf -> NaN when a firm has no
        # binding capital constraint (limit = inf) AND the weight is 0.0; np.minimum
        # then propagates the NaN. Safe at shipped defaults (consider_capital_inputs =
        # 1.0, and limiting_intermediate_inputs is never inf), but it would fire the
        # moment either weight is set to 0.0 -- i.e. exactly the "unclamp" experiment.
        current_target_production = _clamp_towards(
            current_target_production,
            current_limiting_intermediate_inputs,
            self.consider_intermediate_inputs,
        )
        current_target_production = _clamp_towards(
            current_target_production,
            current_limiting_capital_inputs,
            self.consider_capital_inputs,
        )
        return current_target_production
