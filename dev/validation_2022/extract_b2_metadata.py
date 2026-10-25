"""Preserve current table definitions byte-for-byte from downloaded source ZIPs."""
import hashlib
import json
from pathlib import Path
import zipfile
HERE=Path(__file__).resolve().parent
RAW=HERE/'benchmarks/B2/raw'

def main():
    metadata={}
    for table in ('36100587','11100223'):
        source=RAW/(table+'-eng.zip')
        with zipfile.ZipFile(source) as z:
            member=table+'_MetaData.csv'
            content=z.read(member)
        target=RAW/(table+'_metadata.csv');target.write_bytes(content)
        metadata[table]=dict(member=member,zip_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            metadata_sha256=hashlib.sha256(content).hexdigest(),checked_UTC='2026-10-24')
    text=(RAW/'36100587_metadata.csv').read_text(encoding='utf-8-sig')
    assert 'OECD-modified' in text and '0.5' in text and '0.3' in text
    (RAW/'table_definitions_provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')

if __name__=='__main__':main()
