"""Freeze public source blobs and aggregate evidence; exclude all pickles/microdata."""
import json,hashlib
from prepare_sg import HERE,ROOT,BENCH,OUT
def main():
    assert json.loads((OUT/'audit.json').read_text())['passed']
    for p in OUT.glob('*.log'):
        raw=p.read_bytes()
        if raw.startswith(b'\xff\xfe'):p.write_text(raw.decode('utf-16'),encoding='utf-8')
    selected=list(BENCH.rglob('*'))+list(OUT.glob('*.csv'))+list(OUT.glob('*.json'))+list(OUT.glob('*.log'))+[OUT/'.gitattributes']
    for arm in ['FS','FS_T']:selected+=list((OUT/arm).glob('*.csv'))
    selected+=list((OUT/'verification').glob('*'))
    logs=OUT/'execution_logs';logs.mkdir(exist_ok=True)
    for p in HERE.glob('sg*.log'):
        raw=p.read_bytes();enc='utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8';t=logs/p.name;t.write_text(raw.decode(enc),encoding='utf-8');selected.append(t)
    manifest=OUT/'artifact_manifest.json';selected=sorted(set(p for p in selected if p.is_file() and p!=manifest));assert not any(p.suffix=='.pkl' or 'micro' in p.parts for p in selected)
    manifest.write_text(json.dumps(dict(scope='SG public git-blob inputs, aggregate diagnostics, failed-run traces and full-suite evidence. No household microdata, pickles or fabricated12Q results.',files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in selected]),indent=2)+'\n');selected.append(manifest)
    selected += [HERE/n for n in ['sg_households.py','sg_source_audit.py','summarise_sg.py','report_sg.py','audit_sg.py','freeze_sg.py','run_sg_tests.py','after_sg_tests.py','sg_diagnostics.py','sg_accounting_runs.py','sg_failure_probe.py','cache_sg_rent.py','CLOSURE_SG_2026-10-25.md','ISSUE_REGISTER.md']]
    (HERE/'sg_stage_paths.bin').write_bytes(b'\0'.join(p.relative_to(ROOT).as_posix().encode('utf-8') for p in selected)+b'\0');print('SG staging paths',len(selected),'bytes',sum(p.stat().st_size for p in selected))
if __name__=='__main__':main()
