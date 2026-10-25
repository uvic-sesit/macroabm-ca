"""After the full serial suite, perform read-only t0 plan probes without iterations."""
import time,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
while not (HERE/'outputs/HI/verification/full_test_execution.json').exists():time.sleep(3)
subprocess.run([sys.executable,str(HERE/'hi_t0_probe.py')],check=True,cwd=HERE.parents[1])
