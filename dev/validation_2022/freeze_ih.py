"""Select aggregate evidence only; exclude household microdata and all pickles."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'outputs/IH'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert json.loads((OUT/'audit.json').read_text())['passed']
    selected=list(OUT.glob('*.csv'))+list(OUT.glob('*.json'))+[OUT/'.gitattributes']
    selected+=list((HERE/'benchmarks/IH').glob('*'))
    for folder in ['runs','entrant_replays']:
        for run in (OUT/folder).iterdir():
            if not run.is_dir():continue
            selected.extend(p for p in run.iterdir() if p.name in ['manifest.json','accounting.csv','headline.csv','outcomes.csv','banks.csv','resolutions.csv','income_quintiles.csv'])
    selected+=list((OUT/'logs').glob('*.log'))+list((OUT/'source_snapshots').glob('*.py'))
    selected+=list((OUT/'verification_final').glob('*'))
    selected.append(OUT/'verification/full_test_execution.json')
    logs=OUT/'execution_logs';logs.mkdir(exist_ok=True)
    for name in ['ih_execution.log','ih_finish.log','ih_entrant_audit.log','ih_complete.log','ih_pilot.log']:
        p=HERE/name;b=p.read_bytes();encoding='utf-16' if b.startswith(b'\xff\xfe') else 'utf-8'
        target=logs/name;target.write_text(b.decode(encoding),encoding='utf-8');selected.append(target)
    manifest=OUT/'artifact_manifest.json';selected=sorted(set(p for p in selected if p.is_file() and p!=manifest))
    assert all('micro' not in p.parts and p.suffix not in ['.pkl','.pdf'] for p in selected)
    records=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in selected]
    manifest.write_text(json.dumps(dict(files=records,scope='Frozen aggregate IH evidence; excludes household microdata, pickles and unvalidated vintage metrics.'),indent=2)+'\n');selected.append(manifest)
    helpers=['finish_ih.py','complete_ih.py','report_ih.py','audit_ih.py','freeze_ih.py','prepare_ih.py']
    docs=['CLOSURE_IH_2026-10-25.md','IO_HANDOFF_2026-10-25.md','ISSUE_REGISTER.md']
    selected += [HERE/n for n in helpers+docs]
    (HERE/'ih_stage_paths.bin').write_bytes(b'\0'.join(p.relative_to(ROOT).as_posix().encode('utf-8') for p in selected)+b'\0')
    print('Staging paths',len(selected),'aggregate bytes',sum(p.stat().st_size for p in selected))
if __name__=='__main__':main()
