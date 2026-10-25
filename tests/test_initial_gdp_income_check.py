import pytest
from macromodel.economy.economy_ts import validate_initial_gdp


def test_income_check_is_independent_of_expenditure():
    validate_initial_gdp(100., 100., 100.)
    with pytest.raises(AssertionError, match='output/income'):
        validate_initial_gdp(100., 100., 110.)


def test_expenditure_check_keeps_existing_tolerance():
    validate_initial_gdp(100., 100.0001, 100.)
    with pytest.raises(AssertionError, match='output/expenditure'):
        validate_initial_gdp(100., 110., 100.)
