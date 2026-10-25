"""Finalize the frozen report after the serial suite completes."""
import time,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
while not (HERE/'outputs/IH/verification_final/full_test_execution.json').exists():time.sleep(3)
for script in ['report_ih.py','audit_ih.py']:
    subprocess.run([sys.executable,str(HERE/script)],check=True,cwd=HERE.parents[1])
print('IH_REPORT_AND_AUDIT_COMPLETE',flush=True)
