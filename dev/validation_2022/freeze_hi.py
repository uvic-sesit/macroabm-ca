"""Freeze HI aggregate evidence and logs; exclude microdata and pickles."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'outputs/HI'
def main():
    assert json.loads((OUT/'audit.json').read_text())['passed']
    selected=list(OUT.glob('*.csv'))+list(OUT.glob('*.json'))+[OUT/'.gitattributes']
    selected+=list((HERE/'benchmarks/HI').glob('*'))+list((OUT/'verification').glob('*'))
    names=['manifest.json','accounting.csv','headline.csv','outcomes.csv','banks.csv','resolutions.csv','CIS_deciles.csv','income_quintiles.csv','consumption_quintiles.csv','income_flows.csv','investment_cells.csv','investment_calibration.csv','saving_calibration.csv','wealth_definition_audit.csv','household_groups.csv','cash_ledger_groups.csv','constraint_diagnosis.csv','new_lending.csv','L.csv']
    for run in (OUT/'runs').iterdir():selected += [p for p in run.iterdir() if p.name in names]
    logs=OUT/'execution_logs';logs.mkdir(exist_ok=True)
    for source in HERE.glob('hi*.log'):
        raw=source.read_bytes();enc='utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8';p=logs/source.name;p.write_text(raw.decode(enc),encoding='utf-8');selected.append(p)
    manifest=OUT/'artifact_manifest.json';selected=sorted(set(p for p in selected if p.is_file() and p!=manifest))
    assert all('micro' not in p.parts and p.suffix!='.pkl' for p in selected)
    manifest.write_text(json.dumps(dict(scope='HI aggregate evidence. Excludes household microdata, all pickles, and unsupported historical intermediate-stage reconstruction.',files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in selected]),indent=2)+'\n');selected.append(manifest)
    selected += [HERE/n for n in ['run_hi_tests.py','after_hi_tests.py','hi_t0_probe.py','hi_stage_replay.py','summarise_hi.py','report_hi.py','audit_hi.py','freeze_hi.py','CLOSURE_HI_2026-10-25.md','ISSUE_REGISTER.md','hi_income_audit.py']]
    (HERE/'hi_stage_paths.bin').write_bytes(b'\0'.join(p.relative_to(ROOT).as_posix().encode('utf-8') for p in selected)+b'\0')
    print('HI aggregate staging paths:',len(selected),'bytes:',sum(p.stat().st_size for p in selected))
if __name__=='__main__':main()
