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
    """Write down only uncovered bank principal, keep cash/assets/producer.

    Existing contractual interest and amortisation are reduced pro rata with
    principal. No maturity extension is added. An unchanged overdraft remains
    owed to its bank; it is never silently cancelled by this rule.
    """
    f = firms; cm = credit_market
    debt = cm.compute_outstanding_short_term_loans_by_firm() + cm.compute_outstanding_long_term_loans_by_firm()
    service = f.ts.current('debt_installments') + np.maximum(0., f.ts.current('interest_paid_on_loans'))
    streak, default, shortfall = payment_distress(f.ts.current('deposits'), service,
        f.states.get('payment_distress_streak', np.zeros(len(debt), dtype=int)), periods)
    capacity = np.maximum(0., np.asarray(capital_value)) * (1 - haircut)
    loss = np.where(default, np.maximum(0., debt - capacity), 0.)
    retained = np.where(default, debt-loss, 0.)
    cm.restructure_firm_principal(loss)
    f.states.update(is_insolvent=default, payment_distress_streak=np.where(default, 0, streak),
        payment_service_shortfall=shortfall, payment_default_loss=loss,
        payment_default_retained=retained, payment_default_collateral_capacity=capacity,
        payment_default_recovery_cash=np.zeros(len(debt)))
    for name, value in [('short_term_loan_debt',cm.compute_outstanding_short_term_loans_by_firm()),
                        ('long_term_loan_debt',cm.compute_outstanding_long_term_loans_by_firm()),
                        ('debt',debt-loss), ('equity',f.ts.current('equity')+loss)]:
        f.ts.dicts[name][-1] = value
    # A default event is a restructuring date, not permanent exit. A fresh N
    # consecutive distressed quarters is needed for another restructuring.
    return float(loss.sum()/debt.sum()) if debt.sum()>0 else 0.
