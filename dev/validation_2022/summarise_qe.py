"""Frozen QE share gates and headline expenditure decomposition; no tuning."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/QE'


def share_gate(model,reference):
    model=np.asarray(model,float);reference=np.asarray(reference,float)
    return bool(np.isfinite(model).all() and np.all(np.abs(model/reference-1)<=.15+1e-12))


def main():
    bench=json.loads((HERE/'benchmarks/B2/distribution_provenance.json').read_text())
    headline=[];changes=[];decomposition=[];distributions=[];gates=[];quarterly=[];e_metrics=[]
    for p in sorted((OUT/'runs').glob('*_q12_s*/manifest.json')):
        m=json.loads(p.read_text());arm=m['arm'];seed=m['seed'];directory=p.parent
        if m['max_accounting_error']>1e-8:continue
        if arm=='E' and m.get('variant')!='complete':continue
        h=pd.read_csv(directory/'headline.csv');n=h.groupby('quarter').sum(numeric_only=True)
        for t,r in n.iterrows():
            headline.append(dict(arm=arm,seed=seed,quarter=t,**r.to_dict(),implicit_GDP_PPI=n.loc[t,'gdp']/n.loc[t,'gdp_PPI_deflated']))
        for key in ['gdp','gdp_PPI_deflated','C','C_CPI_deflated','household_account_C','I','I_CFPI_deflated','employment']:
            changes.append(dict(arm=arm,seed=seed,metric=key,Q0=n.loc[0,key],Q12=n.loc[12,key],change_pct=100*(n.loc[12,key]/n.loc[0,key]-1)))
        changes.append(dict(arm=arm,seed=seed,metric='implicit_GDP_PPI',Q0=n.loc[0,'gdp']/n.loc[0,'gdp_PPI_deflated'],Q12=n.loc[12,'gdp']/n.loc[12,'gdp_PPI_deflated'],change_pct=100*((n.loc[12,'gdp']/n.loc[12,'gdp_PPI_deflated'])/(n.loc[0,'gdp']/n.loc[0,'gdp_PPI_deflated'])-1)))
        adjusted=n.loc[0,'gdp']-n.loc[0,'expenditure_unallocated']
        changes.append(dict(arm=arm,seed=seed,metric='GDP_PPI_scope_adjusted_t0_diagnostic',Q0=adjusted,Q12=n.loc[12,'gdp_PPI_deflated'],change_pct=100*(n.loc[12,'gdp_PPI_deflated']/adjusted-1)))
        changes.append(dict(arm=arm,seed=seed,metric='GDP_PPI_Q1_to_Q12',Q0=n.loc[1,'gdp_PPI_deflated'],Q12=n.loc[12,'gdp_PPI_deflated'],change_pct=100*(n.loc[12,'gdp_PPI_deflated']/n.loc[1,'gdp_PPI_deflated']-1)))
        # The residual is the identified t0 housing-memo addition; subsequent
        # IO-housing GDP excludes both rent memos. Do not pretend those are new C.
        for key,sign in [('C',1),('G',1),('I',1),('inventories',1),('X',1),('M',-1),('expenditure_unallocated',1)]:
            value=sign*(n.loc[12,key]-n.loc[0,key])
            decomposition.append(dict(arm=arm,seed=seed,component=key,change_CAD=value,contribution_pp=100*value/n.loc[0,'gdp']))
        check=sum(r['change_CAD'] for r in decomposition if r['arm']==arm and r['seed']==seed)
        assert np.isclose(check,n.loc[12,'gdp_expenditure']-n.loc[0,'gdp_expenditure'],rtol=1e-10,atol=.1)
        x=pd.read_csv(directory/'consumption_quintiles.csv')
        for scheme,field in [('DHEA_equivalised_DI','primary_shares'),('SHS_gross_household_income','secondary_shares')]:
            target=bench[field]
            z=x[x.scheme==scheme].groupby(['quarter','quintile']).sum(numeric_only=True)
            for t,block in z.groupby(level='quarter'):
                for j,(_,r) in enumerate(block.iterrows()):
                    share=r.consumption/block.consumption.sum()
                    distributions.append(dict(arm=arm,seed=seed,quarter=t,scheme=scheme,quintile=j+1,
                        consumption_quarterly_CAD=r.consumption,annualised_CAD=4*r.consumption,annualised_per_HH=4*r.consumption/r.households,
                        share=share,benchmark_share=target[j],relative_deviation=share/target[j]-1))
        if (directory/'outcomes.csv').exists():
            xout=pd.read_csv(directory/'outcomes.csv');agg=xout.groupby('quarter').sum(numeric_only=True)
            for key in ['min_capital_ratio','min_resolution_ratio']:
                agg[key]=xout.groupby('quarter')[key].min()
            agg['constrained_share']=agg.constrained_households/agg.represented_households
            agg['cash_saving_rate']=1-agg.consumption/agg.cash_DI
            for t,r in agg.iterrows():quarterly.append(dict(arm=arm,seed=seed,quarter=t,**r.to_dict()))
            if arm=='Q':
                d=pd.DataFrame(distributions);d=d[(d.arm==arm)&(d.seed==seed)&(d.scheme=='DHEA_equivalised_DI')]
                zg=x.groupby('quarter')[['positive_zero_goods','positive_income']].sum()
                zeros=zg.positive_zero_goods/zg.positive_income
                slope=np.polyfit(range(4,13),100*agg.loc[4:12,'constrained_share'],1)[0]
                g0=share_gate(d[d.quarter==0].share,bench['primary_shares'])
                g1=bool((zeros<.02).all());g2=share_gate(d[d.quarter==12].share,bench['primary_shares'])
                saving=100*agg.loc[12,'cash_saving_rate'];c1=agg.loc[1,'consumption']
                g3=bool(slope<=.25 and -5.6<=saving<=4.4 and c1>=.95*3778455e5 and m['max_accounting_error']<=1e-8)
                gates.append(dict(arm=arm,seed=seed,Q_G0=g0,Q_G1=g1,Q_G2=g2,Q_G3=g3,passed=g0 and g1 and g2 and g3,
                    constrained_slope_pp=slope,Q12_saving_pct=saving,Q1_consumption=c1,max_zero_goods_share=zeros.max(),max_accounting_error=m['max_accounting_error']))
            if arm=='E':
                arrears60=100*n.loc[1:12,'mortgage_60plus']/n.loc[1:12,'mortgage_borrowers']
                arrears90=100*n.loc[1:12,'mortgage_90plus']/n.loc[1:12,'mortgage_borrowers']
                debt_mean=n.household_debt.mean();loss=agg.household_writeoffs.sum()
                annual_ratio=100*(loss/3)/debt_mean
                ratio_pass=.05<=annual_ratio<=.28
                g1=bool(arrears60.between(.125,.5).all() and arrears90.between(.075,.3).all() and ratio_pass)
                q1=agg.loc[1,'household_writeoffs'];later=agg.loc[4:12,'household_writeoffs'].mean()
                g2=bool(q1<=2*later+1e-3);g3=m['max_accounting_error']<=1e-8
                gates.append(dict(arm=arm,seed=seed,E_G1=g1,E_G2=g2,E_G3=g3,passed=g1 and g2 and g3,
                    annual_writeoff_pct=annual_ratio,Q12_60plus_pct=arrears60.loc[12],Q12_90plus_pct=arrears90.loc[12],
                    min_60plus_pct=arrears60.min(),max_60plus_pct=arrears60.max(),Q1_writeoffs=q1,Q4_Q12_mean_writeoffs=later,max_accounting_error=m['max_accounting_error']))
                for t in range(1,13):
                    e_metrics.append(dict(seed=seed,quarter=t,**{k:n.loc[t,k] for k in ['mortgage_borrowers','mortgage_30plus','mortgage_60plus','mortgage_90plus','defaults','foreclosure_pending','foreclosure_sales','mortgage_writeoffs','unsecured_writeoffs','household_overdraft_writeoffs','foreclosure_recoveries','foreclosure_surplus','interest_nonaccrual_memo','household_debt']},mortgage_60plus_pct=arrears60.loc[t],mortgage_90plus_pct=arrears90.loc[t]))
    for name,rows in [('headline_quarterly',headline),('headline_changes',changes),('GDP_expenditure_decomposition',decomposition),('consumption_distribution',distributions),('gates',gates),('quarterly',quarterly),('E_metrics',e_metrics)]:pd.DataFrame(rows).to_csv(OUT/(name+'.csv'),index=False)
    q=[r for r in gates if r['arm']=='Q'];e=[r for r in gates if r['arm']=='E']
    bridge=json.loads((OUT/'bridge/gates.json').read_text()) if (OUT/'bridge/gates.json').exists() else dict(passed=False)
    (OUT/'continuation.json').write_text(json.dumps(dict(Q_passed=len(q)==3 and all(r['passed'] for r in q),E_passed=len(e)==3 and all(r['passed'] for r in e),FB_passed=bridge['passed'],combined_started=False,B2_retest_started=False,Phase_B_started=False,C_dp_005_started=False),indent=2)+'\n')
    print(pd.DataFrame(gates).to_string(index=False))

if __name__=='__main__':main()
