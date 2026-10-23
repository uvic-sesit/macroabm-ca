from types import SimpleNamespace as NS
import numpy as np
from macromodel.timeseries import TimeSeries
from macromodel.country.household_closure import cap_household_goods_budget


def test_binding_budget_cuts_investment_before_consumption_including_taxes():
    C=np.array([[20.,20.]]*3);I=np.array([[10.,10.]]*3)
    h=NS(states={'consumption_before_investment':True},ts=TimeSeries(
        target_consumption=C,target_investment=I,wealth_deposits=np.array([107.,67.,37.]),
        received_consumption_loans=np.zeros(3),received_mortgages=np.zeros(3),property_sale_proceeds=np.zeros(3),
        debt_installments=np.zeros(3),rent=np.full(3,7.),interest_paid=np.zeros(3),price_paid_for_property=np.zeros(3)))
    c=NS(households=h,central_government=NS(states={'Value-added Tax':.1,'Capital Formation Tax':.2}))
    cap_household_goods_budget(c,net_receipts=np.zeros(3))
    newC=1.1*h.ts.current('target_consumption').sum(axis=1)
    newI=1.2*h.ts.current('target_investment').sum(axis=1)
    np.testing.assert_allclose(newC,[44.,44.,30.])
    np.testing.assert_allclose(newI,[24.,16.,0.])
    np.testing.assert_allclose(h.states['overdraft_consumption_cut'],[0.,0.,14.])
    np.testing.assert_allclose(h.states['overdraft_investment_cut'],[0.,8.,24.])
    np.testing.assert_allclose(h.ts.current('wealth_deposits')-7.-newC-newI,[32.,0.,0.],atol=1e-12)
    np.testing.assert_allclose(h.ts.current('wealth_deposits'),[107.,67.,37.])
