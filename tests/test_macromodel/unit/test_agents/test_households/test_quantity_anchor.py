"""Unit tests for ``Households.anchor_energy_quantities``.

The household counterpart of the firm quantity anchor, including the additive increment
path the negligible-base guard routes fuels onto.  A light fake covers it: the method
reads one time series and rewrites the consumption weights.
"""

from __future__ import annotations

import types

import numpy as np
import pytest

from macromodel.agents.households.households import Households


# goods: 0 non-energy, 1 electricity, 2 gas.  At a price of 2.0 the nominal spends below
# are real quantities 1.0 of electricity and 9.0 of gas -> energy total 10.0.
def _fake_households(nominal=(0.0, 2.0, 18.0)):
    return types.SimpleNamespace(
        ts=types.SimpleNamespace(current=lambda key: np.asarray(nominal, dtype=float)),
        consumption_weights=np.array([0.5, 0.2, 0.3]),
        consumption_weights_by_income=np.ones((2, 3)),
    )


PRICES = {1: 2.0, 2: 2.0}
ENERGY = [1, 2]


def test_index_path_scales_the_weight():
    hh = _fake_households()
    Households.anchor_energy_quantities(hh, {1: 2.0}, PRICES, 10.0)
    assert hh._energy_quantity_multiplier[1] == pytest.approx(2.0)
    assert hh.consumption_weights[1] == pytest.approx(0.4)


def test_increment_is_a_share_of_total_residential_energy():
    hh = _fake_households()
    # +0.4 of the 10.0 anchor-year energy total -> desired 1.0 + 4.0 = 5.0 against a
    # realised 1.0.
    Households.anchor_energy_quantities(hh, {}, PRICES, 10.0, increments={1: 0.4}, energy_indices=ENERGY)
    assert hh._energy_quantity_anchor_total == pytest.approx(10.0)
    assert hh._energy_quantity_multiplier[1] == pytest.approx(5.0)
    assert hh.consumption_weights[1] == pytest.approx(1.0)
    assert hh.consumption_weights_by_income[0, 1] == pytest.approx(5.0)


def test_energy_total_spans_indexed_and_incremented_fuels_alike():
    # The denominator is the row's TOTAL energy, so a fuel anchored by an index still
    # counts towards the total an increment is measured against.
    hh = _fake_households()
    Households.anchor_energy_quantities(hh, {2: 1.0}, PRICES, 10.0, increments={1: 0.4}, energy_indices=ENERGY)
    assert hh._energy_quantity_anchor_total == pytest.approx(10.0)
    assert hh._energy_quantity_multiplier[1] == pytest.approx(5.0)
    # An index of 1.0 is a no-op by construction.
    assert hh.consumption_weights[2] == pytest.approx(0.3)


def test_increment_wins_over_an_index_for_the_same_fuel():
    hh = _fake_households()
    Households.anchor_energy_quantities(hh, {1: 50.0}, PRICES, 10.0, increments={1: 0.4}, energy_indices=ENERGY)
    assert hh._energy_quantity_multiplier[1] == pytest.approx(5.0)


def test_negative_increment_walks_down_by_the_step_bound():
    hh = _fake_households()
    Households.anchor_energy_quantities(hh, {}, PRICES, 2.0, increments={1: -1.0}, energy_indices=ENERGY)
    assert hh._energy_quantity_multiplier[1] == pytest.approx(0.5)
    assert hh.consumption_weights[1] > 0.0


def test_no_targets_and_no_increments_is_a_no_op():
    hh = _fake_households()
    before = hh.consumption_weights.copy()
    Households.anchor_energy_quantities(hh, {}, PRICES, 2.0)
    assert np.array_equal(hh.consumption_weights, before)
