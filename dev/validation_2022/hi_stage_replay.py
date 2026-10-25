"""Controlled stage reconstruction on copies of retained records, not invented historical snapshots."""
import copy,json
from pathlib import Path
import numpy as np,pandas as pd
from hi_income_audit import SOURCE,OUT,summarize
from macro_data import DataWrapper
from macro_data.readers.population_data.canadianized_household_adapter import CIS_INCOME_SHARES_BY_DECILE

def main():
    d=DataWrapper.init_from_pickle(SOURCE);root=Path(__file__).resolve().parents[2];raw=pd.read_csv(root/'dev/io2022/household_prototype/prototype_household_consumption.csv');raw['key']=raw.Income.round(6);labels=raw.groupby('key').income_decile.agg(['min','max']);rows=[];coverage=[];removed=[]
    for name,c in d.synthetic_countries.items():
        if not str(name).startswith('CAN_'):continue
        pop=copy.deepcopy(c.population);h=pop.household_data;lab=labels.reindex(h['Validated Income'].round(6).to_numpy());valid=lab['min'].notna()&(lab['min']==lab['max']);coverage.append(dict(region=str(name),households=len(h)*c.scale,recoverable_source_label_share=valid.mean()))
        if not valid.all():
            # Do not guess a missing original decile: reconstruct only if uniquely recoverable.
            continue
        dec=lab['min'].to_numpy(int);target=h['Validated Income'].to_numpy()*c.scale/4
        h['Regular Social Transfers']=target*np.array([CIS_INCOME_SHARES_BY_DECILE[k][2] for k in dec]);h['Income from Pensions']=target*np.array([CIS_INCOME_SHARES_BY_DECILE[k][1] for k in dec]);h['Income from Financial Assets']=target*np.array([CIS_INCOME_SHARES_BY_DECILE[k][0] for k in dec]);h['Income']=target
        def capture(stage):
            x=pd.DataFrame(dict(weight=c.scale,income=4*h.Income,wages=4*h['Employee Income'],government_transfers=4*(h['Regular Social Transfers']+h['Unemployment Benefits']),private_pensions=4*h['Income from Pensions'],investment=4*(h['Income from Financial Assets']+h['Rental Income from Real Estate']),taxes=np.nan,self_employment=np.nan));x['stage']=stage;return x
        # Income at entry is the original source target; the individual skeleton is held fixed.
        rows.append(capture('replay_before_transfer_fit').assign(region=str(name)))
        pop.set_household_social_transfers(float(c.central_government.central_gov_data['Other Social Benefits'].iloc[0]));pop.set_household_employee_income();pop.set_household_income();rows.append(capture('replay_transfer_fit_and_existing_jobs').assign(region=str(name)))
        pop.reconcile_labour_income();pop.set_household_income();rows.append(capture('replay_validated_residual_reconciliation').assign(region=str(name)))
        employed=pop.individual_data['Activity Status'].to_numpy()==1;before=pop.individual_data['Employee Income'].to_numpy().copy();nonworkers=before[~employed].sum()*4
        pop.renormalise_labour_income_to_firms(c.firms.firm_data['Total Wages'],(1-c.tax_data.employee_social_insurance_tax)*(1-c.tax_data.income_tax));pop.set_household_income();rows.append(capture('replay_per_firm_payroll_restoration').assign(region=str(name)))
        removed.append(dict(region=str(name),residual_wages_on_nonemployed_annual=nonworkers,total_income_before=4*target.sum(),income_after=4*h.Income.sum()))
    pd.DataFrame(coverage).to_csv(OUT/'stage_reconstruction_coverage.csv',index=False)
    if rows:
        f=pd.concat(rows,ignore_index=True);r=[summarize(stage,z) for stage,z in f.groupby('stage')];pd.concat(r).to_csv(OUT/'controlled_stage_reconstruction.csv',index=False)
    pd.DataFrame(removed).to_csv(OUT/'stage_reconstruction_lost_income.csv',index=False)
    print(pd.DataFrame(coverage).to_string(index=False));print('reconstructed regions',len(removed))
if __name__=='__main__':main()
