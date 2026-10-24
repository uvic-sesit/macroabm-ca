import numpy as np
import pandas as pd
from macromodel.agents.firms.firm_ts import FirmTimeSeries


def make_series(purchases=None):
    names=['Price','Price in USD','Production','Inventory','Total Wages Paid','Taxes paid on Production',
        'Number of Employees','Profits','Unit Costs','Corporate Taxes Paid','Equity','Demand','Debt',
        'Deposits','Debt Installments','Interest paid on deposits','Interest paid on loans','Interest paid',
        'Labour Inputs','Labour Productivity']
    data=pd.DataFrame({key:[1.,1.] for key in names})
    data['Industry']=[0,1]
    matrix=np.array([[2.,3.],[4.,5.]])
    return FirmTimeSeries.from_data(data=data,intermediate_inputs_stock=matrix,
        used_intermediate_inputs=matrix,capital_inputs_stock=matrix*10,used_capital_inputs=matrix,
        initial_good_prices=np.array([1.,2.]),n_industries=2,initial_capital_purchases=purchases)


def test_CFC_and_initial_acquisitions_are_independent_and_default_is_unchanged():
    purchases=np.array([[10.,20.],[30.,40.]])
    series=make_series(purchases)
    np.testing.assert_allclose(series.current('used_capital_inputs_costs'),[8.,14.])
    np.testing.assert_allclose(series.current('total_capital_inputs_bought_costs'),[50.,110.])
    np.testing.assert_allclose(series.current('gross_fixed_capital_formation'),[40.,120.])
    original=make_series()
    np.testing.assert_array_equal(original.current('total_capital_inputs_bought_costs'),
        original.current('used_capital_inputs_costs'))
    np.testing.assert_array_equal(series.current('capital_inputs_stock'),original.current('capital_inputs_stock'))
