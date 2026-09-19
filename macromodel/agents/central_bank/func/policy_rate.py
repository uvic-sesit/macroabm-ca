"""Policy rate determination for central bank monetary policy.

This module implements various strategies for setting policy interest
rates, including:
- Constant rate maintenance
- Taylor-rule based adjustments
- Growth and inflation targeting
- Interest rate smoothing

The policy rate setting considers:
- Inflation gap from target
- Economic growth rates
- Previous policy rates
- Monetary policy parameters
"""

from abc import ABC, abstractmethod


def annual_to_quarterly_effective(rate):
    """Convert annual quoted rates to quarterly effective model-period rates."""
    return (1.0 + rate) ** 0.25 - 1.0


def quarterly_to_annual_effective(rate):
    """Convert quarterly effective model-period rates back to annual quotes."""
    return (1.0 + rate) ** 4.0 - 1.0


class PolicyRate(ABC):
    """Abstract base class for determining policy interest rates.

    This class defines strategies for setting monetary policy rates
    based on:
    - Inflation developments
    - Economic growth
    - Policy objectives
    - Previous rate levels

    The rate setting process considers:
    - Price stability targets
    - Economic growth goals
    - Policy transmission lags
    - Financial stability
    """

    @abstractmethod
    def compute_rate(
        self,
        prev_rate: float,
        inflation: float,
        growth: float,
        central_bank_states: dict[str, float],
    ) -> float:
        """Calculate the appropriate policy interest rate.

        Determines policy rate considering:
        - Previous rate level
        - Current inflation
        - Economic growth
        - Policy parameters

        Args:
            prev_rate (float): Previous period's policy rate
            inflation (float): Current inflation rate
            growth (float): Current economic growth rate
            central_bank_states (dict[str, float]): Policy parameters including:
                - targeted_inflation_rate: Inflation target
                - rho: Interest rate smoothing parameter
                - r_star: Natural real interest rate
                - xi_pi: Inflation gap response coefficient
                - xi_gamma: Output growth response coefficient

        Returns:
            float: New policy interest rate
        """
        pass


class ConstantPolicyRate(PolicyRate):
    """Implementation of constant policy rate strategy.

    This class maintains unchanged policy rates by:
    - Keeping rates at previous levels
    - Ignoring inflation developments
    - Disregarding growth rates
    - Maintaining policy stance

    This approach is useful for:
    - Model testing and validation
    - Policy transmission analysis
    - Baseline scenario creation
    """

    def compute_rate(
        self,
        prev_rate: float,
        inflation: float,
        growth: float,
        central_bank_states: dict[str, float],
    ) -> float:
        """Keep policy rate constant.

        Returns the same rate regardless of economic conditions.

        Args:
            [same as parent class]

        Returns:
            float: Previous policy rate (unchanged, quarterly effective)
        """
        return prev_rate


class PolednaPolicyRate(PolicyRate):
    """Stylized Taylor-type monetary-policy robustness rule.

    The historical Poledna-style ARDL coefficients stored in old pickles are not
    used here: the inflation coefficient has the wrong sign for policy use and is
    explicitly flagged as suspect in the preprocessing code. For diagnostics this
    class keeps the existing configuration hook but uses transparent Taylor-style
    parameters on annual-rate units, then converts the output to the model's
    quarterly effective rate convention.
    """

    def compute_rate(
        self,
        prev_rate: float,
        inflation: float,
        growth: float,
        central_bank_states: dict[str, float],
    ) -> float:
        """Calculate a stylized Taylor policy rate.

        Annual scale:
            i_t = rho i_{t-1}
                  + (1-rho)[r* + pi* + phi_pi(pi_t - pi*)]

        with rho=0.85, r*=0.005, pi*=0.02, phi_pi=1.5, and an 8%
        annual cap by default unless overridden in central_bank_states.
        The model's growth variable is not used here because it is not a
        calibrated output-gap measure in the CAN-2022 diagnostic closure.
        """
        prev_rate_annual = quarterly_to_annual_effective(prev_rate)
        inflation_annual = quarterly_to_annual_effective(inflation)
        rho = central_bank_states.get("stylized_taylor_rho", 0.85)
        r_star = central_bank_states.get("stylized_taylor_r_star", 0.005)
        pi_star = central_bank_states.get("stylized_taylor_inflation_target", 0.02)
        phi_pi = central_bank_states.get("stylized_taylor_phi_pi", 1.5)
        max_rate = central_bank_states.get("stylized_taylor_max_rate", 0.08)
        annual_policy_rate = min(
            max_rate,
            max(
                0.0,
                rho * prev_rate_annual
                + (1 - rho) * (r_star + pi_star + phi_pi * (inflation_annual - pi_star)),
            ),
        )
        return annual_to_quarterly_effective(annual_policy_rate)
