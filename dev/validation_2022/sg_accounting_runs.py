"""After serial suite, finish both independent short accounting diagnostics."""
import json,subprocess,sys,time
from prepare_sg import HERE,OUT
def main():
    while not (OUT/'verification/full_test_execution.json').exists():time.sleep(3)
    while not (OUT/'step1_gates.json').exists():time.sleep(3)
    # Final source checks must identify v3 before runs begin.
    from build_sg import target
    from prepare_sg import sha
    while json.loads((OUT/'step1_gates.json').read_text())['FS'].get('pickle_sha256')!=sha(target('FS')):time.sleep(3)
    results=[]
    for arm in ['FS','FS_T']:
        path=OUT/f'{arm}_accounting.log';command=[sys.executable,str(HERE/'sg_diagnostics.py'),'--arm',arm];start=time.time()
        with path.open('w',encoding='utf-8') as log:r=subprocess.run(command,cwd=HERE.parents[1],stdout=log,stderr=subprocess.STDOUT)
        m=OUT/f'runs/F_CFC_SG_{arm}_q2_s0/manifest.json';manifest=json.loads(m.read_text()) if m.exists() else {}
        results.append(dict(arm=arm,exit_code=r.returncode,seconds=time.time()-start,command=command,pickle_sha256=sha(target(arm)),max_accounting_error=manifest.get('max_accounting_error'),passed=r.returncode==0 and manifest.get('max_accounting_error',1.)<1e-8))
        print('SG short accounting diagnostic',results[-1],flush=True)
    (OUT/'short_accounting_execution.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
