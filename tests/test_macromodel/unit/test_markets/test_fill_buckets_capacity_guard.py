"""Unit tests for the non-finite capacity guard the three fill_buckets share.

The guard's own comment names NaN capacities as the case it handles, and its branch
splits the fill evenly. Its predicate also has to leave ordinary finite input alone.
"""

import numpy as np
import pytest

from macromodel.configurations import CreditMarketConfiguration
from macromodel.markets.credit_market.func.clearing import WaterBucketCreditMarketClearer
from macromodel.markets.credit_market.func.lib_water_bucket import fill_buckets as credit_fill_buckets
from macromodel.markets.goods_market.func.lib_water_bucket import fill_buckets as goods_fill_buckets

FILL_AMOUNT = 150.0
# Fill bucket 2 first, then 0, then 1, as the docstring's example orders them.
PRIORITIES = np.array([2, 0, 1])


def _credit_clearer_fill_buckets(capacities, fill_amount, priorities, minimum_fill):
    clearer = WaterBucketCreditMarketClearer(**CreditMarketConfiguration().functions.clearing.parameters)

    return clearer.fill_buckets(capacities, fill_amount, priorities, minimum_fill)


IMPLEMENTATIONS = [goods_fill_buckets, credit_fill_buckets, _credit_clearer_fill_buckets]
IDS = ["goods_market", "credit_market", "credit_market_clearer"]


@pytest.mark.parametrize("fill_buckets", IMPLEMENTATIONS, ids=IDS)
@pytest.mark.parametrize("capacity", [np.nan, np.inf, -np.inf], ids=["nan", "inf", "-inf"])
def test_a_non_finite_capacity_takes_the_even_split(fill_buckets, capacity):
    allocation = fill_buckets(np.array([100.0, capacity, 75.0]), FILL_AMOUNT, PRIORITIES, 0.0)

    assert np.array_equal(allocation, np.full(3, FILL_AMOUNT / 3))


@pytest.mark.parametrize("fill_buckets", IMPLEMENTATIONS, ids=IDS)
def test_a_capacity_too_large_to_increment_is_still_finite(fill_buckets):
    """A sum of 3e17 is unchanged by adding one, which the guard must not read as non-finite."""
    allocation = fill_buckets(np.array([1e17, 1e17, 1e17]), FILL_AMOUNT, PRIORITIES, 0.0)

    assert allocation[2] == FILL_AMOUNT
    assert allocation.sum() == FILL_AMOUNT


@pytest.mark.parametrize("fill_buckets", IMPLEMENTATIONS, ids=IDS)
def test_ordinary_capacities_are_allocated_by_priority(fill_buckets):
    capacities = np.array([100.0, 50.0, 75.0])

    allocation = fill_buckets(capacities, FILL_AMOUNT, PRIORITIES, 0.0)

    assert allocation.sum() == min(FILL_AMOUNT, capacities.sum())
    assert allocation[2] == 75.0
