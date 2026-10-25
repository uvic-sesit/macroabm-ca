"""FSG source preflight: retain signed product uses and independent inventory flow.

No acquired stock, financial balance, production coefficient or expansion parameter
is changed. Purchaser-price observations supply shares, not a second IO level.
"""
import json,subprocess
import numpy as np,pandas as pd
from macro_data import DataWrapper
from macro_data.processing.synthetic_firms.gfcf_allocation import allocate_product_budget
from prepare_za import ROOT,HERE,OUT,BENCH,IO,sha
from build_za import target,raw_table
from build_firm_cfc_b2 import GEO

TARGET=ROOT/'dev/pkl_files/io2022_fsg_za_v1_2026_10_25.pkl'

def main():
    assert json.loads((OUT/'adoption_final_result.json').read_text())['Step4_authorized']
    if TARGET.exists():raise FileExistsError(TARGET)
    source=target('FS_T');d=DataWrapper.init_from_pickle(source);codes=list(d.industries)
    table=raw_table();raw=HERE/'benchmarks/B2/raw'
    inv=pd.read_csv(raw/'36100096_2022.csv')
    inv=inv[(inv.Prices=='Current prices')&(inv['Flows and stocks']=='Investment')&(inv.Assets=='Total non-residential')].set_index(['GEO','Industry'])
    res=pd.read_csv(raw/'36100099.csv');res=res[(res.REF_DATE==2022)&(res.Prices=='Current prices')&(res['Flows and stocks']=='Investment')&(res.Assets=='Total residential')].set_index('GEO')
    # Preserve the complete source rows and actual vectors used.
    inv.reset_index().to_csv(BENCH/'nonres_investment_2022.csv',index=False)
    res.reset_index().to_csv(BENCH/'residential_investment_2022.csv',index=False)
    name='canonical/product_taxes_final_gross_by_province.csv'
    blob=subprocess.check_output(['git','-c','safe.directory='+IO.as_posix(),'-C',str(IO),'show','d847fb2:'+name])
    taxfile=BENCH/name;taxfile.write_bytes(blob);tax=pd.read_csv(taxfile)
    # Source representation is a prerequisite, before mutating any candidate.
    # Preserve signed entries; a negative IO net use is not a household's
    # nonnegative purchase probability or a documented disposal cash path.
    product_rows=[];scope_rows=[]
    for n,geo in GEO.items():
        fixed=table[(n,'Fixed Capital Formation')].groupby(level=1).sum().reindex(codes).fillna(0)/4
        inventory=table[(n,'Changes in Inventories')].groupby(level=1).sum().reindex(codes).fillna(0)/4
        for code in codes:product_rows.append(dict(region=n,product=code,IO_fixed_quarterly_CAD=fixed[code],inventory_quarterly_CAD=inventory[code],negative_fixed=bool(fixed[code]<0)))
        vals={label:float(inv.loc[(geo,label),'VALUE'])*1e6/4 for label in ['Total all industries','Government sector','Non-profit institutions serving households']}
        residential=float(res.loc[geo,'VALUE'])*1e6/4
        net_tax=tax[(tax.region==n)&(tax.fd_category=='GFCF')]
        net_tax=float((net_tax.gross_product_tax_final-net_tax.gross_product_subsidy_final).sum())*1e6/4
        total=vals['Total all industries']+residential
        sector_amounts=dict(business=vals['Total all industries']-vals['Government sector']-vals['Non-profit institutions serving households'],government=vals['Government sector'],NPISH=vals['Non-profit institutions serving households'],residential=residential)
        for sector,value in sector_amounts.items():scope_rows.append(dict(region=n,sector=sector,observed_quarterly_purchaser_CAD=value,normalized_IO_basic_CAD=fixed.sum()*value/total,share=value/total))
        scope_rows.append(dict(region=n,sector='valuation_bridge',observed_quarterly_purchaser_CAD=total,normalized_IO_basic_CAD=fixed.sum(),source_GFCF_net_product_tax=net_tax,unreconciled_scope_price_gap=total-fixed.sum()-net_tax))
    pre=pd.DataFrame(product_rows);pre.to_csv(OUT/'FSG_source_products.csv',index=False)
    pd.DataFrame(scope_rows).to_csv(OUT/'FSG_source_scope.csv',index=False)
    negative=pre[pre.negative_fixed];negative.to_csv(OUT/'FSG_negative_products.csv',index=False)
    if len(negative):
        meta=dict(passed=False,pickle_built=False,quarters_run=0,dependent_12q_runs='skipped',
            failure='Signed negative regional IO fixed-capital product entries cannot be used as nonnegative goods-purchase budgets. No clipping, redistribution or artificial disposal/cash/stock path implemented.',
            negative_cells=len(negative),negative_annual_CAD=float(4*negative.IO_fixed_quarterly_CAD.sum()),
            national_fixed_annual_CAD=float(4*pre.IO_fixed_quarterly_CAD.sum()),national_inventory_annual_CAD=float(4*pre.inventory_quarterly_CAD.sum()),
            source_pickle=str(source),source_sha256=sha(source),source_IO_commit='d847fb2',
            source_IO_compatibility_sha256=sha(BENCH/'compatibility/compat_icio_2022_can_provinces.csv'),
            material_group_gate='Not evaluated on an executable candidate: no FSG pickle. >50M/q and 2% unchanged.',
            GDP_and_accounting='Not run: no representable candidate; all13 FS_T checks are separate.',
            inventory_note='Signed inventory change identified separately from GFCF, not folded into fixed capital. No opening inventory stock changed.',
            provenance=dict(nonres=json.loads((raw/'36100096_2022_provenance.json').read_text()),residential=json.loads((raw/'36100099_download.json').read_text()),tax_git_commit='d847fb2',tax_git_path=name,tax_sha256=sha(taxfile)))
        (OUT/'FSG_build_gate.json').write_text(json.dumps(meta,indent=2)+'\n')
        print(json.dumps(meta,indent=2),flush=True)
        return
    raise RuntimeError('Source preflight changed: review a new FSG build specification before building')

if __name__=='__main__':main()
