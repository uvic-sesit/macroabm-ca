"""Opt-in fixed-reference buffer-stock spending, with one t0 level anchor."""
import numpy as np


def spending(permanent_income,liquid_assets,b,fallback,kappa,level=0.):
    y=np.asarray(permanent_income,float)
    target=np.where(y>0,np.asarray(b)*y,np.asarray(fallback))
    return np.maximum(0.,y+kappa*(np.asarray(liquid_assets)-target)+level)


def wealth_adjustment(y,liquid_assets,b,fallback,kappa,kappa_below=None):
    y=np.asarray(y,float)
    gap=np.asarray(liquid_assets)-np.where(y>0,np.asarray(b)*y,np.asarray(fallback))
    response=np.where(gap<0,kappa if kappa_below is None else kappa_below,kappa)*gap
    return gap,response


def reanchored_spending(y,liquid_assets,b,fallback,c0,kappa,kappa_below=None):
    _,response=wealth_adjustment(y,liquid_assets,b,fallback,kappa,kappa_below)
    return np.maximum(0.,np.asarray(c0)*np.asarray(y)+response)


def propensity_rescale(income_term,wealth_term,weights_L,private_rent,rent,target):
    """One nonnegative multiplicative c0 rescale; never change wealth MPC/b."""
    def total(factor):
        C=np.maximum(0.,factor*income_term+wealth_term)
        return float((C-np.minimum(C*weights_L,private_rent)+rent).sum())
    if not np.isfinite(total(0)) or total(0)>target+1e-3:
        raise ValueError('Wealth term alone exceeds C target; no nonnegative c0 calibration')
    high=1.
    for _ in range(100):
        if total(high)>=target:break
        high*=2
    else:raise ValueError('Consumption target infeasible with fixed wealth response')
    low=0.
    for _ in range(100):
        mid=(low+high)/2
        if total(mid)<target:low=mid
        else:high=mid
    factor=(low+high)/2
    if not np.isclose(total(factor),target,rtol=1e-12,atol=1e-3):raise AssertionError('c0 calibration failed')
    return factor


def calibrated_level(raw,scales,weights_L,private_rent,rent,target):
    """One common CAD/represented-household intercept; preserve derivatives.

    Match goods including VAT, minus D1 private-rent duplicate, plus paid rent.
    This constant level does not change kappa, b or the smoothing coefficient.
    """
    def total(level):
        C=np.maximum(0.,raw+level*scales)
        return float((C-np.minimum(C*weights_L,private_rent)+rent).sum())
    if target<rent.sum():raise ValueError('Consumption target is below senior rent')
    radius=float(np.max(np.abs(raw/scales))+target/scales.sum()+1)
    low,high=-radius,radius
    for _ in range(100):
        mid=(low+high)/2
        if total(mid)<target:low=mid
        else:high=mid
    level=(low+high)/2
    if not np.isclose(total(level),target,rtol=1e-12,atol=1e-3):raise AssertionError('Buffer level calibration failed')
    return level


def private_rents(country):
    h=country.households;p=country.housing_market.states['properties'];rent=np.zeros(len(h.ts.current('income')))
    z=p[(p['Is Owner-Occupied']==0)&(p['Corresponding Inhabitant Household ID']>=0)&(p['Corresponding Owner Household ID']>=0)]
    np.add.at(rent,z['Corresponding Inhabitant Household ID'].to_numpy(int),z.Rent.to_numpy(float))
    return np.minimum(rent,h.ts.current('rent'))


def basket(h):
    C=np.maximum(0.,h.ts.current('target_consumption'))
    total=C.sum(axis=1)
    return np.divide(C,total[:,None],out=np.broadcast_to(h.consumption_weights,C.shape).copy(),where=total[:,None]>0)


def opening_debt_service(contracts, deposits, overdraft_rates):
    """Initial TS interest is unset; read scheduled contractual cash instead."""
    return sum((v[1]+np.minimum(v[0],v[2])).sum(axis=0) for v in contracts)+np.maximum(0.,-deposits)*overdraft_rates


def initialize(countries):
    selected=[c for c in countries if c.configuration.household_closure.buffer_stock_enabled]
    if not selected:return
    modes={c.configuration.household_closure.buffer_stock_reanchor_enabled for c in selected}
    if len(modes)!=1:raise ValueError('Cannot mix B and B2 initial national anchors')
    reanchor=modes.pop()
    income=np.concatenate([c.households.ts.current('income')/c.scale for c in selected])
    scales=np.concatenate([np.full(len(c.households.ts.current('income')),c.scale) for c in selected])
    order=np.argsort(income,kind='stable');rank=np.empty(len(income));rank[order]=np.cumsum(scales[order])/scales.sum()
    decile=np.minimum(10,np.ceil(10*rank)).astype(int)
    raw=[];rents=[];duplicates=[];Lweights=[];start=0;income_terms=[];wealth_terms=[]
    for c in selected:
        h=c.households;cfg=c.configuration.household_closure;closure=c.household_closure;n=len(h.ts.current('income'))
        q=decile[start:start+n];start+=n
        # Highest initial-income member is a proxy for the SFS major recipient.
        ids=c.individuals.states['Corresponding Household ID'];pay=c.individuals.ts.current('income')
        ages=c.individuals.states['Age'];a=np.zeros(n)
        for i in range(n):
            members=np.flatnonzero(ids==i)
            if len(members):a[i]=ages[members[np.argmax(pay[members])]]
        band=np.where(a>0,np.searchsorted([25,35,45,55,65,80],a,side='right')+1,0)
        ref=cfg.buffer_stock_reference
        b=np.array([ref[f'{int(x)}:{int(y)}'][0] for x,y in zip(q,band)])
        fallback=np.array([ref[f'{int(x)}:{int(y)}'][1]*c.scale for x,y in zip(q,band)])
        receipts=(h.ts.initial('income')-h.ts.initial('income_financial_assets')+
                  closure.planned_mixed+closure.planned_dividends+closure.planned_transfers)
        service=opening_debt_service([c.credit_market.states[k] for k in ('cons_loans','mort_loans')],
            h.ts.current('wealth_deposits'),c.banks.ts.current('overdraft_rate_on_household_deposits')[h.states['Corresponding Bank ID']])
        senior=service+h.ts.current('rent')
        y=receipts-senior
        L=np.maximum(0.,h.ts.current('wealth_deposits'))+np.maximum(0.,h.ts.current('wealth_other_financial_assets')-h.states['protected_pension_assets'])
        W=basket(h)
        h.states.update(buffer_stock_b=b,buffer_stock_fallback=fallback,buffer_stock_permanent_income=y.copy(),
            buffer_stock_initial_permanent_income=y.copy(),buffer_stock_decile=q,buffer_stock_age_band=band,
            buffer_stock_basket=W,buffer_stock_initial_receipts=receipts.copy(),buffer_stock_initial_L=L.copy())
        raw.append(y+cfg.buffer_stock_kappa*(L-np.where(y>0,b*y,fallback)))
        if reanchor:
            c0=np.full(n,1-h.states['average_saving_rate'])
            gap,response=wealth_adjustment(y,L,b,fallback,cfg.buffer_stock_kappa,cfg.buffer_stock_kappa_below)
            income_terms.append(c0*y);wealth_terms.append(response)
            h.states.update(buffer_stock_initial_c0=c0,buffer_stock_initial_gap=gap,buffer_stock_initial_wealth_response=response)
        rents.append(h.ts.current('rent'));duplicates.append(private_rents(c) if cfg.rent_offset_enabled else np.zeros(n));Lweights.append(W[:,41])
    targets={c.configuration.household_closure.initial_annual_consumption_benchmark/4 for c in selected}
    if len(targets)!=1:raise ValueError('One national C target required')
    target=targets.pop();rawall=np.concatenate(raw)
    args=(np.concatenate(Lweights),np.concatenate(duplicates),np.concatenate(rents),target)
    factor=propensity_rescale(np.concatenate(income_terms),np.concatenate(wealth_terms),*args) if reanchor else 1.
    level=0. if reanchor else calibrated_level(rawall,scales,*args)
    for c,r,dup in zip(selected,raw,duplicates):
        h=c.households;vat=c.central_government.states['Value-added Tax'];W=h.states['buffer_stock_basket']
        C=np.maximum(0.,r+level*c.scale)
        if reanchor:
            h.states['buffer_stock_c0']=factor*h.states['buffer_stock_initial_c0']
            C=reanchored_spending(h.states['buffer_stock_initial_permanent_income'],h.states['buffer_stock_initial_L'],
                h.states['buffer_stock_b'],h.states['buffer_stock_fallback'],h.states['buffer_stock_c0'],
                c.configuration.household_closure.buffer_stock_kappa,c.configuration.household_closure.buffer_stock_kappa_below)
        h.states['buffer_stock_level']=np.full(len(C),level*c.scale)
        h.states['buffer_stock_calibration']=dict(level_per_household=level,propensity_rescale=factor,national_target=target,
            initial_pre_D1_goods=C.sum(),initial_account_consumption=(C-np.minimum(C*W[:,41],dup)+h.ts.current('rent')).sum(),
            initial_permanent_income=h.states['buffer_stock_permanent_income'].sum(),kappa=c.configuration.household_closure.buffer_stock_kappa,
            smoothing=c.configuration.household_closure.buffer_stock_smoothing)
        initial=C[:,None]*W/(1+vat)
        adjusted=initial.copy();adjusted[:,41]-=np.minimum(C*W[:,41],dup)/(1+vat)
        h.ts.dicts['target_consumption'][-1]=initial
        h.ts.dicts['consumption'][-1]=adjusted.sum(axis=1)
        h.ts.dicts['total_consumption'][-1]=np.array([(1+vat)*adjusted.sum()])
        h.ts.dicts['total_consumption_before_vat'][-1]=np.array([adjusted.sum()])
        h.ts.dicts['industry_consumption'][-1]=adjusted.sum(axis=0)


def apply(country,receipts):
    h=country.households;cfg=country.configuration.household_closure
    senior=h.ts.current('debt_installments')+h.ts.current('rent')+h.ts.current('interest_paid')
    y=(1-cfg.buffer_stock_smoothing)*h.states['buffer_stock_permanent_income']+cfg.buffer_stock_smoothing*(receipts-senior)
    L=np.maximum(0.,h.ts.current('wealth_deposits'))+np.maximum(0.,h.ts.current('wealth_other_financial_assets')-h.states['protected_pension_assets'])
    C=spending(y,L,h.states['buffer_stock_b'],h.states['buffer_stock_fallback'],cfg.buffer_stock_kappa,h.states['buffer_stock_level'])
    if cfg.buffer_stock_reanchor_enabled:
        C=reanchored_spending(y,L,h.states['buffer_stock_b'],h.states['buffer_stock_fallback'],
            h.states['buffer_stock_c0'],cfg.buffer_stock_kappa,cfg.buffer_stock_kappa_below)
    h.states['buffer_stock_permanent_income']=y
    h.states['buffer_stock_liquid_assets']=L
    h.states['buffer_stock_planned_goods']=C
    h.ts.dicts['target_consumption'][-1]=C[:,None]*h.states['buffer_stock_basket']/(1+country.central_government.states['Value-added Tax'])
