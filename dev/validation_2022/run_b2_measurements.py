"""Serial B2 base and all requested sensitivities on seeds 0-2."""
import subprocess
import sys
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]


def main():
    for variant,kappa,below in [('base',.01,None),('k005',.005,None),('k020',.02,None),('asymmetric',.005,.02)]:
        for seed in range(3):
            for quarters in ((2,12) if variant=='base' else (12,)):
                out=HERE/'outputs/B2/final'/f'B2_{variant}_q{quarters}_s{seed}'
                if (out/'manifest.json').exists():
                    m=json.loads((out/'manifest.json').read_text())
                    assert m['max_accounting_error']<=1e-8
                    continue
                command=[sys.executable,str(HERE/'b2_diagnostics.py'),'--arm','B2','--variant',variant,
                    '--quarters',str(quarters),'--seed',str(seed),'--kappa',str(kappa),'--output',str(out.parent)]
                if below is not None:command+=['--kappa-below',str(below)]
                subprocess.run(command,cwd=ROOT,check=True)


if __name__=='__main__':main()
