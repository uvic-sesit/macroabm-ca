"""New input only: source IO column output and observed signed D29/D39."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from macro_data import DataWrapper
from macro_data.processing.synthetic_firms.canadian_firm_accounts import reconcile_country,finite_initial_unit_costs
SOURCE=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt.pkl'
TARGET=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt_io_v2.pkl'
IO=ROOT.parent/'macroabm-io2022'
OBS=IO/'canonical/VA_tax_output_basic.csv'
OUT=HERE/'outputs/B2/firm_data'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if TARGET.exists():raise FileExistsError('New-build name already exists; do not overwrite')
    OUT.mkdir(parents=True,exist_ok=True);before=sha(SOURCE);data=DataWrapper.init_from_pickle(SOURCE)
    observed=pd.read_csv(OBS,index_col=0);rows=[];stocks=[];snapshots=[]
    for name,c in data.synthetic_countries.items():
        if not str(name).startswith('CAN_'):continue
        f=c.firms;d=f.firm_data
        obs=observed.loc[[str(name)+'|'+i for i in data.industries]].copy()
        for field in ('Debt','Deposits','Equity'):stocks.append((str(name),field,d[field].to_numpy().copy()))
        snapshots.append((str(name),'capital',f.capital_inputs_stock.copy()))
        snapshots.append((str(name),'intermediate',f.intermediate_inputs_stock.copy()))
        bridge=reconcile_country(c,obs)
        f.set_additional_initial_conditions(c.industry_data,c.banks,c.credit_market.longterm_loans,
            c.credit_market.shortterm_loans,c.tax_data)
        total_cost=d['Total Wages Paid'].to_numpy()+f.used_intermediate_inputs.sum(axis=1)+f.used_capital_inputs.sum(axis=1)+d['Taxes paid on Production'].to_numpy()
        d['Unit Costs']=finite_initial_unit_costs(d.Production.to_numpy(),total_cost)
        if not np.isfinite(d[['Production','Unit Costs','Profits']].to_numpy()).all():raise ValueError('Nonfinite initial firm data')
        c.central_government.update_fields(c.tax_data,c.population,f,c.banks,c.industry_data)
        for i,row in d.iterrows():
            j=int(row.Industry);o=obs.iloc[j]
            model_GOS=row.Production*row.Price-row['Total Wages Paid']-f.used_intermediate_inputs[i].sum()-row['Taxes paid on Production']
            benchmark=(o.gross_operating_surplus+o.gross_mixed_income)*1e6/4
            expected=bridge['new_output'][j]
            rows.append(dict(region=str(name),industry=data.industries[j],firm=i,
                old_output=bridge['old_output'][j],new_output=expected,
                row_demand_statistical_residual=bridge['sales_row_statistical_discrepancy'][j],
                intermediate=f.used_intermediate_inputs[i].sum(),wages=row['Total Wages Paid'],
                input_product_tax=bridge['product_tax'][j],other_production_tax=bridge['other_tax'][j],
                source_GOS=benchmark,model_GOS=model_GOS,
                source_zero_activity=bool(expected<=1e-3),
                margin_gap_pp=100*(model_GOS-benchmark)/expected if expected>1e-3 else 0.))
    for name,field,array in stocks:np.testing.assert_array_equal(data.synthetic_countries[name].firms.firm_data[field],array)
    for name,field,array in snapshots:
        current=getattr(data.synthetic_countries[name].firms,field+'_inputs_stock')
        np.testing.assert_array_equal(current,array)
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'io_cost_bridge.csv',index=False)
    observed.loc[[str(n)+'|'+i for n in data.all_country_names if str(n).startswith('CAN_') for i in data.industries]].to_csv(OUT/'observed_VA_2022.csv')
    if frame.margin_gap_pp.abs().max()>1:raise AssertionError('Observed component bridge fails operating-margin gate')
    data.save(TARGET);assert sha(SOURCE)==before
    provenance=dict(source=str(SOURCE),source_sha256=before,new_pickle=str(TARGET),new_pickle_sha256=sha(TARGET),
        reference='2022 provincial detailed supply-use tables, CAD million annual, PRM100000-PRM800000',
        source_table='Provincial detail basic-price supply-use workbooks underlying StatCan 36-10-0478; mapped OECD50 canonical snapshot',
        vector='PRM100000 product taxes, PRM200000 product subsidies, PRM300000 production taxes, PRM400000 production subsidies, PRM500000 wages, PRM600000 employer contributions, PRM700000 mixed income, PRM800000 GOS',
        local_snapshot_checked_UTC='2026-10-24',
        input_files={str(p):sha(p) for p in [OBS,IO/'canonical/SCHEMA.json',IO/'src/ioqc/stages.py',IO/'config/concordance_statcan_to_oecd50.csv']},
        note='Column output = basic intermediate use + input-product valuation + observed VA. Gross sales-row minus column output remains a named ex-ante IO demand discrepancy; no RAS or fictitious buyer. Source-zero agents remain inactive balance-sheet holders with contracts unchanged. Zero-output unit-cost initialization uses the existing runtime zero convention. No financial stock or employee changed. First unaccepted io.pkl build retained but excluded because its legacy initializer left 0/0 unit costs; v2 is finite.',
        max_margin_gap_pp=float(frame.margin_gap_pp.abs().max()),signed_other_tax_annual=float(4*frame.other_production_tax.sum()),
        retained_sales_row_discrepancy_annual=float(4*frame.row_demand_statistical_residual.sum()))
    (OUT/'io_build_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print('Built',TARGET.name,'max margin gap pp',frame.margin_gap_pp.abs().max())


if __name__=='__main__':main()
