"""Unit tests for the income-quantile consumption weights.

take_consumption_weights_by_income_quantile is declared, fitted and passed all the
way into the consumption kernel, which has never read it, so the weights by income
quintile were never applied.
"""

import numpy as np
import pytest

from macromodel.agents.households.func.consumption import DefaultHouseholdConsumption

N_HOUSEHOLDS = 10
# Rising income, so household i sits in quintile i // 2.
INCOME = np.arange(1.0, N_HOUSEHOLDS + 1) * 100.0
FLAT_WEIGHTS = np.array([0.2, 0.3, 0.5])
# One column per quintile, one row per industry.
WEIGHTS_BY_QUINTILE = np.array(
    [
        [0.1, 0.2, 0.3, 0.4, 0.5],
        [0.6, 0.5, 0.4, 0.3, 0.2],
        [0.3, 0.3, 0.3, 0.3, 0.3],
    ]
)


def _target(take_by_quantile):
    rule = DefaultHouseholdConsumption(
        consumption_smoothing_fraction=0.0,
        consumption_smoothing_window=12,
        minimum_consumption_fraction=1.0,
    )

    return rule.compute_target_consumption(
        expected_inflation=0.0,
        current_cpi=1.0,
        initial_cpi=1.0,
        historic_consumption_sum=np.zeros((2, N_HOUSEHOLDS)),
        saving_rates=np.zeros(N_HOUSEHOLDS),
        income=INCOME,
        household_benefits=np.zeros(N_HOUSEHOLDS),
        consumption_weights=FLAT_WEIGHTS,
        consumption_weights_by_income=WEIGHTS_BY_QUINTILE,
        exogenous_total_consumption=None,
        current_time=1,
        take_consumption_weights_by_income_quantile=take_by_quantile,
        tau_vat=0.0,
    )


class TestIncomeQuantileWeights:
    def test_the_flag_off_spends_on_the_flat_weights(self):
        target = _target(take_by_quantile=False)

        assert np.allclose(target, np.outer(INCOME, FLAT_WEIGHTS))

    def test_the_flag_on_spends_on_the_household_quintile_weights(self):
        target = _target(take_by_quantile=True)

        assert np.allclose(target[0], INCOME[0] * WEIGHTS_BY_QUINTILE[:, 0])
        assert np.allclose(target[-1], INCOME[-1] * WEIGHTS_BY_QUINTILE[:, 4])

    def test_the_flag_changes_the_target(self):
        assert not np.allclose(_target(take_by_quantile=False), _target(take_by_quantile=True))

    @pytest.mark.parametrize("take_by_quantile", [False, True])
    def test_a_household_still_spends_its_whole_income(self, take_by_quantile):
        target = _target(take_by_quantile)

        assert np.allclose(target.sum(axis=1), INCOME)
