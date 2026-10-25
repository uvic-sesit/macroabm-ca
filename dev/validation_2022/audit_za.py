"""Check immutable inputs and the recorded ZA evidence; no simulation."""
import json,subprocess
from pathlib import Path
from datetime import datetime,timezone
import numpy as np,pandas as pd
from prepare_za import ROOT,HERE,BENCH,OUT,sha,IO

def main():
    assert subprocess.check_output(['git','branch','--show-current'],cwd=ROOT).decode().strip()=='feature/validation-2022'
    protected=json.loads((HERE/'outputs/SG/audit.json').read_text())['protected_sha256']
    for name,expected in protected.items():assert sha(ROOT/'dev/pkl_files'/name)==expected,name
    source=json.loads((BENCH/'provenance.json').read_text())['sources']
    git=['git','-c','safe.directory='+IO.as_posix(),'-C',str(IO)]
    import hashlib
    for r in source:
        assert sha(BENCH/r['file'])==r['sha256']
        blob=subprocess.check_output(git+['show',r['commit']+':'+r['file']])
        assert hashlib.sha256(blob).hexdigest()==r['sha256']
    fst=json.loads((OUT/'FS_T_pre_run_gates.json').read_text());assert fst['pre_run_passed']
    assert sha(Path(fst['pickle']))==fst['pickle_sha256']
    replay=json.loads((OUT/'positive_output_bit_replay.json').read_text())
    assert replay['passed'] and all(r['numeric_state_arrays_compared']==4082 for r in replay['runs'])
    assert json.loads((OUT/'adoption_final_result.json').read_text())['Step3_passed']
    short=json.loads((OUT/'FS_T_short_certificate.json').read_text());assert short['passed']
    assert sha(OUT/'runs/F_CFC_ZA_FS_T_q2_s0/floor_states.csv')==short['raw_floor_states_sha256']
    zeros=pd.read_csv(OUT/'runs/F_CFC_ZA_FS_T_q2_s0/floor_states.csv')
    zero_states=zeros.pivot(index=['region','firm','quarter'],columns='field',values='value')
    zero_counts={}
    for t in [1,2]:
        z=zero_states.xs(t,level='quarter')
        assert len(z)==68 and (z.production==0).all() and (z.labour_productivity==0).all()
        assert np.isfinite(z.to_numpy()).all()
        zero_counts[str(t)]=len(z)
    (OUT/'zero_runtime_integration_certificate.json').write_text(json.dumps(dict(
        passed=True,source_zero_firms_with_zero_actual_output_and_productivity=zero_counts,
        captured_defined_states_all_finite=True,max_accounting_error=short['max_accounting_error'],
        method='Existing short integration artifacts only; all68 floor-initialized source-zero firms actually produce0 with productivity0 in bothQ1 andQ2. Forecast targets are subsequently capacity-clamped by the work-effort function; no new simulation or intervention.',
        contracts_jobs_initially_preserved=True),indent=2)+'\n')
    execution=json.loads((OUT/'long_execution.json').read_text());assert [r['seed'] for r in execution]==[0,1,2]
    for i,r in enumerate(execution):
        assert r['exit_code']==0
        if i:assert datetime.fromisoformat(r['start_utc'])>=datetime.fromisoformat(execution[i-1]['end_utc'])
        run=OUT/f"runs/F_CFC_ZA_FS_T_q12_s{r['seed']}";m=json.loads((run/'manifest.json').read_text())
        assert m['pickle_sha256']==fst['pickle_sha256'] and m['max_accounting_error']<1e-8
        floor=pd.read_csv(run/'floor_states.csv');defined=~((floor.quarter==0)&(floor.field=='target_production'))
        assert floor.loc[defined,'finite'].all() and (~defined).sum()==68
        assert set(floor.quarter)==set(range(13))
    q=pd.read_csv(OUT/'quarterly_comparison.csv');assert len(q)==72
    components=pd.read_csv(OUT/'GDP_component_changes.csv')
    assert len(components)==12 and components.component_gap_B.abs().max()<1e-8
    assert np.allclose(q.bank_loss_B,q.HH_loss_B+q.firm_loan_loss_B+q.overdraft_loss_B,rtol=1e-12,atol=1e-9)
    fsg=json.loads((OUT/'FSG_build_gate.json').read_text());assert not fsg['passed'] and not fsg['pickle_built']
    assert not (ROOT/'dev/pkl_files/io2022_fsg_za_v1_2026_10_25.pkl').exists()
    neg=pd.read_csv(OUT/'FSG_negative_products.csv')
    assert len(neg)==20 and np.isclose(4*neg.IO_fixed_quarterly_CAD.sum(),fsg['negative_annual_CAD'])
    investors=json.loads((OUT/'FSG_investor_diagnostic.json').read_text())
    assert investors['executable_candidate'] is False
    scopes=pd.read_csv(OUT/'FSG_source_scope.csv')
    nonres=scopes[scopes.sector.isin(['business','government','NPISH'])].normalized_IO_basic_CAD.sum()*4
    assert abs(nonres-investors['annual_normalized_nonres_target'])<1.
    valuation=pd.read_csv(OUT/'FSG_legacy_tax_scope_diagnostic.csv')
    assert len(valuation)==13
    assert np.allclose(valuation.residential_with_legacy_tax,valuation.diagnostic_residential_basic*(1+valuation.legacy_capital_formation_tax))
    assert np.allclose(valuation.purchaser_gap_if_legacy_tax_reused,valuation.residential_with_legacy_tax-valuation.observed_residential_purchaser)
    prior=json.loads((HERE/'benchmarks/IFE/provenance.json').read_text())
    assert sha(HERE/'benchmarks/IFE/household_gfcf_2022.csv')==prior['selected_sha256']
    tax=BENCH/fsg['provenance']['tax_git_path'];assert sha(tax)==fsg['provenance']['tax_sha256']
    blob=subprocess.check_output(git+['show','d847fb2:'+fsg['provenance']['tax_git_path']])
    assert hashlib.sha256(blob).hexdigest()==sha(tax)
    raw=HERE/'benchmarks/B2/raw'
    assert sha(raw/'36100096_2022.csv')==fsg['provenance']['nonres']['selected_year_sha256']
    assert sha(raw/'36100099.csv')==fsg['provenance']['residential']['full_csv_sha256']
    h=pd.read_csv(OUT/'OOH_cash_national.csv');p=pd.read_csv(OUT/'OOH_owner_allocation_by_province.csv')
    hg=pd.read_csv(OUT/'OOH_cash_by_decile_tenure.csv')
    for r in h.itertuples():
        assert sha(ROOT/'dev/pkl_files'/('io2022_household_agreed_bankcap_firmdebt_cfc_v2.pkl' if r.arm=='F_CFC' else 'io2022_household_f_cfc_cisallocation_hi_2026_10_25.pkl'))==r.source_pickle_sha256
        assert abs(r.OOH_removed-235939587000)<1 and abs(r.owner_cash_costs_added-66623975000)<1
        assert abs(r.new_gap-(r.old_gap-r.OOH_removed+r.owner_cash_costs_added))<1
        z=p[p.arm==r.arm];assert abs(z.OOH_removed.sum()-r.OOH_removed)<1
        z=hg[hg.arm==r.arm];assert len(z)==20
        assert abs(z.C.sum()-r.C)<1 and abs(z.DI.sum()-r.DI)<1
        assert abs(z.cash_C_exact_split.sum()-r.new_cash_C)<1
        assert abs(z.negative_residual_households.sum()-r.negative_residual_households)<1
    profit=pd.read_csv(OUT/'OOH_L_profit_bridge.csv');national=pd.read_csv(OUT/'OOH_L_national.csv',index_col=0)
    for field in ['OOH_dwelling_CFC','OOH_actual_net_profit']:
        assert profit[field].isna().all() and pd.isna(national.loc[field,'annual_CAD'])
    tests=json.loads((OUT/'full_test_execution.json').read_text())
    assert tests['additional_failures']==0 and all(f['known'] for f in tests['failures'])
    assert all('Nan in transactor_total_real_supply' in f['message'] for f in tests['failures'])
    assert tests['passed']+len(tests['failures'])==tests['tests']
    assert any(r.get('name')=='sampler_n_cores' and r.get('value')=='1' for r in tests['sampler_properties'])
    audit=dict(passed=True,date_utc=datetime.now(timezone.utc).isoformat(),protected_sha256=protected,
        IO_git_blobs_verified=True,all_long_runs_serial=True,defined_floor_states_finite=True,
        positive_replay_per_firm_bit_identical=True,FS_T_source_positive_and_13_GDP_and_accounting_passed=True,
        FSG_built=False,FSG_failure='20 signed negative product budgets, no clipping or new disposal architecture',
        OOH_source_totals_exact=True,OOH_household_allocation_assumption=True,OOH_missing_net_profit_and_CFC_retained=True,
        full_suite=dict(tests=tests['tests'],passed=tests['passed'],failures=len(tests['failures']),additional_failures=tests['additional_failures']),
        accepted_input_writes=False,push=False,Phase_B=False,C_dp_005=False)
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
