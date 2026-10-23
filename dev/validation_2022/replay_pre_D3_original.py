"""Replay original model sources without checking out or modifying another branch.

Run only when no other simulation/test batch is active. Serialized inputs remain
read-only. The snapshot and instrumentation hashes are retained with the result.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[2]


def replay(args):
    snapshot=args.snapshot.resolve();snapshot.mkdir(parents=True,exist_ok=True)
    archive=subprocess.check_output(['git','archive',args.commit,'macromodel'],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(snapshot,filter='data')
    dest=snapshot/'dev/validation_2022';(dest/'battery').mkdir(parents=True,exist_ok=True)
    for name in ['closure_diagnostics.py','battery/accounting.py']:
        (dest/name).write_bytes((Path(__file__).parent/name).read_bytes())
    env=os.environ.copy()
    env['PYTHONPATH']=str(ROOT)+os.pathsep+env.get('PYTHONPATH','')
    subprocess.run([sys.executable,'-u',str(dest/'closure_diagnostics.py'),
        '--arm',args.arm,'--label','b1','--quarters',str(args.quarters),'--seed',str(args.seed),
        '--pickle',str(ROOT/'dev/pkl_files/io2022_household_agreed.pkl'),
        '--output',str(args.output.resolve())],cwd=ROOT,env=env,check=True)
    path=args.output/f'b1_{args.arm}_q{args.quarters}_s{args.seed}'/'manifest.json'
    manifest=json.loads(path.read_text())
    manifest.update(native_source_commit=subprocess.check_output(['git','rev-parse',args.commit],cwd=ROOT,text=True).strip(),
                    source_archive_sha256=hashlib.sha256(archive).hexdigest(),snapshot_root=str(snapshot))
    path.write_text(json.dumps(manifest,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--commit',default='b1b2960')
    parser.add_argument('--arm',choices=['iii','iv','v','d1'],default='d1')
    parser.add_argument('--quarters',type=int,default=12)
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--snapshot',type=Path,default=ROOT.parent/'.tmp/preD3_b1_source')
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'outputs/pre_D3_checks')
    replay(parser.parse_args())
