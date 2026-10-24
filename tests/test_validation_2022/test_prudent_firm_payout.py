from types import SimpleNamespace as NS
import numpy as np
import pytest
from macromodel.country.firm_payout import prudent_requests,scheduled_reserve
from macromodel.country.household_closure import HouseholdClosure
from macromodel.timeseries import TimeSeries
from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration


def test_dividend_respects_cash_reserve_and_retained_profit_without_shifting_other_flows():
    requests=np.array([[10.,10.,10.],[5.,5.,5.],[50.,50.,50.]])
    result=prudent_requests(requests,np.array([100.,60.,100.]),np.array([20.,100.,-1.]),np.array([30.,30.,30.]))
    np.testing.assert_array_equal(result[:2],requests[:2])
    np.testing.assert_allclose(result[2],[20.,15.,0.])
    assert np.all(np.array([100.,60.,100.])-result.sum(axis=0)>=30.)
    np.testing.assert_array_equal(requests[2],[50.,50.,50.])


def test_reserve_counts_existing_contracts_overdraft_interest_and_wages():
    c=NS(credit_market=NS(states={'st_loans':np.array([[[10.]],[[1.]],[[2.]]]),
                                    'lt_loans':np.array([[[20.]],[[2.]],[[3.]]])}),
         firms=NS(states={'Corresponding Bank ID':np.array([0])},ts=TimeSeries(deposits=np.array([-5.]),total_wage=np.array([7.]))),
         banks=NS(ts=TimeSeries(overdraft_rate_on_firm_deposits=np.array([.2]))))
    np.testing.assert_allclose(scheduled_reserve(c),[16.])


def test_committed_dividend_settles_exactly_and_retained_loss_carries_forward():
    f=NS(states={'payout_retained_profit':np.array([20.])},ts=TimeSeries(deposits=np.array([2.]),
        profits=np.array([-5.]),corporate_taxes_paid=np.array([0.]),household_distributions=np.array([0.]),
        household_distribution_requests=np.zeros((3,1))))
    obj=HouseholdClosure.__new__(HouseholdClosure)
    obj.c=NS(firms=f,central_government=NS(states={'Profit Tax':.2}))
    obj.cfg=HouseholdClosureConfiguration(prudent_firm_payout_enabled=True)
    obj.firm_requests=np.array([[3.],[4.],[10.]])
    obj.requested_firm_payments=obj.firm_requests.copy()
    obj.committed_firm_payments=obj.firm_requests.copy()
    obj.firm_payments()
    np.testing.assert_allclose(obj.actual_firm_payments,[ [3.],[4.],[10.] ])
    assert f.ts.current('deposits')[0]==pytest.approx(-15.)
    assert f.states['payout_retained_profit'][0]==pytest.approx(-2.)
    assert not HouseholdClosureConfiguration().prudent_firm_payout_enabled
