"""All step-1 seed pairs run serially; no F/E starts before the revised gate."""
import json
from pathlib import Path
import subprocess
import sys
import pandas as pd
from ife_gates import investment_gate
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'outputs/IFE'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    gates=[]
    for seed in range(3):
        for quarters in [2,12]:
            label=f'iv-ACDpAI_q{quarters}_s{seed}'
            manifest=OUT/label/'manifest.json'
            if not manifest.exists():
                print('starting',label,flush=True)
                with (OUT/f'{label}.log').open('w',encoding='utf-8') as log:
                    subprocess.run([sys.executable,str(HERE/'ife_diagnostics.py'),'--arm','iv-ACDpAI',
                        '--seed',str(seed),'--quarters',str(quarters)],cwd=ROOT,
                        stdout=log,stderr=subprocess.STDOUT,check=True)
            m=json.loads(manifest.read_text());assert m['max_accounting_error']<=1e-8
            print(label,'accounting passes',m['max_accounting_error'],flush=True)
        x=pd.read_csv(OUT/f'iv-ACDpAI_q12_s{seed}/outcomes.csv')
        result=investment_gate(x[x.quarter==1].investment.sum())
        gates.append(dict(seed=seed,**result))
        print('gate1',gates[-1],flush=True)
    (OUT/'gate1.json').write_text(json.dumps(gates,indent=2)+'\n')
    print('Gate 1 passes on all seeds; F eligible.' if all(g['gate1_pass'] for g in gates)
          else 'STOP before F/E: gate 1 fails.',flush=True)


if __name__=='__main__':main()
