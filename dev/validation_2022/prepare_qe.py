"""Freeze source DHEA ratios and accepted CFC provenance before measurement."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent

def main():
    out=HERE/'benchmarks/QE';out.mkdir(parents=True,exist_ok=True)
    source=HERE/'benchmarks/B2/raw/36100587.csv'
    x=pd.read_csv(source,low_memory=False)
    names=['Lowest income quintile','Second income quintile','Third income quintile','Fourth income quintile','Highest income quintile']
    y=x[(x.REF_DATE==2022)&(x.GEO=='Canada')&(x.Statistics=='Value')&x.Characteristics.isin(names)&x['Income, consumption and savings'].isin(['Household disposable income','Household final consumption expenditure (HFCE)'])]
    y.to_csv(out/'dhea_income_consumption_2022.csv',index=False)
    p=y.pivot(index='Characteristics',columns='Income, consumption and savings',values='VALUE').loc[names]
    ratios=(p['Household final consumption expenditure (HFCE)']/p['Household disposable income']).tolist()
    meta=dict(table='36-10-0587-01',reference=2022,checked_UTC=datetime.now(timezone.utc).isoformat(),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        extract_sha256=hashlib.sha256((out/'dhea_income_consumption_2022.csv').read_bytes()).hexdigest(),
        vectors=y.VECTOR.tolist(),ratios=ratios,
        definitions='Household-weighted OECD-modified equivalised disposable-income quintiles, HFCE excluding STiK; source DI contains noncash imputations absent from model cash DI.',
        consumption_benchmark=dict(table='36-10-0112',vector='v62305982',annual_CAD=1511382e6),
        gate='Relative consumption SHARE deviation <=15%; Q-G0 construction only. Q-G1 positive-income zero goods <2% all quarters; Q-G2 Q12 shares; Q-G3 existing Gate B unchanged.')
    (out/'provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta,indent=2))

if __name__=='__main__':main()
