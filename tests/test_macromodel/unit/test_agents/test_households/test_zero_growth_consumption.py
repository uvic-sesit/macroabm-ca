"""Unit tests for the zero-growth branch of the household consumption target."""

import numpy as np

ZERO_GROWTH_CALL = dict(
    expected_inflation=0.0,
    current_cpi=1.0,
    initial_cpi=1.0,
    exogenous_total_consumption=0.0,
    per_capita_unemployment_benefits=0.0,
    tau_vat=0.0,
    assume_zero_growth=True,
)


class TestZeroGrowthTargetConsumption:
    def test_the_branch_runs_and_has_the_shape_of_the_initial_target(self, test_households):
        target = test_households.compute_target_consumption(**ZERO_GROWTH_CALL)

        assert target.shape == test_households.ts.initial("target_consumption").shape
        assert np.isfinite(target).all()

    def test_no_household_is_given_a_negative_consumption(self, test_households):
        # The build's own consumption column is negative for households whose saving rate
        # exceeds one, and the default consumption function clips before returning.
        target = test_households.compute_target_consumption(**ZERO_GROWTH_CALL)

        assert (target >= 0.0).all()

    def test_the_target_is_the_initial_consumption_spread_over_the_industry_weights(self, test_households):
        target = test_households.compute_target_consumption(**ZERO_GROWTH_CALL)

        expected = np.maximum(
            0.0,
            np.outer(test_households.ts.initial("consumption"), test_households.consumption_weights),
        )
        assert np.allclose(target, expected)

    def test_a_negative_initial_consumption_is_clipped(self, test_households, monkeypatch):
        # The build's consumption column is negative for a household whose saving rate exceeds
        # one. The fixture has none, so the case is driven through the series accessor.
        real_initial = test_households.ts.initial
        negative = np.full(len(test_households.states), -1.0)
        monkeypatch.setattr(
            test_households.ts,
            "initial",
            lambda name: negative if name == "consumption" else real_initial(name),
        )

        target = test_households.compute_target_consumption(**ZERO_GROWTH_CALL)

        assert (target == 0.0).all()
