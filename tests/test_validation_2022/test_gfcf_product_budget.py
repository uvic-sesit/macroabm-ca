import numpy as np
import pytest
from macro_data.processing.synthetic_firms.gfcf_allocation import allocate_product_budget


def test_regional_product_totals_and_investor_shares_both_hold():
    products=np.array([12.,8.,0.]);weights=np.array([3.,1.])
    result=allocate_product_budget(products,weights)
    np.testing.assert_array_equal(result.sum(axis=0),products)
    np.testing.assert_array_equal(result.sum(axis=1),[15.,5.])
    np.testing.assert_array_equal(products,[12.,8.,0.])


def test_missing_investor_is_not_an_unreported_residual_plug():
    with pytest.raises(ValueError):allocate_product_budget([2.,0.],[0.,0.])


def test_negative_source_capital_products_are_not_clipped_or_redistributed():
    source=np.array([12.,-2.]);copy=source.copy()
    with pytest.raises(ValueError):allocate_product_budget(source,[3.,1.])
    np.testing.assert_array_equal(source,copy)
