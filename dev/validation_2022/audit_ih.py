"""IH evidence audit: protected inputs, exact replays, identities and known failures."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'outputs/IH'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    protected={'io2022_phaseA.pkl':'4bf77da7707cab00d507c4505c16740224863298ba9b858e5aaf6d60a9c2dc4c','io2022_household_agreed.pkl':'3b48c0dba90c2d3c837f92bc0477e4b242ba0afa78275b095e26cc52b4fcb313','io2022_household_agreed_bankcap.pkl':'d7b39868a569ea52d749aced375247ed6824c8ff2c9e9493100a43645b0de228','io2022_household_agreed_bankcap_firmdebt.pkl':'0abf12059d02f3bbcce09bee5d504325c740d3b7505f5f6c6a75e2c871bb130d','io2022_household_agreed_bankcap_firmdebt_cfc_v2.pkl':'a16386b64e0eeca5986dc1d4a3d94a4a7c0b33b178f76e1a8933e926948677ae','io2022_household_f_cfc_qe_bridge_2026_10_25.pkl':'8d50412140c5483b06f6b5007dccaea84960299fa3f0ddc182c89f7556d3aa8d'}
    actual={name:sha(ROOT/'dev/pkl_files'/name) for name in protected};assert actual==protected
    runs=[]
    for p in list((OUT/'runs').glob('*/manifest.json'))+list((OUT/'entrant_replays').glob('*/manifest.json')):
        m=json.loads(p.read_text());assert m['max_accounting_error']<=1e-8
        runs.append(dict(path=str(p.parent.relative_to(ROOT)),seed=m['seed'],quarters=m['quarters'],max_accounting_error=m['max_accounting_error'],pickle_sha256=m['pickle_sha256']))
    assert len(runs)==14
    h=pd.read_csv(OUT/'headline.csv');assert np.allclose(h.gdp,h.gdp_expenditure,rtol=1e-8,atol=.001);assert np.allclose(h.gdp,h.gdp_income,rtol=1e-8,atol=.001)
    g=pd.read_csv(OUT/'gates.csv');assert len(g)==33
    assert g[g.gate.isin(['H-G1','H-G2','E-G2','E-G3'])].passed.all();assert not g[g.gate=='E-G1'].passed.any()
    proof=json.loads((OUT/'entrant_replay_proof.json').read_text());assert len(proof)==3 and all(z['economic_paths_exact'] and z['accounting_exact'] for z in proof)
    matched=pd.read_csv(OUT/'behaviour_comparison.csv');assert len(matched)==6 and matched[['outcomes_exact','other_headline_paths_exact','dynamic_GDP_exact']].all().all()
    assert np.allclose(matched.t0_GDP_reduction,64131663566.4259,rtol=0,atol=.001)
    q=pd.read_csv(OUT/'quarterly.csv');bankres=q.bank_losses-q.household_writeoffs-q.firm_loan_losses-q.overdraft_losses;assert bankres.abs().max()<.001
    e=pd.read_csv(OUT/'E2_loss_quarterly.csv');hhres=e.household_writeoffs-e.mortgage_writeoffs-e.formal_unsecured_writeoffs-e.household_overdraft_writeoffs;assert hhres.abs().max()<.001
    inc=pd.read_csv(OUT/'consumption_cash_bridge.csv');assert inc.DI_residual.abs().max()<.001
    # Demonstrate that t0 acquisitions are the old CFC proxy, never an observed-GFCF anchor.
    f=pd.read_csv(OUT/'runs/F_CFC_IH_F_CFC_q12_s0/investment_cells.csv');f=f[f.quarter==0];old=pd.read_csv(HERE/'outputs/B2/firm_data/cfc_cost_bridge.csv');z=f.merge(old[['region','firm','old_CFC']],on=['region','firm'],validate='one_to_one');assert np.allclose(z.realised,z.old_CFC,rtol=1e-12,atol=.001)
    provenance=json.loads((HERE/'benchmarks/IH/provenance.json').read_text())
    for s in provenance['sources']+provenance.get('derived_input_sources',[]):
        assert sha(ROOT/s['source'])==s['sha256']
    for name,s in zip(['DHEA_components_2022.csv','nonres_investment_CFC_2022.csv'],provenance['sources'][:2]):assert sha(HERE/'benchmarks/IH'/name)==s['extract_sha256']
    cure=json.loads((HERE/'benchmarks/IH/cure_assumption.json').read_text())
    for s in cure['sources']:assert sha(Path(s['cached_file']))==s['sha256']
    p=OUT/'verification_final/full_test_execution.json';tests=json.loads(p.read_text());assert len(tests['failures'])==30 and all(x['known_nan'] for x in tests['failures'])
    oldtests=json.loads((HERE/'outputs/QE/verification_complete/full_test_execution.json').read_text());ids=lambda j:{(x['test']['classname'],x['test']['name']) for x in j['failures']};assert ids(tests)==ids(oldtests)
    assert any(x['name']=='sampler_n_cores' and x['value']=='1' for x in tests['sampler_properties'])
    audit=dict(passed=True,git_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),protected_sha256=actual,runs=runs,max_bank_loss_residual=float(bankres.abs().max()),max_household_loss_residual=float(hhres.abs().max()),max_DI_reconstruction_residual=float(inc.DI_residual.abs().max()),t0_firm_investment_equals_legacy_CFC=True,exact_economic_replays=9,tests=dict(total=tests['tests'],passed=tests['passed'],failures=30,beyond_known=0,sampler_workers=1),benchmark_hashes_passed=True)
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit['tests']),flush=True)
if __name__=='__main__':main()
