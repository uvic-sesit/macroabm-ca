"""Freeze public sources and aggregate ZA evidence, never household microdata."""
import json
from prepare_za import HERE,ROOT,BENCH,OUT,sha

def main():
    assert json.loads((OUT/'audit.json').read_text())['passed']
    selected=list(BENCH.rglob('*'))+list(OUT.glob('*.csv'))+list(OUT.glob('*.json'))+list(OUT.glob('*.log'))+list(OUT.glob('*.xml'))+[OUT/'.gitattributes']
    selected+=list((OUT/'logs').glob('*'))
    for arm in ['FS_T','FS']:selected+=list((OUT/arm).glob('*.csv'))
    run_names=['manifest.json','accounting.csv','headline.csv','outcomes.csv','banks.csv','resolutions.csv',
        'floor_states.csv','income_flows.csv','income_quintiles.csv','household_groups.csv',
        'constraint_diagnosis.csv','cash_ledger_groups.csv','investment_calibration.csv','investment_rule.csv',
        'saving_calibration.csv','consumption_quintiles.csv','price_parameters.csv']
    for directory in (OUT/'runs').iterdir():
        selected += [directory/name for name in run_names if (directory/name).exists()]
    logs=OUT/'logs'
    for name in ['za_positive_replay.log','za_build_FS_T.log','za_check_FS_T.log','za_adoption.log','za_long.log','za_housing.log']:
        original=HERE/name
        if original.exists():
            raw=original.read_bytes();path=logs/name
            path.write_text(raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8'),encoding='utf-8')
            selected.append(path)
    manifest=OUT/'artifact_manifest.json'
    selected=sorted(set(p for p in selected if p.is_file() and p!=manifest))
    assert not any(p.suffix=='.pkl' or 'micro' in p.parts or p.name in ['new_lending.csv'] for p in selected)
    for p in selected:
        if p.suffix=='.log':
            raw=p.read_bytes()
            if raw.startswith(b'\xff\xfe'):p.write_text(raw.decode('utf-16'),encoding='utf-8')
    manifest.write_text(json.dumps(dict(scope='ZA immutable public-source excerpts, aggregate seed/quarter evidence, firm-floor audits, failed preflight logs and exact full-suite evidence. No pickles or household microdata.',files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in selected]),indent=2)+'\n')
    selected.append(manifest)
    selected += [HERE/name for name in ['za_housing.py','za_fsg_investors.py','summarise_za.py','report_za.py','audit_za.py','freeze_za.py','after_za_tests.py','run_za_full_tests.py','CLOSURE_ZA_2026-10-25.md','ISSUE_REGISTER.md']]
    (HERE/'za_stage_paths.bin').write_bytes(b'\0'.join(p.relative_to(ROOT).as_posix().encode() for p in selected)+b'\0')
    print('ZA evidence paths',len(selected),'bytes',sum(p.stat().st_size for p in selected))

if __name__=='__main__':main()
