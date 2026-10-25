"""One validation simulation at a time; no fitting after construction failure."""
import subprocess,sys,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def main():
    for arm in ['C','F','F_CFC','Q']:
        for seed in range(3):
            out=HERE/'outputs/QE/runs'/f'{arm}_base_q12_s{seed}'
            if (out/'manifest.json').exists():
                assert json.loads((out/'manifest.json').read_text())['max_accounting_error']<=1e-8
                continue
            subprocess.run([sys.executable,str(HERE/'qe_diagnostics.py'),'--arm',arm,'--quarters','12','--seed',str(seed)],cwd=ROOT,check=True)

if __name__=='__main__':main()
