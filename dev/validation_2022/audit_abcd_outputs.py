"""Audit frozen measurement evidence without starting another simulation."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE/'outputs/ABCD'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def failed(xml):
    return {(c.get('classname'), c.get('name')) for c in ET.parse(xml).iter('testcase')
            if c.find('failure') is not None or c.find('error') is not None}


def main():
    rows = []
    for base in [OUT, HERE/'outputs/ABCD_original_d1']:
        for p in sorted(base.glob('*/manifest.json')):
            m = json.loads(p.read_text())
            if m.get('label') == 'bankcap':
                continue  # Earlier B-only preflight, not the frozen A-D comparison.
            assert m['max_accounting_error'] < 1e-8
            assert sha(ROOT/m['pickle']) == m['pickle_sha256']
            for source, checksum in m['source_sha256'].items():
                assert sha(ROOT/source) == checksum, (p, source)
            b = pd.read_csv(p.parent/'banks.csv')
            assert (b[b.stage=='end'].equity >= 0).all()
            r = pd.read_csv(p.parent/'resolutions.csv')
            assert (r.recapitalisation >= 0).all()
            assert np.allclose(r.equity_after.to_numpy(float)-r.equity_before.to_numpy(float),
                               r.recapitalisation.to_numpy(float), rtol=1e-12)
            rows.append(dict(run=str(p.parent.relative_to(HERE)), error=m['max_accounting_error'],
                             resolutions=len(r), source_hashes_match=True, input_hash_matches=True))
    assert len(rows) == 16
    tests = json.loads((OUT/'full_test_execution.json').read_text())
    assert tests['passed'] == 398 and len(tests['failures']) == 30
    assert all(f['known_nan'] for f in tests['failures'])
    assert tests['sampler_properties'] == [{'name':'sampler_n_cores','value':'1'}]
    assert failed(OUT/'full_tests.xml') == failed(HERE/'outputs/pre_D3_checks/full_tests.xml')
    protected = {'io2022_phaseA.pkl':'4bf77da7707cab00d507c4505c16740224863298ba9b858e5aaf6d60a9c2dc4c',
                 'io2022_household_agreed.pkl':'3b48c0dba90c2d3c837f92bc0477e4b242ba0afa78275b095e26cc52b4fcb313'}
    for name, checksum in protected.items():
        assert sha(ROOT/'dev/pkl_files'/name) == checksum
    audit = dict(runs=rows, full_suite=dict(passed=398,known_failures=30,extra_failures=0,
                 failure_identities_match_previous_suite=True,sampler_workers=1),
                 protected_pickles=protected, native_head='3054d2e')
    (OUT/'audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    files = {}
    for base in [OUT, HERE/'outputs/ABCD_original_d1', HERE/'benchmarks/ABCD']:
        for p in base.rglob('*'):
            if p.is_file() and 'micro' not in p.parts and p.name != 'artifact_manifest.json':
                files[str(p.relative_to(ROOT))] = sha(p)
    (OUT/'artifact_manifest.json').write_text(json.dumps(files, indent=2)+'\n')
    print(f'{len(rows)} measurement runs audited; 398 pass / same 30 known failures; protected inputs unchanged')


if __name__ == '__main__':
    main()
