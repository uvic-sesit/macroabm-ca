"""Unit tests for the function names the configurations offer.

A name a configuration accepts is imported by `functions_from_model` at build time,
so an option naming a class its module does not define validates and then raises.
"""

import importlib

import pytest
from pydantic import ValidationError

from macromodel.configurations.firms_configuration import GrowthEstimator
from macromodel.configurations.individuals_configuration import LabourInputsFunction
from macromodel.configurations.row_configuration import Imports

# Removed because no module defines them; each raised AttributeError at build time.
RETIRED = [
    (GrowthEstimator, "ZeroGrowthEstimator"),
    (LabourInputsFunction, "ConstantIndividualsLabourInputsSetter"),
    (Imports, "DefaultRoWImportsSetter"),
]

# The surviving option of each, with the module its functions are built from.
LIVE = [
    (GrowthEstimator, "macromodel.agents.firms"),
    (LabourInputsFunction, "macromodel.agents.individuals"),
    (Imports, "macromodel.rest_of_the_world"),
]


@pytest.mark.parametrize("configuration_class,retired_name", RETIRED, ids=[name for _, name in RETIRED])
def test_a_name_no_module_defines_is_rejected(configuration_class, retired_name):
    with pytest.raises(ValidationError):
        configuration_class(name=retired_name)


@pytest.mark.parametrize("configuration_class,loc", LIVE, ids=[configuration.__name__ for configuration, _ in LIVE])
def test_the_remaining_name_is_defined_by_its_module(configuration_class, loc):
    configuration = configuration_class()
    module = importlib.import_module(f"{loc}.func.{configuration.path_name}")

    assert hasattr(module, configuration.name)
