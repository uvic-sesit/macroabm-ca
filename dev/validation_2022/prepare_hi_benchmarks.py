"""Freeze CIS published distribution tables for the HI audit."""
from pathlib import Path
import requests,zipfile,io,json,hashlib
from datetime import datetime,timezone
import pandas as pd
HERE=Path(__file__).resolve().parent;OUT=HERE/'benchmarks/HI';OUT.mkdir(parents=True,exist_ok=True)
for table in ['11100192','11100193']:
    url=f'https://www150.statcan.gc.ca/n1/tbl/csv/{table}-eng.zip';r=requests.get(url,timeout=120);r.raise_for_status();raw=r.content;z=zipfile.ZipFile(io.BytesIO(raw));name=next(n for n in z.namelist() if n==table+'.csv');b=z.read(name);d=pd.read_csv(io.BytesIO(b),low_memory=False);sel=d[(d.REF_DATE.astype(str)=='2022')&(d.GEO=='Canada')];p=OUT/(table+'_2022.csv');sel.to_csv(p,index=False)
    meta=next(n for n in z.namelist() if 'MetaData' in n or 'metadata' in n.lower());(OUT/(table+'_metadata.csv')).write_bytes(z.read(meta))
    (OUT/(table+'_provenance.json')).write_text(json.dumps(dict(url=url,table=table,reference='2022',retrieved_utc=datetime.now(timezone.utc).isoformat(),zip_sha256=hashlib.sha256(raw).hexdigest(),full_csv_sha256=hashlib.sha256(b).hexdigest(),extract_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),metadata_sha256=hashlib.sha256(z.read(meta)).hexdigest()),indent=2)+'\n')
    print(table,sel.columns.tolist(),flush=True)
