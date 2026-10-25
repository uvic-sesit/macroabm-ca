"""Serial final suite: compare exact test IDs against the accepted SG failures."""
import json,subprocess,sys,time,xml.etree.ElementTree as ET
from prepare_za import ROOT,HERE,OUT

def main():
    assert (OUT/'adoption_final_result.json').exists()
    command=[sys.executable,str(HERE/'run_pre_D3_tests.py'),'tests/','-q',
             '--basetemp',str(ROOT.parent/'.tmp/za_tests'),'--junitxml',str(OUT/'full_tests.xml')]
    start=time.time()
    with (OUT/'full_tests.log').open('w',encoding='utf-8') as log:
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    cases=list(ET.parse(OUT/'full_tests.xml').iter('testcase'))
    old=list(ET.parse(HERE/'outputs/SG/verification/full_tests.xml').iter('testcase'))
    key=lambda c:(c.get('classname'),c.get('name'))
    failed=lambda c:c.find('failure') is not None or c.find('error') is not None
    known={key(c) for c in old if failed(c)}
    failures=[dict(test=c.attrib,message=''.join(c.itertext()),known=key(c) in known) for c in cases if failed(c)]
    new=[f for f in failures if not f['known']]
    record=dict(command=command,seconds=time.time()-start,exit_code=result.returncode,tests=len(cases),
                passed=sum(not failed(c) and c.find('skipped') is None for c in cases),failures=failures,
                additional_failures=len(new),removed_known_failures=[list(k) for k in known-{key(c) for c in cases if failed(c)}],
                sampler_properties=[p.attrib for c in cases if c.get('name')=='test_sampler' for p in c.iter('property')])
    (OUT/'full_test_execution.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k not in ['command','failures']},indent=2),flush=True)
    assert not new

if __name__=='__main__':main()
