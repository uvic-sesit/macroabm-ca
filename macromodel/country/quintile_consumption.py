"""Opt-in DHEA initial-rank propensities, without a liquid-wealth term."""
import numpy as np
from .buffer_stock import basket, private_rents, propensity_rescale


def ranked_propensities(equivalised_income, weights, ratios):
    income=np.asarray(equivalised_income,float); weights=np.asarray(weights,float)
    ratios=np.asarray(ratios,float)
    if ratios.shape!=(5,) or not np.all(np.isfinite(ratios)) or np.any(ratios<0):
        raise ValueError('Five finite nonnegative DHEA ratios required')
    order=np.argsort(income,kind='stable'); ranks=np.empty(len(income))
    ranks[order]=(np.cumsum(weights[order])-.5*weights[order])/weights.sum()
    return np.interp(ranks,[.1,.3,.5,.7,.9],ratios)


def initial_income(c):
    h=c.households; closure=c.household_closure; cm=c.credit_market
    receipts=h.ts.current('income')-h.ts.current('income_financial_assets')+closure.planned_mixed+closure.planned_dividends+closure.planned_transfers
    deposits=h.ts.current('wealth_deposits'); ids=h.states['Corresponding Bank ID']
    interest=sum(cm.states[k][1].sum(axis=0) for k in ('cons_loans','mort_loans'))
    interest+=np.maximum(0.,-deposits)*c.banks.ts.current('overdraft_rate_on_household_deposits')[ids]
    interest-=np.maximum(0.,deposits)*c.banks.ts.current('interest_rate_on_household_deposits')[ids]
    return receipts-interest


def initialize(countries):
    selected=[c for c in countries if c.configuration.household_closure.quintile_propensity_enabled]
    if not selected:return
    if any(c.configuration.household_closure.buffer_stock_enabled for c in selected):
        raise ValueError('Q and B2 cannot share an initial anchor')
    ys=[]; ranks=[]; weights=[]; baskets=[]; rents=[]; duplicates=[]
    for c in selected:
        h=c.households; y=initial_income(c); n=len(y)
        ids=np.asarray(c.individuals.states['Corresponding Household ID'],int)
        ages=np.asarray(c.individuals.states['Age'])
        adults=np.bincount(ids,weights=(ages>=14),minlength=n)
        kids=np.bincount(ids,weights=(ages<14),minlength=n)
        units=np.maximum(1.,1.+.5*np.maximum(0.,adults-1)+.3*kids)
        ys.append(y);ranks.append(y/c.scale/units);weights.append(np.full(n,c.scale))
        baskets.append(basket(h));rents.append(h.ts.current('rent'));duplicates.append(private_rents(c))
    ratio_sets={tuple(c.configuration.household_closure.quintile_consumption_income_ratios) for c in selected}
    if len(ratio_sets)!=1:raise ValueError('One national DHEA ratio schedule required')
    prop=ranked_propensities(np.concatenate(ranks),np.concatenate(weights),ratio_sets.pop())
    y=np.concatenate(ys); terms=prop*np.maximum(0.,y)
    target=selected[0].configuration.household_closure.initial_annual_consumption_benchmark/4
    factor=propensity_rescale(terms,np.zeros(len(y)),np.concatenate([b[:,41] for b in baskets]),np.concatenate(duplicates),np.concatenate(rents),target)
    start=0
    for c,y,W,dup in zip(selected,ys,baskets,duplicates):
        h=c.households;n=len(y);p=prop[start:start+n]*factor;start+=n
        h.states['quintile_consumption_propensity']=p;h.states['quintile_consumption_basket']=W
        h.states['quintile_consumption_calibration']=dict(common_multiplier=factor,national_target=target)
        vat=c.central_government.states['Value-added Tax'];C=p*np.maximum(0.,y)
        planned=C[:,None]*W/(1+vat); adjusted=planned.copy()
        adjusted[:,41]-=np.minimum(C*W[:,41],dup)/(1+vat)
        h.ts.dicts['target_consumption'][-1]=planned
        for key,val in [('consumption',adjusted.sum(axis=1)),('total_consumption',np.array([(1+vat)*adjusted.sum()])),('total_consumption_before_vat',np.array([adjusted.sum()])),('industry_consumption',adjusted.sum(axis=0))]:h.ts.dicts[key][-1]=val


def apply(c,receipts):
    """Retain F's consumption function/floors; replace its propensity and DI base."""
    h=c.households;income=receipts-h.ts.current('interest_paid')
    old=h.ts.current('expected_income').copy()
    h.ts.dicts['expected_income'][-1]=income
    try:
        target=h.compute_target_consumption(expected_inflation=c.economy.ts.current('estimated_cpi_inflation')[0],
            current_cpi=c.economy.ts.current('cpi')[0],initial_cpi=c.economy.ts.initial('cpi')[0],
            exogenous_total_consumption=0.,per_capita_unemployment_benefits=c.central_government.ts.current('unemployment_benefits_by_individual')[0],
            tau_vat=c.central_government.states['Value-added Tax'],assume_zero_growth=False)
    finally:h.ts.dicts['expected_income'][-1]=old
    h.ts.dicts['target_consumption'][-1]=target
