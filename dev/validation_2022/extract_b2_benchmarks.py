"""Extract reference years in a streaming pass; retain full-source hashes."""
import hashlib
import json
import zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
RAW=HERE/'benchmarks/B2/raw'


def main():
    for cube,year in [('11100223','2023'),('36100096','2022')]:
        archive=RAW/f'{cube}-eng.zip';out=RAW/f'{cube}_{year}.csv'
        digest=hashlib.sha256();rows=0
        with zipfile.ZipFile(archive) as z:
            name=next(n for n in z.namelist() if n.endswith('.csv') and 'MetaData' not in n)
            with z.open(name) as source,out.open('wb') as target:
                header=source.readline();digest.update(header);target.write(header)
                for line in source:
                    digest.update(line)
                    if line.startswith((year+',').encode()) or line.startswith(('"'+year+'",').encode()):
                        target.write(line);rows+=1
        metadata=json.loads((RAW/f'{cube}_download.json').read_text())
        metadata.update(table=cube,reference=year,full_csv_sha256=digest.hexdigest(),
            selected_year_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),selected_rows=rows,
            extraction='Reference year only, unchanged source rows and vector IDs')
        (RAW/f'{cube}_{year}_provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print(cube,year,rows,out.stat().st_size,flush=True)


if __name__=='__main__':main()
