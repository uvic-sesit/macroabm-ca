"""Serial B base/sensitivity or prudent-payout runs; fail on first error."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main(payout=False):
    specs=[(s,q,'base',.1,.25) for s in range(3) for q in (2,12)]
    if not payout:
        specs += [(0,12,'k005',.05,.25),(0,12,'k015',.15,.25),
                  (0,12,'l0125',.1,.125),(0,12,'l0375',.1,.375)]
    arm='iv-ACDpAIFBP' if payout else 'iv-ACDpAIFB'
    for seed,quarters,variant,kappa,smoothing in specs:
        path=HERE/'outputs/BE'/f'{arm}_{variant}_q{quarters}_s{seed}'
        if (path/'manifest.json').exists():
            meta=json.loads((path/'manifest.json').read_text())
            if meta['max_accounting_error']>1e-8:raise AssertionError('Completed run fails accounting')
            continue
        command=[sys.executable,str(HERE/'be_diagnostics.py'),'--arm',arm,'--quarters',str(quarters),
                 '--seed',str(seed),'--variant',variant,'--kappa',str(kappa),'--smoothing',str(smoothing)]
        if payout: command+=['--payout']
        subprocess.run(command,cwd=ROOT,check=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--payout',action='store_true');main(ap.parse_args().payout)
