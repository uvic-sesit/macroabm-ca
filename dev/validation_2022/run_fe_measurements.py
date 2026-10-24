"""Serial measurements. Caller first verifies external simulations have ended.

The initial pilot predated discovery of a separate user linkage run. Final
measurements live in outputs/FE/serial; never overwrite completed runs.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'outputs/FE/serial'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for seed in range(3):
        for quarters in (2,12):
            target=OUT/f'iv-ACDpAIF_q{quarters}_s{seed}'
            if (target/'manifest.json').exists():
                meta=json.loads((target/'manifest.json').read_text())
                if meta['max_accounting_error']>1e-8:raise RuntimeError('Failed completed measurement')
                continue
            subprocess.run([sys.executable,str(HERE/'fe_diagnostics.py'),'--arm','iv-ACDpAIF',
                '--quarters',str(quarters),'--seed',str(seed),'--output',str(OUT)],cwd=ROOT,check=True)


if __name__=='__main__':main()
