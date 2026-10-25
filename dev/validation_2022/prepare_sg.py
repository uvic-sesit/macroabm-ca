"""Read immutable IO git blobs; never depend on or modify its working tree."""
from pathlib import Path
import subprocess,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];IO=ROOT.parent/'macroabm-io2022';BENCH=HERE/'benchmarks/SG';OUT=HERE/'outputs/SG'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    BENCH.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
    git=['git','-c','safe.directory='+IO.as_posix(),'-C',str(IO)]
    commit=subprocess.check_output(git+['rev-parse','feature/sut-balance']).decode().strip();assert commit.startswith('d847fb2')
    files=['HANDOFF_TO_VALIDATION_2026-10-25.md','SUT_BALANCE_2026-10-25.md','compatibility/compat_icio_2022_can_provinces.csv','canonical/VA_tax_output_basic.csv','canonical/Z_intermediate_basic.csv','canonical/FD_by_source_and_category_basic.csv','canonical/reexports_by_province_commodity_basic.csv','validation/final_checks.json','src/ioqc/stages.py','canonical/SCHEMA.json']
    meta=[]
    for ref,names,prefix in [('feature/sut-balance',files,''),('479dcb4',files[2:6],'before/')]:
        for name in names:
            b=subprocess.check_output(git+['show',ref+':'+name]);p=BENCH/(prefix+name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
            meta.append(dict(file=prefix+name,git_ref=ref,commit=commit if not prefix else '479dcb4',sha256=sha(p),CRLF_sha256=hashlib.sha256(b.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')).hexdigest(),retrieved_utc='2026-10-25'))
    compat=meta[2];assert compat['CRLF_sha256']=='41590fdb19d9eb79758169b51afc0751e6d5c19ce88183bb8fbe330889e689aa'
    (BENCH/'source_provenance.json').write_text(json.dumps(dict(files=meta,hash_note='Handoff SHA is Windows CRLF bytes. Git show returns LF bytes; both hashes recorded and CRLF conversion matches exactly. No numerical/content substitution.'),indent=2)+'\n')
    (BENCH/'.gitattributes').write_text('* -text -whitespace\n')
    (OUT/'.gitattributes').write_text('* -text -whitespace\n')
    print('Verified source commit and compatibility content; LF hash',compat['sha256'])
if __name__=='__main__':main()
