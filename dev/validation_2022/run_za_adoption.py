"""Enforce serial adoption gates; no fallback tuning and no dependent runs on failure."""
import json,subprocess,sys,time
from datetime import datetime,timezone
from prepare_za import HERE,ROOT,OUT
def main():
    while not (OUT/'OOH_method.json').exists():time.sleep(3)
    attempts=[];chosen=None
    def execute(label,command):
        path=OUT/'logs'/f'{label}.log';path.parent.mkdir(exist_ok=True);start=datetime.now(timezone.utc).isoformat();clock=time.time()
        with path.open('w',encoding='utf-8') as log:r=subprocess.run([sys.executable,*command],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        record=dict(label=label,command=command,start_utc=start,end_utc=datetime.now(timezone.utc).isoformat(),seconds=time.time()-clock,exit_code=r.returncode);attempts.append(record);(OUT/'adoption_execution.json').write_text(json.dumps(attempts,indent=2)+'\n');print(label,'exit',r.returncode,flush=True);return r.returncode==0
    for arm in ['FS_T','FS']:
        if arm=='FS':
            if not execute('FS_v4_build',[str(HERE/'build_za.py'),'--arm','FS']):continue
            if not execute('FS_v4_prechecks',[str(HERE/'check_za.py'),'--arm','FS']):continue
        gate=json.loads((OUT/f'{arm}_pre_run_gates.json').read_text())
        if not gate['pre_run_passed']:continue
        if not execute(f'{arm}_q2_s0',[str(HERE/'za_diagnostics.py'),'--arm',arm,'--quarters','2','--seed','0']):continue
        m=json.loads((OUT/f'runs/F_CFC_ZA_{arm}_q2_s0/manifest.json').read_text());assert m['max_accounting_error']<1e-8
        results=[]
        for seed in range(3):
            ok=execute(f'{arm}_q12_s{seed}',[str(HERE/'za_diagnostics.py'),'--arm',arm,'--quarters','12','--seed',str(seed)]);results.append(ok)
        if all(results):chosen=arm;break
    result=dict(passing_arm=chosen,Step3_passed=chosen is not None,Step4_authorized=chosen is not None,rule='No tuning. FS tried only after FS_T fails.12Q seeds0-2 run serially only after prechecks and2Q accounting pass.')
    (OUT/'adoption_result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
