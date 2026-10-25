"""Candidate E: cash servicing, non-accrual arrears and market foreclosure.

Unpaid interest is an off-balance-sheet, non-accrual arrears memo, not
income or newly created principal. Unsold collateral remains encumbered by
the original mortgage until an actual market sale, without cash recovery.
"""
import numpy as np
from .household_closure import known_household_receipts,liquidatable_household_assets


def allocate_service(principal,interest,scheduled,resources,old_principal_arrears,old_interest_arrears):
    """Interest first, then principal; pro rata across existing bank contracts."""
    due_p=np.minimum(principal,scheduled+old_principal_arrears)
    due_i=interest+old_interest_arrears
    cash=np.maximum(0.,resources)
    total_i=due_i.sum(axis=(0,1)); total_p=due_p.sum(axis=(0,1))
    fi=np.minimum(1.,np.divide(cash,total_i,out=np.ones_like(cash),where=total_i>0))
    paid_i=due_i*fi[None,None,:]; cash=np.maximum(0.,cash-paid_i.sum(axis=(0,1)))
    fp=np.minimum(1.,np.divide(cash,total_p,out=np.ones_like(cash),where=total_p>0))
    paid_p=due_p*fp[None,None,:]
    return paid_p,paid_i,due_p-paid_p,due_i-paid_i


def foreclosure_waterfall(principal,net_sale_proceeds):
    principal=float(principal);proceeds=float(net_sale_proceeds)
    if min(principal,proceeds)<0:raise ValueError('Nonnegative principal and sale proceeds required')
    repayment=min(principal,proceeds)
    return dict(repayment=repayment,loss=principal-repayment,surplus=proceeds-repayment)


def arrears_days(previous_days,unpaid,paid,total_due):
    """Quarterly approximation: cash available first, monthly due dates equally spaced.

    Within-quarter 30/60 buckets are inferred, not observed monthly receipts.
    Existing uncured arrears age another 90 days; full cure resets to zero.
    """
    fraction=np.divide(paid,total_due,out=np.ones_like(paid),where=total_due>0)
    first=30*(3-np.minimum(2,np.floor(3*fraction+1e-12)))
    return np.where(unpaid>1e-8,np.where(previous_days>0,previous_days+90,first),0).astype(int)


def service(c):
    h=c.households;cm=c.credit_market
    receipts=known_household_receipts(c);d=h.ts.current('wealth_deposits')
    ids=h.states['Corresponding Bank ID']
    deposit_interest=(np.maximum(0.,-d)*c.banks.ts.current('overdraft_rate_on_household_deposits')[ids]
        -np.maximum(0.,d)*c.banks.ts.current('interest_rate_on_household_deposits')[ids])
    cash=(d+receipts+liquidatable_household_assets(h)+h.ts.current('received_consumption_loans')+
        h.ts.current('received_mortgages')+h.ts.current('property_sale_proceeds')-
        h.ts.current('rent')-h.ts.current('price_paid_for_property')-deposit_interest)
    loans=np.stack([cm.states[k] for k in ('cons_loans','mort_loans')])
    shape=loans[:,0].shape
    oldp=cm.states.get('E_principal_arrears',np.zeros(shape));oldi=cm.states.get('E_interest_arrears',np.zeros(shape))
    paidp,paidi,ap,ai=allocate_service(loans[:,0],loans[:,1],loans[:,2],cash,oldp,oldi)
    for j,key in enumerate(('cons_loans','mort_loans')):cm.states[key][0]-=paidp[j]
    cm.states['E_interest_paid_by_bank']=paidi.sum(axis=(0,2))
    cm.states['E_interest_paid_by_household']=paidi.sum(axis=(0,1))
    cm.states['E_principal_arrears']=ap;cm.states['E_interest_arrears']=ai
    previous=cm.states.get('E_days_past_due',np.zeros((2,shape[-1]),int))
    unpaid=(ap+ai).sum(axis=1); paid=(paidp+paidi).sum(axis=1)
    cm.states['E_days_past_due']=arrears_days(previous,unpaid,paid,unpaid+paid)
    periods=cm.states.get('E_arrears_quarters',np.zeros((2,shape[-1]),int))
    cm.states['E_arrears_quarters']=np.where(unpaid>1e-8,periods+1,0)
    h.states['E_scheduled_service']=unpaid+paid;h.states['E_unpaid_service']=unpaid
    h.states['E_paid_service']=paid
    return paidp.sum(axis=(0,1))


class PaymentDefaultHandler:
    def __init__(self,country):self.c=country

    def handle_insolvency(self,households,banks,credit_market):
        h=households;cm=credit_market;c=self.c;cfg=c.configuration.household_closure
        quarters=cm.states['E_arrears_quarters'];n=len(h.ts.current('wealth_deposits'))
        eligible=quarters>=cfg.household_payment_default_periods
        cons=cm.states['cons_loans'][0].sum(axis=0);mort=cm.states['mort_loans'][0].sum(axis=0)
        loss=np.where(eligible[0],cons,0.)
        fraction=np.divide(loss,cons,out=np.zeros(n),where=cons>0)
        by_bank=(cm.states['cons_loans'][0]*fraction).sum(axis=1)
        cm.states['cons_loans']*=(1-fraction)[None,None,:]
        cm._record_writeoff(float(loss.sum()),by_bank=by_bank)
        for key in ('E_principal_arrears','E_interest_arrears'):cm.states[key][0,:,eligible[0]]=0.
        cm.states['E_arrears_quarters'][0,eligible[0]]=0
        cm.states['E_days_past_due'][0,eligible[0]]=0
        queue=h.states.get('E_foreclosure_queue',np.zeros(n,bool)).copy()
        newly_queued=eligible[1]&(mort>1e-8)&~queue
        queue&=cm.states['E_days_past_due'][1]>0
        queue|=eligible[1]&(mort>1e-8);h.states['E_foreclosure_queue']=queue
        h.states['E_unsecured_writeoff']=loss
        h.states['E_new_defaults']=(loss>1e-8)|newly_queued
        sync_debt(h,cm)
        return (eligible.any(axis=0).mean(),loss.sum()/cons.sum() if cons.sum() else 0.,0.)


def sync_debt(h,cm):
    cons=cm.states['cons_loans'][0].sum(axis=0);mort=cm.states['mort_loans'][0].sum(axis=0)
    for key,val in [('consumption_loan_debt',cons),('mortgage_debt',mort),('debt',cons+mort),('net_wealth',h.ts.current('wealth')-cons-mort)]:h.ts.dicts[key][-1]=val.copy()
    for key,val in [('total_consumption_loan_debt',cons),('total_mortgage_debt',mort)]:h.ts.dicts[key][-1]=np.array([val.sum()])


def list_foreclosures(c):
    h=c.households;props=c.housing_market.states['properties']
    queue=h.states.get('E_foreclosure_queue',np.zeros(len(h.ts.current('wealth_deposits')),bool))
    owners=props['Corresponding Owner Household ID'].to_numpy(int)
    mask=(owners>=0)&queue[np.maximum(0,owners)]
    props['E foreclosure']=mask
    props.loc[mask,'Temporarily for Sale']=True
    props.loc[mask,'Sale Price']=props.loc[mask,'Value']*(1-c.configuration.household_closure.foreclosure_sale_haircut)


def settle_foreclosures(c):
    """Executed sales alone repay creditors; no hypothetical buyer or REO cash."""
    cm=c.credit_market;h=c.households;market=c.housing_market
    sales=market.states['current_sales'];props=market.states['properties'];n=len(h.ts.current('wealth_deposits'))
    repayments=np.zeros(n);losses=np.zeros(n);surpluses=np.zeros(n)
    by_bank=np.zeros(cm.states['mort_loans'].shape[1])
    for r in sales.itertuples(index=False):
        if r.sales_types!='Sell' or not r.executed or not props.at[int(r.property_id),'E foreclosure']:continue
        seller=int(r.seller_id);book=cm.states['mort_loans'][0,:,seller].copy();debt=book.sum()
        recovery=min(float(r.price_or_rent),debt)
        # All property collateral is pooled because source loans lack property IDs.
        remaining_owned=(props['Corresponding Owner Household ID']==seller).any()
        loss=0. if remaining_owned else debt-recovery
        reduction=recovery+loss
        factor=1-reduction/debt if debt>0 else 1.
        cm.states['mort_loans'][:,:,seller]*=factor
        repayments[seller]+=recovery;losses[seller]+=loss;surpluses[seller]+=float(r.price_or_rent)-recovery
        if debt>0:by_bank+=book/debt*loss
        if not remaining_owned:
            h.states['E_foreclosure_queue'][seller]=False
            for key in ('E_principal_arrears','E_interest_arrears'):
                if key in cm.states:cm.states[key][1,:,seller]=0.
    cm._record_writeoff(float(losses.sum()),by_bank=by_bank)
    h.states['E_mortgage_writeoff']=losses;h.states['E_foreclosure_repayment']=repayments;h.states['E_foreclosure_surplus']=surpluses
    return repayments
