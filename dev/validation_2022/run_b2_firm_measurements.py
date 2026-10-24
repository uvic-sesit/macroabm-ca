"""Independent Step 2 on accepted FE arm F; validation simulations serial."""
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    for seed in range(3):
        for quarters in (2,12):
            out=HERE/'outputs/B2/final'/f'F_CFC_base_q{quarters}_s{seed}'
            if (out/'manifest.json').exists():
                m=json.loads((out/'manifest.json').read_text())
                assert m['max_accounting_error']<=1e-8
                continue
            subprocess.run([sys.executable,str(HERE/'b2_diagnostics.py'),
                '--arm','F_CFC','--household-base','F','--seed',str(seed),'--quarters',str(quarters),
                '--pickle',str(ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt_cfc_v2.pkl'),
                '--output',str(out.parent)],cwd=ROOT,check=True)

if __name__=='__main__':main()
