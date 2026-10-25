"""Finish corrected read-only replays, full serial tests, report and final audit."""
import json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]


def main():
    print('Waiting for all 15 corrected, accounting-checked distribution replays',flush=True)
    while True:
        manifests=list((HERE/'outputs/QE/distribution_corrected').glob('*/manifest.json'))
        try:
            ready=len(manifests)==15 and all(json.loads(p.read_text())['max_accounting_error']<=1e-8 for p in manifests)
        except json.JSONDecodeError:ready=False
        if ready:break
        time.sleep(5)
    for name in ['summarise_qe.py','run_qe_full_tests.py','report_qe.py','audit_qe.py']:
        print('Starting '+name,flush=True)
        subprocess.run([sys.executable,str(HERE/name)],cwd=ROOT,check=True)
    print('Corrected replays, final full tests, report and audit complete',flush=True)

if __name__=='__main__':main()
