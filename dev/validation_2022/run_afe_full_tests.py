"""Run the full suite serially after measurements, recording failures verbatim."""
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE/'outputs/AFE'


def main():
    start = time.time()
    command = [sys.executable, str(HERE/'run_pre_D3_tests.py'), 'tests/', '-q',
               '--basetemp', str(ROOT.parent/'.tmp/afe_tests'),
               '--junitxml', str(OUT/'full_tests.xml')]
    with (OUT/'full_tests.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    xml = ET.parse(OUT/'full_tests.xml')
    cases = list(xml.iter('testcase'))
    failures = []
    for c in cases:
        f = c.find('failure')
        e = c.find('error')
        if f is not None or e is not None:
            node = f if f is not None else e
            failures.append(dict(test=c.attrib, message=node.attrib.get('message',''),
                                 known_nan='Nan in transactor_total_real_supply' in ''.join(node.itertext())))
    metadata = dict(command=command, seconds=time.time()-start, exit_code=result.returncode,
        tests=len(cases), failures=failures,
        passed=sum(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases),
        sampler_properties=[p.attrib for c in cases if c.attrib.get('name')=='test_sampler' for p in c.iter('property')])
    (OUT/'full_test_execution.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps({k:v for k,v in metadata.items() if k not in ['failures','command']}), flush=True)
    print('Failures:',len(failures), 'Beyond known NaN cases:',sum(not f['known_nan'] for f in failures), flush=True)
    if len(failures) != 30 or any(not f['known_nan'] for f in failures):
        raise RuntimeError('Full suite differs from the 30 known NaN cases; inspect log')


if __name__ == '__main__':
    main()
