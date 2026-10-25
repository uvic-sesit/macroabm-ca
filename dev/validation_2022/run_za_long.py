"""Continue only from independently certified short-run gates; serial seeds."""
import json,subprocess,sys,time
from datetime import datetime,timezone
from prepare_za import HERE,ROOT,OUT
def main():
    # The earlier controller finishes its independent FS fallback checks first.
    while not (OUT/'adoption_result.json').exists():time.sleep(3)
    pre=json.loads((OUT/'FS_T_pre_run_gates.json').read_text());short=json.loads((OUT/'FS_T_short_certificate.json').read_text());assert pre['pre_run_passed'] and short['passed']
    records=[]
    for seed in range(3):
        start=datetime.now(timezone.utc).isoformat();path=OUT/'logs'/f'FS_T_q12_s{seed}.log';cmd=[sys.executable,str(HERE/'za_diagnostics.py'),'--arm','FS_T','--quarters','12','--seed',str(seed)]
        with path.open('w',encoding='utf-8') as log:r=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        records.append(dict(seed=seed,exit_code=r.returncode,start_utc=start,end_utc=datetime.now(timezone.utc).isoformat(),command=cmd));(OUT/'long_execution.json').write_text(json.dumps(records,indent=2)+'\n');print('FS_T seed',seed,'exit',r.returncode,flush=True)
    passed=all(r['exit_code']==0 for r in records)
    (OUT/'adoption_final_result.json').write_text(json.dumps(dict(passing_arm='FS_T' if passed else None,Step3_passed=passed,Step4_authorized=passed,short_certificate='FS_T_short_certificate.json',note='Earlier controller incorrectly treated the undefinedQ0 forecast placeholder as a state failure; wrapper/audit corrected, economic2Q run/accounting unchanged. Its FS fallback prechecks retained as an extra diagnostic, not a new adoption choice.'),indent=2)+'\n')
if __name__=='__main__':main()
