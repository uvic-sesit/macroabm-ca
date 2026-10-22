"""Unit tests for ``Firms.anchor_energy_intensity`` and the programme recipe blend.

Light fakes, as in ``test_quantity_anchor``: the methods read two time series and
rewrite the base productivity matrix.
"""

from __future__ import annotations

import types

import numpy as np
import pytest

from macromodel.agents.firms.firms import Firms


# industries: C20 (0, buyer), D (1, electricity), B05 (2, gas).
# One firm in industry 0 producing 10.0 and buying 1.0 of D and 9.0 of B05:
# energy per unit of output 1.0, electricity share 0.1, gas share 0.9.
def _fake_firms(bought=((0.0, 1.0, 9.0),), output=(10.0,)):
    n = 3
    series = {
        "real_amount_bought_as_intermediate_inputs": np.asarray(bought, dtype=float),
        "production": np.asarray(output, dtype=float),
    }
    return types.SimpleNamespace(
        states={"Industry": np.array([0]), "intermediate_tech_multipliers": np.ones((1, n))},
        ts=types.SimpleNamespace(current=lambda key: series[key]),
        base_intermediate_inputs_productivity_matrix=np.full((n, n), 4.0),
    )


def _mult(firms, i, k):
    return firms._firm_intensity_multiplier[(i, k)]


def test_fuel_mix_shift_moves_shares_at_constant_energy_per_output():
    firms = _fake_firms()
    Firms.anchor_energy_intensity(firms, {(0, 1): 0.1, (0, 2): -0.1}, [1, 2], max_step=10.0)
    # Electricity 0.1 -> 0.2 of 10.0: target 2.0 vs 1.0 bought; gas 8.0 vs 9.0.
    assert _mult(firms, 0, 1) == pytest.approx(2.0)
    assert _mult(firms, 0, 2) == pytest.approx(8.0 / 9.0)
    assert firms.base_intermediate_inputs_productivity_matrix[1, 0] == pytest.approx(2.0)


def test_target_follows_output_not_a_fixed_quantity():
    firms = _fake_firms()
    Firms.anchor_energy_intensity(firms, {(0, 1): 0.0}, [1, 2], max_step=10.0)
    assert _mult(firms, 0, 1) == pytest.approx(1.0)
    # Output halves, purchases with it: still on target, no coefficient change.
    firms.ts = _fake_firms(bought=((0.0, 0.5, 4.5),), output=(5.0,)).ts
    Firms.anchor_energy_intensity(firms, {(0, 1): 0.0}, [1, 2], max_step=10.0)
    assert _mult(firms, 0, 1) == pytest.approx(1.0)


def test_energy_index_scales_energy_per_unit_of_output():
    firms = _fake_firms()
    Firms.anchor_energy_intensity(firms, {(0, 1): 0.0, (0, 2): 0.0}, [1, 2], max_step=10.0,
                                  energy_index={0: 0.5})
    assert _mult(firms, 0, 1) == pytest.approx(0.5)
    assert _mult(firms, 0, 2) == pytest.approx(0.5)


def test_pair_ratio_zero_walks_down_and_mix_keeps_the_rest_of_the_bundle():
    firms = _fake_firms()
    Firms.anchor_energy_intensity(firms, {(0, 1): 0.0}, [1, 2], max_step=2.0,
                                  pair_ratio={(0, 2): 0.0})
    assert _mult(firms, 0, 2) == pytest.approx(0.5)  # 1 / max_step
    # Electricity keeps its own 0.1 of the anchor bundle (no share of the gas freed).
    assert _mult(firms, 0, 1) == pytest.approx(1.0)


def test_excluded_pair_is_left_out_of_the_bundle():
    firms = _fake_firms()
    Firms.anchor_energy_intensity(firms, {(0, 1): 0.0}, [1, 2], max_step=10.0,
                                  exclude_pairs={(0, 2)})
    assert (0, 2) not in firms._firm_intensity_multiplier
    e0, v0 = firms._intensity_anchor[0]
    assert e0 == pytest.approx(0.1) and v0 == {1: pytest.approx(1.0)}


def test_own_output_counts_only_when_included():
    firms = _fake_firms(bought=((2.0, 1.0, 9.0),))
    Firms.anchor_energy_intensity(firms, {(0, 1): 0.0}, [0, 1, 2], max_step=10.0)
    assert 0 not in firms._intensity_anchor[0][1]
    firms = _fake_firms(bought=((2.0, 1.0, 9.0),))
    Firms.anchor_energy_intensity(firms, {(0, 1): 0.0}, [0, 1, 2], max_step=10.0, include_self={0})
    assert firms._intensity_anchor[0][1][0] == pytest.approx(2.0 / 12.0)


def test_max_multiplier_caps_the_coefficient_change():
    firms = _fake_firms()
    summary = Firms.anchor_energy_intensity(firms, {(0, 1): 0.5, (0, 2): -0.5}, [1, 2],
                                            max_step=10.0, max_multiplier=3.0)
    assert _mult(firms, 0, 1) == pytest.approx(3.0)  # 6x asked
    assert summary["capped"] == 1


def test_recipe_blend_mixes_input_requirements_per_unit_of_output():
    firms = types.SimpleNamespace(_recipe_blend={0: (0.25, np.array([0.0, 1.0]))})
    productivity = np.array([[2.0, np.inf], [4.0, 4.0]])  # firm 0 needs 0.5 of good 0
    out = Firms._apply_recipe_blend(firms, productivity)
    # 0.75 * own + 0.25 * recipe: good 0 0.375, good 1 0.25 per unit of output.
    assert out[0] == pytest.approx([1.0 / 0.375, 4.0])
    assert np.array_equal(out[1], productivity[1])
