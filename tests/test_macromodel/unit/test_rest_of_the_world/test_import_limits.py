"""Tests for the ROW import-share cap (``RestOfTheWorld.set_import_limits``).

The rest of the world is an unconstrained residual supplier, so any demand domestic
firms cannot meet is silently imported.  For sectors where the scenario intends the
domestic sector to build capacity (e.g. electricity under electrification), that
absorbs the entire demand increase and the domestic sector never expands.  These
tests pin the opt-in cap that prevents it.
"""

import numpy as np

from macromodel.rest_of_the_world import RestOfTheWorld


class _Series(list):
    """Minimal stand-in for the time-series container used by RestOfTheWorld."""


class _FakeTS:
    def __init__(self, initial):
        self.desired_exports_real = _Series([np.array(initial, dtype=float)])
        self._initial = np.array(initial, dtype=float)

    def current(self, name):
        assert name == "desired_exports_real"
        return self.desired_exports_real[-1]

    def initial(self, name):
        assert name == "desired_exports_real"
        return self._initial


def _row(initial, current):
    """Build a bare RestOfTheWorld carrying only what _apply_import_limits touches."""
    row = RestOfTheWorld.__new__(RestOfTheWorld)
    row._import_limited_industries = []
    row.ts = _FakeTS(initial)
    row.ts.desired_exports_real.append(np.array(current, dtype=float))
    return row


def test_no_limits_is_a_noop():
    row = _row([10.0, 10.0], [99.0, 99.0])
    row._apply_import_limits(1.0)
    np.testing.assert_allclose(row.ts.current("desired_exports_real"), [99.0, 99.0])


def test_limited_industry_is_capped_at_base_year_level():
    row = _row([10.0, 10.0], [99.0, 99.0])
    row.set_import_limits([0])
    row._apply_import_limits(1.0)
    # Industry 0 capped to its base-year level; industry 1 untouched.
    np.testing.assert_allclose(row.ts.current("desired_exports_real"), [10.0, 99.0])


def test_cap_scales_with_production_index_so_it_limits_share_not_level():
    row = _row([10.0], [99.0])
    row.set_import_limits([0])
    row._apply_import_limits(2.5)  # economy 2.5x larger => imports may be 2.5x larger
    np.testing.assert_allclose(row.ts.current("desired_exports_real"), [25.0])


def test_cap_never_raises_imports_below_the_cap():
    """The clamp is one-sided: it must not inflate imports that are already low."""
    row = _row([10.0], [3.0])
    row.set_import_limits([0])
    row._apply_import_limits(1.0)
    np.testing.assert_allclose(row.ts.current("desired_exports_real"), [3.0])


def test_non_finite_or_zero_index_falls_back_to_unit_scaling():
    for bad in (0.0, -1.0, np.nan, np.inf):
        row = _row([10.0], [99.0])
        row.set_import_limits([0])
        row._apply_import_limits(bad)
        np.testing.assert_allclose(row.ts.current("desired_exports_real"), [10.0])


def test_out_of_range_indices_are_ignored():
    row = _row([10.0], [99.0])
    row.set_import_limits([0, 7])
    row._apply_import_limits(1.0)
    np.testing.assert_allclose(row.ts.current("desired_exports_real"), [10.0])


def test_set_import_limits_deduplicates_and_can_be_cleared():
    row = _row([10.0, 10.0], [99.0, 99.0])
    row.set_import_limits([1, 1, 0])
    assert row._import_limited_industries == [0, 1]
    row.set_import_limits([])
    assert row._import_limited_industries == []
    row._apply_import_limits(1.0)
    np.testing.assert_allclose(row.ts.current("desired_exports_real"), [99.0, 99.0])
