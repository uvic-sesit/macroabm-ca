"""All B2 gates, source-specific distributions, seed/sensitivity evidence."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import summarise_b2_core as core
from b2_gates import assess
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/B2';RUNS=OUT/'final'


def main():
    core.main()
    summary=pd.read_csv(RUNS/'summary.csv').rename(columns={'gate_passed':'legacy_saving_slope_passed'})
    q=pd.read_csv(RUNS/'quarterly.csv');bench=json.loads((HERE/'benchmarks/B2/distribution_provenance.json').read_text())
    comparisons=[];zeros=[];rows=[];initial=[]
    for mpath in sorted(RUNS.glob('*/manifest.json')):
        m=json.loads(mpath.read_text());p=mpath.parent
        if m['quarters']!=12 or m['arm']!='B2':continue
        key=dict(arm=m['arm'],variant=m['variant'],seed=m['seed'])
        sub=summary[(summary.arm==m['arm'])&(summary.variant==m['variant'])&(summary.seed==m['seed'])].iloc[0]
        x=pd.read_csv(p/'consumption_quintiles.csv').groupby(['scheme','quarter','quintile']).sum(numeric_only=True).reset_index()
        for scheme,benchmark in [('DHEA_equivalised_DI',bench['primary_shares']),('SHS_gross_household_income',bench['secondary_shares'])]:
            a=x[x.scheme==scheme].copy();a['share']=a.consumption/a.groupby('quarter').consumption.transform('sum')
            a['benchmark_share']=a.quintile.map(dict(zip(range(1,6),benchmark)))
            a['relative_deviation']=a.share/a.benchmark_share-1
            a['off_over_15_pct']=a.relative_deviation.abs()>.15
            a['annual_model_consumption_per_household']=4*a.consumption/a.households
            for k,v in key.items():a[k]=v
            comparisons.append(a)
        a=x[x.scheme=='DHEA_equivalised_DI'].groupby('quarter').sum(numeric_only=True)
        a['zero_positive_share']=a.positive_zero_goods/a.positive_income
        for k,v in key.items():a[k]=v
        zeros.append(a.reset_index())
        comp=comparisons[-2]
        refpath=HERE/'outputs/FE/serial'/f'iv-ACDpAIF_q12_s{m["seed"]}'/'outcomes.csv'
        ref=pd.read_csv(refpath).query('quarter==12')
        gates=assess(a.zero_positive_share.to_numpy(),sub.constrained_slope_pp,sub.Q12_saving_pct,
            m['Q1_cash_consumption'],m['initial_quarterly_C_target'],comp.relative_deviation.to_numpy(),
            sub.Q12_consumption,sub.Q12_GDP,ref.consumption.sum(),ref.gdp.sum(),m['max_accounting_error'])
        r=dict(**sub.to_dict(),**gates,max_zero_positive_pct=100*a.zero_positive_share.max(),
            max_DHEA_relative_deviation_pct=100*comp.relative_deviation.abs().max(),
            max_SHS_relative_deviation_pct=100*comparisons[-1].relative_deviation.abs().max(),
            Q12_C_F_ref=ref.consumption.sum(),Q12_GDP_F_ref=ref.gdp.sum(),
            Q12_C_vs_F_pct=100*(sub.Q12_consumption/ref.consumption.sum()-1),
            Q12_GDP_vs_F_pct=100*(sub.Q12_GDP/ref.gdp.sum()-1))
        rows.append(r)
        init=pd.read_csv(p/'buffer_calibration.csv')
        if 'propensity_rescale' in init:
            initial.append(dict(**key,propensity_rescale=init.propensity_rescale.iloc[0],
                initial_C=init.initial_account_consumption.sum(),level_per_household=init.level_per_household.iloc[0]))
    result=pd.DataFrame(rows)
    result.to_csv(OUT/'gates.csv',index=False)
    pd.concat(comparisons,ignore_index=True).to_csv(OUT/'quintile_comparisons.csv',index=False)
    pd.concat(zeros,ignore_index=True).to_csv(OUT/'zero_goods_shares.csv',index=False)
    pd.DataFrame(initial).to_csv(OUT/'initial_calibration.csv',index=False)
    q.to_csv(OUT/'quarterly.csv',index=False)
    base=result[(result.arm=='B2')&(result.variant=='base')]
    continuation=dict(base_seeds=base[['seed','accounting','G1','G2','G3','G4','pass_all']].to_dict('records'),
        start_E=bool(len(base)==3 and base.pass_all.all()),
        step2_household_base='B2' if len(base)==3 and base.pass_all.all() else 'accepted FE arm F',
        phase_B_started=False,C_dp_005_started=False)
    (OUT/'continuation.json').write_text(json.dumps(continuation,indent=2)+'\n')
    (RUNS/'continuation.json').write_text(json.dumps(continuation,indent=2)+'\n')
    print(result[['arm','variant','seed','G1','G2','G3','G4','pass_all']].to_string(index=False))


if __name__=='__main__':main()
