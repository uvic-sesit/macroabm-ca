"""Audit current or historically committed sources, prefixes and known failures."""
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import pandas as pd
from audit_fe import EXPECTED
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'outputs/BE'
EXPECTED=dict(EXPECTED,io2022_household_agreed_bankcap_firmdebt_pkl='0abf12059d02f3bbcce09bee5d504325c740d3b7505f5f6c6a75e2c871bb130d')
EXPECTED['io2022_household_agreed_bankcap_firmdebt.pkl']=EXPECTED.pop('io2022_household_agreed_bankcap_firmdebt_pkl')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def source_matches(path,digest,head):
    if sha(ROOT/path)==digest:return 'working_tree'
    # The first 2Q pilot preceded the instrumentation commit; its exact source
    # was subsequently committed without changes. Git normalises text endings.
    for revision in (head,'6a973a6'):
        data=subprocess.run(['git','show',f'{revision}:{path}'],cwd=ROOT,capture_output=True)
        if data.returncode:continue
        blob=data.stdout;lf=blob.replace(b'\r\n',b'\n')
        if digest in [hashlib.sha256(v).hexdigest() for v in (blob,lf,lf.replace(b'\n',b'\r\n'))]:return revision
    raise AssertionError(f'Untraceable source {path} ({head})')


def main():
    protected={n:sha(ROOT/'dev/pkl_files'/n) for n in EXPECTED}
    assert protected==EXPECTED,'Protected input modified'
    provenance=json.loads((HERE/'benchmarks/BE/buffer_provenance.json').read_text())
    assert sha(Path(provenance['source']))==provenance['source_sha256']
    assert sha(HERE/'benchmarks/BE/sfs_liquid_buffers.csv')==provenance['extract_sha256']
    runs=[];maxerr=0.
    for manifest in sorted(OUT.glob('*/manifest.json')):
        m=json.loads(manifest.read_text());p=manifest.parent
        assert m['pickle_sha256']==EXPECTED['io2022_household_agreed_bankcap_firmdebt.pkl']
        assert m['max_accounting_error']<=1e-8
        historical=[]
        for source,digest in m['source_sha256'].items():
            revision=source_matches(source,digest,m['head'])
            if revision!='working_tree':historical.append(dict(path=source,revision=revision))
        paired=False
        if m['quarters']==12 and m['variant']=='base':
            a=pd.read_csv(p/'outcomes.csv').query('quarter<=2').reset_index(drop=True)
            b=pd.read_csv(p.with_name(p.name.replace('_q12_','_q2_'))/'outcomes.csv')
            assert a[['region','quarter']].equals(b[['region','quarter']])
            cols=a.select_dtypes('number').columns
            assert np.allclose(a[cols],b[cols],rtol=1e-12,atol=1e-4,equal_nan=True)
            paired=True
        maxerr=max(maxerr,m['max_accounting_error'])
        runs.append(dict(run=p.name,head=m['head'],error=m['max_accounting_error'],prefix_match=paired,historical_sources=historical))
    def failures(p):
        return {(c.attrib.get('classname'),c.attrib.get('name')) for c in ET.parse(p).iter('testcase')
                if c.find('failure') is not None or c.find('error') is not None}
    tests=json.loads((OUT/'full_test_execution.json').read_text())
    assert failures(OUT/'full_tests.xml')==failures(HERE/'outputs/FE/full_tests.xml')
    assert len(tests['failures'])==30 and all(f['known_nan'] for f in tests['failures'])
    micro={str(p.relative_to(ROOT)):sha(p) for p in OUT.glob('*/micro/*.csv')}
    (OUT/'micro_hashes.json').write_text(json.dumps(micro,indent=2)+'\n')
    (OUT/'audit.json').write_text(json.dumps(dict(protected_inputs=protected,runs=runs,max_accounting_error=maxerr,
        full_suite_failure_ids_match_baseline=True,tests=tests['tests'],passed=tests['passed'],known_failures=30,extra_failures=0),indent=2)+'\n')
    inventory={str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*') if p.is_file() and 'micro' not in p.parts and p.name!='artifact_manifest.json'}
    (OUT/'artifact_manifest.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print(f'{len(runs)} serial runs audited; protected inputs unchanged; full-suite failures match baseline')


if __name__=='__main__':main()
