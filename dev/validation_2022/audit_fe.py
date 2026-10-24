"""Verify protected inputs, source identity, paired serial runs and full-suite failures."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'outputs/FE'
EXPECTED={
 'io2022_phaseA.pkl':'4bf77da7707cab00d507c4505c16740224863298ba9b858e5aaf6d60a9c2dc4c',
 'io2022_household_agreed.pkl':'3b48c0dba90c2d3c837f92bc0477e4b242ba0afa78275b095e26cc52b4fcb313',
 'io2022_household_agreed_bankcap.pkl':'d7b39868a569ea52d749aced375247ed6824c8ff2c9e9493100a43645b0de228'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    protected={n:sha(ROOT/'dev/pkl_files'/n) for n in EXPECTED}
    assert protected==EXPECTED,'Accepted input was modified'
    build=json.loads((OUT/'build_provenance.json').read_text())
    new=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt.pkl'
    assert sha(new)==build['new_pickle_sha256']
    provenance=json.loads((HERE/'benchmarks/FE/industry_provenance.json').read_text())
    assert sha(HERE/'benchmarks/FE/33100225_2022Q4.csv')==provenance['extract_sha256']
    runs=[]
    for seed in range(3):
        frames=[]
        for quarters in (2,12):
            p=OUT/'serial'/f'iv-ACDpAIF_q{quarters}_s{seed}'
            m=json.loads((p/'manifest.json').read_text())
            assert m['pickle_sha256']==sha(new)
            assert m['max_accounting_error']<=1e-8
            for source,digest in m['source_sha256'].items():
                assert sha(ROOT/source)==digest,f'Source changed since run: {source}'
            frames.append(pd.read_csv(p/'outcomes.csv'))
            runs.append(dict(seed=seed,quarters=quarters,head=m['head'],error=m['max_accounting_error']))
        a,b=frames[0],frames[1].query('quarter<=2')
        assert a[['region','quarter']].equals(b[['region','quarter']])
        cols=a.select_dtypes('number').columns
        assert np.allclose(a[cols],b[cols],rtol=1e-12,atol=1e-4,equal_nan=True)
    def failures(p):
        return {(c.attrib.get('classname'),c.attrib.get('name')) for c in ET.parse(p).iter('testcase')
                if c.find('failure') is not None or c.find('error') is not None}
    assert failures(OUT/'full_tests.xml')==failures(HERE/'outputs/IFE/full_tests.xml')
    tests=json.loads((OUT/'full_test_execution.json').read_text())
    assert len(tests['failures'])==30 and all(f['known_nan'] for f in tests['failures'])
    micro=[]
    for p in (OUT/'serial').rglob('micro/*.csv'):
        micro.append(dict(file=str(p.relative_to(ROOT)),sha256=sha(p)))
    (OUT/'micro_hashes.json').write_text(json.dumps(micro,indent=2)+'\n')
    (OUT/'audit.json').write_text(json.dumps(dict(protected_inputs=protected,new_input=sha(new),
        runs=runs,full_suite_failure_ids_match_baseline=True,tests=tests['tests'],passed=tests['passed'],
        known_failures=30,extra_failures=0),indent=2)+'\n')
    inventory={str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*')
               if p.is_file() and 'micro' not in p.parts and p.name!='artifact_manifest.json'}
    (OUT/'artifact_manifest.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print('Protected inputs, six serial runs, sources, paired prefixes and failure IDs verified')


if __name__=='__main__':main()
