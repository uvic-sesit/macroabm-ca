from pathlib import Path
import pandas as pd,numpy as np,json,hashlib

root=Path(__file__).resolve().parents[2];arch=root/'dev/validation_2022/outputs/household_corrections/historical'
weights=json.loads((arch/'L_weights.json').read_text())
base=pd.read_csv(arch/'default_s0_households_national.csv').iloc[-1]
ba=pd.read_csv(arch/'default_s0_accounting_regions.csv');fa=ba[ba.t==11].fa_income_unfunded.sum()
result=[]
for arm in ['fixed','income']:
    h=pd.read_csv(arch/f'{arm}_s0_households_national.csv');r=pd.read_csv(arch/f'{arm}_s0_households_regions.csv');a=pd.read_csv(arch/f'{arm}_s0_accounting_regions.csv')
    last=h.iloc[-1];alast=a[a.t==11];direct_d2=alast.hh_distributions.sum()-fa
    removed=0.
    for _,v in r[r.t==11].iterrows():
        w=weights[v.region]
        rents=float(alast.loc[alast.region==v.region,'hh_rent_paid'].iloc[0])
        removed+=(v.consumption_cash-rents)*w/(1-w)
    y0,c0=float(base.cash_disposable_income),float(base.consumption_cash)
    s0=1-c0/y0;s2=1-c0/(y0+direct_d2);s1=1-(c0-removed)/(y0+direct_d2)
    # Q1 has no D3 event (three consecutive distress periods required).
    initial=h.debt.iloc[0]+a[a.t==0].hh_principal.sum()-h.new_credit.iloc[0]
    result.append(dict(arm=arm,old_default_saving_pct=100*s0,D2_direct_pp=100*(s2-s0),
        D1_removed_bundle_pp=100*(s1-s2),deposit_only_direct_pp=0.,
        residual_dynamics_and_propensity_pp=100*(last.cash_saving_rate-s1),final_saving_pct=100*last.cash_saving_rate,
        removed_L_cash_bn=removed/1e9,D2_net_income_replacement_bn=direct_d2/1e9,
        q12_DI_bn=last.cash_disposable_income/1e9,q12_consumption_bn=last.consumption_cash/1e9,
        initial_debt_bn=initial/1e9,principal_bn=a.hh_principal.sum()/1e9,new_credit_bn=h.new_credit.sum()/1e9,
        inferred_household_writeoffs_bn=(initial+h.new_credit.sum()-a.hh_principal.sum()-last.debt)/1e9,
        q12_debt_bn=last.debt/1e9))
out=root/'dev/validation_2022/outputs/household_corrections'
pd.DataFrame(result).to_csv(out/'historical_saving_bridge.csv',index=False)
files=list(arch.glob('*s0_households*csv'))+list(arch.glob('*s0_accounting_regions.csv'))
(out/'historical_sources.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
print(pd.DataFrame(result).to_string(index=False))
