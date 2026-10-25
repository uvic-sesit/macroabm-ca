import numpy as np
from macromodel.country.household_payment_default import allocate_service,foreclosure_waterfall,arrears_days
from macromodel.country.household_payment_default import settle_foreclosures,PaymentDefaultHandler
from types import SimpleNamespace
import pandas as pd


def test_payment_shortfall_retains_unpaid_principal_and_nonaccrual_interest():
    p=np.array([[[100.]],[[200.]]]);i=np.array([[[2.]],[[3.]]]);s=np.array([[[10.]],[[20.]]])
    pp,pi,ap,ai=allocate_service(p,i,s,np.array([15.]),np.zeros_like(p),np.zeros_like(p))
    assert pi.sum()==5 and np.isclose(pp.sum(),10)
    np.testing.assert_allclose(pp+ap,s);np.testing.assert_allclose(pi+ai,i)
    assert np.isclose((p-pp).sum(),290.)


def test_payments_met_do_not_depend_on_negative_net_worth():
    p=np.array([[[100.]]]);i=np.array([[[2.]]]);s=np.array([[[10.]]])
    pp,pi,ap,ai=allocate_service(p,i,s,np.array([12.]),np.zeros_like(p),np.zeros_like(p))
    assert (ap+ai).sum()==0 and pp.sum()==10 and pi.sum()==2


def test_foreclosure_shortfall_and_surplus_are_exact():
    assert foreclosure_waterfall(100,80)==dict(repayment=80.,loss=20.,surplus=0.)
    assert foreclosure_waterfall(100,120)==dict(repayment=100.,loss=0.,surplus=20.)


def test_quarterly_arrears_buckets_and_cure():
    np.testing.assert_array_equal(arrears_days(np.array([0,0,0,60]),np.array([1.,1.,1.,0]),np.array([0.,1.,2.,3.]),np.full(4,3.)),[90,60,30,0])


def test_executed_foreclosure_reduces_bank_book_by_repayment_plus_loss():
    loans=np.array([[[60.],[40.]],[[3.],[2.]],[[6.],[4.]]])
    cm=SimpleNamespace(states={'mort_loans':loans})
    recorded=[];cm._record_writeoff=lambda amount,by_bank:recorded.append((amount,by_bank.copy()))
    h=SimpleNamespace(states={'E_foreclosure_queue':np.array([True])},ts=SimpleNamespace(current=lambda key:np.zeros(1)))
    props=pd.DataFrame({'Corresponding Owner Household ID':[1],'E foreclosure':[True]})
    sales=pd.DataFrame([dict(sales_types='Sell',property_id=0,seller_id=0,buyer_id=1,price_or_rent=80.,executed=True)])
    c=SimpleNamespace(households=h,credit_market=cm,housing_market=SimpleNamespace(states={'properties':props,'current_sales':sales}))
    repayments=settle_foreclosures(c)
    assert repayments.sum()==80 and cm.states['mort_loans'].sum()==0
    assert recorded[0][0]==20
    np.testing.assert_allclose(recorded[0][1],[12,8])
    # Buyer cash debit=80; seller receipt=80 and principal debit=80;
    # bank assets fall 100, deposits fall 80, and equity absorbs 20.
    assert -100 == -repayments.sum()-recorded[0][0]
    assert h.states['E_foreclosure_surplus'].sum()==0


def test_handler_does_not_default_negative_net_worth_when_payments_are_met():
    vals={'wealth_deposits':[np.array([1.])],'wealth':[np.array([0.])],
        'net_wealth':[np.array([-100.])],'consumption_loan_debt':[np.array([100.])],
        'mortgage_debt':[np.array([0.])],'debt':[np.array([100.])],
        'total_consumption_loan_debt':[np.array([100.])],'total_mortgage_debt':[np.array([0.])]}
    ts=SimpleNamespace(dicts=vals,current=lambda key:vals[key][-1]);h=SimpleNamespace(ts=ts,states={})
    cons=np.array([[[100.]],[[2.]],[[10.]]]);zero=np.zeros((2,1,1))
    cm=SimpleNamespace(states={'cons_loans':cons.copy(),'mort_loans':np.zeros_like(cons),
        'E_arrears_quarters':np.zeros((2,1),int),'E_days_past_due':np.zeros((2,1),int),
        'E_principal_arrears':zero.copy(),'E_interest_arrears':zero.copy()})
    losses=[];cm._record_writeoff=lambda amount,by_bank:losses.append(amount)
    cfg=SimpleNamespace(household_payment_default_periods=3)
    country=SimpleNamespace(configuration=SimpleNamespace(household_closure=cfg))
    result=PaymentDefaultHandler(country).handle_insolvency(h,None,cm)
    assert result[0]==0 and sum(losses)==0
    np.testing.assert_array_equal(cm.states['cons_loans'],cons)
    assert h.ts.current('net_wealth')[0]==-100
