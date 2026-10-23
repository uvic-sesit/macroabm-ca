from types import SimpleNamespace as NS
import numpy as np
import pytest
from macromodel.timeseries import TimeSeries
from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration
from macromodel.country.household_closure import recalibrate_household_investment
from macromodel.agents.households.func.investment import DefaultHouseholdInvestment


def country(enabled=True):
    cfg=HouseholdClosureConfiguration(investment_benchmark_enabled=enabled,initial_annual_investment_benchmark=400.)
    rates=np.array([.2,.4])
    h=NS(states={'investment_rate':rates},investment_weights=np.array([.25,.75]),
        ts=TimeSeries(income=np.array([80.,120.]),income_financial_assets=np.array([5.,15.]),
            investment=np.array([[2.,6.],[3.,9.]]),target_investment=np.array([[2.,6.],[3.,9.]]),
            total_investment=np.array([24.]),total_investment_before_vat=np.array([20.]),
            industry_investment=np.array([5.,15.])))
    return NS(households=h,configuration=NS(household_closure=cfg),
        central_government=NS(states={'Capital Formation Tax':.2}),
        household_closure=NS(planned_mixed=np.array([10.,20.]),planned_dividends=np.array([5.,5.]),planned_transfers=np.zeros(2)))


def test_investment_calibration_matches_initial_gfcf_preserving_relative_rates_and_weights():
    c=country();h=c.households;old=h.states['investment_rate']
    recalibrate_household_investment([c])
    base=np.array([90.,130.])
    assert (h.states['investment_rate']*base).sum()==pytest.approx(100.)
    assert h.ts.current('total_investment')[0]==pytest.approx(100.)
    assert h.states['investment_rate'][1]/h.states['investment_rate'][0]==pytest.approx(2.)
    np.testing.assert_array_equal(old,[.2,.4])
    expected=DefaultHouseholdInvestment().compute_target_investment(0.,1.,1.,base,None,0,
        h.investment_weights,h.states['investment_rate'],.2)
    np.testing.assert_allclose(h.ts.initial('investment'),expected)
    np.testing.assert_allclose(h.ts.initial('industry_investment'),expected.sum(axis=0))
    np.testing.assert_array_equal(h.ts.initial('income'),[80.,120.])


def test_investment_calibration_is_opt_in():
    c=country(False)
    recalibrate_household_investment([c])
    np.testing.assert_array_equal(c.households.states['investment_rate'],[.2,.4])
    assert c.households.ts.current('total_investment')[0]==24.
