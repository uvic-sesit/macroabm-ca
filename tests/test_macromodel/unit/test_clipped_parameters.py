"""Unit tests for the constructor parameters documented as lying in [0, 1].

Each of these is clipped into that range on construction, so an out-of-range
configuration value has to be stored clipped rather than raw.
"""

import importlib

import pytest

from macromodel.configurations import FirmsConfiguration, GoodsMarketConfiguration

FIRMS = "macromodel.agents.firms"
GOODS_MARKET = "macromodel.markets.goods_market"

# (configuration, module root, function key, parameter)
CASES = [
    (FirmsConfiguration, FIRMS, "demand_estimator", "firm_growth_adjustment_speed"),
    (FirmsConfiguration, FIRMS, "excess_demand", "consider_intermediate_inputs"),
    (FirmsConfiguration, FIRMS, "excess_demand", "consider_capital_inputs"),
    (FirmsConfiguration, FIRMS, "excess_demand", "consider_labour_inputs"),
    (FirmsConfiguration, FIRMS, "labour_productivity", "consider_intermediate_inputs"),
    (FirmsConfiguration, FIRMS, "labour_productivity", "consider_capital_inputs"),
    (FirmsConfiguration, FIRMS, "prices", "price_setting_speed_gf"),
    (FirmsConfiguration, FIRMS, "prices", "price_setting_speed_dp"),
    (FirmsConfiguration, FIRMS, "prices", "price_setting_speed_cp"),
    (FirmsConfiguration, FIRMS, "target_production", "intermediate_inputs_target_considers_labour_inputs"),
    (FirmsConfiguration, FIRMS, "target_production", "intermediate_inputs_target_considers_intermediate_inputs"),
    (FirmsConfiguration, FIRMS, "target_production", "intermediate_inputs_target_considers_capital_inputs"),
    (FirmsConfiguration, FIRMS, "target_production", "capital_inputs_target_considers_labour_inputs"),
    (FirmsConfiguration, FIRMS, "target_production", "capital_inputs_target_considers_intermediate_inputs"),
    (FirmsConfiguration, FIRMS, "target_production", "capital_inputs_target_considers_capital_inputs"),
    (GoodsMarketConfiguration, GOODS_MARKET, "clearing", "real_country_prioritisation"),
]

IDS = [f"{key}.{parameter}" for _, _, key, parameter in CASES]


def _build(configuration_class, loc, key, parameter, value):
    """Build the configured function with one parameter set out of range."""
    entry = getattr(configuration_class().functions, key)
    module = importlib.import_module(f"{loc}.func.{entry.path_name}")
    function_class = getattr(module, entry.name)

    return function_class(**{**entry.parameters, parameter: value})


@pytest.mark.parametrize("configuration_class,loc,key,parameter", CASES, ids=IDS)
def test_a_value_above_one_is_stored_clipped(configuration_class, loc, key, parameter):
    function = _build(configuration_class, loc, key, parameter, 1.5)

    assert getattr(function, parameter) == 1.0


@pytest.mark.parametrize("configuration_class,loc,key,parameter", CASES, ids=IDS)
def test_a_value_below_zero_is_stored_clipped(configuration_class, loc, key, parameter):
    function = _build(configuration_class, loc, key, parameter, -0.5)

    assert getattr(function, parameter) == 0.0
