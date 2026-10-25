import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path('dev/validation_2022').resolve()))
import hi_income_audit as audit

def test_cis_household_income_deduplicates_family_then_sums_distinct_families(tmp_path,monkeypatch):
    x=pd.DataFrame(dict(PUMFID=[1,1,1,2],EFID=[10,10,11,20],FWEIGHT=[2.,2.,2.,3.],HHSIZE=[3,3,3,1],PROV=[35]*4,EFATINC=[100,100,50,200],EFWGSAL=[60,60,20,100],EFSEMP=[0]*4,EFINVA=[0]*4,EFGTR=[40,40,30,100],EFINCTX=[0]*4,EFPRPEN=[0]*4))
    p=tmp_path/'cis.csv';x.to_csv(p,index=False);monkeypatch.setattr(audit,'PUMF',p)
    out=audit.cis_households();assert out.loc[1,'income']==150 and out.loc[1,'government_transfers']==70
    assert out.loc[1,'weight']==2 and out.loc[2,'income']==200
