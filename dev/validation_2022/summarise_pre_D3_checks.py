"""Reproduce the four diagnostic tables from saved, instrumented runs."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/pre_D3_checks';BASE=OUT/'b1_iv_q12_s0'


def income_bridge():
    f=pd.read_csv(BASE/'income_flows.csv').groupby('quarter').sum(numeric_only=True)
    # Detailed property receipts are disaggregation of 36-10-0112 property income.
    # Rental income is displayed with property for readability but belongs to mixed income in SNA.
    lines=[('compensation','compensation',1378.529,'36-10-0112','v62305952',1),
           ('nonrental mixed income','mixed',97.274,'36-10-0112','v62305955 minus v62305958',1),
           ('rental income (cash model / net actual+imputed SNA)','cash_rent',127.567,'36-10-0112','v62305958',1),
           ('deposit interest received','deposit_interest',17.779,'36-10-0482','v80013650',1),
           ('other direct interest received',None,11.364,'36-10-0482','v80013651',1),
           ('pension/insurance/implicit interest received',None,87.818,'36-10-0482','v80013649 minus v80013650 minus v80013651',1),
           ('dividends','dividends',92.052,'36-10-0482','v80013659',1),
           ('foreign/miscellaneous property income',None,37.575,'36-10-0482','v80013660 plus v80013661',1),
           ('government transfers','gov_transfers',286.670,'36-10-0112','v62305967',1),
           ('corporate transfers','corporate_transfers',121.500,'36-10-0112','v62305966',1),
           ('NPISH/nonresident transfers',None,14.354,'36-10-0112','v62305965 plus v62305971',1),
           ('personal income taxes','income_taxes',348.148,'36-10-0112','v62305976',-1),
           ('government social contributions','social_contributions',131.280,'36-10-0112','v62305978',-1),
           ('other current transfers paid',None,206.503,'36-10-0112','v62305972 minus v62305976 minus v62305978',-1),
           ('interest paid','interest_paid',84.211,'36-10-0112','v62305961',-1)]
    rows=[]
    for t in [0,1]:
        for name,key,bench,table,vector,sign in lines:
            value=float(f.loc[t,key])*4/1e9 if key else 0.
            # t0 has an unfunded financial-income proxy, not realized D2 dividend receipts;
            # initial interest and tax time series are placeholders. Do not interpret those zeros as measured flows.
            if t==0 and key=='interest_paid':value=np.nan
            rows.append(dict(quarter=t,line=name,model_B_per_year=value,benchmark_B_per_year=bench,gap_B_per_year=value-bench,sign=sign,table=table,vector=vector))
        if t==0:
            rows.append(dict(quarter=0,line='unfunded financial-income proxy (initialization only)',
                             model_B_per_year=float(f.loc[0,'financial_income_proxy'])*4/1e9,
                             benchmark_B_per_year=np.nan,gap_B_per_year=np.nan,sign=1,table='none',vector='none'))
        for name,key,bench,vector in [('cash disposable income','cash_DI',1502.340,'v62305981'),('consumption','consumption',1511.382,'v62305982')]:
            value=float(f.loc[t,key])*4/1e9
            rows.append(dict(quarter=t,line=name,model_B_per_year=value if t or name=='consumption' else np.nan,
                             benchmark_B_per_year=bench,gap_B_per_year=value-bench if t or name=='consumption' else np.nan,sign=0,table='36-10-0112',vector=vector))
    bridge=pd.DataFrame(rows);bridge.to_csv(OUT/'income_bridge.csv',index=False)
    q1=bridge[bridge.quarter==1];model=(q1.model_B_per_year*q1.sign).sum();bench=(q1.benchmark_B_per_year*q1.sign).sum()
    assert abs(model-f.loc[1,'cash_DI']*4/1e9)<1e-6
    assert abs(bench-1502.340)<1e-6
    di=model;c=float(f.loc[1,'consumption']*4/1e9);observed=1-1511.382/1502.340
    result=dict(model_Q1_DI=di,model_Q1_C=c,observed_D8_free_saving_pct=100*observed,
                model_Q1_saving_pct=100*(1-c/di),income_gap_effect_pp=100*((1-1511.382/di)-observed),
                spending_gap_effect_pp=100*((1-c/di)-(1-1511.382/di)),initial_booked_income=f.loc[0,'income_booked']*4/1e9,
                initial_C=f.loc[0,'consumption']*4/1e9,initial_FA_proxy=f.loc[0,'financial_income_proxy']*4/1e9)
    (OUT/'income_summary.json').write_text(json.dumps(result,indent=2,default=float))


def cohorts():
    f=pd.read_csv(BASE/'micro/cohort.csv');f['deposits_per_HH']=f.t0_deposit/f.represented;f['nw_per_HH']=f.t0_net_worth/f.represented
    f['age_band']=pd.cut(f.oldest_age,[-np.inf,34,44,54,64,np.inf],labels=['<35','35-44','45-54','55-64','65+'])
    f['deposit_band']=pd.cut(f.deposits_per_HH,[-np.inf,-.01,.01,1000,10000,50000,np.inf],labels=['negative','zero','0-1k','1-10k','10-50k','50k+'])
    f['net_worth_band']=pd.cut(f.nw_per_HH,[-np.inf,-.01,.01,25000,100000,np.inf],labels=['negative','zero','0-25k','25-100k','100k+'])
    f['t0_state']=np.select([(f.t0_net_worth<0)&(f.t0_deposit<0),f.t0_net_worth<0,
                            f.t0_net_worth<f.t0_income],['already insolvent','negative NW, nonnegative deposits','near: 0<=NW<one quarter income'],default='NW>=one quarter income')
    rows=[];bad=f[f.written_off];total=bad.represented.sum();debt=bad.debt.sum()
    for key in ['decile','tenure','age_band','deposit_band','net_worth_band','main_cause','t0_state']:
        for group,g in f.groupby(key,observed=True):
            a=g[g.written_off]
            rows.append(dict(dimension=key,group=str(group),simulated_count=len(a),represented_count=a.represented.sum(),
                             count_share_pct=100*a.represented.sum()/total,group_incidence_pct=100*a.represented.sum()/g.represented.sum(),
                             debt_B=a.debt.sum()/1e9,debt_share_pct=100*a.debt.sum()/debt,group_debt_written_pct=100*a.debt.sum()/g.debt.sum() if g.debt.sum()>0 else 0.))
    pd.DataFrame(rows).to_csv(OUT/'Q1_cohort_groups.csv',index=False)
    result=dict(simulated_count=len(bad),represented_count=total,writeoff_B=debt/1e9,
                already_insolvent_count=bad.loc[(bad.t0_net_worth<0)&(bad.t0_deposit<0),'represented'].sum(),
                negative_NW_at_t0_pct=100*bad.loc[bad.t0_net_worth<0,'represented'].sum()/total,
                t0_NW_B=bad.t0_net_worth.sum()/1e9,Q1_NW_B=bad.net_worth.sum()/1e9,
                initial_deposits_B=bad.t0_deposit.sum()/1e9,final_deposits_B=bad.deposit.sum()/1e9,
                real_asset_change_B=bad.real_asset_change.sum()/1e9,
                overdraft_cause_B={k:bad[k].sum()/1e9 for k in ['spending_OD','service_OD','rent_OD','other_OD']})
    (OUT/'Q1_cohort_summary.json').write_text(json.dumps(result,indent=2,default=float))


def runs():
    summary=[];firmq=[];L=[];writeoffs=[];industry=[];banks=[];Lregions={}
    for path in sorted(OUT.glob('*_q*_s*')):
        if not (path/'manifest.json').exists():continue
        meta=json.loads((path/'manifest.json').read_text());tag=path.name
        f=pd.read_csv(path/'firms.csv');b=pd.read_csv(path/'banks.csv');o=pd.read_csv(path/'outcomes.csv');loans=pd.read_csv(path/'micro/originations.csv')
        if tag=='b1_iv_q12_s0':
            utilities=f[f.region.isin(['CAN_ON','CAN_BC'])&f.industry.eq(27)&f.quarter.isin([7,8,9])].copy()
            utilities['noncash_assets_residual']=utilities.equity+utilities.debt-utilities.deposits
            utilities.to_csv(OUT/'Q9_utilities_balance_bridge.csv',index=False)
        banks.append(b.assign(run=tag))
        for (q,ind),g in f[f.failed].groupby(['quarter','industry']):
            industry.append(dict(run=tag,quarter=q,industry=ind,insolvencies=len(g),
                                 loan_debt_B=g.loan_debt.sum()/1e9,overdraft_loss_B=g.overdraft_cancelled.sum()/1e9))
        audit_path=path/'micro/origination_audit.csv'
        inputs=[path/'micro/cohort.csv',path/'micro/originations.csv']
        if not audit_path.exists() or audit_path.stat().st_mtime<max(p.stat().st_mtime for p in inputs):
            cohort=pd.read_csv(inputs[0])
            audit=loans.merge(cohort[['region','household','represented']],on=['region','household'],validate='many_to_one')
            for key in ['value','deposit','overdraft','net_worth','income','installment_debt','existing_service','loss']:
                audit[key+'_per_household_CAD']=audit[key]/audit.represented
            audit.to_csv(audit_path,index=False)
        total=loans.value.sum();loss=loans.loss.sum()
        last=o[o.quarter.eq(o.quarter.max())]
        flows=pd.read_csv(path/'income_flows.csv')
        flows=flows[flows.quarter.eq(flows.quarter.max())].sum(numeric_only=True)
        summary.append(dict(run=tag,new_lending_B=total/1e9,new_principal_written_B=loss/1e9,loss_pct=100*loss/total if total else 0.,
                            orig_value_eventually_written_pct=100*loans.loc[loans.ever_loss,'value'].sum()/total if total else 0.,
                            lent_to_overdrawn_pct=100*loans.loc[loans.overdraft>0,'value'].sum()/total if total else 0.,
                            lent_to_negative_NW_pct=100*loans.loc[loans.net_worth<0,'value'].sum()/total if total else 0.,
                            total_HH_writeoffs_B=o.writeoffs.sum()/1e9,total_bank_losses_B=o.bank_losses.sum()/1e9,
                            min_bank_equity_B=b.equity.min()/1e9,negative_bank_observations=int((b.equity<0).sum()),
                            last_GDP_B=last.gdp.sum()/1e9,last_debt_B=last.debt.sum()/1e9,
                            last_saving_pct=100*(1-flows.consumption/flows.cash_DI),
                            accounting_error=meta['max_accounting_error']))
        for q,g in f.groupby('quarter'):
            a=g[g.failed];r=dict(run=tag,quarter=q,insolvencies=len(a),firm_debt_B=a.loan_debt.sum()/1e9,overdraft_loss_B=a.overdraft_cancelled.sum()/1e9,
                               profits_failed_B=a.profits.sum()/1e9,industry_counts=json.dumps(a.industry.value_counts().sort_index().to_dict()),
                               bank_losses_B=o[o.quarter==q].bank_losses.sum()/1e9,HH_writeoffs_B=o[o.quarter==q].writeoffs.sum()/1e9)
            for key in ['requested_dividends','paid_dividends','requested_mixed','paid_mixed','requested_transfers','paid_transfers','cash_before_payout','cash_after_payout']:
                r[key+'_B']=g[key].sum()/1e9 if key in g else 0.
            if 'paid_dividends' in g:
                r['dividends_paid_current_loss_makers_B']=g.loc[g.profits<0,'paid_dividends'].sum()/1e9
                r['all_payouts_cash_short_B']=g.loc[g.cash_before_payout<0,['paid_dividends','paid_mixed','paid_transfers']].sum().sum()/1e9
                r['created_overdraft_count']=int(((g.cash_before_payout>=0)&(g.cash_after_payout<-.01)).sum())
            firmq.append(r)
        Lregions[tag]=pd.read_csv(path/'L.csv')
        z=Lregions[tag].groupby('quarter').sum(numeric_only=True)
        for q,row in z.iterrows():
            r=row.to_dict();r.update(run=tag,quarter=q,price=row.sales/row.quantity);L.append(r)
        for q,g in o.groupby('quarter'):writeoffs.append(dict(run=tag,quarter=q,HH_writeoffs_B=g.writeoffs.sum()/1e9,bank_losses_B=g.bank_losses.sum()/1e9,new_lending_B=g.new_loans.sum()/1e9))
    pd.DataFrame(summary).to_csv(OUT/'run_summary.csv',index=False);pd.DataFrame(firmq).to_csv(OUT/'firm_quarterly.csv',index=False)
    pd.DataFrame(industry).to_csv(OUT/'firm_industry_quarterly.csv',index=False)
    pd.concat(banks,ignore_index=True).to_csv(OUT/'bank_quarterly.csv',index=False)
    l=pd.DataFrame(L);l.to_csv(OUT/'L_quarterly.csv',index=False);pd.DataFrame(writeoffs).to_csv(OUT/'writeoffs_quarterly.csv',index=False)
    effects=[]
    for label,seeds in [('b1',[0]),('fixed',[0,1,2]),('buyers',[0]),('final',[0,1,2])]:
        for seed in seeds:
            a=l[l.run.eq(f'{label}_iv_q12_s{seed}')].set_index('quarter');b=l[l.run.eq(f'{label}_d1_q12_s{seed}')].set_index('quarter')
            if a.empty or b.empty:continue
            for q in a.index:
                p0,p1=a.loc[q,'price'],b.loc[q,'price'];q0,q1=a.loc[q,'quantity'],b.loc[q,'quantity']
                ra=Lregions[f'{label}_iv_q12_s{seed}'];rb=Lregions[f'{label}_d1_q12_s{seed}']
                rr=ra[ra.quarter.eq(q)].merge(rb[rb.quarter.eq(q)],on='region',suffixes=('_0','_1'),validate='one_to_one')
                rp0=np.divide(rr.sales_0,rr.quantity_0,out=rr.price_min_0.to_numpy().copy(),where=rr.quantity_0>0)
                rp1=np.divide(rr.sales_1,rr.quantity_1,out=rr.price_min_1.to_numpy().copy(),where=rr.quantity_1>0)
                effects.append(dict(label=label,seed=seed,quarter=q,base_sales_B=a.loc[q,'sales']/1e9,D1_sales_B=b.loc[q,'sales']/1e9,
                                    delta_sales_B=(p1*q1-p0*q0)/1e9,delta_pct=100*((p1*q1)/(p0*q0)-1),
                                    price_effect_B=(p1-p0)*(q0+q1)/2/1e9,quantity_effect_B=(q1-q0)*(p0+p1)/2/1e9,
                                    regional_price_effect_B=((rp1-rp0)*(rr.quantity_0+rr.quantity_1)/2).sum()/1e9,
                                    regional_quantity_effect_B=((rr.quantity_1-rr.quantity_0)*(rp0+rp1)/2).sum()/1e9,
                                    price_base=p0,price_D1=p1,inventory_base_B_units=a.loc[q,'inventory']/1e9,inventory_D1_B_units=b.loc[q,'inventory']/1e9))
    pd.DataFrame(effects).to_csv(OUT/'L_price_quantity_effects.csv',index=False)


if __name__=='__main__':
    income_bridge();cohorts();runs()
    # Microdata are local only, but all are traceable by hashes in this manifest.
    files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix in ['.csv','.json','.xml','.log'] and p.name!='result_manifest.json']
    (OUT/'result_manifest.json').write_text(json.dumps({str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
