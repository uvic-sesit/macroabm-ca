"""Correct the read-only reset classification; prove all economic paths unchanged."""
import subprocess,sys,json
from pathlib import Path
import pandas as pd,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'outputs/IH';proof=[]
for seed in range(3):
    with (OUT/'logs'/f'entrant_replay_s{seed}.log').open('w',encoding='utf-8') as log:
        subprocess.run([sys.executable,str(HERE/'ih_diagnostics.py'),'--arm','E','--seed',str(seed),'--quarters','12','--variant','IH_E_entrant_audit','--output',str(OUT/'entrant_replays')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    old=OUT/'runs'/f'E_IH_E_q12_s{seed}';new=OUT/'entrant_replays'/f'E_IH_E_entrant_audit_q12_s{seed}'
    for filename in ['outcomes.csv','headline.csv','accounting.csv']:
        a=pd.read_csv(old/filename);b=pd.read_csv(new/filename);assert a.equals(b),(seed,filename)
    proof.append(dict(seed=seed,economic_paths_exact=True,accounting_exact=True,max_accounting_error=json.loads((new/'manifest.json').read_text())['max_accounting_error']))
    print('entrant audit',seed,'exact',flush=True)
(OUT/'entrant_replay_proof.json').write_text(json.dumps(proof,indent=2)+'\n')
import run_be_full_tests as tests
tests.OUT=OUT/'verification_final';tests.OUT.mkdir(exist_ok=True);tests.main()
