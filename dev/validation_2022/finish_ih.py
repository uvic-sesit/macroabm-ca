"""Wait for serial IH measurements, then run the full one-worker suite."""
import time,subprocess,sys,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/IH/verification';OUT.mkdir(parents=True,exist_ok=True)
log=HERE/'ih_execution.log'
while 'E2_q12_s2 0' not in log.read_text(encoding='utf-16' if log.read_bytes().startswith(b'\xff\xfe') else 'utf-8'):
    text=log.read_text(encoding='utf-16' if log.read_bytes().startswith(b'\xff\xfe') else 'utf-8')
    if 'Traceback' in text:raise RuntimeError('Serial run failed; inspect ih_execution.log')
    time.sleep(3)
subprocess.run([sys.executable,str(HERE/'summarise_ih.py')],check=True)
import run_be_full_tests as tests
tests.OUT=OUT
tests.main()
