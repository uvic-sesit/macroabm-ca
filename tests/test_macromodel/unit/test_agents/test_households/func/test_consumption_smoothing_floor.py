"""Unit tests for the consumption smoothing floor.

The floor is the third operand of the target-consumption maximum. Passed positionally
to np.maximum it binds to `out=` instead, which makes it an output buffer rather than
an operand, so it can never raise the target.
"""

import numpy as np
import pytest

from macromodel.agents.households.func.consumption import (
    CESHouseholdConsumption,
    DefaultHouseholdConsumption,
)

# Two households, four periods of consumption history at 40.0 each.
HISTORY = np.full((4, 2), 40.0)
SAVING_RATES = np.zeros(2)
INCOME = np.full(2, 10.0)
BENEFITS = np.full(2, 4.0)
ONE_INDUSTRY = np.array([1.0])
WEIGHTS_BY_INCOME = np.zeros((1, 1))
SMOOTHING_WINDOW = 12
MINIMUM_FRACTION = 1.0

# The floor sums history[1:][-window:] (three rows, 120.0) and divides by the window,
# which min() caps at the history length of four: 30.0 * fraction.
EXPECTED = {0.0: 10.0, 0.5: 15.0, 1.0: 30.0}


def _default_kernel(fraction):
    return DefaultHouseholdConsumption._compute_target_consumption(
        HISTORY,
        SAVING_RATES,
        INCOME,
        BENEFITS,
        ONE_INDUSTRY,
        WEIGHTS_BY_INCOME,
        False,
        0.0,
        SMOOTHING_WINDOW,
        fraction,
        MINIMUM_FRACTION,
    )


def _ces_method(fraction):
    consumption = CESHouseholdConsumption(
        consumption_smoothing_fraction=fraction,
        consumption_smoothing_window=SMOOTHING_WINDOW,
        minimum_consumption_fraction=MINIMUM_FRACTION,
    )

    return consumption._compute_target_consumption_ces(
        HISTORY,
        SAVING_RATES,
        INCOME,
        BENEFITS,
        ONE_INDUSTRY,
        WEIGHTS_BY_INCOME,
        False,
        0.0,
    )


@pytest.mark.parametrize("compute", [_default_kernel, _ces_method], ids=["default_kernel", "ces_method"])
@pytest.mark.parametrize("fraction", [0.5, 1.0])
def test_a_binding_smoothing_floor_raises_the_target(compute, fraction):
    target = compute(fraction)

    assert np.allclose(target.ravel(), EXPECTED[fraction])


@pytest.mark.parametrize("compute", [_default_kernel, _ces_method], ids=["default_kernel", "ces_method"])
def test_the_shipped_fraction_leaves_the_target_on_income(compute):
    # consumption_smoothing_fraction ships at 0.0, where the floor is zero and income wins.
    target = compute(0.0)

    assert np.allclose(target.ravel(), EXPECTED[0.0])
