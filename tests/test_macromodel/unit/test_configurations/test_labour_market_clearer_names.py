"""Unit tests for the labour market clearers the configuration accepts.

DefaultLabourMarketClearer reads firms.states["offered_wage_function"], which is written
only by an assignment that is quoted out in Country, so selecting it fails inside the
first step rather than at validation.
"""

import importlib

import pytest
from pydantic import ValidationError

from macromodel.configurations.labour_market_configuration import Clearing

LOC = "macromodel.markets.labour_market"


def test_the_unrunnable_clearer_is_rejected():
    with pytest.raises(ValidationError):
        Clearing(name="DefaultLabourMarketClearer")


@pytest.mark.parametrize("name", ["NoLabourMarketClearer", "PolednaLabourMarketClearer"])
def test_an_accepted_clearer_is_defined_by_its_module(name):
    clearing = Clearing(name=name)
    module = importlib.import_module(f"{LOC}.func.{clearing.path_name}")

    assert hasattr(module, clearing.name)


def test_the_default_is_still_poledna():
    assert Clearing().name == "PolednaLabourMarketClearer"
