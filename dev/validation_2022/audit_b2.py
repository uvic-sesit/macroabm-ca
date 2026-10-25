"""Protected inputs, exact run sources, accounting, prefixes and known failures."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from audit_be import EXPECTED,sha
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'outputs/B2'

def source_match(path,digest,head):
    if sha(ROOT/path)==digest:return 'working_tree'
    for revision in (head,'c2c3eb8','ea3485a','55fb64a','2237cb1','c3df2d9'):
        r=subprocess.run(['git','show',revision+':'+path.replace('\\','/')],cwd=ROOT,capture_output=True)
        if r.returncode:continue
        lf=r.stdout.replace(b'\r\n',b'\n')
        if digest in [hashlib.sha256(x).hexdigest() for x in (r.stdout,lf,lf.replace(b'\n',b'\r\n'))]:return revision
    raise AssertionError('Untraceable source '+path)

def failure_ids(p):
    return {(c.get('classname'),c.get('name')) for c in ET.parse(p).iter('testcase')
        if c.find('failure') is not None or c.find('error') is not None}

def main():
    assert subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='feature/validation-2022'
    protected={n:sha(ROOT/'dev/pkl_files'/n) for n in EXPECTED}
    assert protected==EXPECTED
    runs=[]
    for path in sorted((OUT/'final').glob('*/manifest.json')):
        m=json.loads(path.read_text());p=path.parent
        assert sha(Path(m['pickle']))==m['pickle_sha256']
        assert m['max_accounting_error']<=1e-8
        sources={source:source_match(source,digest,m['head']) for source,digest in m['source_sha256'].items()}
        prefix=None
        if m['quarters']==12 and m['variant']=='base':
            a=pd.read_csv(p/'outcomes.csv').query('quarter<=2').reset_index(drop=True)
            b=pd.read_csv(p.with_name(p.name.replace('_q12_','_q2_'))/'outcomes.csv')
            assert a[['region','quarter']].equals(b[['region','quarter']])
            assert np.allclose(a.select_dtypes('number'),b.select_dtypes('number'),rtol=1e-12,atol=1e-4,equal_nan=True)
            prefix=True
        runs.append(dict(run=p.name,head=m['head'],error=m['max_accounting_error'],sources=sources,prefix=prefix))
    assert len(runs)==21
    assert failure_ids(OUT/'verification/full_tests.xml')==failure_ids(HERE/'outputs/BE/full_tests.xml')
    tests=json.loads((OUT/'verification/full_test_execution.json').read_text())
    assert len(tests['failures'])==30 and all(f['known_nan'] for f in tests['failures'])
    assert any(p.get('name')=='sampler_n_cores' and p.get('value')=='1' for p in tests['sampler_properties'])
    benchmarks=json.loads((HERE/'benchmarks/B2/distribution_provenance.json').read_text())
    for name,digest in benchmarks['extracts'].items():assert sha(HERE/'benchmarks/B2'/name)==digest
    index=json.loads((HERE/'benchmarks/B2/benchmark_index.json').read_text())
    for name,digest in index['selected_files'].items():assert sha(HERE/name)==digest
    for name,digest in index['inherited_provenance'].items():assert sha(HERE/name)==digest
    for name in ('io_build_provenance.json','cfc_build_provenance.json'):
        m=json.loads((OUT/'firm_data'/name).read_text())
        assert sha(Path(m['source']))==m['source_sha256']
        assert sha(Path(m['new_pickle']))==m['new_pickle_sha256']
    # The new CFC input changes consumption of capital, not financing, stocks,
    # producer output, initial purchases, or accepted household tax receipts.
    from macro_data import DataWrapper
    old=DataWrapper.init_from_pickle(ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt.pkl')
    new=DataWrapper.init_from_pickle(ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt_cfc_v2.pkl')
    for name,c in new.synthetic_countries.items():
        if not str(name).startswith('CAN_'):continue
        before=old.synthetic_countries[name]
        np.testing.assert_array_equal(c.firms.firm_data[['Debt','Deposits','Equity','Production','Demand']],
            before.firms.firm_data[['Debt','Deposits','Equity','Production','Demand']])
        np.testing.assert_array_equal(c.firms.capital_inputs_stock,before.firms.capital_inputs_stock)
        np.testing.assert_array_equal(c.firms.initial_capital_purchases,before.firms.used_capital_inputs)
        pd.testing.assert_frame_equal(c.banks.bank_data,before.banks.bank_data)
        fiscal=['VAT','Capital Formation Taxes','Taxes on Products','Taxes on Production','Income Taxes']
        pd.testing.assert_frame_equal(c.central_government.central_gov_data[fiscal],
            before.central_government.central_gov_data[fiscal])
    gates=pd.read_csv(OUT/'gates.csv');assert len(gates)==12 and not gates.pass_all.any()
    assert not json.loads((OUT/'continuation.json').read_text())['start_E']
    replays=[];replay_errors=[]
    for path in sorted((OUT/'distribution_replays_v2').glob('*/manifest.json')):
        m=json.loads(path.read_text());assert m['all_macro_paths_match'] and m['max_accounting_error']<=1e-8
        replay_errors.append(m['max_accounting_error'])
        assert sha(ROOT/m['original_manifest'])==m['original_manifest_sha256']
        for source,digest in m['source_sha256'].items():assert source_match(source,digest,m['head'])
        replays.append(path.parent.name)
    assert len(replays)==15
    micro={str(p.relative_to(ROOT)):sha(p) for sub in ('final','distribution_replays_v2')
        for p in (OUT/sub).glob('*/micro/*') if p.is_file()}
    (OUT/'micro_hashes.json').write_text(json.dumps(micro,indent=2)+'\n')
    result=dict(protected_inputs=protected,runs=runs,distribution_replays=replays,
        max_accounting_error=max([r['error'] for r in runs]+replay_errors),
        max_replay_accounting_error=max(replay_errors),
        tests=tests['tests'],passed=tests['passed'],known_failures=30,extra_failures=0,
        failure_ids_match_baseline=True,primary_G3='DHEA quintile shares',step2_base='accepted FE F',
        E_started=False,phase_B_started=False,C_dp_005_started=False)
    (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    inventory={str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*')
        if p.is_file() and 'micro' not in p.parts and p.name!='artifact_manifest.json'
        and (len(p.relative_to(OUT).parts)==1 or p.relative_to(OUT).parts[0] in {'final','firm_data','distribution_replays_v2','verification'})}
    (OUT/'artifact_manifest.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print('Audited',len(runs),'runs; protected inputs and exact known failures match')

if __name__=='__main__':main()
