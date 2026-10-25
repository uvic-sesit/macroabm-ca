"""Certify recorded short run, distinguishing an unset Q0 forecast from model state."""
import json
import numpy as np,pandas as pd
from prepare_za import OUT,ROOT,sha
def main():
    p=OUT/'runs/F_CFC_ZA_FS_T_q2_s0';m=json.loads((p/'manifest.json').read_text());f=pd.read_csv(p/'floor_states.csv');defined=~((f.quarter==0)&(f.field=='target_production'))
    assert f.loc[defined,'finite'].all() and m['max_accounting_error']<1e-8
    assert ((f.loc[~defined,'quarter']==0)&(f.loc[~defined,'field']=='target_production')).all() and len(f.loc[~defined])==68
    # Preserve original raw output. The annotated audit is a separate artifact.
    annotated=f.assign(defined=defined);annotated.to_csv(OUT/'FS_T_short_floor_states_defined.csv',index=False)
    result=dict(passed=True,accounting_passed=True,floor_defined_state_finite=True,max_accounting_error=m['max_accounting_error'],raw_floor_states_sha256=sha(p/'floor_states.csv'),undefined_initial_forecast_cells=int((~defined).sum()),correction='The first wrapper exit1 was an audit-schema error after the successful simulation/accounting. target_production is initializedNaN for all firms atQ0 and computed fromQ1. No economic value, code path, tolerance or parameter changed; original artifact and failed wrapper log retained.',schema_source='macromodel/agents/firms/firm_ts.py',schema_source_sha256=sha(ROOT/'macromodel/agents/firms/firm_ts.py'))
    (OUT/'FS_T_short_certificate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
