import numpy as np
import pandas as pd
from types import SimpleNamespace
from macro_data.processing.synthetic_firms.sut_source_update import net_surplus_gate,rescale_output_units


def test_net_surplus_gate_includes_cfc_on_both_sides():
    gap,above=net_surplus_gate(np.array([100.,100.]),np.ones(2),np.array([.9,1.1]),np.array([10.,20.]),np.array([20.,10.]))
    np.testing.assert_allclose(gap,0.,atol=1e-12)
    assert not above.any()  # second source has negative NOS


def test_above_price_without_negative_observed_nos_fails():
    gap,above=net_surplus_gate(np.array([100.]),np.ones(1),np.array([1.1]),np.array([10.]),np.array([20.]))
    assert above[0] and abs(gap[0])>1


def test_output_source_units_preserve_input_use_cfc_and_contracts():
    d=pd.DataFrame({'Industry':[0],'Production':[100.],'Demand':[100.],'Debt':[30.],'Deposits':[20.],'Equity':[90.]})
    industry={'industry_vectors':pd.DataFrame({'Output in LCU':[100.],'Output in USD':[100.]})}
    industry.update({k:pd.DataFrame([[v]]) for k,v in [('intermediate_inputs_productivity_matrix',2.),('capital_inputs_productivity_matrix',5.),('capital_inputs_depreciation_matrix',.1)]})
    f=SimpleNamespace(firm_data=d,labour_productivity_by_industry=np.array([10.]))
    c=SimpleNamespace(firms=f,industry_data=industry);before=d[['Debt','Deposits','Equity']].copy()
    rescale_output_units(c,np.array([80.]))
    assert d.Production.iloc[0]/f.intermediate_inputs_productivity_matrix[0,0]==50.
    assert d.Production.iloc[0]*f.capital_inputs_depreciation_matrix[0,0]==10.
    pd.testing.assert_frame_equal(before,d[['Debt','Deposits','Equity']])


def test_observed_zero_output_retains_contract_holder():
    d=pd.DataFrame({'Industry':[0],'Production':[100.],'Demand':[100.],'Debt':[30.]})
    industry={'industry_vectors':pd.DataFrame({'Output in LCU':[100.],'Output in USD':[100.]})}
    industry.update({k:pd.DataFrame([[1.]]) for k in ['intermediate_inputs_productivity_matrix','capital_inputs_productivity_matrix','capital_inputs_depreciation_matrix']})
    f=SimpleNamespace(firm_data=d,labour_productivity_by_industry=np.array([10.]))
    rescale_output_units(SimpleNamespace(firms=f,industry_data=industry),np.array([0.]))
    assert d.Production.iloc[0]==0. and d.Debt.iloc[0]==30.
