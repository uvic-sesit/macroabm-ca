"""F continuation decision and complete source/seed comparisons, without fitting."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from fe_gates import constrained_slope,firm_gate,planned_investment_gate

HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/FE'
RUNS=OUT/'serial'


def main():
    baseline=pd.read_csv(HERE/'outputs/IFE/summary.csv').query('quarters==12').set_index('seed')
    summary=pd.read_csv(OUT/'summary.csv').query('quarters==12').set_index('seed')
    quarterly=pd.read_csv(OUT/'quarterly.csv').query('quarters==12')
    decisions=[];groups=[];leverage=[];defaults=[];plans=[]
    for seed in range(3):
        p=RUNS/f'iv-ACDpAIF_q12_s{seed}'
        q=quarterly[quarterly.seed==seed].sort_values('quarter')
        b=baseline.loc[seed];s=summary.loc[seed]
        old_loss=b.firm_loan_losses+b.overdraft_losses
        new_loss=s.firm_loan_losses+s.overdraft_losses
        slope=constrained_slope(q.constrained_share)
        calibration=pd.read_csv(p/'investment_calibration.csv')
        plan0=calibration.target.sum()
        decisions.append(dict(seed=seed,initial_planned_investment=plan0,
            investment_gate_pass=planned_investment_gate(plan0),
            baseline_firm_losses=old_loss,firm_losses=new_loss,firm_loss_reduction=1-new_loss/old_loss,
            gate_F=firm_gate(s.max_accounting_error,new_loss,old_loss),
            constrained_slope=slope,constrained_slope_pp_per_quarter=100*slope,
            household_check_pass=slope<=0,Q12_constrained_share=s.Q12_constrained_share,
            Q12_cash_saving=s.Q12_cash_saving,Q12_GDP=s.Q12_GDP,bank_losses=s.bank_losses,
            recapitalisation=s.recapitalisation,max_accounting_error=s.max_accounting_error))
        x=pd.read_csv(p/'constraint_diagnosis.csv');x['seed']=seed;groups.append(x)
        plan=x.groupby('quarter')[['planned_consumption','planned_investment']].sum();plan['seed']=seed
        plans.append(plan.reset_index())
        l=pd.read_csv(p/'firm_leverage.csv');l['seed']=seed
        l['overdraft']=np.maximum(0.,-l.deposits);leverage.append(l)
        f=pd.read_csv(p/'firms.csv');f['seed']=seed;defaults.append(f[f.failed])
    decision=pd.DataFrame(decisions)
    decision.to_csv(OUT/'gates_and_comparison.csv',index=False)
    (OUT/'continuation.json').write_text(json.dumps(dict(
        planned_investment_gate_pass=bool(decision.investment_gate_pass.all()),
        gate_F_pass=bool(decision.gate_F.all()),
        household_check_pass=bool(decision.household_check_pass.all()),
        start_E=bool(decision.gate_F.all() and decision.household_check_pass.all()),
        material_loss_threshold='At least 25% lower, declared before 12Q outcomes',
        parameters=dict(firm_distress_periods=3,firm_collateral_haircut=.2,
            status='Provisional assumptions, not estimated Canadian parameters')),
        indent=2)+'\n')
    diagnosis=pd.concat(groups,ignore_index=True)
    nums=[c for c in diagnosis.select_dtypes('number') if c not in ['seed','quarter','decile']]
    for keys,label in [(['seed','quarter','diagnosis'],'mechanism'),
                       (['seed','quarter','decile','diagnosis'],'decile'),
                       (['seed','quarter','asset_band','diagnosis'],'assets')]:
        diagnosis.groupby(keys)[nums].sum().to_csv(OUT/f'constraint_{label}.csv')
    l=pd.concat(leverage,ignore_index=True)
    for keys,label in [(['seed','quarter'],'national'),(['seed','quarter','industry'],'industry')]:
        g=l.groupby(keys)[['debt','capital','GOS','deposits','overdraft']].sum()
        g['debt_to_capital']=g.debt/g.capital
        g['debt_to_annualised_GOS']=g.debt/(4*g.GOS)
        g['total_bank_credit']=g.debt+g.overdraft
        g['credit_to_capital']=g.total_bank_credit/g.capital
        g['credit_to_annualised_GOS']=g.total_bank_credit/(4*g.GOS)
        g.to_csv(OUT/f'leverage_{label}.csv')
    f=pd.concat(defaults,ignore_index=True)
    columns=['loan_debt','overdraft_cancelled','retained_contract','retained_loan','retained_overdraft',
             'recovery_cash','service_shortfall','collateral_capacity']
    if len(f):
        g=f.groupby(['seed','quarter','industry']).agg(defaults=('firm','size'),**{k:(k,'sum') for k in columns})
        g.to_csv(OUT/'firm_defaults_detail.csv')
    else:
        pd.DataFrame(columns=['seed','quarter','industry','defaults']+columns).to_csv(OUT/'firm_defaults_detail.csv',index=False)
    pd.concat(plans,ignore_index=True).to_csv(OUT/'planned_household_spending.csv',index=False)
    # Initial GOS is independent of financing interest; use the same physical
    # input/output/wage/tax initial state for old/new debt denominators.
    initial=pd.read_csv(RUNS/'iv-ACDpAIF_q12_s0/initial_firm_leverage.csv')
    debt=pd.read_csv(OUT/'initial_firm_debt.csv').merge(initial[['region','firm','GOS']],on=['region','firm'],validate='one_to_one')
    g=debt.groupby('industry')[['debt_before','debt_after','capital','GOS','consolidation_equity_credit','scope_equity_adjustment']].sum()
    codes=json.loads((HERE/'outputs/pre_D3_checks/industry_mapping.json').read_text())
    g.insert(0,'industry_code',[codes[str(i)] for i in g.index])
    for version in ('before','after'):
        g[f'debt_capital_{version}']=g[f'debt_{version}']/g.capital
        g[f'debt_annualised_GOS_{version}']=g[f'debt_{version}']/(4*g.GOS)
    g.to_csv(OUT/'initial_industry_bridge.csv')
    print(decision.to_string(index=False))


if __name__=='__main__':main()
