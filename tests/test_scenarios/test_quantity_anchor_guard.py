"""Unit tests for the quantity-anchor negligible-base guard in ``run_cims_linkage``.

The guard decides, per (row, fuel) pair, whether the external demand path is applied as a
growth INDEX or as a level INCREMENT.  It is pure, so it is tested directly rather than
through a simulation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scenarios.run_cims_linkage import _quantity_anchor_spec, _row_energy_total


ENERGY_CODES = ["D", "B05a", "C19"]
INDUSTRIES = ["C20", "D", "B05a", "C19"]


# ---------------------------------------------------------------------------
# _quantity_anchor_spec
# ---------------------------------------------------------------------------

def test_floor_zero_reproduces_the_index_exactly():
    # The production default. Nothing is below a floor of zero, so every pair that used
    # to form a ratio still forms the same ratio -- bit for bit, not merely closely.
    assert _quantity_anchor_spec(4.0, 7.0, 100.0, 0.0) == ("index", 7.0 / 4.0)
    # Including the pathological one the guard exists to catch, when it is not enabled.
    assert _quantity_anchor_spec(0.001, 1.8, 100.0, 0.0) == ("index", 1800.0)


def test_floor_zero_still_drops_a_zero_base():
    # An index cannot be formed at all without a base, and with the guard off there is
    # nothing else to apply.
    assert _quantity_anchor_spec(0.0, 5.0, 100.0, 0.0) is None


def test_negligible_base_becomes_a_level_increment():
    # 0.05 is 0.05% of the row's 100.0 energy total, below a 0.1% floor: the 1800x index
    # this would produce is refused and CER's level change carried instead.
    kind, value = _quantity_anchor_spec(0.05, 90.0, 100.0, 0.001)
    assert kind == "increment"
    assert value == pytest.approx((90.0 - 0.05) / 100.0)


def test_zero_base_is_well_defined_under_the_guard():
    # The case an index cannot express at all: nothing in the anchor year, real by the
    # target year.  This is the demand the "just skip it" option would silently drop.
    assert _quantity_anchor_spec(0.0, 25.0, 100.0, 0.001) == ("increment", 0.25)


def test_a_material_base_keeps_its_index():
    # 5.0 is 5% of the total, well clear of the floor, so the pair is untouched by the
    # guard -- the guard must not quietly convert the pairs that were working.
    assert _quantity_anchor_spec(5.0, 10.0, 100.0, 0.001) == ("index", 2.0)


def test_pair_negligible_at_both_ends_carries_nothing():
    assert _quantity_anchor_spec(0.0, 0.0, 100.0, 0.001) is None
    assert _quantity_anchor_spec(1e-12, 1e-12, 100.0, 0.001) is None


def test_a_fuel_that_dies_out_gives_a_negative_increment():
    kind, value = _quantity_anchor_spec(0.05, 0.0, 100.0, 0.001)
    assert kind == "increment"
    assert value < 0.0


@pytest.mark.parametrize("now,base", [(np.nan, 1.0), (1.0, np.nan), (np.inf, 1.0)])
def test_non_finite_inputs_carry_nothing(now, base):
    assert _quantity_anchor_spec(base, now, 100.0, 0.001) is None


def test_an_empty_row_total_falls_back_to_the_index():
    # Without a denominator the guard cannot say "negligible for this industry", so it
    # must not claim to: the pair keeps whatever the index path makes of it.
    assert _quantity_anchor_spec(0.001, 1.8, 0.0, 0.001) == ("index", 1800.0)
    assert _quantity_anchor_spec(0.0, 1.8, 0.0, 0.001) is None


# ---------------------------------------------------------------------------
# _row_energy_total
# ---------------------------------------------------------------------------

def _rq(values: dict[str, float]) -> pd.DataFrame:
    df = pd.DataFrame(0.0, index=INDUSTRIES, columns=INDUSTRIES)
    for code, v in values.items():
        df.loc["C20", code] = v
    return df


def test_row_energy_total_sums_the_energy_columns():
    df = _rq({"D": 2.0, "B05a": 3.0, "C19": 5.0})
    # The non-energy column C20 is not part of the total.
    df.loc["C20", "C20"] = 99.0
    assert _row_energy_total(df, "C20", ENERGY_CODES, INDUSTRIES) == pytest.approx(10.0)


def test_row_energy_total_excludes_the_self_input():
    df = pd.DataFrame(0.0, index=INDUSTRIES, columns=INDUSTRIES)
    df.loc["D", "D"] = 50.0
    df.loc["D", "B05a"] = 4.0
    # Electricity's own consumption of electricity is not anchored, so it must not sit in
    # the denominator either.
    assert _row_energy_total(df, "D", ENERGY_CODES, INDUSTRIES) == pytest.approx(4.0)


def test_row_energy_total_ignores_fuels_the_model_has_no_industry_for():
    df = _rq({"D": 2.0, "B05a": 3.0, "C19": 5.0})
    assert _row_energy_total(df, "C20", ENERGY_CODES, ["C20", "D"]) == pytest.approx(2.0)


def test_row_energy_total_of_an_absent_row_is_zero():
    df = _rq({"D": 2.0})
    assert _row_energy_total(df, "ZZZ", ENERGY_CODES, INDUSTRIES + ["ZZZ"]) == 0.0
