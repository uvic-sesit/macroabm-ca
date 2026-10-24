from types import SimpleNamespace as NS
import numpy as np
import pytest
from macromodel.country.buffer_stock import spending,calibrated_level,apply,opening_debt_service
from macromodel.country.household_closure import cap_household_goods_budget
from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration
from macromodel.timeseries import TimeSeries


def test_wealth_above_and_below_target_changes_spending():
    assert spending([100],[300],[2],[0],.1)[0]==110
    assert spending([100],[100],[2],[0],.1)[0]==90


def test_initial_service_uses_contracts_without_unset_interest_series():
    loans=np.array([[[10.,0.]],[[1.,0.]],[[2.,0.]]])
    np.testing.assert_allclose(opening_debt_service([loans],np.array([0.,-5.]),np.array([.1,.2])),[3.,1.])


def test_nonpositive_income_uses_level_buffer_and_consumption_never_negative():
    assert spending([-10],[100],[999],[20],.1)[0]==0
    assert spending([0],[100],[999],[20],.1)[0]==8
    assert not HouseholdClosureConfiguration().buffer_stock_enabled


def test_one_level_calibration_includes_rent_offset_and_clipping():
    raw=np.array([-10.,100.]);scales=np.array([1.,2.]);wL=np.array([.2,.3]);dup=np.array([3.,7.]);rent=np.array([3.,7.])
    level=calibrated_level(raw,scales,wL,dup,rent,120.)
    C=np.maximum(0.,raw+level*scales)
    assert (C-np.minimum(C*wL,dup)+rent).sum()==pytest.approx(120.)


def test_smoothed_income_and_exact_D_priority_cash_identity():
    cfg=HouseholdClosureConfiguration(buffer_stock_enabled=True)
    h=NS(states=dict(buffer_stock_permanent_income=np.array([100.]),buffer_stock_b=np.array([1.]),
        buffer_stock_fallback=np.array([20.]),buffer_stock_level=np.array([0.]),buffer_stock_basket=np.array([[.4,.6]]),
        protected_pension_assets=np.array([0.]),consumption_before_investment=True,financial_asset_drawdown=True),
        ts=TimeSeries(target_consumption=np.array([[1.,1.]]),target_investment=np.array([[5.,5.]]),
            wealth_deposits=np.array([10.]),wealth_other_financial_assets=np.array([5.]),
            debt_installments=np.array([2.]),rent=np.array([3.]),interest_paid=np.array([0.]),
            received_consumption_loans=np.array([0.]),received_mortgages=np.array([0.]),property_sale_proceeds=np.array([0.]),price_paid_for_property=np.array([0.])))
    c=NS(households=h,configuration=NS(household_closure=cfg),central_government=NS(states={'Value-added Tax':.1,'Capital Formation Tax':.2}))
    receipts=np.array([25.]);apply(c,receipts)
    assert h.states['buffer_stock_permanent_income'][0]==80  # .75*100 + .25*(25-5)
    cap_household_goods_budget(c,net_receipts=receipts)
    C=1.1*h.ts.current('target_consumption').sum();I=1.2*h.ts.current('target_investment').sum()
    assert C==pytest.approx(35.);assert I==0
    assert 10+25+5-2-3-C-I==pytest.approx(0.,abs=1e-12)
