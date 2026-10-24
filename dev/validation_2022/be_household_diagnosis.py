"""Aggregate local micro ledgers; publish group evidence, not household rows."""
from pathlib import Path
import json
import sys
import pandas as pd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
OUT=HERE/'outputs/BE'


def main():
    from macro_data import DataWrapper
    data=DataWrapper.init_from_pickle(HERE.parent/'pkl_files/io2022_household_agreed_bankcap_firmdebt.pkl')
    initial=[]
    for name,c in data.synthetic_countries.items():
        if not str(name).startswith('CAN_'):continue
        h=c.population.household_data
        initial.append(dict(region=str(name),debt=h.Debt.sum(),
            mortgage=h['Outstanding Balance of HMR Mortgages'].sum()+h['Outstanding Balance of Mortgages on other Properties'].sum(),
            unsecured=h['Outstanding Balance of other Non-Mortgage Loans'].sum()))
    pd.DataFrame(initial).to_csv(OUT/'initial_household_debt.csv',index=False)
    groups=[]
    for manifest in sorted(OUT.glob('*/manifest.json')):
        m=json.loads(manifest.read_text());p=manifest.parent
        if m['quarters']!=12:continue
        for t in (1,12):
            frames=[]
            for file in (p/'micro').glob(f'ledger_*_q{t}.csv'):
                x=pd.read_csv(file)
                x['zero_goods_households']=x.households*(x.consumption_VAT<=1e-5)
                x['income_positive_zero_goods']=x.households*((x.consumption_VAT<=1e-5)&(x.income>1e-5))
                x['cash_DI']=x.income-x.interest
                x['consumption_with_rent']=x.consumption_VAT+x.rent
                x['cash_saving']=x.cash_DI-x.consumption_with_rent
                cols=['households','zero_goods_households','income_positive_zero_goods','cash_DI',
                      'consumption_with_rent','cash_saving','investment_CF','asset_liquidation','deposit_change','OFA_change']
                frames.append(x.groupby(['decile','asset_band'])[cols].sum())
            g=pd.concat(frames).groupby(['decile','asset_band']).sum().reset_index()
            for k in ('arm','variant','seed'):g[k]=m[k]
            g['quarter']=t;groups.append(g)
    if groups:pd.concat(groups,ignore_index=True).to_csv(OUT/'household_zero_consumption_diagnosis.csv',index=False)


if __name__=='__main__':main()
