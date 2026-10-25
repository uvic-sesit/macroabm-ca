"""Aggregate SG evidence without changing a model or source benchmark."""
import json
import numpy as np,pandas as pd
from prepare_sg import HERE,OUT
from macro_data import DataWrapper
from qe_baseline import PICKLE

def main():
    f=pd.concat([pd.read_csv(OUT/f'{arm}_firm_bridge.csv') for arm in ['FS','FS_T']])
    source=DataWrapper.init_from_pickle(PICKLE)
    f['compensation']=[float(source.synthetic_countries[r.region].firms.firm_data['Total Wages Paid'].iloc[r.firm]) for r in f.itertuples()]
    f['old_implied_VA']=f.old_GOS+f.compensation
    f['new_implied_VA']=f.old_implied_VA+f.output_change
    values=['old_output','new_output','output_change','old_VA','new_VA','observed_VA','old_implied_VA','new_implied_VA','old_GOS','new_GOS','observed_GOS','CFC','exports','export_change','signed_other_tax']
    for dim in ['industry','region']:
        f.groupby(['arm',dim])[values].sum().mul(4/1e9).reset_index().to_csv(OUT/f't0_by_{dim}_annual_B.csv',index=False)
    f.loc[f.margin_gap_pp.abs()>1].to_csv(OUT/'margin_exceptions.csv',index=False)
    history=[];losses=[]
    codes=f[f.arm=='FS'].industry.drop_duplicates().tolist()
    for seed in range(3):
        run=HERE/f'outputs/IH/runs/F_CFC_IH_F_CFC_q12_s{seed}';firm=pd.read_csv(run/'firms.csv');firm['industry_code']=firm.industry.map(dict(enumerate(codes)));a=firm.groupby('industry_code')[['loan_debt','overdraft_cancelled','failed']].sum().reset_index();a['seed']=seed;losses.append(a)
        q=pd.read_csv(HERE/'outputs/IH/quarterly.csv');q=q[(q.arm=='F_CFC')&(q.seed==seed)];h=pd.read_csv(run/'headline.csv').groupby('quarter').sum(numeric_only=True);i=pd.read_csv(run/'investment_cells.csv').groupby('quarter').realised.sum();r=q[q.quarter==12].iloc[0]
        history.append(dict(seed=seed,GDP_Q0_Q12_pct=100*(h.loc[12,'gdp']/h.loc[0,'gdp']-1),GDP_Q1_Q12_pct=100*(h.loc[12,'gdp']/h.loc[1,'gdp']-1),household_loss_B=q.household_writeoffs.sum()/1e9,firm_loss_B=q.firm_loan_losses.sum()/1e9,overdraft_loss_B=q.overdraft_losses.sum()/1e9,bank_loss_B=q.bank_losses.sum()/1e9,recapitalisation_B=q.recapitalisation.sum()/1e9,Q12_constrained_pct=100*r.constrained_share,Q12_HH_investment_B=r.investment/1e9,Q12_firm_investment_B=i.loc[12]/1e9,Q12_employment=h.loc[12,'employment']))
    pd.DataFrame(history).to_csv(OUT/'IH_reference_only.csv',index=False)
    loss=pd.concat(losses);loss.to_csv(OUT/'IH_firm_losses_by_seed_industry.csv',index=False);a=loss.groupby('industry_code')[['loan_debt','overdraft_cancelled','failed']].mean().reset_index();a['historic_loss_B']=(a.loan_debt+a.overdraft_cancelled)/1e9
    bridge=f[f.arm=='FS_T'].groupby('industry')[['output_change','old_GOS','new_GOS']].sum().mul(4/1e9).reset_index();a=a.merge(bridge,left_on='industry_code',right_on='industry').sort_values('historic_loss_B',ascending=False);a.to_csv(OUT/'prior_loss_industries_t0_change.csv',index=False)
    c=pd.read_csv(OUT/'CIS_concepts.csv');summary=[]
    for (arm,concept),g in c.groupby(['arm','concept']):
        summary.append(dict(arm=arm,concept=concept,max_absolute_relative_gap_pct=float(100*g.relative_gap.abs().max()),top_share_pct=float(100*g[g.decile==10].model_share.iloc[0]),CIS_top_share_pct=float(100*g[g.decile==10].CIS_share.iloc[0]),top_relative_gap_pct=float(100*g[g.decile==10].relative_gap.iloc[0])))
    pd.DataFrame(summary).to_csv(OUT/'CIS_summary.csv',index=False)
    housing=pd.read_csv(OUT/'housing_national.csv');housing['gap_after_memo_proxy']=housing.gap-housing.memo_proxy;housing['gap_after_all_owner_L_removed']=housing.gap-housing.owner_L;housing['dissaver_reduction_proxy_pp']=100*(housing.C_dissaver_share-housing.C_memo_proxy_dissaver_share);housing.to_csv(OUT/'housing_summary.csv',index=False)
    old=json.loads((OUT/'source_audit.json').read_text());gates=json.loads((OUT/'step1_gates.json').read_text());assert not any(g['passed'] for g in gates.values())
    short=OUT/'short_accounting_execution.json'
    if short.exists():
        for r in json.loads(short.read_text()):
            gates[r['arm']]['accounting_passed']=r['passed']
            gates[r['arm']]['accounting']='Failed before Q1 completes: nonfinite settled-cash/senior-payment guard. No battery pass.' if not r['passed'] else 'Two-quarter battery passed.'
        (OUT/'step1_gates.json').write_text(json.dumps(gates,indent=2)+'\n')
    (OUT/'step_dependencies.json').write_text(json.dumps(dict(step1=gates,step2=dict(started=False,reason='Neither FS nor FS_T passes all unchanged net-surplus cost gates. No FSG build or runs.'),step3=dict(completed=True,read_only=True,exact_imputed_rent_purchase_identification=False),step4=dict(completed=True,read_only=True,no_new_household_build=True),twelve_quarter_runs_started=False,Phase_B_started=False),indent=2)+'\n')
    print(pd.DataFrame(summary).to_string(index=False))
if __name__=='__main__':main()
