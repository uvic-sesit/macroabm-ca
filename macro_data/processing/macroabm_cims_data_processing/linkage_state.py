"""Iteration bookkeeping for the CIMS--macroABM linkage.

The linkage is an outer loop that alternates CIMS and macroABM runs.  This
class tracks the iteration counter (as a zero-padded string matching the
filenames the orchestrator writes, e.g. ``'00'``, ``'01'``) and provides a
small helper for the provincial-GDP-growth convergence test described in the
M3-linkages runner.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LinkageState:
    """Tracks the CIMS--macroABM iteration counter.

    Args:
        max_iterations: Hard cap on the number of outer iterations.
    """

    max_iterations: int = 4
    _itr: int = 0

    @property
    def current(self) -> str:
        return self._fmt(self._itr)

    @property
    def iteration(self) -> int:
        return self._itr

    def increment(self) -> str:
        self._itr += 1
        return self.current

    def reset(self) -> None:
        self._itr = 0

    @property
    def reached_max(self) -> bool:
        return self._itr >= self.max_iterations

    @staticmethod
    def _fmt(value: int) -> str:
        return f"{value:02d}"


def gdp_growth_converged(
    previous_growth: dict[str, float],
    current_growth: dict[str, float],
    tolerance: float = 0.10,
) -> bool:
    """Return True if provincial GDP growth has stabilised between iterations.

    The convergence criterion for the CIMS--macroABM linkage is that the
    start-to-end GDP growth of every province changes by less than *tolerance*
    (default 10%) between successive iterations.

    Args:
        previous_growth: Province code -> GDP growth (end/start - 1) from the
            previous iteration.
        current_growth: Same for the current iteration.
        tolerance: Maximum allowed relative change in any province's growth
            figure between iterations.

    Returns:
        True if all provinces are within *tolerance*; False if any province
        moved more than *tolerance* or if there is no previous iteration to
        compare against.
    """
    if not previous_growth:
        return False

    for province, current in current_growth.items():
        previous = previous_growth.get(province)
        if previous is None:
            return False
        denom = abs(previous) if abs(previous) > 1e-12 else 1e-12
        if abs(current - previous) / denom > tolerance:
            return False
    return True
