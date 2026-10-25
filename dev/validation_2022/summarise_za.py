"""Read existing run artifacts only; no simulation, fitting or input rebuild."""
import json
import numpy as np,pandas as pd
from prepare_za import HERE,OUT

def main():
    codes=pd.read_csv(OUT/'FS_T_firm_bridge.csv').query("region=='CAN_NL'").sort_values('firm').industry.tolist()
    quarters=[];summary=[];industries=[];regions=[];resolutions=[];components=[]
    for arm in ['F_CFC','FS_T']:
        for seed in range(3):
            run=(HERE/f'outputs/IH/runs/F_CFC_IH_F_CFC_q12_s{seed}' if arm=='F_CFC'
                 else OUT/f'runs/F_CFC_ZA_FS_T_q12_s{seed}')
            o=pd.read_csv(run/'outcomes.csv');h=pd.read_csv(run/'headline.csv')
            a=o.groupby('quarter').sum(numeric_only=True);head=h.groupby('quarter').sum(numeric_only=True)
            inv=pd.read_csv(run/'investment_cells.csv').groupby('quarter')[['planned','realised','CFC']].sum()
            for start in [0,1]:
                delta=(head.loc[12]-head.loc[start])/1e9
                record=dict(arm=arm,seed=seed,start=start,end=12,GDP_change_B=delta.gdp,
                    C_B=delta.C,G_B=delta.G,I_B=delta.I,inventory_B=delta.inventories,
                    X_B=delta.X,minus_M_B=-delta.M)
                record['component_gap_B']=record['GDP_change_B']-sum(record[k] for k in ['C_B','G_B','I_B','inventory_B','X_B','minus_M_B'])
                components.append(record)
            minima=o.groupby('quarter')[['min_capital_ratio','min_resolution_ratio']].min()
            f=pd.read_csv(run/'firms.csv');f['industry_code']=f.industry.map(dict(enumerate(codes)))
            for dimension,collection in [('industry_code',industries),('region',regions)]:
                z=f.groupby(['quarter',dimension])[['loan_debt','overdraft_cancelled','failed','profits','total_wage']].sum().reset_index();z['arm']=arm;z['seed']=seed;collection.append(z)
            for q,r in a.iterrows():
                quarters.append(dict(arm=arm,seed=seed,quarter=int(q),GDP_B=head.loc[q,'gdp']/1e9,
                    GDP_income_B=head.loc[q,'gdp_income']/1e9,GDP_expenditure_B=head.loc[q,'gdp_expenditure']/1e9,
                    C_B=r.consumption/1e9,cash_DI_B=r.cash_DI/1e9,cash_saving_pct=100*(r.cash_DI-r.consumption)/r.cash_DI,
                    HH_investment_B=r.investment/1e9,firm_investment_B=inv.loc[q,'realised']/1e9,
                    firm_planned_investment_B=inv.loc[q,'planned']/1e9,CFC_B=inv.loc[q,'CFC']/1e9,
                    HH_loss_B=r.household_writeoffs/1e9,firm_loan_loss_B=r.firm_loan_losses/1e9,
                    overdraft_loss_B=r.overdraft_losses/1e9,bank_loss_B=r.bank_losses/1e9,
                    recap_B=r.recapitalisation/1e9,min_capital_ratio=minima.loc[q,'min_capital_ratio'],
                    min_resolution_ratio=minima.loc[q,'min_resolution_ratio'],constrained_pct=100*r.constrained_households/r.represented_households,
                    employment=head.loc[q,'employment'],GDP_PPI_deflated_B=head.loc[q,'gdp_PPI_deflated']/1e9,
                    inventory_B=head.loc[q,'inventories']/1e9,X_B=head.loc[q,'X']/1e9,M_B=head.loc[q,'M']/1e9,
                    G_B=head.loc[q,'G']/1e9,I_B=head.loc[q,'I']/1e9))
            m=json.loads((run/'manifest.json').read_text());r=pd.DataFrame(quarters).query('arm==@arm and seed==@seed').set_index('quarter')
            summary.append(dict(arm=arm,seed=seed,GDP_Q0_B=head.loc[0,'gdp']/1e9,GDP_Q1_B=r.loc[1,'GDP_B'],GDP_Q12_B=r.loc[12,'GDP_B'],
                GDP_Q0_Q12_pct=100*(head.loc[12,'gdp']/head.loc[0,'gdp']-1),GDP_Q1_Q12_pct=100*(head.loc[12,'gdp']/head.loc[1,'gdp']-1),
                GDP_real_Q0_Q12_pct=100*(head.loc[12,'gdp_PPI_deflated']/head.loc[0,'gdp_PPI_deflated']-1),
                household_loss_B=r.HH_loss_B.sum(),firm_loan_loss_B=r.firm_loan_loss_B.sum(),overdraft_loss_B=r.overdraft_loss_B.sum(),bank_loss_B=r.bank_loss_B.sum(),recap_B=r.recap_B.sum(),
                Q12_constrained_pct=r.loc[12,'constrained_pct'],Q12_employment=r.loc[12,'employment'],Q12_C_B=r.loc[12,'C_B'],Q12_HH_I_B=r.loc[12,'HH_investment_B'],Q12_firm_I_B=r.loc[12,'firm_investment_B'],max_accounting_error=m['max_accounting_error']))
            rr=pd.read_csv(run/'resolutions.csv');rr['arm']=arm;rr['seed']=seed;resolutions.append(rr)
            z=h.groupby(['region','quarter'])[['gdp','employment','C','G','I','X','M']].sum().unstack('quarter')
            z.columns=['%s_Q%s'%v for v in z.columns];z=z.reset_index();z['arm']=arm;z['seed']=seed;z.to_csv(OUT/f'{arm}_seed{seed}_regional_paths_wide.csv',index=False)
    pd.DataFrame(quarters).to_csv(OUT/'quarterly_comparison.csv',index=False)
    pd.DataFrame(components).to_csv(OUT/'GDP_component_changes.csv',index=False)
    pd.DataFrame(summary).to_csv(OUT/'seed_comparison.csv',index=False)
    pd.concat(industries).to_csv(OUT/'firm_losses_by_industry_quarter.csv',index=False)
    pd.concat(regions).to_csv(OUT/'firm_losses_by_region_quarter.csv',index=False)
    pd.concat(resolutions).to_csv(OUT/'resolution_comparison.csv',index=False)
    f=pd.read_csv(OUT/'FS_T_firm_bridge.csv');values=['old_output','new_output','output_change','old_GOS','new_GOS','signed_other_tax']
    for dim in ['industry','region']:
        f.groupby(dim)[values].sum().mul(4/1e9).reset_index().to_csv(OUT/f'FS_T_t0_{dim}_annual_B.csv',index=False)
    l=pd.read_csv(OUT/'OOH_L_profit_bridge.csv');l.sum(numeric_only=True,min_count=1).rename('annual_CAD').to_csv(OUT/'OOH_L_national.csv')
    print(pd.DataFrame(summary).to_string(index=False),flush=True)

if __name__=='__main__':main()
