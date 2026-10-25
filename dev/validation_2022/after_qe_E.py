"""Finish independent read-only C accounting replay, summary, then full tests."""
import json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def main():
    final=HERE/'outputs/QE/runs/E_cashfix_q12_s2'
    print('Waiting for serial E measurements',flush=True)
    while True:
        try:
            m=json.loads((final/'manifest.json').read_text())
            ready=(final/'headline.csv').exists() and 'QE_sources' in m and m['max_accounting_error']<=1e-8
        except (FileNotFoundError,json.JSONDecodeError):ready=False
        if ready:break
        time.sleep(5)
    for script in ['replay_qe_C_banks.py','summarise_qe.py','run_qe_full_tests.py']:
        print('Starting '+script,flush=True)
        subprocess.run([sys.executable,str(HERE/script)],cwd=ROOT,check=True)
    print('All serial measurements and final tests complete',flush=True)

if __name__=='__main__':main()
