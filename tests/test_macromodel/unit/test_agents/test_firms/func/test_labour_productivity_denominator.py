"""Unit tests for the labour capacity a work-effort factor is measured against.

A firm with no employees, or one in an industry with zero productivity, has a zero
denominator. The guard leaves such a firm's work effort unchanged.
"""

import warnings

import numpy as np

from macromodel.agents.firms.func.labour_productivity import WorkEffortLabourProductivitySetter
from macromodel.configurations import FirmsConfiguration

TARGET = np.array([60.0])
FINITE_LIMIT = np.array([100.0])


def _setter():
    return WorkEffortLabourProductivitySetter(**FirmsConfiguration().functions.labour_productivity.parameters)


class TestZeroLabourCapacity:
    def test_a_firm_with_no_employees_keeps_its_work_effort(self):
        factor = _setter().compute_labour_productivity_factor(
            TARGET, FINITE_LIMIT, FINITE_LIMIT, np.array([0.0]), np.array([1.0])
        )

        assert factor[0] == 1.0

    def test_a_zero_industry_productivity_keeps_its_work_effort(self):
        factor = _setter().compute_labour_productivity_factor(
            TARGET, FINITE_LIMIT, FINITE_LIMIT, np.array([50.0]), np.array([0.0])
        )

        assert factor[0] == 1.0

    def test_a_zero_denominator_divides_no_longer(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)

            _setter().compute_labour_productivity_factor(
                TARGET, FINITE_LIMIT, FINITE_LIMIT, np.array([0.0]), np.array([1.0])
            )

    def test_a_positive_denominator_is_unchanged(self):
        factor = _setter().compute_labour_productivity_factor(
            TARGET, FINITE_LIMIT, FINITE_LIMIT, np.array([50.0]), np.array([1.0])
        )

        assert factor[0] == 1.2  # 60 / (50 * 1.0), at speed 1.0
