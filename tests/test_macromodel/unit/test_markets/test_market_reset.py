"""Unit tests for the function reinstantiation each market performs on reset.

update_functions reinstantiates a function only when the configured class differs
from the installed one, and it resolves that class under the module path it is
given, so the path has to be the one the market's own construction uses.
"""

from types import SimpleNamespace

import pytest

from macromodel.configurations import (
    CreditMarketConfiguration,
    GoodsMarketConfiguration,
    HousingMarketConfiguration,
    LabourMarketConfiguration,
)
from macromodel.markets.credit_market.credit_market import CreditMarket
from macromodel.markets.goods_market.goods_market import GoodsMarket
from macromodel.markets.housing_market.housing_market import HousingMarket
from macromodel.markets.labour_market.labour_market import LabourMarket

MARKETS = [
    (GoodsMarket, GoodsMarketConfiguration),
    (CreditMarket, CreditMarketConfiguration),
    (HousingMarket, HousingMarketConfiguration),
    (LabourMarket, LabourMarketConfiguration),
]


class _Installed:
    """A previously installed function, of a class no configuration names."""


def _market(market_class, function_names: list[str]):
    """The market attributes reset() touches, and nothing else."""
    return SimpleNamespace(
        ts=SimpleNamespace(reset=lambda: None),
        initial_states={},
        states={},
        functions={name: _Installed() for name in function_names},
    )


@pytest.mark.parametrize("market_class,configuration_class", MARKETS, ids=lambda value: value.__name__)
def test_reset_installs_the_configured_functions(market_class, configuration_class):
    configuration = configuration_class()
    names = list(configuration.functions.__dict__)
    market = _market(market_class, names)

    market_class.reset(market, configuration)

    assert {name: type(function).__name__ for name, function in market.functions.items()} == {
        name: getattr(configuration.functions, name).name for name in names
    }
