"""Wait for the one-worker suite, then verify final source candidates serially."""
import time,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    while not (HERE/'outputs/SG/verification/full_test_execution.json').exists():time.sleep(3)
    for name in ['check_sg.py','summarise_sg.py']:
        subprocess.run([sys.executable,str(HERE/name)],check=True,cwd=HERE.parents[1])
