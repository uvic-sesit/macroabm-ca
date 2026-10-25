"""Freeze the exact cached rental benchmark, preserving its accepted vintage."""
import json
import pandas as pd
from prepare_sg import HERE,BENCH,sha
def main():
    source=HERE/'benchmarks/raw/dbn_36100124.json';data=json.loads(source.read_text())
    doc=next(d for d in data['series']['docs'] if d['series_code']=='1.1.1.18')
    rows=[dict(period=p,value_M=v,table='36-10-0124-01',series_code=doc['series_code'],series_name=doc['series_name']) for p,v in zip(doc['period'],doc['value']) if p.startswith('2022')]
    assert len(rows)==4 and sum(r['value_M'] for r in rows)==235938.
    target=BENCH/'imputed_rent_accepted_2022.csv';pd.DataFrame(rows).to_csv(target,index=False)
    meta=dict(table='36-10-0124-01',reference='2022 current prices, Canada, seasonally adjusted at quarterly rates; sum four quarters',series_code='1.1.1.18',native_StatCan_vector=None,source_note='DBnomics series ID, not a native v-number. Original cache has no native vector. Official bulk download attempted2026-10-25 but connection closed; web download also timed out. No native ID invented.',cached_indexed_at=doc['indexed_at'],checked_utc='2026-10-25',source=str(source.relative_to(HERE.parents[1])),source_sha256=sha(source),extract_sha256=sha(target),annual_CAD=235938e6,values=rows,url='https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610012401')
    (BENCH/'rent_vector_provenance.json').write_text(json.dumps(meta,indent=2)+'\n');print('Exact accepted imputed-rent vintage verified:',meta['annual_CAD'])
if __name__=='__main__':main()
