"""Independent FB data experiment; leave every unexplained GDP residual visible."""
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from macro_data import DataWrapper
from macro_data.processing.synthetic_firms.canadian_firm_accounts import reconcile_country,finite_initial_unit_costs
from macro_data.processing.synthetic_firms.qe_gdp_bridge import gdp_bridge
from qe_baseline import PICKLE,PICKLE_SHA256
TARGET=ROOT/'dev/pkl_files/io2022_household_f_cfc_qe_bridge_2026_10_25.pkl'
OBS=ROOT.parent/'macroabm-io2022/canonical/VA_tax_output_basic.csv'
OUT=HERE/'outputs/QE/bridge'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if TARGET.exists():raise FileExistsError('Do not overwrite an earlier build')
    assert sha(PICKLE)==PICKLE_SHA256
    data=DataWrapper.init_from_pickle(PICKLE);observed=pd.read_csv(OBS,index_col=0)
    OUT.mkdir(parents=True,exist_ok=True);rows=[];regions=[]
    # Recorded t0 macro accounts are unchanged by subsequent closure installation.
    initial=pd.read_csv(HERE/'outputs/QE/runs/C_base_q12_s0/headline.csv').query('quarter==0').set_index('region')
    for name,c in data.synthetic_countries.items():
        if not str(name).startswith('CAN_'):continue
        name=str(name);f=c.firms;d=f.firm_data;obs=observed.loc[[name+'|'+j for j in data.industries]]
        financial=d[['Debt','Deposits','Equity']].to_numpy().copy();capital=f.capital_inputs_stock.copy()
        acquisitions=f.initial_capital_purchases.copy();oldtax=float(c.central_government.central_gov_data['Taxes on Production'].iloc[0])
        bridge=reconcile_country(c,obs)
        inactive=bridge['new_output']<=1e-3;d['Source inactive holder']=inactive[d.Industry.to_numpy(int)]
        f.set_additional_initial_conditions(c.industry_data,c.banks,c.credit_market.longterm_loans,c.credit_market.shortterm_loans,c.tax_data)
        costs=d['Total Wages Paid'].to_numpy()+f.used_intermediate_inputs.sum(axis=1)+f.used_capital_inputs.sum(axis=1)+d['Taxes paid on Production'].to_numpy()
        d['Unit Costs']=finite_initial_unit_costs(d.Production.to_numpy(),costs)
        g=c.central_government.central_gov_data;newtax=d['Taxes paid on Production'].sum()
        newcorp=d['Corporate Taxes Paid'].sum()+c.banks.bank_data['Corporate Taxes Paid'].sum();oldcorp=float(g['Corporate Taxes'].iloc[0])
        for field,delta in [('Taxes on Production',newtax-oldtax),('Taxes on Products',newtax-oldtax),('Corporate Taxes',newcorp-oldcorp),('Revenue',newtax-oldtax+newcorp-oldcorp)]:g[field]+=delta
        np.testing.assert_array_equal(d[['Debt','Deposits','Equity']],financial)
        np.testing.assert_array_equal(f.capital_inputs_stock,capital)
        np.testing.assert_array_equal(f.initial_capital_purchases,acquisitions)
        gos=(obs.gross_operating_surplus+obs.gross_mixed_income).to_numpy()*1e6/4
        wages=(obs.wages_salaries+obs.employers_social_contributions).to_numpy()*1e6/4
        intermediate=f.used_intermediate_inputs.sum(axis=1)
        result=gdp_bridge(bridge['new_output'].sum(),intermediate.sum(),bridge['product_tax'].sum(),wages.sum(),gos.sum(),bridge['other_tax'].sum(),
            float(g[['VAT','Capital Formation Taxes','Export Taxes']].sum(axis=1).iloc[0]),
            initial.loc[name,'real_rent']+initial.loc[name,'imputed_rent'],initial.loc[name,'gdp_expenditure'])
        regions.append(dict(region=name,**{k:float(v) for k,v in result.items()},input_product_tax=bridge['product_tax'].sum(),other_production_tax=bridge['other_tax'].sum(),row_column_adjustment=bridge['sales_row_statistical_discrepancy'].sum()))
        for i,r in d.iterrows():
            j=int(r.Industry);output=float(r.Production*r.Price)
            modelgos=output-f.used_intermediate_inputs[i].sum()-r['Total Wages Paid']-r['Taxes paid on Production']
            rows.append(dict(region=name,industry=data.industries[j],firm=i,output=output,source_inactive=bool(inactive[j]),debt=r.Debt,
                unit_cost=r['Unit Costs'],price=r.Price,CFC=f.used_capital_inputs[i].sum(),IO_GOS=gos[j],model_GOS=modelgos,
                margin_gap_pp=100*(modelgos-gos[j])/output if output>1e-3 else 0.,
                above_price_nonnegative_GOS=bool(output>1e-3 and r['Unit Costs']>r.Price+1e-8 and gos[j]>=0)))
    pd.DataFrame(rows).to_csv(OUT/'firm_bridge.csv',index=False);pd.DataFrame(regions).to_csv(OUT/'GDP_bridge.csv',index=False)
    data.save(TARGET);assert sha(PICKLE)==PICKLE_SHA256
    meta=dict(source=str(PICKLE),source_sha256=PICKLE_SHA256,new_pickle=str(TARGET),new_pickle_sha256=sha(TARGET),
        checked_UTC=datetime.now(timezone.utc).isoformat(),source_table='2022 provincial detailed SUT, 36-10-0478 mapped canonical OECD50',
        vectors='PRM100000/200000/300000/400000/500000/600000/700000/800000',
        source_files={str(p):sha(p) for p in [OBS,OBS.parent/'SCHEMA.json',ROOT.parent/'macroabm-io2022/config/concordance_statcan_to_oecd50.csv']},
        note='CFC-only accepted source; preserve acquisitions, capital and financial stocks. Signed producer taxes update only corresponding fiscal terms. No invented buyer, inventory, trade or cash plug; expenditure residual retained. Zero-source producers retain debts and stocks as inactive holders. This is an unaccepted data experiment until all regional GDP/cost gates pass.')
    (OUT/'provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta,indent=2))

if __name__=='__main__':main()
