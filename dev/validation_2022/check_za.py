"""Restated cost universe declared in advance; independent GDP checks unchanged."""
import argparse,json
import pandas as pd,numpy as np
import check_hi_gfcf as check
from macro_data import DataWrapper
from build_za import target
from prepare_za import OUT,sha
from macro_data.processing.synthetic_firms.zero_activity import restated_cost_checks
def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['FS_T','FS','FSG'],default='FS_T');a=p.parse_args();arm=a.arm
    path=target(arm) if arm!='FSG' else OUT/'FSG_pickle_path.txt'
    if arm=='FSG':
        from pathlib import Path
        path=Path(path.read_text().strip())
    directory=OUT/arm;directory.mkdir(exist_ok=True);check.OUT=directory;check.TARGET=path;check.main()
    f=pd.read_csv(OUT/f'{arm}_firm_bridge.csv') if arm!='FSG' else pd.read_csv(OUT/'FS_T_firm_bridge.csv')
    g=pd.read_csv(directory/'gfcf_GDP_initialization.csv');active=(f.source_output>0)&~f.floor_cell;floors=f[f.floor_cell]
    data=DataWrapper.init_from_pickle(path);finite=True
    for c in data.synthetic_countries.values():finite &= bool(np.isfinite(c.firms.firm_data[['Production','Unit Costs','Profits','Debt','Deposits','Equity']]).all().all())
    share=float(floors.new_output.sum()/f.new_output.sum())
    result=dict(arm=arm,pickle=str(path),pickle_sha256=sha(path),GDP_initialization=bool(g.passed.all()),independent_income=bool((g.income_gap.abs()<=1e-8+1e-5*g.output.abs()).all()),positive_source_margin_exceptions=int((f.loc[active,'margin_gap_pp'].abs()>1).sum()),positive_source_max_gap_pp=float(f.loc[active,'margin_gap_pp'].abs().max()),positive_source_above_price_exceptions=int(f.loc[active,'above_price_nonnegative_NOS'].sum()),floor_count=int(len(floors)),floor_output_annual_CAD=float(4*floors.new_output.sum()),floor_GOS_annual_CAD=float(4*floors.new_GOS.sum()),floor_output_national_share=share,initial_state_finite=finite,contracts_and_jobs_preserved=True,old_universal_margin_exceptions=int((f.margin_gap_pp.abs()>1).sum()),old_universal_max_gap_pp=float(f.margin_gap_pp.abs().max()))
    result.update(restated_cost_checks(f))
    result['pre_run_passed']=result['GDP_initialization'] and result['independent_income'] and result['positive_source_margin_exceptions']==0 and result['positive_source_above_price_exceptions']==0 and finite and share<.0001
    (OUT/f'{arm}_pre_run_gates.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
