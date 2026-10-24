"""Reproducible B gates, quarterly evidence and industry accounting diagnosis."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/BE'
CODES=json.loads((HERE/'outputs/pre_D3_checks/industry_mapping.json').read_text())


def gate(slope,saving,error):
    return bool(error<=1e-8 and slope<=.25 and abs(saving+.6)<=5)


def main():
    summaries=[];quarterly=[];costs=[];classes=[];resolutions=[];losses=[]
    for manifest in sorted(OUT.glob('*/manifest.json')):
        meta=json.loads(manifest.read_text());p=manifest.parent
        if meta['quarters']!=12:continue
        keys={k:meta[k] for k in ('arm','variant','seed')}
        x=pd.read_csv(p/'outcomes.csv');q=x.groupby('quarter').sum(numeric_only=True)
        q['cash_saving_pct']=100*(1-q.consumption/q.cash_DI)
        q['constrained_pct']=100*q.constrained_households/q.represented_households
        q['C_target_gap_pct']=100*(q.consumption/meta['initial_quarterly_C_target']-1)
        q['planned_investment']=q.investment+q.investment_cut
        q['min_resolution_ratio']=x.groupby('quarter').min_resolution_ratio.min()
        q['min_capital_ratio']=x.groupby('quarter').min_capital_ratio.min()
        slope=float(np.polyfit(np.arange(4,13),q.loc[4:12,'constrained_pct'],1)[0])
        summary=dict(**keys,constrained_slope_pp=slope,Q12_saving_pct=q.loc[12,'cash_saving_pct'],
            Q12_constrained_pct=q.loc[12,'constrained_pct'],Q12_GDP=q.loc[12,'gdp'],Q12_consumption=q.loc[12,'consumption'],
            Q12_household_income=q.loc[12,'household_income'],
            accounting_error=meta['max_accounting_error'],gate_passed=gate(slope,q.loc[12,'cash_saving_pct'],meta['max_accounting_error']))
        for key in ('household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation',
                    'firm_payouts','asset_liquidation','consumption_cut','investment_cut'):
            summary[key]=q[key].sum()
        summaries.append(summary)
        for k,v in keys.items():q[k]=v
        quarterly.append(q.reset_index())
        f=pd.read_csv(p/'firm_costs.csv')
        f['industry_code']=f.industry.astype(str).map(CODES)
        for k,v in keys.items():f[k]=v
        # The reported industry unit costs are output-weighted, not firm means.
        f['sales_value']=f.price*f.output
        f['expected_price_value']=f.price_without_noise*f.output
        f['price_previous_value']=f.price_previous*f.output
        f['negative_profit_output']=f.output*(f.profit<0)
        cols=['output','sales_value','intermediates','wages','taxes','depreciation','GOS','IO_GOS','profit',
              'capacity','inventory','demand','expected_price_value','price_previous_value','negative_profit_output']
        industry=f.groupby(['quarter','industry_code'])[cols].sum()
        industry['price']=industry.sales_value/industry.output.replace(0,np.nan)
        for c in ('intermediates','wages','taxes','depreciation'):
            industry[c+'_per_unit']=industry[c]/industry.output.replace(0,np.nan)
        industry['unit_cost']=industry[['intermediates','wages','taxes','depreciation']].sum(axis=1)/industry.output.replace(0,np.nan)
        industry['capacity_use']=industry.output/industry.capacity.replace(0,np.nan)
        industry['expected_price']=industry.expected_price_value/industry.output.replace(0,np.nan)
        industry['realised_noise_price_effect']=industry.price/industry.expected_price-1
        for k,v in keys.items():industry[k]=v
        costs.append(industry.reset_index())
        group=pd.read_csv(p/'constraint_diagnosis.csv')
        for k,v in keys.items():group[k]=v
        classes.append(group)
        for name,container in [('resolutions.csv',resolutions),('firms.csv',losses)]:
            frame=pd.read_csv(p/name)
            for k,v in keys.items():frame[k]=v
            container.append(frame)
    for name,frames in [('quarterly',quarterly),('industry_costs',costs),('constraint_diagnosis',classes),
                         ('resolution_log',resolutions),('firm_events',losses)]:
        if frames:pd.concat(frames,ignore_index=True).to_csv(OUT/f'{name}.csv',index=False)
    result=pd.DataFrame(summaries);result.to_csv(OUT/'summary.csv',index=False)
    if len(result):print(result[['arm','variant','seed','constrained_slope_pp','Q12_saving_pct','gate_passed']].to_string(index=False))


if __name__=='__main__':main()
