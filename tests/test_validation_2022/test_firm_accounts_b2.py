import numpy as np
import pandas as pd
import pytest
from macro_data.processing.synthetic_firms.canadian_firm_accounts import column_output,cfc_coefficients,finite_initial_unit_costs
from macro_data.processing.synthetic_firms.canadian_firm_accounts import reconcile_country
from types import SimpleNamespace


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


def test_initial_zero_output_costs_are_finite_like_runtime_without_fictitious_production():
    output=np.array([0.,10.]);cost=np.array([0.,7.])
    np.testing.assert_allclose(finite_initial_unit_costs(output,cost),[0.,.7])
    np.testing.assert_array_equal(output,[0.,10.])


def test_IO_reexpression_preserves_inputs_stocks_and_contracts_without_zero_output_nan():
    d=pd.DataFrame(dict(Industry=[0,1],Production=[25e6,1e6],Demand=[25e6,1e6],
        Debt=[7.,8.],Deposits=[9.,10.],Equity=[11.,12.]))
    vectors=pd.DataFrame({'Output in LCU':[25e6,1e6]})
    matrix=pd.DataFrame([[2.,3.],[4.,5.]])
    f=SimpleNamespace(firm_data=d,labour_productivity_by_industry=np.array([2.,3.]),
        capital_inputs_stock=np.array([[1.,2.],[3.,4.]]))
    data=dict(industry_vectors=vectors,intermediate_inputs_productivity_matrix=matrix.copy(),
        capital_inputs_productivity_matrix=matrix.copy(),capital_inputs_depreciation_matrix=matrix.copy())
    country=SimpleNamespace(firms=f,industry_data=data)
    obs=pd.DataFrame(dict(output_basic=[180.,0.],net_product_tax_intermediate=[20.,0.],
        tax_production=[3.,0.],subsidy_production=[-1.,0.],wages_salaries=[20.,0.],
        employers_social_contributions=[2.,0.],gross_operating_surplus=[10.,0.],gross_mixed_income=[1.,0.]))
    financial=d[['Debt','Deposits','Equity']].copy();stock=f.capital_inputs_stock.copy()
    reconcile_country(country,obs)
    np.testing.assert_allclose(d.Production,[50e6,0.])
    np.testing.assert_allclose(f.intermediate_inputs_productivity_matrix[:,0],[4.,8.])
    np.testing.assert_allclose(f.capital_inputs_depreciation_matrix[:,0],[1.,2.])
    pd.testing.assert_frame_equal(d[['Debt','Deposits','Equity']],financial)
    np.testing.assert_array_equal(f.capital_inputs_stock,stock)
    assert np.isfinite(f.intermediate_inputs_productivity_matrix).all()
    assert vectors['Taxes Less Subsidies in LCU'].iloc[0]==pytest.approx(.5e6)
