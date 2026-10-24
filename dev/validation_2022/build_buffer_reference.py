"""Read-only SFS 2023 extraction: fixed income-decile/age liquid buffers."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT.parent/'macroabm-ca/dev/raw_data/can_2022/pumf/sfs_2023/sfs2023_efam_pumf.csv'
OUT=ROOT/'dev/validation_2022/benchmarks/BE'


def weighted_median(x,w):
    order=np.argsort(x,kind='stable');x=np.asarray(x)[order];w=np.asarray(w)[order]
    return float(x[np.searchsorted(np.cumsum(w),.5*w.sum())])


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(SOURCE);income=d.PEFATINC.to_numpy(float);w=d.PWEIGHT.to_numpy(float)
    valid=np.isfinite(income)&(income<99999999)&np.isfinite(w)&(w>0)
    d=d[valid].copy();income=income[valid];w=w[valid]
    L=d[['PWASTDEP','PWASTMUI','PWASTSTK','PWASTBND','PWASTOIN','PWATFS']].clip(lower=0).sum(axis=1).to_numpy()
    order=np.argsort(income,kind='stable');r=np.empty(len(w));r[order]=np.cumsum(w[order])/w.sum()
    decile=np.minimum(10,np.ceil(10*r)).astype(int);age=d.PAGEMIEG.to_numpy(int)
    rows=[]
    for q in range(1,11):
        for a in range(8):
            mask=(decile==q)&((age==a) if a else True);pos=mask&(income>0)
            if not mask.any() or not pos.any():raise ValueError(f'Empty SFS reference cell {q}/{a}')
            rows.append(dict(income_decile=q,age_band=a,n_records=int(mask.sum()),represented_families=w[mask].sum(),
                b_quarters=weighted_median(4*L[pos]/income[pos],w[pos]),
                fallback_buffer_CAD=weighted_median(L[mask],w[mask])))
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'sfs_liquid_buffers.csv',index=False)
    meta=dict(table='SFS 2023 economic-family PUMF, StatCan 13M0006X',vector='PUMF variables, no vector IDs',
        url='https://www150.statcan.gc.ca/n1/en/catalogue/13M0006X',reference='SFS 2023 assets and PEFATINC income',
        extracted_utc=datetime.now(timezone.utc).isoformat(),source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        extract_sha256=hashlib.sha256((OUT/'sfs_liquid_buffers.csv').read_bytes()).hexdigest(),
        variables=dict(weight='PWEIGHT',income='PEFATINC',age='PAGEMIEG',liquid_assets=['PWASTDEP','PWASTMUI','PWASTSTK','PWASTBND','PWASTOIN','PWATFS']),
        method='Weighted median of individual L/(annual after-tax income/4) among positive-income families, in weighted income decile x SFS age cell. No pensions or debt netting. Age 0 pools ages within income decile.',
        fallback='For nonpositive model permanent income use the fixed cell weighted-median liquid-assets level, converted to model scale; not b times negative income.',
        exclusions=int((~valid).sum()),survey_weights_unchanged=True,
        model_mapping='Initial national model income decile, with initial highest-income linked individual age as major-income-recipient proxy; unknown age uses pooled-age SFS cell. Fixed thereafter.',
        uncertainty='Survey economic families differ from model households; 2023 wealth vintage, Canadian income ranks with retained member skeleton; source ratios are not fitted to gates.')
    (OUT/'buffer_provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(frame.to_string(index=False))


if __name__=='__main__':main()
