"""Released independent E arm on accepted F_CFC, one simulation at a time."""
import json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def main():
    for seed,quarters in [(0,2),(0,4),(0,12),(1,12),(2,12)]:
        out=HERE/'outputs/QE/runs'/f'E_cashfix_q{quarters}_s{seed}'
        if (out/'manifest.json').exists():
            assert json.loads((out/'manifest.json').read_text())['max_accounting_error']<=1e-8
            continue
        subprocess.run([sys.executable,str(HERE/'qe_diagnostics.py'),'--arm','E','--quarters',str(quarters),'--seed',str(seed),'--variant','cashfix'],cwd=ROOT,check=True)

if __name__=='__main__':main()
