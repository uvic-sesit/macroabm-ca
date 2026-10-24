import numpy as np
import pandas as pd
import pytest
from macro_data.processing.synthetic_firms.canadian_firm_accounts import column_output,cfc_coefficients


def test_cost_side_output_uses_product_valuation_and_signed_other_taxes():
    obs=pd.DataFrame(dict(output_basic=[90.,100.],net_product_tax_intermediate=[10.,-5.],
        tax_production=[3.,1.],subsidy_production=[-5.,-.5]))
    np.testing.assert_allclose(column_output(obs),np.array([100.,95.])*1e6/4)
    # Output = basic inputs + input product tax + wages + GOS + signed D29-D39.
    basic_inputs=50.;product_tax=10.;wages=30.;net_other=-2.;gross_surplus=12.
    assert basic_inputs+product_tax+wages+net_other+gross_surplus==100.


def test_observed_CFC_exactly_changes_level_preserving_capital_good_mix():
    original=np.array([[1.,2.],[3.,2.]])
    result=cfc_coefficients(original,np.array([20.,10.]),np.array([100.,50.]))
    np.testing.assert_allclose(result.sum(axis=0)*[100.,50.],[20.,10.])
    assert result[0,0]/result[1,0]==pytest.approx(1/3)
    assert result[0,1]==result[1,1]
    np.testing.assert_array_equal(original,[[1.,2.],[3.,2.]])


def test_CFC_missing_output_or_capital_composition_is_not_silently_fitted():
    with pytest.raises(ValueError,match='zero-output'):cfc_coefficients([[1.]],np.array([1.]),np.array([0.]))
    with pytest.raises(ValueError,match='composition'):cfc_coefficients([[0.]],np.array([1.]),np.array([10.]))
