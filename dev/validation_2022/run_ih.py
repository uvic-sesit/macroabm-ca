"""Serial IH measurements, with accounting checked before each later run."""
from pathlib import Path
import subprocess,sys,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'outputs/IH'
OUT.mkdir(exist_ok=True);(OUT/'logs').mkdir(exist_ok=True)
for arm,quarters,seed in ([('F_CFC',12,s) for s in range(3)]+[('E',12,s) for s in range(3)]+[('E2',2,0)]+[('E2',12,s) for s in range(3)]):
    name=f'{arm}_q{quarters}_s{seed}'
    with (OUT/'logs'/f'{name}.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,str(HERE/'ih_diagnostics.py'),'--arm',arm,'--quarters',str(quarters),'--seed',str(seed)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    print(name,result.returncode,flush=True)
    if result.returncode:raise RuntimeError(name+' failed; see log')
