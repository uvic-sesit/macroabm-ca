"""Serial step A paired accounting/measurement runs; enforce gate before F/E."""
import json
from pathlib import Path
import subprocess
import sys
import pandas as pd
from afe_gate import asset_gate

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'outputs/AFE'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    gates=[]
    for seed in range(3):
        for quarters in [2,12]:
            label=f'iv-ACDpA_q{quarters}_s{seed}'
            manifest=OUT/label/'manifest.json'
            if not manifest.exists():
                print('starting',label,flush=True)
                with (OUT/f'{label}.log').open('w',encoding='utf-8') as log:
                    subprocess.run([sys.executable,str(HERE/'afe_diagnostics.py'),'--arm','iv-ACDpA',
                        '--seed',str(seed),'--quarters',str(quarters)],cwd=ROOT,
                        stdout=log,stderr=subprocess.STDOUT,check=True)
            m=json.loads(manifest.read_text())
            assert m['max_accounting_error']<=1e-8
            print(label,'accounting passes',m['max_accounting_error'],flush=True)
        frame=pd.read_csv(OUT/f'iv-ACDpA_q12_s{seed}'/'outcomes.csv').groupby('quarter').sum(numeric_only=True)
        result=asset_gate(frame.index,frame.constrained_households/frame.represented_households,
                          1-frame.consumption/frame.cash_DI)
        gates.append(dict(seed=seed,**result))
        print('gate',gates[-1],flush=True)
    (OUT/'step_A_gates.json').write_text(json.dumps(gates,indent=2)+'\n')
    if not all(g['gate_pass'] for g in gates):
        print('STOP: Step A gate failed. F and E must not start.',flush=True)
    else:
        print('Step A gate passed on every seed; F is eligible to start.',flush=True)


if __name__=='__main__':
    main()
