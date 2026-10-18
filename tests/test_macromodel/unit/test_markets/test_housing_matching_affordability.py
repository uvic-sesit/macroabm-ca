"""Unit tests for the automatic housing matcher's respect for the stated maximum.

The cost is the distance between the household's maximum and the listed price, so a
listing above the maximum is as close as one the same distance below it.
"""

import numpy as np
import pandas as pd
import pytest

from macromodel.markets.housing_market.func.clearing import AutomaticHousingMarketClearer

TENURE = np.zeros(2)


def _housing_data(prices):
    n = len(prices)

    return pd.DataFrame(
        {
            "Up for Rent": [True] * n,
            "Rent": list(prices),
            "Temporarily for Sale": [False] * n,
            "Sale Price": list(prices),
            "Value": [price * 10 for price in prices],
            "Corresponding Owner Household ID": list(range(n)),
        }
    )


def _match(prices, max_willing_to_pay):
    clearer = AutomaticHousingMarketClearer(random_assignment_shock_variance=0.0)

    return clearer.perform_matching(
        housing_data=_housing_data(prices),
        household_main_residence_tenure_status=TENURE,
        max_willing_to_pay=np.array(max_willing_to_pay),
        is_rental_market=True,
    )


class TestMatchingRespectsTheStatedMaximum:
    def test_no_match_costs_more_than_the_buyer_stated(self):
        # Two households at 20 and 60 against listings at 10 and 100. The cheapest total
        # distance pairs the second household with the listing it cannot afford.
        maxima = [20.0, 60.0]

        matches = _match([10.0, 100.0], maxima)

        assert (matches["price_or_rent"].values <= np.array(maxima)[matches["buyer_id"].values]).all()

    def test_the_affordable_match_is_still_made(self):
        matches = _match([10.0, 100.0], [20.0, 60.0])

        assert list(matches["price_or_rent"].values) == [10.0]

    def test_every_affordable_listing_is_matched_when_all_are_affordable(self):
        maxima = [60.0, 120.0]

        matches = _match([10.0, 100.0], maxima)
        all_affordable = _match([10.0, 50.0], maxima)

        assert len(all_affordable) == 2
        assert (all_affordable["price_or_rent"].values <= np.array(maxima)[all_affordable["buyer_id"].values]).all()
        assert len(matches) == 2  # both are affordable at these maxima too


@pytest.mark.parametrize("prices", [[10.0, 100.0], [100.0, 200.0], [5.0, 5.0]])
def test_a_household_is_never_assigned_above_its_maximum(prices):
    maxima = [20.0, 60.0]

    matches = _match(prices, maxima)

    assert (matches["price_or_rent"].values <= np.array(maxima)[matches["buyer_id"].values]).all()
