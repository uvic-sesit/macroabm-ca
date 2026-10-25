"""One CIS-donor allocation candidate, preserving source regional income budgets."""
import json,hashlib,sys
from pathlib import Path
import numpy as np,pandas as pd
from hi_income_audit import cis_households,SOURCE,OUT,BENCH,sha
from macro_data import DataWrapper
from macro_data.processing.synthetic_population.cis_cash_allocation import normalized_weights,conserve_payroll
TARGET=SOURCE.with_name('io2022_household_f_cfc_cisallocation_hi_2026_10_25.pkl')
def donors(values,weights,source,mask):
    a=np.asarray(values);order=np.argsort(a,kind='stable');cdf=(np.cumsum(np.asarray(weights)[order])-.5*np.asarray(weights)[order])/sum(weights)
    z=source[mask].sort_values('income',kind='stable');w=z.weight.to_numpy();quant=(np.cumsum(w)-.5*w)/w.sum();which=np.searchsorted(quant,cdf).clip(0,len(z)-1);ids=np.empty(len(a),int);ids[order]=z.index.to_numpy()[which];return ids

def main():
    if TARGET.exists():raise FileExistsError(TARGET)
    cis=cis_households().reset_index(drop=True);d=DataWrapper.init_from_pickle(SOURCE);rows=[];checks=[]
    codes={'CAN_NL':10,'CAN_PE':11,'CAN_NS':12,'CAN_NB':13,'CAN_QC':24,'CAN_ON':35,'CAN_MB':46,'CAN_SK':47,'CAN_AB':48,'CAN_BC':59}
    for name,c in d.synthetic_countries.items():
        name=str(name)
        if not name.startswith('CAN_'):continue
        h=c.population.household_data;i=c.population.individual_data;n=len(h);original=h.copy(deep=True)
        weights=np.full(n,c.scale);income=h['Validated Income'].to_numpy();employed=i['Activity Status'].to_numpy()==1;hh=i['Corresponding Household ID'].to_numpy(int);workers=np.bincount(hh[employed],minlength=n)
        business=h['Value of Self-Employment Businesses'].to_numpy()>0;chosen=np.zeros(n,int);fallback=[]
        for labour in [False,True]:
            for owner in [False,True]:
                ix=np.flatnonzero((workers>0)==labour);ix=ix[business[ix]==owner]
                if not len(ix):continue
                mask=(cis.wages>0)==labour;mask&=(cis.self_employment>0)==owner
                regional=mask&(cis.PROV==codes.get(name,-1))
                if regional.any():mask=regional
                elif not mask.any():mask=(cis.wages>0)==labour;fallback.append('no joint business/labour donor: use labour cell')
                if not mask.any():mask=np.ones(len(cis),bool);fallback.append('no labour donor: national pool')
                chosen[ix]=donors(income[ix],weights[ix],cis,mask)
        selected=cis.loc[chosen].reset_index(drop=True)
        w,L,payfallback=conserve_payroll(hh,i['Corresponding Firm ID'].to_numpy(),employed,i['Employee Income'].to_numpy(),i['Labour Inputs'].to_numpy(),np.maximum(0,selected.wages.to_numpy()))
        i['Employee Income']=w;i['Labour Inputs']=L;i['Income']=w+i['Income from Unemployment Benefits'].to_numpy()
        h['Employee Income']=np.bincount(hh,weights=w,minlength=n)
        # Public transfers use public GTR (never private pension receipts); public budget unchanged.
        gov=normalized_weights(selected.government_transfers.to_numpy());assert gov.any()
        h['Regular Social Transfers']=gov*original['Regular Social Transfers'].sum();h['CIS government allocation']=gov
        inv=normalized_weights(selected.investment.to_numpy());inv=inv if inv.any() else normalized_weights(original['Income from Financial Assets'].to_numpy())
        h['Income from Financial Assets']=inv*original['Income from Financial Assets'].sum()
        h['CIS mixed allocation']=np.maximum(0,selected.self_employment.to_numpy())
        h['CIS dividend allocation']=np.maximum(0,selected.investment.to_numpy())
        h['CIS pension allocation']=np.maximum(0,selected.private_pensions.to_numpy())
        # Never create recipients if a region has no supported donor for a D2 component.
        for col,fallbackcol in [('CIS mixed allocation','Value of Self-Employment Businesses'),('CIS dividend allocation','Wealth in Financial Assets'),('CIS pension allocation','Voluntary Pension')]:
            if h[col].sum()==0:h[col]=original[fallbackcol].to_numpy();fallback.append(col+' unsupported: original shares')
        c.population.set_household_income()
        changed={'Income','Employee Income','Regular Social Transfers','Income from Financial Assets'}
        for col in original.columns:
            if col not in changed:pd.testing.assert_series_equal(h[col],original[col])
        for col in changed:assert np.isclose(h[col].sum(),original[col].sum(),rtol=1e-12,atol=.001),(name,col)
        c.cis_allocation_provenance=dict(method='CIS household donor within labour/business-support cell, regional if available, stable income-rank match; fixed regional component totals; per-employer payroll conservation. No residual household-income target.',fallback=fallback,payroll_fallback_firms=payfallback)
        rows.append(dict(region=name,households=n*c.scale,source_income=original.Income.sum()*4,new_income=h.Income.sum()*4,payroll_fallbacks=len(payfallback),donor_fallback=';'.join(fallback)))
    d.save(TARGET);pd.DataFrame(rows).to_csv(OUT/'cis_allocation_build.csv',index=False)
    (OUT/'cis_allocation_provenance.json').write_text(json.dumps(dict(source=str(SOURCE),source_sha256=sha(SOURCE),new_pickle=str(TARGET),new_pickle_sha256=sha(TARGET),cis_source=json.loads((BENCH/'cash_concept.json').read_text()),stock_columns_exact=True,all_regional_component_totals_exact=True,rule='One source-defined candidate. No adjustment after its first gate measurement.'),indent=2)+'\n');print(TARGET,flush=True)
if __name__=='__main__':main()
