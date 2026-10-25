"""Independent canonical identities from frozen git CSVs, not pipeline check results."""
import json
import numpy as np,pandas as pd
from prepare_sg import BENCH,OUT,sha
from build_sg import raw_table,sales
from qe_baseline import PICKLE
from macro_data import DataWrapper

def main():
    v=pd.read_csv(BENCH/'canonical/VA_tax_output_basic.csv',index_col=0);old=pd.read_csv(BENCH/'before/canonical/VA_tax_output_basic.csv',index_col=0)
    z=pd.read_csv(BENCH/'canonical/Z_intermediate_basic.csv',index_col=0);fd=pd.read_csv(BENCH/'canonical/FD_by_source_and_category_basic.csv',header=[0,1],index_col=0)
    va_fields=['wages_salaries','employers_social_contributions','gross_mixed_income','gross_operating_surplus','tax_production','subsidy_production']
    VA=v[va_fields].sum(axis=1);regions=[n for n in v.index.str.split('|').str[0].unique() if n.startswith('CAN_')];rc=[];gdp=[]
    row=z.sum(axis=1)+fd.sum(axis=1);column=z.sum(axis=0).reindex(v.index)+VA+v.net_product_tax_intermediate
    for cell in v.index:
        if not cell.startswith('CAN_'):continue
        rc.append(dict(cell=cell,row_M=float(row[cell]),column_M=float(column[cell]),gap_M=float(row[cell]-column[cell]),output_basic_M=float(v.loc[cell,'output_basic']),output_gap_M=float(row[cell]-v.loc[cell,'output_basic'])))
    allregions=z.index.str.split('|').str[0]
    for r in regions:
        mask=allregions==r;others=~mask;finaldest=fd.columns.get_level_values(0)==r
        exports=z.loc[mask,z.columns.str.split('|').str[0]!=r].to_numpy().sum()+fd.loc[mask,~finaldest].to_numpy().sum()
        imports=z.loc[others,z.columns.str.split('|').str[0]==r].to_numpy().sum()+fd.loc[others,finaldest].to_numpy().sum()
        final=fd.loc[:,finaldest].to_numpy().sum();ptax=v.loc[v.index.str.startswith(r+'|'),'net_product_tax_intermediate'].sum()
        production=row.loc[mask].sum()-z.loc[:,z.columns.str.split('|').str[0]==r].to_numpy().sum()-ptax
        income=VA.loc[mask].sum();expenditure=final+exports-imports-ptax
        gdp.append(dict(region=r,production_basic_M=production,income_basic_M=income,expenditure_basic_M=expenditure,production_gap_M=production-income,expenditure_gap_M=expenditure-income))
    pd.DataFrame(rc).to_csv(OUT/'canonical_row_column.csv',index=False);pd.DataFrame(gdp).to_csv(OUT/'canonical_GDP_basic.csv',index=False)
    d=DataWrapper.init_from_pickle(PICKLE);codes=list(d.industries);comparisons=[]
    for prefix in ['before/','']:
        raw=raw_table(prefix);s=sales(raw,codes);can=s.index.get_level_values(0)!='ROW';columns=raw.columns.get_level_values(1).isin(codes);intermediate=raw.loc[raw.index.get_level_values(1).isin(codes),columns].sum(axis=0);tax=raw.loc[('TOTAL','Taxes Less Subsidies'),columns]
        valueadded=s*4-intermediate.reindex(s.index).fillna(0)-tax.reindex(s.index).fillna(0)
        comparisons.append(dict(vintage='main' if prefix else 'balanced',reader_sales_B=float(4*s.loc[can].sum()/1e9),reader_VA_B=float(valueadded.loc[can].sum()/1e9),international_exports_B=float(raw.loc[(raw.index.get_level_values(0)!='ROW')&raw.index.get_level_values(1).isin(codes),'ROW'].to_numpy().sum()/1e9),international_imports_B=float(raw.loc['ROW',raw.columns.get_level_values(0).isin([str(n) for n in d.all_country_names if str(n).startswith('CAN_')])].to_numpy().sum()/1e9)))
    pd.DataFrame(comparisons).to_csv(OUT/'compatibility_before_after.csv',index=False)
    reexports=pd.read_csv(BENCH/'canonical/reexports_by_province_commodity_basic.csv');removed=reexports.reexports_imported_excluded.sum()/1e3;change=comparisons[0]['international_exports_B']-comparisons[1]['international_exports_B']
    can=v.index.str.startswith('CAN_');va_old=old.loc[can,va_fields].to_numpy();va_new=v.loc[can,va_fields].to_numpy()
    result=dict(canonical_row_column_max_M=float(pd.DataFrame(rc).gap_M.abs().max()),canonical_GDP_max_gap_M=float(pd.DataFrame(gdp)[['production_gap_M','expenditure_gap_M']].abs().to_numpy().max()),canonical_VA_components_unchanged=bool(np.array_equal(va_old,va_new)),GDP_basic_B=float(VA.loc[can&~v.index.str.startswith('CAN_CE|')].sum()/1e3),canonical_output_basic_change_B=float((v.loc[can,'output_basic']-old.loc[can,'output_basic']).sum()/1e3),intermediate_net_product_tax_B=float(v.loc[can,'net_product_tax_intermediate'].sum()/1e3),excluded_reexports_B=float(removed),domestic_margin_kept_B=float(reexports.reexports_domestic_margin_kept.sum()/1e3),international_export_fall_B=change,reexport_export_difference_B=float(change-removed),compatibility_VA6_gap_B=float(comparisons[1]['reader_VA_B']-VA.loc[can&~v.index.str.startswith('CAN_CE|')].sum()/1e3),signed_other_tax_B=float((v.loc[can&~v.index.str.startswith('CAN_CE|'),'tax_production']+v.loc[can&~v.index.str.startswith('CAN_CE|'),'subsidy_production']).sum()/1e3))
    assert result['canonical_row_column_max_M']<1e-3 and result['canonical_GDP_max_gap_M']<1e-3
    assert result['canonical_VA_components_unchanged'] and abs(result['reexport_export_difference_B'])<1e-5
    (OUT/'source_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
