"""Unit tests for the intensity-target CIMS linkage in ``Firms.link``.

These exercise the pure index helpers and the milestone-setting logic of
``Firms._link_intensity_target`` without constructing a full ``Firms`` agent:
the method only touches a handful of duck-typed attributes, so a light fake
gives faithful coverage of the baseline capture, index math, and multiplier
reset.
"""

from __future__ import annotations

import types

import numpy as np
import pandas as pd
import pytest

from macromodel.agents.firms.firms import (
    Firms,
    _intensity_target_productivity,
    _weighted_effective_coefficient,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_intensity_target_productivity_inverse_of_intensity():
    # Intensity doubles -> productivity halves (energy per output doubles).
    assert _intensity_target_productivity(3.0, anchor_intensity=1.0, current_intensity=2.0) == pytest.approx(1.5)
    # Intensity unchanged -> productivity unchanged (anchor call).
    assert _intensity_target_productivity(3.0, 1.0, 1.0) == pytest.approx(3.0)
    # Intensity falls -> productivity rises.
    assert _intensity_target_productivity(3.0, 2.0, 1.0) == pytest.approx(6.0)


@pytest.mark.parametrize(
    "baseline,anchor,current",
    [(0.0, 1.0, 1.0), (3.0, 0.0, 1.0), (3.0, 1.0, 0.0), (np.nan, 1.0, 1.0), (3.0, np.inf, 1.0)],
)
def test_intensity_target_productivity_guards(baseline, anchor, current):
    assert _intensity_target_productivity(baseline, anchor, current) is None


def test_weighted_effective_coefficient_production_weighted():
    multipliers = np.array([[1.0, 2.0], [1.0, 4.0]])  # 2 firms, input j=1 mults 2 and 4
    firms_idx = np.array([0, 1])
    production = np.array([3.0, 1.0])  # weight firm0 heavier
    # base=2.0; weighted mean multiplier = (3*2 + 1*4)/4 = 2.5 -> 5.0
    eff = _weighted_effective_coefficient(2.0, multipliers, firms_idx, input_j=1, production=production)
    assert eff == pytest.approx(5.0)


def test_weighted_effective_coefficient_zero_production_falls_back_to_mean():
    multipliers = np.array([[1.0, 2.0], [1.0, 4.0]])
    eff = _weighted_effective_coefficient(
        2.0, multipliers, np.array([0, 1]), input_j=1, production=np.array([0.0, 0.0])
    )
    assert eff == pytest.approx(2.0 * 3.0)  # mean multiplier 3.0


def test_weighted_effective_coefficient_no_firms_returns_none():
    assert _weighted_effective_coefficient(2.0, None, np.array([], dtype=int), 0, np.array([])) is None


# ---------------------------------------------------------------------------
# _link_intensity_target milestone behaviour (light fake Firms)
# ---------------------------------------------------------------------------

def _fake_firms(industries, industry_of_firm, production, base_interm, interm_mult):
    return types.SimpleNamespace(
        industries=list(industries),
        states={
            "Industry": np.asarray(industry_of_firm),
            "intermediate_tech_multipliers": np.asarray(interm_mult, dtype=float),
        },
        ts=types.SimpleNamespace(current=lambda key: np.asarray(production, dtype=float)),
        base_intermediate_inputs_productivity_matrix=np.asarray(base_interm, dtype=float),
        base_capital_inputs_productivity_matrix=np.zeros_like(np.asarray(base_interm, dtype=float)),
    )


def _intensity_df(value):
    # Producing sector C20 uses energy good D.
    df = pd.DataFrame(0.0, index=["C20", "D"], columns=["C20", "D"])
    df.loc["C20", "D"] = value
    return df


def test_link_intensity_target_anchor_captures_baseline_and_preserves_effective():
    # industries: C20 (idx 0, comparable), D (idx 1, energy). 2 firms: one C20, one D.
    industries = ["C20", "D"]
    base_interm = [[0.0, 0.0], [2.0, 0.0]]  # base[input=D=1, producing=C20=0] = 2.0
    interm_mult = [[1.0, 1.5], [1.0, 1.0]]  # firm0 (C20) multiplier on input D = 1.5
    firms = _fake_firms(industries, [0, 1], [10.0, 5.0], base_interm, interm_mult)

    anchor = _intensity_df(4.0)
    Firms._link_intensity_target(
        firms,
        comparable_codes=["C20"],
        energy_bundle_codes=["D"],
        energy_intensity=anchor,  # current == anchor at the anchor year
        anchor_energy_intensity=anchor,
        capital_intensity=None,
        anchor_capital_intensity=None,
        is_anchor=True,
        reset_multipliers=True,
    )

    # Baseline effective = base(2.0) * multiplier(1.5) = 3.0; effective stays 3.0.
    assert firms._link_intermediate_baseline[("C20", "D")] == pytest.approx(3.0)
    assert firms.base_intermediate_inputs_productivity_matrix[1, 0] == pytest.approx(3.0)
    # Multiplier for the C20 firm's energy input reset to 1.
    assert firms.states["intermediate_tech_multipliers"][0, 1] == pytest.approx(1.0)


def test_link_intensity_target_milestone_sets_energy_per_output():
    industries = ["C20", "D"]
    base_interm = [[0.0, 0.0], [2.0, 0.0]]
    interm_mult = [[1.0, 1.5], [1.0, 1.0]]
    firms = _fake_firms(industries, [0, 1], [10.0, 5.0], base_interm, interm_mult)

    anchor = _intensity_df(4.0)
    # Anchor first to capture baseline (effective 3.0).
    Firms._link_intensity_target(
        firms, comparable_codes=["C20"], energy_bundle_codes=["D"],
        energy_intensity=anchor, anchor_energy_intensity=anchor,
        capital_intensity=None, anchor_capital_intensity=None,
        is_anchor=True, reset_multipliers=True,
    )
    # Later milestone: CIMS energy intensity doubles (8.0 vs anchor 4.0).
    Firms._link_intensity_target(
        firms, comparable_codes=["C20"], energy_bundle_codes=["D"],
        energy_intensity=_intensity_df(8.0), anchor_energy_intensity=anchor,
        capital_intensity=None, anchor_capital_intensity=None,
        is_anchor=False, reset_multipliers=True,
    )
    # productivity = baseline(3.0) * anchor/current (4/8) = 1.5 -> energy per output doubles.
    assert firms.base_intermediate_inputs_productivity_matrix[1, 0] == pytest.approx(1.5)


def test_link_intensity_target_skips_when_no_anchor_intensity():
    industries = ["C20", "D"]
    base_interm = [[0.0, 0.0], [2.0, 0.0]]
    firms = _fake_firms(industries, [0, 1], [10.0, 5.0], base_interm, [[1.0, 1.0], [1.0, 1.0]])
    before = firms.base_intermediate_inputs_productivity_matrix.copy()
    # anchor_energy_intensity None -> intermediate channel skipped entirely.
    Firms._link_intensity_target(
        firms, comparable_codes=["C20"], energy_bundle_codes=["D"],
        energy_intensity=_intensity_df(8.0), anchor_energy_intensity=None,
        capital_intensity=None, anchor_capital_intensity=None,
        is_anchor=False, reset_multipliers=True,
    )
    assert np.array_equal(firms.base_intermediate_inputs_productivity_matrix, before)
