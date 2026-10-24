"""Opt-in fixed-reference buffer-stock spending, with one t0 level anchor."""
import numpy as np


def spending(permanent_income,liquid_assets,b,fallback,kappa,level=0.):
    y=np.asarray(permanent_income,float)
    target=np.where(y>0,np.asarray(b)*y,np.asarray(fallback))
    return np.maximum(0.,y+kappa*(np.asarray(liquid_assets)-target)+level)


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


def initialize(countries):
    selected=[c for c in countries if c.configuration.household_closure.buffer_stock_enabled]
    if not selected:return
    income=np.concatenate([c.households.ts.current('income')/c.scale for c in selected])
    scales=np.concatenate([np.full(len(c.households.ts.current('income')),c.scale) for c in selected])
    order=np.argsort(income,kind='stable');rank=np.empty(len(income));rank[order]=np.cumsum(scales[order])/scales.sum()
    decile=np.minimum(10,np.ceil(10*rank)).astype(int)
    raw=[];rents=[];duplicates=[];Lweights=[];start=0
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
        senior=h.ts.current('debt_installments')+h.ts.current('rent')+h.ts.current('interest_paid')
        y=receipts-senior
        L=np.maximum(0.,h.ts.current('wealth_deposits'))+np.maximum(0.,h.ts.current('wealth_other_financial_assets')-h.states['protected_pension_assets'])
        W=basket(h)
        h.states.update(buffer_stock_b=b,buffer_stock_fallback=fallback,buffer_stock_permanent_income=y.copy(),
            buffer_stock_initial_permanent_income=y.copy(),buffer_stock_decile=q,buffer_stock_age_band=band,
            buffer_stock_basket=W)
        raw.append(y+cfg.buffer_stock_kappa*(L-np.where(y>0,b*y,fallback)))
        rents.append(h.ts.current('rent'));duplicates.append(private_rents(c) if cfg.rent_offset_enabled else np.zeros(n));Lweights.append(W[:,41])
    targets={c.configuration.household_closure.initial_annual_consumption_benchmark/4 for c in selected}
    if len(targets)!=1:raise ValueError('One national C target required')
    target=targets.pop();rawall=np.concatenate(raw)
    level=calibrated_level(rawall,scales,np.concatenate(Lweights),np.concatenate(duplicates),np.concatenate(rents),target)
    for c,r,dup in zip(selected,raw,duplicates):
        h=c.households;vat=c.central_government.states['Value-added Tax'];W=h.states['buffer_stock_basket']
        C=np.maximum(0.,r+level*c.scale)
        h.states['buffer_stock_level']=np.full(len(C),level*c.scale)
        h.states['buffer_stock_calibration']=dict(level_per_household=level,national_target=target,
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
    h.states['buffer_stock_permanent_income']=y
    h.states['buffer_stock_liquid_assets']=L
    h.states['buffer_stock_planned_goods']=C
    h.ts.dicts['target_consumption'][-1]=C[:,None]*h.states['buffer_stock_basket']/(1+country.central_government.states['Value-added Tax'])
