from types import SimpleNamespace as NS
import numpy as np
import pytest
from macromodel.timeseries import TimeSeries
from macromodel.agents.households.func.insolvency import PersistentDistressHouseholdInsolvencyHandler
from macromodel.markets.credit_market.credit_market import CreditMarket
def distress_fixture():
    h = NS(states={}, ts=TimeSeries(wealth_deposits=np.array([0.]), debt_installments=np.array([10.]),
             interest_paid_on_loans=np.array([0.]), wealth_main_residence=np.array([100.]),
             wealth_other_properties=np.array([0.]), wealth_other_real_assets=np.array([0.]),
             wealth_other_financial_assets=np.array([0.]), wealth=np.array([70.]), debt=np.array([150.]),
             net_wealth=np.array([-80.]), consumption_loan_debt=np.array([0.]), mortgage_debt=np.array([150.]),
             total_consumption_loan_debt=[0.], total_mortgage_debt=[150.]))
    cm = NS(states={"cons_loans": np.zeros((3, 1, 1)), "mort_loans": np.array([[[150.]], [[1.5]], [[10.]]])})
    cm._record_writeoff = lambda amount, by_bank: CreditMarket._record_writeoff(cm, amount, by_bank)
    return h, cm


def test_persistent_distress_preserves_collateral_claim_and_books_only_loss():
    h, cm = distress_fixture()
    handler = PersistentDistressHouseholdInsolvencyHandler(3, 0.2)
    for t in range(3):
        h.ts.wealth_deposits.append(np.array([-10. * (t + 1)]))
        result = handler.handle_insolvency(h, None, cm)
        if t < 2:
            assert result[0] == 0
            assert cm.states["mort_loans"][0].sum() == 150
    assert result[0] == 1
    assert cm.states["mort_loans"][0].sum() == pytest.approx(80)
    assert cm.states["pending_writeoffs_by_bank"].sum() == pytest.approx(70)
    assert h.ts.current("mortgage_debt").sum() == pytest.approx(80)
    assert h.ts.current("wealth_main_residence").sum() == 100
    assert cm.states["mort_loans"][2].sum() == pytest.approx(10 * 80 / 150)


def test_negative_net_worth_and_old_overdraft_alone_do_not_trigger_default():
    h, cm = distress_fixture()
    h.ts.wealth_deposits.append(np.array([-30.]))
    h.ts.wealth_deposits.append(np.array([-30.]))
    rule = PersistentDistressHouseholdInsolvencyHandler(1)
    assert rule.handle_insolvency(h, None, cm)[0] == 0
    assert cm.states["mort_loans"][0].sum() == 150


def test_other_recoverable_assets_cover_an_underwater_mortgage_deficiency():
    h, cm = distress_fixture()
    h.ts.dicts["wealth_other_financial_assets"][-1] = np.array([200.])
    h.ts.wealth_deposits.append(np.array([-10.]))
    rule = PersistentDistressHouseholdInsolvencyHandler(1, 0.2)
    assert rule.handle_insolvency(h, None, cm)[0] == 0
    assert cm.states["mort_loans"][0].sum() == 150


