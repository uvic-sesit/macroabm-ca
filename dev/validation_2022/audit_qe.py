"""QE evidence audit: protected inputs, sources, empirical gates, exact failures."""
import hashlib,json,subprocess,sys
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from audit_be import EXPECTED
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'outputs/QE'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


@lru_cache(None)
def trace(source,digest):
    source=source.replace('\\','/')
    if sha(ROOT/source)==digest:return 'working_tree'
    snapshot=OUT/'source_snapshots'/(digest+'.py')
    if snapshot.exists() and sha(snapshot)==digest:return str(snapshot.relative_to(ROOT))
    commits=subprocess.check_output(['git','log','--format=%H','7a1767e..HEAD'],cwd=ROOT,text=True).splitlines()+['7a1767e']
    for revision in commits:
        r=subprocess.run(['git','show',revision+':'+source],cwd=ROOT,capture_output=True)
        if r.returncode:continue
        lf=r.stdout.replace(b'\r\n',b'\n')
        if digest in [hashlib.sha256(x).hexdigest() for x in [r.stdout,lf,lf.replace(b'\n',b'\r\n')]]:return revision
    raise AssertionError('Untraceable run source '+source+' '+digest)


def failure_ids(path):
    return {(c.get('classname'),c.get('name')) for c in ET.parse(path).iter('testcase') if c.find('failure') is not None or c.find('error') is not None}


def main():
    assert subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='feature/validation-2022'
    protected={n:sha(ROOT/'dev/pkl_files'/n) for n in EXPECTED};assert protected==EXPECTED
    from qe_baseline import PICKLE,PICKLE_SHA256
    assert sha(PICKLE)==PICKLE_SHA256
    protected[PICKLE.name]=PICKLE_SHA256
    primary=[];excluded=[];traces={}
    for p in sorted((OUT/'runs').glob('*/manifest.json')):
        m=json.loads(p.read_text());valid=m['max_accounting_error']<=1e-8
        assert sha(Path(m['pickle']))==m['pickle_sha256']
        for source,digest in {**m.get('source_sha256',{}),**m.get('QE_sources',{})}.items():traces[source+' @ '+digest]=trace(source,digest)
        selected=valid and m['quarters']==12 and ((m['arm']=='E' and m.get('variant')=='cashfix') or (m['arm']!='E' and m.get('variant','base')=='base'))
        if not selected:
            excluded.append(dict(run=p.parent.name,valid_accounting=valid,error=m['max_accounting_error'],reason='pilot/debug or rejected pre-fix run'))
            continue
        assert (p.parent/'headline.csv').exists()
        z=pd.read_csv(p.parent/'consumption_quintiles.csv')
        a=z[z.scheme=='DHEA_equivalised_DI'].groupby('quarter').consumption.sum()
        b=z[z.scheme=='SHS_gross_household_income'].groupby('quarter').consumption.sum()
        np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-3)
        h=pd.read_csv(p.parent/'headline.csv').groupby('quarter').sum(numeric_only=True)
        np.testing.assert_allclose(a,h.household_account_C,rtol=1e-12,atol=1e-3)
        if m['arm']=='Q':
            assert np.isclose(a.loc[0],3778455e5,rtol=1e-12,atol=1e-3)
            calibration=pd.read_csv(p.parent/'Q_calibration.csv')
            assert calibration.common_multiplier.nunique()==1
        if (p.parent/'outcomes.csv').exists():
            x=pd.read_csv(p.parent/'outcomes.csv')
            np.testing.assert_allclose(x.bank_losses,x.household_writeoffs+x.firm_loan_losses+x.overdraft_losses,rtol=1e-12,atol=1e-3)
        if m['arm'] in ['F','F_CFC']:
            old=(HERE/'outputs/FE/serial'/f'iv-ACDpAIF_q12_s{m["seed"]}') if m['arm']=='F' else (HERE/'outputs/B2/final'/f'F_CFC_base_q12_s{m["seed"]}')
            a=pd.read_csv(p.parent/'outcomes.csv');b=pd.read_csv(old/'outcomes.csv')
            cols=['gdp','consumption','household_writeoffs','bank_losses','recapitalisation','constrained_households','cash_DI']
            np.testing.assert_allclose(a[cols],b[cols],rtol=1e-12,atol=1e-3,equal_nan=True)
        primary.append(dict(run=p.parent.name,arm=m['arm'],seed=m['seed'],error=m['max_accounting_error']))
    assert len(primary)==15
    assert all(sorted(r['seed'] for r in primary if r['arm']==arm)==[0,1,2] for arm in ['C','F','F_CFC','Q','E'])
    for quarters in [2,4]:
        a=pd.read_csv(OUT/'runs/E_cashfix_q12_s0/outcomes.csv').query('quarter<=@quarters').reset_index(drop=True)
        b=pd.read_csv(OUT/'runs'/f'E_cashfix_q{quarters}_s0/outcomes.csv')
        np.testing.assert_allclose(a.select_dtypes('number'),b.select_dtypes('number'),rtol=1e-12,atol=1e-3,equal_nan=True)
    for p in sorted((OUT/'C_bank_replays').glob('*/manifest.json')):
        m=json.loads(p.read_text());assert m['exact_macro_and_distribution_match'] and m['max_accounting_error']<=1e-8
    assert len(list((OUT/'C_bank_replays').glob('*/manifest.json')))==3
    # New unaccepted FB input preserves all accepted balance-sheet stocks.
    from macro_data import DataWrapper
    old=DataWrapper.init_from_pickle(PICKLE)
    bm=json.loads((OUT/'bridge/provenance.json').read_text());assert sha(Path(bm['new_pickle']))==bm['new_pickle_sha256']
    new=DataWrapper.init_from_pickle(Path(bm['new_pickle']))
    for name,c in old.synthetic_countries.items():
        if not str(name).startswith('CAN_'):continue
        after=new.synthetic_countries[name]
        np.testing.assert_array_equal(c.firms.firm_data[['Debt','Deposits','Equity']],after.firms.firm_data[['Debt','Deposits','Equity']])
        np.testing.assert_array_equal(c.firms.capital_inputs_stock,after.firms.capital_inputs_stock)
        np.testing.assert_array_equal(c.firms.initial_capital_purchases,after.firms.initial_capital_purchases)
        pd.testing.assert_frame_equal(c.banks.bank_data,after.banks.bank_data)
        inactive=after.firms.firm_data['Source inactive holder']
        assert (after.firms.firm_data.loc[inactive,'Production']==0).all()
    benchmarks=json.loads((HERE/'benchmarks/QE/provenance.json').read_text())
    assert sha(HERE/'benchmarks/QE/dhea_income_consumption_2022.csv')==benchmarks['extract_sha256']
    sf=json.loads((HERE/'benchmarks/QE/sfs_deposit_provenance.json').read_text())
    assert sha(HERE/'benchmarks/QE/sfs_deposit_buffers.csv')==sf['extract_sha256']
    credit=json.loads((HERE/'benchmarks/QE/credit_benchmarks.json').read_text())
    for name,digest in credit['file_hashes'].items():assert sha(HERE/name)==digest
    if '--precheck' in sys.argv:
        (OUT/'precheck.json').write_text(json.dumps(dict(protected_inputs=protected,primary_runs=primary,excluded_diagnostics=excluded,traceable_sources=traces,
            F_and_F_CFC_match_accepted_macro_paths=True,C_bank_replays_match=True,E_prefixes_match=True,FB_financial_stocks_unchanged=True),indent=2)+'\n')
        print('Measurement/source/stock precheck passed; final full-test audit still pending',flush=True)
        return
    tests=json.loads((OUT/'verification/full_test_execution.json').read_text())
    assert len(tests['failures'])==30 and all(r['known_nan'] for r in tests['failures'])
    assert failure_ids(OUT/'verification/full_tests.xml')==failure_ids(HERE/'outputs/B2/verification/full_tests.xml')
    assert any(p.get('name')=='sampler_n_cores' and p.get('value')=='1' for p in tests['sampler_properties'])
    continuation=json.loads((OUT/'continuation.json').read_text())
    assert not any(continuation.values())
    gates=pd.read_csv(OUT/'gates.csv');assert not gates.passed.any()
    assert not pd.read_csv(OUT/'bridge/unchanged_GDP_checks.csv').initialisation_passed.any()
    audit=dict(protected_inputs=protected,primary_runs=primary,excluded_diagnostics=excluded,traceable_sources=traces,
        accounting_max=max(r['error'] for r in primary),F_and_F_CFC_match_accepted_macro_paths=True,C_bank_replays_match=True,
        E_two_and_four_quarter_prefixes_match=True,FB_financial_stocks_unchanged=True,
        tests=tests['tests'],passed=tests['passed'],known_failures=30,extra_failures=0,failure_ids_match=True,
        sampler_workers=1,continuation=continuation)
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    micro={str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*') if p.is_file() and 'micro' in p.parts}
    (OUT/'micro_hashes.json').write_text(json.dumps(micro,indent=2)+'\n')
    files={str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*') if p.is_file() and 'micro' not in p.parts and p.name!='artifact_manifest.json'}
    (OUT/'artifact_manifest.json').write_text(json.dumps(files,indent=2)+'\n')
    print('Audited 15 primary 12-quarter runs, three C replays, protected inputs, unchanged stocks and exact known failures',flush=True)

if __name__=='__main__':main()
