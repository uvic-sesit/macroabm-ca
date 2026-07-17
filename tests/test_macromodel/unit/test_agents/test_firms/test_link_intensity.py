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


# ---------------------------------------------------------------------------
# Energy-bundle substitution config (increment 2)
# ---------------------------------------------------------------------------

def test_firms_bundle_enables_bundled_leontief():
    """Passing a substitution bundle switches production/target setters to bundled variants."""
    from macromodel.configurations.firms_configuration import FirmsConfiguration

    cfg = FirmsConfiguration.n_industries_default(n_industries=6, bundles=[[1, 4]])
    assert cfg.functions.production.name == "BundledLeontief"
    assert cfg.functions.target_intermediate_inputs.name == "BundleWeightedTargetIntermediateInputsSetter"
    assert cfg.functions.target_capital_inputs.name == "BundleWeightedTargetCapitalInputsSetter"
    # Bundled industries 1 and 4 share a bundle id; the other four are singletons.
    b = cfg.substitution_bundles
    assert b[1] == b[4]
    assert len({b[0], b[1], b[2], b[3], b[5]}) == 5


def test_no_bundle_keeps_pure_leontief():
    from macromodel.configurations.firms_configuration import FirmsConfiguration

    cfg = FirmsConfiguration.n_industries_default(n_industries=6)
    assert cfg.functions.production.name == "PureLeontief"


def test_bundle_aggregate_matches_matmul_for_finite_and_is_nan_safe():
    """_bundle_aggregate == matmul for finite inputs, and avoids inf*0=NaN."""
    from macromodel.agents.firms.func.production import _bundle_aggregate

    # 3 goods, 2 bundles: goods 0&1 share a bundle (weight 0.5), good 2 singleton.
    bundle_matrix = np.array([[0.5, 0.0], [0.5, 0.0], [0.0, 1.0]])

    finite = np.array([[2.0, 4.0, 7.0], [1.0, 3.0, 9.0]])
    np.testing.assert_allclose(
        _bundle_aggregate(finite, bundle_matrix), finite @ bundle_matrix
    )

    # An out-of-bundle inf (good 2 for bundle 0) must NOT poison bundle 0.
    with_inf = np.array([[2.0, 4.0, np.inf]])
    out = _bundle_aggregate(with_inf, bundle_matrix)
    assert not np.isnan(out).any()
    assert out[0, 0] == pytest.approx(3.0)  # mean of goods 0,1
    assert np.isinf(out[0, 1])  # singleton bundle of the inf good stays inf


def _fake_firms_growth_limit(industry_of_firm, prod_history):
    return types.SimpleNamespace(
        states={"Industry": np.asarray(industry_of_firm)},
        ts=types.SimpleNamespace(historic=lambda key: prod_history),
    )


def test_growth_limit_caps_upside_and_downside_for_listed_sectors():
    # firm0 -> industry 0 (capped), firm1 -> industry 1 (not capped). ref = 4 steps ago.
    hist = [np.array([10.0, 20.0])] * 4
    f = _fake_firms_growth_limit([0, 1], hist)
    Firms.set_growth_limits(f, industry_indices=[0], max_growth_per_year=0.05, max_decline_per_year=0.05, steps_per_year=4)

    # Both firms want to double: capped firm0 pinned to +5% band; firm1 untouched.
    out = Firms._apply_growth_limits(f, np.array([20.0, 40.0]))
    assert out[0] == pytest.approx(10.5)   # min(20, 10*1.05)
    assert out[1] == pytest.approx(40.0)   # uncapped sector unchanged

    # Both firms want to collapse: capped firm0 floored to -5% band; firm1 untouched.
    out = Firms._apply_growth_limits(f, np.array([2.0, 5.0]))
    assert out[0] == pytest.approx(9.5)    # max(2, 10*0.95)
    assert out[1] == pytest.approx(5.0)


def test_growth_limit_skips_without_enough_history_or_zero_reference():
    # Not enough history (need >= steps_per_year) -> unchanged.
    f = _fake_firms_growth_limit([0], [np.array([10.0])] * 3)
    Firms.set_growth_limits(f, [0], 0.05, 0.05, 4)
    assert Firms._apply_growth_limits(f, np.array([99.0]))[0] == pytest.approx(99.0)

    # Zero reference (idle firm) -> not clamped, free to start up.
    f = _fake_firms_growth_limit([0], [np.array([0.0])] * 4)
    Firms.set_growth_limits(f, [0], 0.05, 0.05, 4)
    assert Firms._apply_growth_limits(f, np.array([99.0]))[0] == pytest.approx(99.0)


def test_growth_limit_noop_when_unset():
    f = _fake_firms_growth_limit([0], [np.array([10.0])] * 4)
    # No set_growth_limits call -> getattr defaults -> passthrough.
    assert Firms._apply_growth_limits(f, np.array([99.0]))[0] == pytest.approx(99.0)


def test_industry_timeseries_dataframes_aggregates_by_industry():
    """Per-industry export sums quantity fields and production-weights price."""
    # 3 firms: two in industry 0 ("A"), one in industry 1 ("B"). 2 timesteps.
    industries = ["A", "B"]
    industry_of_firm = np.array([0, 0, 1])
    history = {
        "production": [np.array([2.0, 3.0, 5.0]), np.array([4.0, 4.0, 10.0])],
        "estimated_demand": [np.array([1.0, 1.0, 1.0]), np.array([2.0, 2.0, 2.0])],
        "real_amount_sold": [np.array([1.0, 1.0, 1.0]), np.array([2.0, 2.0, 2.0])],
        "inventory": [np.array([0.0, 0.0, 0.0]), np.array([1.0, 1.0, 1.0])],
        "limiting_intermediate_inputs": [np.array([9.0, 9.0, 9.0]), np.array([9.0, 9.0, 9.0])],
        "price": [np.array([10.0, 20.0, 7.0]), np.array([10.0, 10.0, 5.0])],
    }
    f = types.SimpleNamespace(
        industries=industries,
        states={"Industry": industry_of_firm},
        ts=types.SimpleNamespace(historic=lambda key: history[key]),
    )
    frames = Firms.industry_timeseries_dataframes(f)

    # Extensive field summed within industry A (firms 0+1) at t=0: 2+3 = 5.
    assert frames["production"].loc[0, "A"] == pytest.approx(5.0)
    assert frames["production"].loc[0, "B"] == pytest.approx(5.0)   # single firm
    assert frames["production"].loc[1, "A"] == pytest.approx(8.0)   # 4+4
    # Price is production-weighted within A at t=0: (2*10 + 3*20)/(2+3) = 16.
    assert frames["price"].loc[0, "A"] == pytest.approx(16.0)
    assert frames["price"].loc[0, "B"] == pytest.approx(7.0)
    assert list(frames["inventory"].columns) == industries


def test_technical_growth_inf_coefficients_no_nan_warning():
    """Unused inputs carry inf productivity; growth must be finite with no 0*inf warning."""
    import warnings

    from macromodel.agents.firms.func.technical_coefficients_growth import SimpleTechnicalGrowth

    g = SimpleTechnicalGrowth()
    base = np.array([[1.0, np.inf], [np.inf, 1.0]])  # inf = unused input
    kwargs = dict(
        current_multipliers=np.ones((2, 2)),
        cumulative_improvements=np.zeros((2, 2)),
        base_coefficients=base,
        firm_industries=np.array([0, 1]),
        technical_investment=np.array([[1.0, 1.0], [1.0, 1.0]]),
        production=np.array([0.0, 5.0]),  # idle firm triggers 0*inf without the guard
        prices=np.array([1.0, 1.0]),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)  # any 0*inf warning fails the test
        gi = g.compute_intermediate_multiplier_growth(**kwargs)
        gc = g.compute_capital_multiplier_growth(**kwargs)
    assert np.all(np.isfinite(gi)) and np.all(np.isfinite(gc))
