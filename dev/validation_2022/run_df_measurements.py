"""Steps 1–3 only: one 2Q/12Q household pair at a time; never start F."""
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE/'outputs/DF'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for seed in range(3):
        for arm in ['iv-ACDp','v-ACDp']:
            for quarters in [2,12]:
                label = f'{arm}_q{quarters}_s{seed}'
                manifest = OUT/label/'manifest.json'
                if not manifest.exists():
                    print('starting',label,flush=True)
                    with (OUT/f'{label}.log').open('w',encoding='utf-8') as log:
                        subprocess.run([sys.executable,str(HERE/'df_diagnostics.py'),'--arm',arm,
                            '--seed',str(seed),'--quarters',str(quarters)],cwd=ROOT,
                            stdout=log,stderr=subprocess.STDOUT,check=True)
                m = json.loads(manifest.read_text())
                assert m['max_accounting_error'] <= 1e-8
                print(label, 'passed accounting; Q1 gap',m['Q1_consumption_shortfall'],
                      'household gate',m['household_gate_passed'],flush=True)
    print('Steps 1–3 complete. F is not implemented in this staged pass.',flush=True)


if __name__ == '__main__':
    main()
