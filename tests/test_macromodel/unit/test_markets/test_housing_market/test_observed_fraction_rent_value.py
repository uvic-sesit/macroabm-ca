"""Unit tests for the runtime rent/value refit.

The series is read everywhere as rent per value, so the fit takes the property
value as the independent variable and the rent as the dependent one.
"""

import numpy as np
import pandas as pd
import pytest

from macromodel.markets.housing_market.housing_market import HousingMarket

RENT_PER_VALUE = 0.005

# Four completed rentals on the ratio above, and one sale whose price is 0.978 of its
# value: a fit that admitted the sale row could not return the rental ratio.
CURRENT_SALES = pd.DataFrame(
    {
        "sales_types": ["Rental", "Rental", "Sell", "Rental", "Rental"],
        "property_value": [2.0e5, 3.0e5, 4.5e5, 4.0e5, 5.0e5],
        "price_or_rent": [1.0e3, 1.5e3, 4.4e5, 2.0e3, 2.5e3],
    }
)


class _TimeSeriesStub:
    """Stand-in for the market's time series, carrying what the refit touches."""

    def __init__(self):
        self.rent_value_histogram: list[np.ndarray] = []

    def current(self, series_name: str) -> np.ndarray:
        raise AssertionError(f"{series_name} was read instead of fitted, so no rental reached the fit")


def _market(current_sales: pd.DataFrame) -> HousingMarket:
    market = HousingMarket.__new__(HousingMarket)
    market.states = {"current_sales": current_sales}
    market.ts = _TimeSeriesStub()
    return market


class TestObservedFractionRentValue:
    def test_slope_is_rent_per_value(self):
        slope, intercept = _market(CURRENT_SALES.copy()).compute_observed_fraction_rent_value()

        assert slope == pytest.approx(RENT_PER_VALUE, rel=1e-6)
        assert intercept == pytest.approx(0.0, abs=1e-6)
