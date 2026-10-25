"""Finalize read-only evidence only after the serial suite has finished."""
import json,subprocess,sys,time
from prepare_za import ROOT,HERE,OUT

def main():
    while True:
        try:
            tests=json.loads((OUT/'full_test_execution.json').read_text())
            break
        except (FileNotFoundError,json.JSONDecodeError):
            time.sleep(10)
    assert tests['additional_failures']==0
    for name in ['summarise_za.py','audit_za.py','report_za.py','freeze_za.py']:
        print('FINALIZE',name,flush=True)
        subprocess.run([sys.executable,str(HERE/name)],cwd=ROOT,check=True)
    print('ZA_FINAL_EVIDENCE_READY',flush=True)

if __name__=='__main__':main()
