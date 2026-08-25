"""Unit tests for ``Firms.anchor_energy_quantities``.

The method touches only a handful of duck-typed attributes, so a light fake gives
faithful coverage of the anchor capture, the growth-index path, and the additive
increment path that the negligible-base guard routes pairs onto.
"""

from __future__ import annotations

import types

import numpy as np
import pytest

from macromodel.agents.firms.firms import Firms


# industries: C20 (0, buyer), D (1, electricity), B05 (2, gas).
# One firm, in industry 0, buying 1.0 of D and 9.0 of B05 -> energy total 10.0.
def _fake_firms(bought=((0.0, 1.0, 9.0),), base=None):
    n = 3
    base = np.full((n, n), 4.0) if base is None else np.asarray(base, dtype=float)
    return types.SimpleNamespace(
        states={
            "Industry": np.array([0]),
            "intermediate_tech_multipliers": np.ones((1, n)),
        },
        ts=types.SimpleNamespace(current=lambda key: np.asarray(bought, dtype=float)),
        base_intermediate_inputs_productivity_matrix=base,
    )


def test_index_path_scales_the_coefficient():
    firms = _fake_firms()
    # Target 2x the anchor (1.0 bought) -> productivity halves, energy per output doubles.
    Firms.anchor_energy_quantities(firms, {(0, 1): 2.0}, max_step=10.0)
    assert firms.base_intermediate_inputs_productivity_matrix[1, 0] == pytest.approx(2.0)
    assert firms._firm_quantity_anchor[(0, 1)] == pytest.approx(1.0)


def test_increment_is_a_share_of_the_industry_energy_total():
    firms = _fake_firms()
    # +0.4 of the industry's 10.0 anchor-year energy -> desired 1.0 + 4.0 = 5.0, so the
    # multiplier is 5x the realised 1.0 and productivity is divided by it.
    Firms.anchor_energy_quantities(
        firms, {}, increments={(0, 1): 0.4}, energy_indices=[1, 2], max_step=10.0
    )
    assert firms._firm_quantity_multiplier[(0, 1)] == pytest.approx(5.0)
    assert firms.base_intermediate_inputs_productivity_matrix[1, 0] == pytest.approx(0.8)


def test_increment_needs_no_base_year_quantity_of_its_own():
    """The point of the increment: it is well defined where the index is not.

    An index cannot be formed at all when the external base is zero, and is enormous when
    the base is merely negligible.  The increment reads only the LEVEL change, so a pair
    that the guard rejects still lands a bounded, sensible correction.
    """
    firms = _fake_firms()
    Firms.anchor_energy_quantities(
        firms, {}, increments={(0, 1): 1.0}, energy_indices=[1, 2], max_step=100.0
    )
    # The whole of the industry's energy total is added on: 1.0 + 10.0 = 11x realised, and
    # bounded by that total -- never the 1800x an index off a near-zero base produces.
    assert firms._firm_quantity_multiplier[(0, 1)] == pytest.approx(11.0)


def test_increment_compounds_over_milestones_and_keeps_the_first_anchor():
    firms = _fake_firms()
    Firms.anchor_energy_quantities(
        firms, {}, increments={(0, 1): 0.4}, energy_indices=[1, 2], max_step=2.0
    )
    # Step bound holds the first move to 2x, leaving the pair short of the 5.0 target.
    assert firms._firm_quantity_multiplier[(0, 1)] == pytest.approx(2.0)
    # Next milestone: purchases have followed to 2.0, the anchor and the energy total are
    # still the first call's, so the remaining 5.0/2.0 is applied on top of the stored 2.0.
    firms.ts = types.SimpleNamespace(
        current=lambda key: np.array([[0.0, 2.0, 9.0]], dtype=float)
    )
    Firms.anchor_energy_quantities(
        firms, {}, increments={(0, 1): 0.4}, energy_indices=[1, 2], max_step=2.0
    )
    assert firms._firm_quantity_anchor[(0, 1)] == pytest.approx(1.0)
    assert firms._firm_energy_anchor_total[0] == pytest.approx(10.0)
    # The remaining 5.0/2.0 is itself over the bound, so the stored 2.0 compounds by
    # another 2.0 rather than jumping straight to 5.0: the increment converges on its
    # target over milestones, it does not arrive in one.
    assert firms._firm_quantity_multiplier[(0, 1)] == pytest.approx(4.0)


def test_energy_total_comes_from_the_first_call_not_the_first_increment():
    """At the anchor year every level change is zero, so no increment is formed there.

    The denominator still has to be the anchor year's, or the increment is scaled by an
    energy total the model has already grown into.
    """
    firms = _fake_firms()
    # Anchor-year call: indices only, all 1.0.
    Firms.anchor_energy_quantities(
        firms, {(0, 1): 1.0, (0, 2): 1.0}, energy_indices=[1, 2], max_step=10.0
    )
    assert firms._firm_energy_anchor_total[0] == pytest.approx(10.0)
    # The industry's energy has doubled by the milestone that first carries an increment.
    firms.ts = types.SimpleNamespace(
        current=lambda key: np.array([[0.0, 2.0, 18.0]], dtype=float)
    )
    Firms.anchor_energy_quantities(
        firms, {}, increments={(0, 1): 0.4}, energy_indices=[1, 2], max_step=100.0
    )
    # Still 10.0, so desired = anchor 1.0 + 4.0 against a realised 2.0.
    assert firms._firm_energy_anchor_total[0] == pytest.approx(10.0)
    assert firms._firm_quantity_multiplier[(0, 1)] == pytest.approx(2.5)


def test_energy_total_excludes_the_self_input():
    # Industry 1 (D) buying its own output is not anchored, so it must not appear in the
    # denominator either -- the same exclusion the caller applies.
    firms = _fake_firms(bought=((0.0, 5.0, 9.0), (0.0, 100.0, 4.0)))
    firms.states["Industry"] = np.array([0, 1])
    firms.states["intermediate_tech_multipliers"] = np.ones((2, 3))
    Firms.anchor_energy_quantities(
        firms, {}, increments={(1, 2): 1.0}, energy_indices=[1, 2], max_step=100.0
    )
    assert firms._firm_energy_anchor_total[1] == pytest.approx(4.0)


def test_increment_without_energy_indices_is_a_no_op():
    firms = _fake_firms()
    before = firms.base_intermediate_inputs_productivity_matrix.copy()
    Firms.anchor_energy_quantities(firms, {}, increments={(0, 1): 0.4}, max_step=10.0)
    assert np.array_equal(firms.base_intermediate_inputs_productivity_matrix, before)


def test_increment_wins_over_an_index_for_the_same_pair():
    # The index is exactly what the caller's guard rejected, so it must not also apply.
    firms = _fake_firms()
    Firms.anchor_energy_quantities(
        firms,
        {(0, 1): 50.0},
        increments={(0, 1): 0.4},
        energy_indices=[1, 2],
        max_step=10.0,
    )
    assert firms._firm_quantity_multiplier[(0, 1)] == pytest.approx(5.0)


def test_negative_increment_walks_down_by_the_step_bound():
    firms = _fake_firms()
    # -1.0 of a 10.0 total would take the pair well below zero; the coefficient must stay
    # positive and simply move down by the bound.
    Firms.anchor_energy_quantities(
        firms, {}, increments={(0, 1): -1.0}, energy_indices=[1, 2], max_step=2.0
    )
    assert firms._firm_quantity_multiplier[(0, 1)] == pytest.approx(0.5)
    assert firms.base_intermediate_inputs_productivity_matrix[1, 0] > 0.0


# --- conserve_total: the composition-mismatch fix -------------------------------
# Two buying industries (0 and 2) both purchasing good 1, so a per-good total exists.
def _two_buyer_firms(bought=((0.0, 1.0, 0.0), (0.0, 3.0, 0.0))):
    n = 3
    return types.SimpleNamespace(
        states={
            "Industry": np.array([0, 2]),
            "intermediate_tech_multipliers": np.ones((2, n)),
        },
        ts=types.SimpleNamespace(current=lambda key: np.asarray(bought, dtype=float)),
        base_intermediate_inputs_productivity_matrix=np.full((n, n), 4.0),
    )


def test_conserve_total_holds_the_anchored_total_to_the_source_rate():
    # Anchors 1.0 and 3.0 (total 4.0).  Raw indices 8.0 and 1.0 would give a desired
    # total of 8 + 3 = 11 (2.75x) -- the runaway.  The source says the total grows 2.0x,
    # so the pairs must be rescaled to sum to 8.0 while keeping their 8:1 ratio.
    firms = _two_buyer_firms()
    Firms.anchor_energy_quantities(
        firms, {(0, 1): 8.0, (2, 1): 1.0}, max_step=100.0, conserve_total={1: 2.0}
    )
    scale = 8.0 / 11.0
    assert firms._firm_quantity_multiplier[(0, 1)] == pytest.approx(8.0 * scale)
    # Composition preserved: the ratio between the two pairs' desired levels is unchanged.
    got = (firms._firm_quantity_multiplier[(0, 1)] * 1.0,
           firms._firm_quantity_multiplier[(2, 1)] * 3.0)
    assert got[0] / got[1] == pytest.approx(8.0 / 3.0)
    assert sum(got) == pytest.approx(4.0 * 2.0)


def test_conserve_total_absent_is_bit_identical():
    a, b = _two_buyer_firms(), _two_buyer_firms()
    Firms.anchor_energy_quantities(a, {(0, 1): 8.0, (2, 1): 1.0}, max_step=100.0)
    Firms.anchor_energy_quantities(b, {(0, 1): 8.0, (2, 1): 1.0}, max_step=100.0,
                                   conserve_total=None)
    assert np.array_equal(a.base_intermediate_inputs_productivity_matrix,
                          b.base_intermediate_inputs_productivity_matrix)
    assert a._firm_quantity_multiplier == b._firm_quantity_multiplier


def test_conserve_total_leaves_increment_pairs_fixed():
    # The increment's denominator is industry 0's OWN anchor energy (1.0), so that pair
    # desires 1.0 + 0.4*1.0 = 1.4 and must not move.  The index pair absorbs the whole
    # rescale: target total 4.0*2.0 = 8.0, less the 1.4 increment, leaves 6.6.
    firms = _two_buyer_firms()
    Firms.anchor_energy_quantities(
        firms, {(2, 1): 1.0}, increments={(0, 1): 0.4}, energy_indices=[1],
        max_step=100.0, conserve_total={1: 2.0},
    )
    assert firms._firm_quantity_multiplier[(0, 1)] * 1.0 == pytest.approx(1.4)
    assert firms._firm_quantity_multiplier[(2, 1)] * 3.0 == pytest.approx(6.6)


def test_conserve_total_ignores_a_good_whose_increments_exceed_the_target():
    # Increments alone want 1.0 + 8.0*1.0 = 9.0 against a target total of 8.0: the index
    # pair cannot be driven negative, so the good is left unscaled.
    firms = _two_buyer_firms()
    Firms.anchor_energy_quantities(
        firms, {(2, 1): 1.0}, increments={(0, 1): 8.0}, energy_indices=[1],
        max_step=100.0, conserve_total={1: 2.0},
    )
    assert firms._firm_quantity_multiplier[(2, 1)] == pytest.approx(1.0)


def test_conserve_total_ignores_non_positive_or_unknown_goods():
    firms = _two_buyer_firms()
    Firms.anchor_energy_quantities(
        firms, {(0, 1): 2.0}, max_step=100.0, conserve_total={1: 0.0, 2: 5.0},
    )
    assert firms._firm_quantity_multiplier[(0, 1)] == pytest.approx(2.0)
