from types import SimpleNamespace as NS
import numpy as np
import pytest

from macromodel.timeseries import TimeSeries
from macromodel.country.household_closure import (cap_household_goods_budget,
    liquidatable_household_assets, needed_asset_liquidation)
from macromodel.agents.households.func.wealth import DefaultWealthSetter
from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration


def household():
    h=NS(states=dict(financial_asset_drawdown=True,protected_pension_assets=np.array([50.,0.,0.,80.])),
        ts=TimeSeries(target_consumption=np.full((4,2),50.),target_investment=np.zeros((4,2)),
            wealth_deposits=np.array([0.,0.,100.,0.]),
            wealth_other_financial_assets=np.array([130.,0.,100.,80.]),
            received_consumption_loans=np.zeros(4),received_mortgages=np.zeros(4),
            property_sale_proceeds=np.zeros(4),debt_installments=np.zeros(4),
            rent=np.zeros(4),interest_paid=np.zeros(4),price_paid_for_property=np.zeros(4)))
    return h


def test_cash_then_nonpension_assets_then_proportional_cut():
    h=household()
    c=NS(households=h,central_government=NS(states={'Value-added Tax':0.,'Capital Formation Tax':0.}))
    cap_household_goods_budget(c,net_receipts=np.full(4,20.))
    np.testing.assert_array_equal(h.ts.current('target_consumption').sum(axis=1),[100.,20.,100.,20.])
    np.testing.assert_array_equal(h.states['budget_planned_asset_liquidation'],[80.,0.,0.,0.])
    np.testing.assert_array_equal(h.states['overdraft_unused_capacity'],0.)
    # Planning cannot consume stock or liquidate the protected pension.
    np.testing.assert_array_equal(h.ts.current('wealth_other_financial_assets'),[130.,0.,100.,80.])
    assert not HouseholdClosureConfiguration().financial_asset_drawdown


@pytest.mark.parametrize('spent,senior,deposit,ofa,pension,expected_L,expected_cash',[
    (100.,0.,0.,130.,50.,80.,0.),
    (20.,0.,0.,0.,0.,0.,0.),
    (100.,0.,100.,100.,0.,0.,20.),
    (20.,30.,0.,80.,50.,30.,0.),
    (20.,50.,0.,80.,50.,30.,-20.),
])
def test_existing_wealth_booking_preserves_exact_cash_and_asset_identity(
        spent,senior,deposit,ofa,pension,expected_L,expected_cash):
    income=20.
    cash_before=deposit+income-spent-senior
    liquidation=needed_asset_liquidation(cash_before,max(0.,ofa-pension))
    used_deposits=max(0.,spent-income)-liquidation
    new_deposits=max(0.,income-spent)
    cash=DefaultWealthSetter.compute_wealth_in_deposits(
        deposit,new_deposits,used_deposits,senior,0.,0.,0.,0.,0.)
    assets=DefaultWealthSetter.compute_wealth_in_other_financial_assets(
        None,ofa,0.,liquidation)
    assert liquidation==expected_L
    assert cash==expected_cash
    assert assets>=pension
    assert cash+assets==pytest.approx(deposit+ofa+income-spent-senior)
