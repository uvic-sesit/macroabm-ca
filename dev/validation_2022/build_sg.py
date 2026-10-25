"""FS/FS_T: input-isolated IO substitution, preserving accepted non-IO inputs."""
from pathlib import Path
import json,copy
import numpy as np,pandas as pd
from macro_data import DataWrapper
from macro_data.processing.synthetic_firms.sut_source_update import rescale_output_units,net_surplus_gate
from macro_data.processing.synthetic_firms.canadian_firm_accounts import finite_initial_unit_costs
from macro_data.readers.io_tables.icio_reader import ICIOReader,normalise_iot
from qe_baseline import PICKLE,PICKLE_SHA256
from prepare_sg import HERE,ROOT,BENCH,OUT,sha
ALIASES={'C17T18':'C17_18','C24a':'C24A','C24b':'C24B','C30a':'C301','C30b':'C302T309','J62T63':'J62_63'}
def raw_table(prefix=''):
    return pd.read_csv(BENCH/(prefix+'compatibility/compat_icio_2022_can_provinces.csv'),header=[0,1],index_col=[0,1]).rename(index=ALIASES,columns=ALIASES,level=1)*1e6
def sales(x,codes):
    return x.loc[x.index.get_level_values(1).isin(codes),x.columns!=('TOTAL','Output')].sum(axis=1)/4
def target(arm):return ROOT/f'dev/pkl_files/io2022_{arm.lower()}_sg_v3_2026_10_25.pkl'
def main():
    assert sha(PICKLE)==PICKLE_SHA256
    oldraw=raw_table('before/');newraw=raw_table();source=DataWrapper.init_from_pickle(PICKLE);codes=list(source.industries)
    oldsales=sales(oldraw,codes);newsales=sales(newraw,codes);obs=pd.read_csv(BENCH/'canonical/VA_tax_output_basic.csv',index_col=0)
    for arm in ['FS','FS_T']:
        if target(arm).exists():raise FileExistsError(target(arm))
        data=copy.deepcopy(source);rows=[];regional=[]
        for name,c in data.synthetic_countries.items():
            name=str(name);f=c.firms;d=f.firm_data;v=c.industry_data['industry_vectors'];ids=d.Industry.to_numpy(int)
            financial=d[['Debt','Deposits','Equity']].copy();capital=f.capital_inputs_stock.copy();initial=f.initial_capital_purchases.copy();hh=c.population.household_data.copy(deep=True);bank=c.banks.bank_data.copy(deep=True)
            delta=(newsales.loc[name]-oldsales.loc[name]).reindex(codes).to_numpy();before=v['Output in LCU'].to_numpy().copy();new=before+delta
            old,ratio=rescale_output_units(c,new)
            new=v['Output in LCU'].to_numpy()
            d['Source inactive holder']=new[ids]<=1e-3
            # The explicit VA6 row is not reader-implied residual VA.
            # The balanced source leaves observed VA6 unchanged.
            cells=[(name,i) for i in codes]
            va_delta=(newraw.loc[('TOTAL','Value Added'),cells]-oldraw.loc[('TOTAL','Value Added'),cells]).to_numpy()/4
            for k in ['Value Added in LCU','Value Added in USD']:v[k]=v[k].to_numpy()+va_delta
            assert np.allclose(v['Value Added in LCU'],source.synthetic_countries[name].industry_data['industry_vectors']['Value Added in LCU'],rtol=0,atol=.001)
            export_delta=(newraw.loc[name,'ROW'].sum(axis=1)-oldraw.loc[name,'ROW'].sum(axis=1)).reindex(codes).to_numpy()/4
            for k in ['Exports in LCU','Exports in USD','Exports in LCU to ROW','Exports in USD to ROW']:v[k]=v[k].to_numpy()+export_delta
            o=obs.loc[[name+'|'+i for i in codes]];other=(o.tax_production+o.subsidy_production).to_numpy()*1e6/4
            oldrate=v['Taxes Less Subsidies Rates'].to_numpy().copy()
            paid_before=d['Taxes paid on Production'].sum()
            if arm=='FS_T':
                product=v['Taxes Less Subsidies in LCU'].to_numpy().copy()
                v['Other Production Taxes Net of Subsidies in LCU']=other;v['Product Taxes on Intermediate Inputs in LCU']=product
                v['Taxes Less Subsidies Rates']=np.divide(product+other,new,out=np.zeros_like(new),where=new>0)
            else:
                # Preserve tax amounts when the unit of output changes.
                v['Taxes Less Subsidies Rates']=np.divide(oldrate*old,new,out=np.zeros_like(new),where=new>0)
            f.set_additional_initial_conditions(c.industry_data,c.banks,c.credit_market.longterm_loans,c.credit_market.shortterm_loans,c.tax_data)
            costs=d['Total Wages Paid'].to_numpy()+f.used_intermediate_inputs.sum(axis=1)+f.used_capital_inputs.sum(axis=1)+d['Taxes paid on Production'].to_numpy()
            d['Unit Costs']=finite_initial_unit_costs(d.Production.to_numpy(),costs)
            g=c.central_government.central_gov_data;taxdelta=d['Taxes paid on Production'].sum()-paid_before;corpdelta=d['Corporate Taxes Paid'].sum()+c.banks.bank_data['Corporate Taxes Paid'].sum()-g['Corporate Taxes'].iloc[0]
            for k in ['Taxes on Production','Taxes on Products']:g[k]+=taxdelta
            g['Corporate Taxes']+=corpdelta;g['Revenue']+=taxdelta+corpdelta
            pd.testing.assert_frame_equal(financial,d[['Debt','Deposits','Equity']]);np.testing.assert_array_equal(capital,f.capital_inputs_stock);np.testing.assert_array_equal(initial,f.initial_capital_purchases);pd.testing.assert_frame_equal(hh,c.population.household_data);pd.testing.assert_frame_equal(bank,c.banks.bank_data)
            output=(d.Production*d.Price).to_numpy();sourcegos=(o.gross_operating_surplus+o.gross_mixed_income).to_numpy()*1e6/4;CFC=f.used_capital_inputs.sum(axis=1);modelgos=output-f.used_intermediate_inputs.sum(axis=1)-d['Total Wages Paid'].to_numpy()-d['Taxes paid on Production'].to_numpy()
            gap,above=net_surplus_gate(output,d.Price.to_numpy(),d['Unit Costs'].to_numpy(),CFC,sourcegos[ids])
            for i in range(len(d)):
                j=ids[i];rows.append(dict(arm=arm,region=name,industry=codes[j],firm=i,old_output=old[j],new_output=output[i],output_change=delta[j],old_VA=float(source.synthetic_countries[name].industry_data['industry_vectors']['Value Added in LCU'].iloc[j]),new_VA=float(v['Value Added in LCU'].iloc[j]),observed_VA=float(o.iloc[j][['wages_salaries','employers_social_contributions','gross_operating_surplus','gross_mixed_income','tax_production','subsidy_production']].sum()*1e6/4),old_GOS=float(old[j]-source.synthetic_countries[name].firms.used_intermediate_inputs[i].sum()-d['Total Wages Paid'].iloc[i]-source.synthetic_countries[name].firms.firm_data['Taxes paid on Production'].iloc[i]),new_GOS=modelgos[i],observed_GOS=sourcegos[j],CFC=CFC[i],exports=float(v['Exports in LCU to ROW'].iloc[j]),export_change=export_delta[j],net_margin=(d.Price.iloc[i]-d['Unit Costs'].iloc[i])/d.Price.iloc[i],margin_gap_pp=gap[i],above_price_nonnegative_NOS=bool(above[i]),inherited_floor=bool(oldsales.loc[(name,codes[j])]<=0 and old[j]>0),signed_other_tax=other[j]))
            regional.append(dict(region=name,tax_change=taxdelta,corporate_tax_change=corpdelta,output_change=delta.sum(),export_change=export_delta.sum()))
        # Updated international trade weights use the new source flows, not old export shares.
        flow=newraw.copy();flow=flow.loc[flow.index.get_level_values(1).isin(codes)];flow=flow.loc[:,flow.columns.get_level_values(0)!='TOTAL']
        # Only these shares use the reader; no GFCF split or national rescale is performed.
        reader=ICIOReader(flow,[str(n) for n in data.all_country_names if str(n)!='ROW'],codes,{},2022)
        data.origin_trade_proportions=reader.get_origin_trade_proportions();data.destination_trade_proportions=reader.get_destination_trade_proportions()
        row=data.synthetic_rest_of_the_world
        # Transfer the same source IO delta to the external counterparty.
        # Source row prices/exchange rate remain unchanged.
        canadian_rows=(newraw.index.get_level_values(0)!='ROW')&newraw.index.get_level_values(1).isin(codes)
        row_import_delta=(newraw.loc[canadian_rows,'ROW'].sum(axis=1)-oldraw.loc[canadian_rows,'ROW'].sum(axis=1)).groupby(level=1).sum().reindex(codes).to_numpy()/4
        old_imports=row.row_data['Imports in USD'].to_numpy().copy()
        row.row_data['Imports in USD']=old_imports+row_import_delta
        row.row_data['Imports in LCU']+=row_import_delta*row.row_data['Price in LCU'].to_numpy()/row.row_data['Price in USD'].to_numpy()
        assert np.allclose(row.row_data['Imports in USD'].to_numpy()-source.synthetic_rest_of_the_world.row_data['Imports in USD'].to_numpy(),row_import_delta,atol=.001,rtol=1e-12)
        frame=pd.DataFrame(rows);frame.to_csv(OUT/f'{arm}_firm_bridge.csv',index=False);pd.DataFrame(regional).to_csv(OUT/f'{arm}_fiscal_bridge.csv',index=False)
        data.save(target(arm));meta=dict(arm=arm,source_sha256=PICKLE_SHA256,new_pickle=str(target(arm)),new_pickle_sha256=sha(target(arm)),source_provenance=json.loads((BENCH/'source_provenance.json').read_text()),financial_household_bank_capital_and_acquisitions_exact=True,method='Clone accepted F_CFC; apply source IO sales/export deltas, preserve physical inputs and CFC and rescale output-unit coefficients; preserve inherited empty-sector floors. FS_T adds signed D29/D39 amounts only; counterpart fiscal terms updated.',margin_passed=bool(frame.margin_gap_pp.abs().max()<=1),above_price_passed=bool(not frame.above_price_nonnegative_NOS.any()),max_margin_gap_pp=float(frame.margin_gap_pp.abs().max()),above_price_exceptions=int(frame.above_price_nonnegative_NOS.sum()))
        (OUT/f'{arm}_build_provenance.json').write_text(json.dumps(meta,indent=2)+'\n');print(arm,'margin',meta['max_margin_gap_pp'],'above-price',meta['above_price_exceptions'],flush=True)
    assert sha(PICKLE)==PICKLE_SHA256
if __name__=='__main__':main()
