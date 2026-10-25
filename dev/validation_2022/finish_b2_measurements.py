"""Wait for serial diagnostic replays, then final verification and report."""
from pathlib import Path
import subprocess
import sys
import time
import psutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def replay_running():
    for p in psutil.process_iter(['cmdline']):
        try:
            if any(a.replace('\\','/').endswith('/replay_b2_distributions.py') for a in p.info['cmdline'] or []):return True
        except (psutil.AccessDenied,psutil.NoSuchProcess):pass
    return False

def main():
    while replay_running():time.sleep(3)
    complete=list((HERE/'outputs/B2/distribution_replays_v2').glob('*/manifest.json'))
    if len(complete)!=15:raise RuntimeError(f'Expected 15 completed distribution replays, found {len(complete)}')
    for script in ['summarise_b2.py','run_b2_full_tests.py','report_b2.py','update_b2_issue_register.py','audit_b2.py']:
        print('Starting',script,flush=True)
        subprocess.run([sys.executable,str(HERE/script)],cwd=ROOT,check=True)
    print('Final report and audit complete',flush=True)

if __name__=='__main__':main()
