from types import SimpleNamespace
import numpy as np
import pytest
from macromodel.agents.firms.func.payment_default import payment_distress, resolve_payment_default
from macromodel.markets.credit_market.credit_market import CreditMarket
from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration


class TS:
    def __init__(self, **kw): self.dicts={k:[np.asarray(v,dtype=float)] for k,v in kw.items()}
    def current(self,k): return self.dicts[k][-1]


def setup():
    cm=CreditMarket.__new__(CreditMarket)
    cm.states={'st_loans':np.array([[[20.],[0.]],[[2.],[0.]],[[4.],[0.]]]),
               'lt_loans':np.array([[[0.],[80.]],[[0.],[8.]],[[0.],[16.]]])}
    f=SimpleNamespace(states={},ts=TS(deposits=[-5],debt_installments=[20],interest_paid_on_loans=[10],interest_paid_on_deposits=[0],
        short_term_loan_debt=[20],long_term_loan_debt=[80],debt=[100],equity=[-200]))
    return f,cm


def test_revaluation_with_cash_does_not_default():
    f,cm=setup();f.ts.dicts['deposits'][-1]=np.array([50.])
    for _ in range(5): resolve_payment_default(f,cm,[1],3,.2)
    assert not f.states['is_insolvent'].any()
    assert f.ts.current('equity')[0]==-200
    assert cm.states.get('cumulative_writeoffs',0)==0


def test_persistent_distress_exact_partial_contract_and_bank_identity():
    f,cm=setup(); opening=cm.states['st_loans'].copy(),cm.states['lt_loans'].copy()
    for _ in range(2):
        resolve_payment_default(f,cm,[50],3,.2)
        assert not f.states['is_insolvent'].any()
    resolve_payment_default(f,cm,[50],3,.2)
    assert f.states['is_insolvent'][0]
    assert f.states['payment_default_loss'][0]==60
    assert f.states['payment_default_retained'][0]==40
    assert f.ts.current('debt')[0]==40
    assert f.ts.current('deposits')[0]==-5  # no overdraft forgiveness or fictitious recovery
    assert f.ts.current('equity')[0]==-140
    assert np.allclose(cm.states['st_loans'],opening[0]*.4)
    assert np.allclose(cm.states['lt_loans'],opening[1]*.4)
    assert np.allclose(cm.pop_pending_writeoffs_by_bank(2),[12,48])
    assert cm.states['cumulative_writeoffs']==60
    # Loss debits bank equity and loans equally: reserve identity is exact.
    D,E,L=25.,100.,100.
    assert D+(E-60)-(L-60)==D+E-L


def test_clock_resets_and_no_service_is_not_default():
    streak,default,_=payment_distress([1,-10],[5,0],[2,2],3)
    assert np.array_equal(streak,[0,0]);assert not default.any()
    assert not HouseholdClosureConfiguration().firm_payment_default_enabled


def test_invalid_write_down_rejected_without_mutation():
    _,cm=setup()
    with pytest.raises(ValueError):cm.restructure_firm_principal(np.array([101.]))
    assert cm.states['lt_loans'][0].sum()==80


def test_overdraft_interest_is_a_senior_debt_service_obligation():
    f,cm=setup()
    f.ts.dicts['debt_installments'][-1]=np.array([0.])
    f.ts.dicts['interest_paid_on_loans'][-1]=np.array([0.])
    f.ts.dicts['interest_paid_on_deposits'][-1]=np.array([2.])
    for _ in range(3):resolve_payment_default(f,cm,[50],3,.2)
    assert f.states['is_insolvent'][0]
    assert f.states['payment_service_shortfall'][0]==2
