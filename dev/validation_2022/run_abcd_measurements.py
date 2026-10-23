"""One subprocess/simulation at a time; stop immediately on a failed battery."""
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE/'outputs/ABCD'
SPECS = [(a, 2, 0) for a in ['iv-A', 'iv-AC', 'iv-ACD', 'v-ACD']]
SPECS += [(a, 12, 0) for a in ['iv-A', 'iv-AC', 'iv-ACD', 'v-ACD']]
SPECS += [(a, 12, s) for s in [1, 2] for a in ['iv-ACD', 'v-ACD']]
SPECS += [('final_d1', 12, s) for s in [1, 2]]


def main():
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONPATH=str(ROOT))
    for arm, quarters, seed in SPECS:
        label = f'{arm}_q{quarters}_s{seed}'
        manifest = OUT/label/'manifest.json'
        if manifest.exists():
            if json.loads(manifest.read_text())['max_accounting_error'] > 1e-8:
                raise RuntimeError(f'Existing failed accounting run: {label}')
            print('completed', label, flush=True)
            continue
        print('starting', label, flush=True)
        with (OUT/f'{label}.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, str(HERE/'abcd_diagnostics.py'), '--arm', arm,
                            '--quarters', str(quarters), '--seed', str(seed)],
                           env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        print('passed', label, flush=True)


if __name__ == '__main__':
    main()
