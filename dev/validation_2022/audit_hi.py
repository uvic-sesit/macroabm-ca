"""Final HI audit: unchanged accepted inputs, reproducible benchmarks and failed gates."""
from pathlib import Path
import hashlib,json,subprocess
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'outputs/HI'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    old=json.loads((HERE/'outputs/IH/audit.json').read_text())
    protected={n:sha(ROOT/'dev/pkl_files'/n) for n in old['protected_sha256']}
    assert protected==old['protected_sha256']
    for name in ['cis_allocation','gfcf_build']:
        p=json.loads((OUT/f'{name}_provenance.json').read_text());assert sha(Path(p['new_pickle']))==p['new_pickle_sha256']
        assert p['source_sha256']==protected['io2022_household_agreed_bankcap_firmdebt_cfc_v2.pkl']
    b=HERE/'benchmarks/HI';sources=[]
    for t in ['11100192','11100193']:
        p=json.loads((b/f'{t}_provenance.json').read_text())
        for file,key in [(f'{t}_2022.csv','extract_sha256'),(f'{t}_metadata.csv','metadata_sha256')]:assert sha(b/file)==p[key]
        sources.append(p)
    cash=json.loads((b/'cash_concept.json').read_text())
    for path,key in [('pumf','pumf_sha256'),('source_adapter','source_adapter_sha256')]:assert sha(Path(cash[path]))==cash[key]
    inherited=json.loads((HERE/'benchmarks/IH/provenance.json').read_text())
    for p in inherited['sources']+inherited.get('derived_input_sources',[]):assert sha(ROOT/p['source'])==p['sha256']
    tests=json.loads((OUT/'verification/full_test_execution.json').read_text());prior=json.loads((HERE/'outputs/IH/verification_final/full_test_execution.json').read_text())
    ids=lambda t:{(x['test']['classname'],x['test']['name']) for x in t['failures']}
    assert ids(tests)==ids(prior) and len(tests['failures'])==30 and all(x['known_nan'] for x in tests['failures'])
    assert tests['tests']==518 and tests['passed']==488
    assert any(x['name']=='sampler_n_cores' and x['value']=='1' for x in tests['sampler_properties'])
    runs=[]
    for mpath in (OUT/'runs').glob('*/manifest.json'):
        m=json.loads(mpath.read_text());assert m['quarters']==2 and m['seed']==0 and m['max_accounting_error']<1e-8
        runs.append(dict(path=str(mpath.parent.relative_to(ROOT)),max_accounting_error=m['max_accounting_error']))
    assert len(runs)==2
    base=pd.read_csv(OUT/'runs/F_CFC_HI_baseline_audit_q2_s0/outcomes.csv')
    history=pd.read_csv(HERE/'outputs/IH/runs/F_CFC_IH_F_CFC_q12_s0/outcomes.csv');history=history[history.quarter<=2]
    keys=['region','quarter'];columns=[c for c in base if c in history and c not in ['arm','seed','quarters']]
    a=base.sort_values(keys).reset_index(drop=True);h=history.sort_values(keys).reset_index(drop=True)
    for c in columns:
        if pd.api.types.is_numeric_dtype(a[c]):assert np.allclose(a[c],h[c],rtol=1e-12,atol=.001,equal_nan=True),c
        else:assert a[c].equals(h[c]),c
    probe=pd.read_csv(OUT/'t0_stage_probe.csv');assert np.isfinite(probe[['income','planned_C','cash_DI','persistent','unable']]).all().all()
    s=pd.read_csv(OUT/'stage_deciles.csv');assert s.taxes.isna().all()
    gates=json.loads((OUT/'gates.json').read_text());assert not any(gates[k]['passed'] for k in ['HI_G2','HI_G3','HI_G5']) and not gates['STEP4']['started']
    assert gates['HI_G4']['stock_marginals_exact'] and gates['HI_G4']['regional_income_budgets_exact']
    assert len(pd.read_csv(OUT/'stage_reconstruction_lost_income.csv'))==0 if (OUT/'stage_reconstruction_lost_income.csv').stat().st_size>2 else True
    index=dict(created_utc='2026-10-25',primary_CIS=cash,published_crosschecks=sources,inherited_sources=inherited,custom_tabulation_vectors=None,custom_tabulation_reason='PUMF household custom aggregation has no published vector IDs.',inherited_concordance=dict(path='dev/validation_2022/outputs/IH/observed_investment_concordance.csv',sha256=sha(HERE/'outputs/IH/observed_investment_concordance.csv')),benchmark_files=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted(b.iterdir()) if p.is_file()])
    (OUT/'benchmark_index.json').write_text(json.dumps(index,indent=2)+'\n')
    audit=dict(passed=True,git_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),protected_sha256=protected,benchmark_hashes_passed=True,runs=runs,baseline_two_quarter_economic_prefix_matches_IH=True,tests=dict(total=518,passed=488,failures=30,beyond_known=0,sampler_workers=1),gates=gates,limitations=['Historical intermediate donor/fit IDs not retained; no exact complete-region replay is claimed.','Investment input fails initialization; no simulated accounting pass is claimed.','No passing input and no new 12-quarter or combined build.','t0 persistent-dissaver metric holds income and the consumption rule fixed; it is not a measured longitudinal household outcome.'])
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');print('HI audit passed:',audit['tests'])
if __name__=='__main__':main()
