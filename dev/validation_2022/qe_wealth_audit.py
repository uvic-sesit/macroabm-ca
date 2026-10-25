"""Read-only deposits-only SFS sensitivity; no wealth term enters arm Q."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from build_buffer_reference import SOURCE,weighted_median
from macromodel.country.buffer_stock import opening_debt_service
HERE=Path(__file__).resolve().parent


def build_reference():
    out=HERE/'benchmarks/QE';d=pd.read_csv(SOURCE)
    income=d.PEFATINC.to_numpy(float);w=d.PWEIGHT.to_numpy(float)
    mask=np.isfinite(income)&(income<99999999)&np.isfinite(w)&(w>0)
    d=d[mask];income=income[mask];w=w[mask];L=d.PWASTDEP.clip(lower=0).to_numpy(float)
    order=np.argsort(income,kind='stable');r=np.empty(len(w));r[order]=np.cumsum(w[order])/w.sum()
    decile=np.minimum(10,np.ceil(10*r)).astype(int);ages=d.PAGEMIEG.to_numpy(int);rows=[]
    for q in range(1,11):
        for a in range(8):
            cell=(decile==q)&((ages==a) if a else True);pos=cell&(income>0)
            rows.append(dict(income_decile=q,age_band=a,b_quarters=weighted_median(4*L[pos]/income[pos],w[pos]),fallback_buffer_CAD=weighted_median(L[cell],w[cell])))
    pd.DataFrame(rows).to_csv(out/'sfs_deposit_buffers.csv',index=False)
    meta=dict(table='SFS 2023 economic-family PUMF 13M0006X',vector='PWASTDEP, PEFATINC, PWEIGHT, PAGEMIEG (no vector IDs)',
        date=datetime.now(timezone.utc).isoformat(),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        extract_sha256=hashlib.sha256((out/'sfs_deposit_buffers.csv').read_bytes()).hexdigest(),
        method='Same weighted medians, income deciles, age bands, family weights and fallback definition as BE, replacing L solely by PWASTDEP. 2023 family-vs-model-household scope gap retained.')
    (out/'sfs_deposit_provenance.json').write_text(json.dumps(meta,indent=2)+'\n')


def capture(sim):
    broad=pd.read_csv(HERE/'benchmarks/BE/sfs_liquid_buffers.csv').set_index(['income_decile','age_band'])
    deposit=pd.read_csv(HERE/'benchmarks/QE/sfs_deposit_buffers.csv').set_index(['income_decile','age_band'])
    countries=list(sim.countries.values());income=np.concatenate([c.households.ts.current('income')/c.scale for c in countries])
    weights=np.concatenate([np.full(len(c.households.ts.current('income')),c.scale) for c in countries])
    order=np.argsort(income,kind='stable');r=np.empty(len(weights));r[order]=np.cumsum(weights[order])/weights.sum()
    decile=np.minimum(10,np.ceil(10*r)).astype(int);start=0;rows=[]
    for c in countries:
        h=c.households;cl=c.household_closure;n=len(h.ts.current('income'));q=decile[start:start+n];start+=n
        ids=c.individuals.states['Corresponding Household ID'];pay=c.individuals.ts.current('income');ages=c.individuals.states['Age'];a=np.zeros(n)
        for j in range(n):
            members=np.flatnonzero(ids==j)
            if len(members):a[j]=ages[members[np.argmax(pay[members])]]
        band=np.where(a>0,np.searchsorted([25,35,45,55,65,80],a,side='right')+1,0)
        receipts=h.ts.current('income')-h.ts.current('income_financial_assets')+cl.planned_mixed+cl.planned_dividends+cl.planned_transfers
        service=opening_debt_service([c.credit_market.states[k] for k in ('cons_loans','mort_loans')],h.ts.current('wealth_deposits'),c.banks.ts.current('overdraft_rate_on_household_deposits')[h.states['Corresponding Bank ID']])
        y=receipts-service-h.ts.current('rent');D=np.maximum(0.,h.ts.current('wealth_deposits'))
        L=D+np.maximum(0.,h.ts.current('wealth_other_financial_assets')-h.states['protected_pension_assets'])
        for label,ref,assets in [('deposits_plus_OFA',broad,L),('deposits_only',deposit,D),('deposits_only_fixed_broad_buffer',broad,D)]:
            b=np.array([ref.loc[(int(x),int(z)),'b_quarters'] for x,z in zip(q,band)])
            fallback=np.array([ref.loc[(int(x),int(z)),'fallback_buffer_CAD']*c.scale for x,z in zip(q,band)])
            gap=assets-np.where(y>0,b*y,fallback)
            rows.append(dict(region=str(c.country_name),definition=label,L=assets.sum(),target=(assets-gap).sum(),gap=gap.sum(),hypothetical_kappa_gap=.01*gap.sum(),C_target=3778455e5))
    return pd.DataFrame(rows)

if __name__=='__main__':build_reference()
