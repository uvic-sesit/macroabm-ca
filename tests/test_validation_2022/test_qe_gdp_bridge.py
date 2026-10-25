import numpy as np
from macro_data.processing.synthetic_firms.qe_gdp_bridge import gdp_bridge


def test_input_product_tax_is_not_other_production_tax_or_value_added():
    r=gdp_bridge(110,40,10,30,25,5,7,3,70)
    assert r['production_basic']==60 and r['income_basic']==60
    assert r['production_market']==70 and r['expenditure_residual']==0


def test_signed_subsidy_and_statistical_residual_are_retained():
    r=gdp_bridge(100,40,5,30,30,-5,7,3,72)
    assert r['production_income_residual']==0
    assert r['expenditure_residual']==7


def test_regional_residuals_cannot_be_hidden_by_national_netting():
    r=gdp_bridge(np.array([100,100]),40,5,30,20,5,0,0,np.array([60,50]))
    np.testing.assert_array_equal(r['expenditure_residual'],[5,-5])
