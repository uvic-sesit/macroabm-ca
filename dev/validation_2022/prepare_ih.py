"""Frozen IH benchmarks and independent net-surplus gate; no simulation."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'outputs/IH';BENCH=HERE/'benchmarks/IH'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def net_gate(f):
    f=f.copy();active=f.output>1e-3
    f['observed_NOS']=f.IO_GOS-f.CFC
    f['model_net_margin']=(f.price-f.unit_cost)/f.price
    f['observed_net_margin']=np.divide(f.observed_NOS,f.output,out=np.zeros(len(f)),where=active)
    f['net_margin_gap_pp']=100*(f.model_net_margin-f.observed_net_margin)
    f['margin_fail']=active&(f.net_margin_gap_pp.abs()>1)
    f['above_price_exception']=active&(f.unit_cost>f.price+1e-8)&(f.observed_NOS>=0)
    return f

def main():
    OUT.mkdir(exist_ok=True);BENCH.mkdir(exist_ok=True);sources=[]
    p=HERE/'benchmarks/B2/raw/36100587.csv';d=pd.read_csv(p,low_memory=False)
    q=['Lowest income quintile','Second income quintile','Third income quintile','Fourth income quintile','Highest income quintile']
    names=['Household disposable income','Compensation of employees','Net mixed income','Property income received','Less: property income paid','Current transfers received','Less: current transfers paid']
    sel=d[(d.REF_DATE.astype(str)=='2022')&(d.GEO=='Canada')&d.Statistics.isin(['Value','Value per household','Value per consumption unit'])&d.Characteristics.isin(q)&d['Income, consumption and savings'].isin(names)].copy();sel['quintile']=sel.Characteristics.map({x:i+1 for i,x in enumerate(q)});sel.to_csv(BENCH/'DHEA_components_2022.csv',index=False)
    sources.append(dict(table='36-10-0587-01',reference='2022',source=str(p.relative_to(ROOT)),sha256=sha(p),retrieval=json.loads((p.parent/'36100587_download.json').read_text()),extract_sha256=sha(BENCH/'DHEA_components_2022.csv'),vectors=sel.VECTOR.tolist()))
    p=HERE/'benchmarks/B2/raw/36100096_2022.csv';d=pd.read_csv(p,low_memory=False)
    sel=d[(d.Prices=='Current prices')&(d.Assets=='Total non-residential')&d['Flows and stocks'].isin(['Investment','Geometric depreciation'])].copy();sel.to_csv(BENCH/'nonres_investment_CFC_2022.csv',index=False)
    sources.append(dict(table='36-10-0096-01',reference='2022',source=str(p.relative_to(ROOT)),sha256=sha(p),retrieval=json.loads((p.parent/'36100096_2022_provenance.json').read_text()),extract_sha256=sha(BENCH/'nonres_investment_CFC_2022.csv'),vectors=sel.VECTOR.tolist()))
    totals=sel[(sel.GEO=='Canada')&sel.Industry.isin(['Total all industries','Government sector','Non-profit institutions serving households'])].pivot(index='Industry',columns='Flows and stocks',values='VALUE');totals.loc['Business residual excluding government and NPISH']=totals.loc['Total all industries']-totals.loc['Government sector']-totals.loc['Non-profit institutions serving households'];totals['net_investment']=totals.Investment-totals['Geometric depreciation'];totals.to_csv(OUT/'observed_investment_totals_MCAD_annual.csv')
    gates=[]
    for arm,p in [('F_CFC',HERE/'outputs/B2/firm_data/cfc_cost_bridge.csv'),('FB_unaccepted',HERE/'outputs/QE/bridge/firm_bridge.csv')]:
        f=pd.read_csv(p)
        if arm=='F_CFC':f=f.rename(columns={'new_CFC':'CFC'})
        f=net_gate(f);f.to_csv(OUT/(arm+'_net_margin_gate.csv'),index=False)
        gates.append(dict(arm=arm,active_cells=int((f.output>1e-3).sum()),margin_failures=int(f.margin_fail.sum()),above_price_exceptions=int(f.above_price_exception.sum()),max_gap_pp=float(f.loc[f.output>1e-3,'net_margin_gap_pp'].abs().max()),passed=bool(not(f.margin_fail|f.above_price_exception).any()),source_sha256=sha(p)))
    pd.DataFrame(gates).to_csv(OUT/'unit_cost_gates.csv',index=False)
    # Preserve the exact accepted input hashes and raw IO bridge provenance.
    for p in [HERE/'qe_baseline.py',HERE/'outputs/QE/bridge/provenance.json',HERE/'outputs/B2/firm_data/cfc_build_provenance.json',HERE/'benchmarks/QE/credit_benchmarks.json']:
        if p.exists():sources.append(dict(source=str(p.relative_to(ROOT)),sha256=sha(p)))
    (BENCH/'provenance.json').write_text(json.dumps(dict(created_utc=datetime.now(timezone.utc).isoformat(),sources=sources),indent=2)+'\n')
    print(pd.DataFrame(gates).to_string(index=False));print(totals.to_string())
if __name__=='__main__':main()
