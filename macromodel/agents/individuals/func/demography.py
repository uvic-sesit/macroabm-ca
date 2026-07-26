"""Individual demographic dynamics management.

This module implements strategies for managing individual demographic changes
through:
- Population size updates
- Birth and death events
- Workforce entry/exit
- Age-based transitions

The implementation handles:
- Natural population changes
- Labor force dynamics
- Demographic transitions
- Age structure evolution
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

import numpy as np

from macromodel.agents.individuals.individual_properties import ActivityStatus


class IndividualDemography(ABC):
    """Abstract base class for individual demographic management.

    This class defines strategies for handling demographic changes in
    the individual population through:
    - Population size tracking
    - Life events (birth/death)
    - Labor force participation changes
    - Age-based transitions

    The strategies consider:
    - Natural population dynamics
    - Workforce demographics
    - Age structure changes
    - Population stability
    """

    @abstractmethod
    def update(
        self,
        prev_n_individuals: float,
    ) -> float:
        """Update total population size.

        Args:
            prev_n_individuals (float): Previous period's population

        Returns:
            float: New population size
        """
        pass

    @abstractmethod
    def check_for_death(
        self,
    ) -> None:
        """Process individual death events."""
        pass

    @abstractmethod
    def check_for_birth(
        self,
    ) -> None:
        """Process individual birth events."""
        pass

    @abstractmethod
    def individuals_joining_the_workforce(
        self,
        current_individuals_activity: Optional[np.ndarray] = None,
    ) -> None:
        """Process individuals entering the labor force.

        Args:
            current_individuals_activity: Activity-status array, mutated in place by
                implementations that move individuals into the labour force. Optional
                so that implementations which ignore it (NoAging) keep working.
        """
        pass

    @abstractmethod
    def individuals_leaving_the_workforce(
        self,
        current_individuals_activity: Optional[np.ndarray] = None,
    ) -> None:
        """Process individuals exiting the labor force.

        Args:
            current_individuals_activity: Activity-status array, mutated in place.
        """
        pass


class NoAging(IndividualDemography):
    """Static demographic implementation with no population changes.

    This class implements a simplified approach that:
    - Maintains constant population size
    - Ignores demographic transitions
    - Preserves workforce composition
    - Keeps age structure static

    Used for:
    - Model testing
    - Baseline scenarios
    - Short-term simulations
    - Controlled experiments
    """

    def update(
        self,
        prev_n_individuals: float,
    ) -> float:
        """Maintain constant population size.

        Args:
            prev_n_individuals (float): Previous period's population

        Returns:
            float: Same population size (no change)
        """
        return prev_n_individuals

    def check_for_death(
        self,
    ) -> None:
        """No death events processed."""
        pass

    def check_for_birth(
        self,
    ) -> None:
        """No birth events processed."""
        pass

    def individuals_joining_the_workforce(
        self,
        current_individuals_activity: Optional[np.ndarray] = None,
    ) -> None:
        """No workforce entry events processed."""
        pass

    def individuals_leaving_the_workforce(
        self,
        current_individuals_activity: Optional[np.ndarray] = None,
    ) -> None:
        """No workforce exit events processed."""
        pass


class ExogenousLabourForcePath(NoAging):
    """OPT-IN: drive the labour force along an exogenous index path.

    Purpose: a falsification test of the labour-constraint hypothesis. Under NoAging
    the labour force is a fixed pool (population frozen, participation never wired),
    so employment can only ever grow by absorbing the initial unemployment stock --
    at most ~+7.5% once. This class relaxes that ceiling in the smallest way that
    preserves every accounting flow.

    Mechanism
    ---------
    NO new individuals are created and NO array is resized. The population
    (`n_individuals`) is unchanged -- `update` is inherited from NoAging. Only the
    `Activity Status` of ALREADY-EXISTING individuals changes:

        entry:  NOT_ECONOMICALLY_ACTIVE -> UNEMPLOYED   (joins the matching pool)
        exit :  UNEMPLOYED              -> NOT_ECONOMICALLY_ACTIVE

    Entrants are NOT placed into jobs. They become unemployed job-seekers and must
    pass through the existing labour-market matching process like anyone else, so
    employment rises only if firms actually demand the labour. Reclassified
    individuals keep their existing income, benefit, consumption and tax machinery
    (they are the same agents), so no accounting term is added or removed.

    Exit rule (for declining paths)
    -------------------------------
    Symmetric to entry but deliberately conservative: ONLY currently UNEMPLOYED
    individuals are moved out of the labour force. Employed workers are NEVER
    reclassified, so a declining path cannot abruptly destroy matches. If the target
    would require more exits than there are unemployed individuals, only the
    available unemployed are removed and the shortfall is logged rather than forcing
    employed workers out.

    Timing
    ------
    `update_population_structure` runs at the END of a quarter (simulation.py:361),
    after `clear_labour_market` (simulation.py:316). Entrants therefore first face
    matching in the FOLLOWING quarter -- a one-quarter lag inherent to the existing
    iterate order, not introduced here.

    Args:
        labour_force_index: quarterly index of the target labour force, base 1.0 at
            t0. Index i is applied at quarter i; the last value is held for any
            quarters beyond the path. Empty/None makes the class inert (== NoAging).
        seed: seed for reproducible selection of which individuals are reclassified.
    """

    def __init__(
        self,
        labour_force_index: Optional[list[float]] = None,
        seed: int = 0,
    ) -> None:
        self.labour_force_index = list(labour_force_index) if labour_force_index else []
        self.seed = int(seed)
        self._rng = np.random.default_rng(self.seed)
        self._t = -1
        self._initial_labour_force: Optional[int] = None
        self._entries = 0
        self._exits = 0
        self._exit_shortfall = 0
        self.log: list[dict[str, Any]] = []

    # -- helpers ---------------------------------------------------------------
    @staticmethod
    def _in_labour_force(activity: np.ndarray) -> np.ndarray:
        """Labour-force membership, matching economy.py:846-852 exactly."""
        return (
            (activity == ActivityStatus.EMPLOYED)
            | (activity == ActivityStatus.UNEMPLOYED)
            | (activity == ActivityStatus.FIRM_INVESTOR)
            | (activity == ActivityStatus.BANK_INVESTOR)
        )

    def _target(self, activity: np.ndarray) -> Optional[int]:
        if not self.labour_force_index:
            return None
        if self._initial_labour_force is None:
            self._initial_labour_force = int(self._in_labour_force(activity).sum())
        i = min(max(self._t, 0), len(self.labour_force_index) - 1)
        return int(round(self._initial_labour_force * self.labour_force_index[i]))

    def update(self, prev_n_individuals: float) -> float:
        """Advance the quarter counter. Population is unchanged (no new agents)."""
        self._t += 1
        self._entries = 0
        self._exits = 0
        self._exit_shortfall = 0
        return prev_n_individuals

    # -- entry / exit ----------------------------------------------------------
    def individuals_joining_the_workforce(
        self,
        current_individuals_activity: Optional[np.ndarray] = None,
    ) -> None:
        if current_individuals_activity is None:
            return
        activity = current_individuals_activity
        target = self._target(activity)
        if target is None:
            return
        delta = target - int(self._in_labour_force(activity).sum())
        if delta <= 0:
            return
        inactive = np.flatnonzero(activity == ActivityStatus.NOT_ECONOMICALLY_ACTIVE)
        n = int(min(delta, inactive.size))
        if n <= 0:
            return
        chosen = self._rng.choice(inactive, size=n, replace=False)
        activity[chosen] = ActivityStatus.UNEMPLOYED
        self._entries = n

    def individuals_leaving_the_workforce(
        self,
        current_individuals_activity: Optional[np.ndarray] = None,
    ) -> None:
        if current_individuals_activity is None:
            return
        activity = current_individuals_activity
        target = self._target(activity)
        if target is None:
            return
        delta = target - int(self._in_labour_force(activity).sum())
        if delta < 0:
            wanted = -delta
            unemployed = np.flatnonzero(activity == ActivityStatus.UNEMPLOYED)
            n = int(min(wanted, unemployed.size))
            if n > 0:
                chosen = self._rng.choice(unemployed, size=n, replace=False)
                activity[chosen] = ActivityStatus.NOT_ECONOMICALLY_ACTIVE
                self._exits = n
            # never reclassify EMPLOYED individuals; record the unmet exit instead
            self._exit_shortfall = int(wanted - n)

        # last hook of the quarter: record the resulting state
        in_lf = self._in_labour_force(activity)
        employed = int((activity == ActivityStatus.EMPLOYED).sum())
        unemployed_n = int((activity == ActivityStatus.UNEMPLOYED).sum())
        lf = int(in_lf.sum())
        self.log.append(
            {
                "t": self._t,
                "target_labour_force": target,
                "labour_force": lf,
                "employed": employed,
                "unemployed": unemployed_n,
                "unemployment_rate": (unemployed_n / lf) if lf else float("nan"),
                "entries": self._entries,
                "exits": self._exits,
                "exit_shortfall": self._exit_shortfall,
                "nea_headroom": int((activity == ActivityStatus.NOT_ECONOMICALLY_ACTIVE).sum()),
            }
        )
