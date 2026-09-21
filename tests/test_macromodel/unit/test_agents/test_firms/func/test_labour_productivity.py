"""Unit tests for the input clamps in the work-effort labour productivity setter."""

import numpy as np

from macromodel.agents.firms.func.labour_productivity import WorkEffortLabourProductivitySetter
from macromodel.configurations import FirmsConfiguration

TARGET = np.array([60.0])
LABOUR_INPUTS = np.array([50.0])
INDUSTRY_PRODUCTIVITY = np.array([1.0])


def _setter(**overrides):
    parameters = dict(FirmsConfiguration().functions.labour_productivity.parameters)

    return WorkEffortLabourProductivitySetter(**{**parameters, **overrides})


class TestLabourProductivityClamps:
    def test_infinite_limit_at_zero_weight_produces_no_nan(self):
        # A firm with no binding capital constraint has limit = inf; the naive clamp
        # evaluates 0.0 * inf -> NaN at weight 0.0 and np.minimum propagates it.
        setter = _setter(consider_capital_inputs=0.0)

        factor = setter.compute_labour_productivity_factor(
            TARGET, np.array([100.0]), np.array([np.inf]), LABOUR_INPUTS, INDUSTRY_PRODUCTIVITY
        )

        assert not np.isnan(factor).any()
        assert factor[0] == 1.2  # 60 / (50 * 1.0), unclamped, at speed 1.0

    def test_finite_limits_match_the_naive_clamp(self):
        # Where both limits are finite the guarded clamp must leave the factor unchanged.
        setter = _setter()
        for intermediate, capital in [(100.0, 100.0), (55.0, 100.0), (100.0, 40.0), (55.0, 40.0)]:
            clamped = np.minimum(TARGET, TARGET + 1.0 * (np.array([intermediate]) - TARGET))
            clamped = np.minimum(clamped, clamped + 1.0 * (np.array([capital]) - clamped))
            naive = 1.0 + 1.0 * (np.minimum(1.5, clamped / (LABOUR_INPUTS * INDUSTRY_PRODUCTIVITY)) - 1.0)

            factor = setter.compute_labour_productivity_factor(
                TARGET, np.array([intermediate]), np.array([capital]), LABOUR_INPUTS, INDUSTRY_PRODUCTIVITY
            )

            assert np.allclose(factor, naive)
