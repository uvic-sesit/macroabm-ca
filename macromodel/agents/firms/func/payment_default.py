"""Opt-in payment distress with retained collateral and continuing production.

N=3 quarters and a 20% capital valuation haircut are provisional assumptions,
not fitted Canadian estimates. Secured principal is retained, not a cash
recovery: no collateral is sold and no fictitious recovery receipt is booked.
"""
import numpy as np


def payment_distress(deposits_after_service, scheduled_service, previous, periods):
    """Service funded by an overdraft is not service met from cash.

    The existing settlement pays scheduled principal/interest using deposits
    (including overdrafts). Reconstruct available cash before service; the
    trigger measures its shortfall without reversing those actual payments.
    A quarter without scheduled service resets the consecutive-service clock.
    """
    service = np.maximum(0., np.asarray(scheduled_service))
    cash_before = np.asarray(deposits_after_service) + service
    shortfall = np.maximum(0., service - np.maximum(0., cash_before))
    distressed = (service > 0) & (shortfall > 1e-6)
    streak = np.where(distressed, np.asarray(previous) + 1, 0)
    return streak, streak >= periods, shortfall


def resolve_payment_default(firms, credit_market, capital_value, periods, haircut):
    """Write down uncovered total bank credit, keeping assets and producer.

    Existing contractual interest and amortisation are reduced pro rata with
    principal. No maturity extension is added. Overdrafts share collateral and
    uncovered losses pro rata with formal loans; their covered debit balance
    remains owed. Relief never creates positive cash or collateral-sale money.
    """
    f = firms; cm = credit_market
    debt = cm.compute_outstanding_short_term_loans_by_firm() + cm.compute_outstanding_long_term_loans_by_firm()
    service = (f.ts.current('debt_installments') + np.maximum(0., f.ts.current('interest_paid_on_loans'))
               + np.maximum(0., f.ts.current('interest_paid_on_deposits')))
    streak, default, shortfall = payment_distress(f.ts.current('deposits'), service,
        f.states.get('payment_distress_streak', np.zeros(len(debt), dtype=int)), periods)
    capacity = np.maximum(0., np.asarray(capital_value)) * (1 - haircut)
    overdraft = np.maximum(0., -f.ts.current('deposits'))
    total_credit = debt + overdraft
    total_loss = np.where(default, np.maximum(0., total_credit - capacity), 0.)
    fraction = np.divide(total_loss,total_credit,out=np.zeros_like(debt),where=total_credit>0)
    loss = debt * fraction
    od_loss = overdraft * fraction
    retained = np.where(default, total_credit-total_loss, 0.)
    cm.restructure_firm_principal(loss)
    if od_loss.any():
        cm.queue_bank_losses(np.bincount(np.asarray(f.states['Corresponding Bank ID'],dtype=int),
            weights=od_loss,minlength=cm.states['st_loans'].shape[1]))
    f.states.update(is_insolvent=default, payment_distress_streak=np.where(default, 0, streak),
        payment_service_shortfall=shortfall, payment_default_loss=loss,
        payment_default_overdraft_loss=od_loss,overdraft_writeoff_current=od_loss,
        payment_default_total_loss=total_loss,
        payment_default_retained_loans=np.where(default,debt-loss,0.),
        payment_default_retained_overdraft=np.where(default,overdraft-od_loss,0.),
        payment_default_retained=retained, payment_default_collateral_capacity=capacity,
        payment_default_recovery_cash=np.zeros(len(debt)))
    for name, value in [('short_term_loan_debt',cm.compute_outstanding_short_term_loans_by_firm()),
                        ('long_term_loan_debt',cm.compute_outstanding_long_term_loans_by_firm()),
                        ('debt',debt-loss), ('deposits',f.ts.current('deposits')+od_loss),
                        ('equity',f.ts.current('equity')+loss+od_loss)]:
        f.ts.dicts[name][-1] = value
    # A default event is a restructuring date, not permanent exit. A fresh N
    # consecutive distressed quarters is needed for another restructuring.
    return float(loss.sum()/debt.sum()) if debt.sum()>0 else 0.
