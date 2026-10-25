"""Wait for the final serial Q measurement, then probe FB and E accounting."""
import json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def main():
    final=HERE/'outputs/QE/runs/Q_base_q12_s2'
    print('Waiting for all initial measurements to finish',flush=True)
    while True:
        try:
            ready=(final/'headline.csv').exists() and 'QE_sources' in json.loads((final/'manifest.json').read_text())
        except (FileNotFoundError,json.JSONDecodeError):ready=False
        if ready:break
        time.sleep(5)
    print('Initial serial measurements complete; checking FB then E pilot',flush=True)
    subprocess.run([sys.executable,str(HERE/'check_qe_bridge.py')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(HERE/'qe_diagnostics.py'),'--arm','E','--quarters','2','--seed','0'],cwd=ROOT,check=True)
    print('FB probe and E accounting pilot complete',flush=True)

if __name__=='__main__':main()
