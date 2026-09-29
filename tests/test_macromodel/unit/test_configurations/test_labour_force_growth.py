"""Tests for post-sample labour-force growth in the real-growth baseline.

The bundled observed labour-force index ends in 2024.  By default the index is held flat
past that tail; ``post_sample_growth`` continues it at a constant annual rate so labour
supply keeps expanding over the projection (production passes StatCan's per-province
working-age population projections).
"""

import numpy as np

from macromodel.configurations.growth_baseline_preset import observed_labour_force_index

# The tests below read the bundled index on its own 2014 base (the loader default), so
# the quarter offsets are counted from 2014Q1.  Production rebases to the 2022 start via
# ``base_year``; that path is covered in test_growth_baseline_preset.py.
N_QUARTERS = 90          # 2014Q1 .. 2036Q2
LAST_OBSERVED_Q = 40     # 2024
Q_2030, Q_2035 = 64, 84


def _index(rate=None, province="CAN_ON"):
    return np.array(observed_labour_force_index(N_QUARTERS, province=province, post_sample_growth=rate))


def test_default_is_flat_past_the_data_tail():
    """Regression: the default must keep the flat-tail behaviour."""
    a = _index()
    assert a[Q_2030] == a[Q_2035]
    np.testing.assert_allclose(a[Q_2035], a[Q_2030], rtol=0, atol=0)


def test_growth_rate_expands_labour_supply_past_the_tail():
    a = _index(0.0072)
    assert a[Q_2035] > a[Q_2030] > a[LAST_OBSERVED_Q]


def test_growth_compounds_at_the_requested_annual_rate():
    """Ratio between two post-tail quarters must be the pure compounded rate.

    Compared across two points *inside* the extrapolated region so the assertion does not
    depend on where the last observation sits (it is mid-year, at q41.5, not q40).
    """
    rate = 0.01
    a = _index(rate)
    years = (Q_2035 - Q_2030) / 4.0
    np.testing.assert_allclose(a[Q_2035] / a[Q_2030], (1.0 + rate) ** years, rtol=1e-9)


def test_in_sample_path_is_untouched_by_the_growth_option():
    """Only the post-2024 tail may change; observed history must be identical."""
    base = _index()
    grown = _index(0.02)
    np.testing.assert_allclose(base[: LAST_OBSERVED_Q + 1], grown[: LAST_OBSERVED_Q + 1], rtol=1e-12)


def test_index_is_still_normalised_to_one_at_t0():
    for rate in (None, 0.0072, 0.02):
        np.testing.assert_allclose(_index(rate)[0], 1.0, rtol=1e-12)


def test_zero_growth_matches_the_flat_default():
    np.testing.assert_allclose(_index(0.0), _index(), rtol=1e-12)


def test_negative_growth_shrinks_the_tail():
    """Negative rates are legitimate (QC and NL working-age populations shrink to 2050)."""
    a = _index(-0.005)
    assert a[Q_2035] < a[Q_2030] < a[LAST_OBSERVED_Q + 2]


def test_applies_to_every_province():
    grown = observed_labour_force_index(N_QUARTERS, post_sample_growth=0.01)
    flat = observed_labour_force_index(N_QUARTERS)
    assert set(grown) == set(flat)
    for province in grown:
        assert grown[province][Q_2035] > flat[province][Q_2035]
