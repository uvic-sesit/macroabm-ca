"""Read-only HI stage snapshots and household-unit CIS benchmark extraction."""
import sys,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from macro_data import DataWrapper
from b2_instrumentation import fixed_groups
from macro_data.readers.population_data.canadianized_household_adapter import CIS_INCOME_SHARES_BY_DECILE
OUT=HERE/'outputs/HI';BENCH=HERE/'benchmarks/HI';OUT.mkdir(exist_ok=True);BENCH.mkdir(exist_ok=True)
PUMF=ROOT.parent/'macroabm-ca/dev/raw_data/can_2022/pumf/cis_2022/CIS2022_PUMF.csv'
SOURCE=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt_cfc_v2.pkl'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cis_households():
    cols=['PUMFID','EFID','FWEIGHT','HHSIZE','EFATINC','EFWGSAL','EFSEMP','EFINVA','EFGTR','EFINCTX','EFPRPEN','PROV']
    x=pd.read_csv(PUMF,usecols=cols);assert x.groupby('PUMFID').FWEIGHT.nunique().max()==1
    x=x.drop_duplicates('EFID');money=[k for k in cols if k.startswith('EF') and k!='EFID']
    for k in money:x[k]=x[k].mask(x[k]>=999999999990)
    # Family variables include all member income; deduplicate family records, then sum to household.
    a=x.groupby('PUMFID')[money].sum(min_count=1);s=x.groupby('PUMFID')[['FWEIGHT','HHSIZE','PROV']].first();a=a.join(s);a=a[np.isfinite(a.EFATINC)&(a.FWEIGHT>0)]
    return a.rename(columns={'EFATINC':'income','EFWGSAL':'wages','EFSEMP':'self_employment','EFINVA':'investment','EFGTR':'government_transfers','EFINCTX':'taxes','EFPRPEN':'private_pensions','FWEIGHT':'weight'})
def summarize(stage,a):
    a=a.copy();a['decile']=fixed_groups(a.income.to_numpy()/a.weight.to_numpy(),a.weight.to_numpy(),10)
    q=a.groupby('decile').sum(numeric_only=True);q['share']=q.income/q.income.sum();q['per_HH']=q.income/q.weight;q['stage']=stage
    return q.reset_index()
def main():
    cis=cis_households();cis['decile']=fixed_groups(cis.income.to_numpy(),cis.weight.to_numpy(),10)
    z=cis.copy();money=['income','wages','self_employment','investment','government_transfers','taxes','private_pensions'];z[money]=z[money].mul(z.weight,axis=0);b=summarize('CIS_2022_households',z[['weight']+money]);b.to_csv(BENCH/'cis_household_deciles_2022.csv',index=False)
    cis.groupby('decile').apply(lambda g:pd.Series(dict(government_recipient_share=np.average(g.government_transfers>0,weights=g.weight),private_pension_recipient_share=np.average(g.private_pensions>0,weights=g.weight))),include_groups=False).reset_index().to_csv(BENCH/'cis_recipients_2022.csv',index=False)
    source=HERE/'../../dev/io2022/household_prototype/prototype_household_consumption.csv';source=source.resolve();x=pd.read_csv(source);rows=[]
    # Actual source/adapter stage: validated income is annual household cash proxy, national DHEA-scaled.
    a=pd.DataFrame(dict(weight=x.Weight,income=x.Income*x.Weight));ranks=fixed_groups(x.Income.to_numpy(),x.Weight.to_numpy(),10)
    for name,j in [('investment',0),('private_pensions',1),('government_transfers',2)]:a[name]=x.Income.to_numpy()*x.Weight.to_numpy()*np.array([CIS_INCOME_SHARES_BY_DECILE[int(d)][j] for d in x.income_decile])
    a['wages']=a.income-a.investment-a.private_pensions-a.government_transfers;a['self_employment']=0.;a['taxes']=np.nan;rows.append(summarize('actual_adapter_source',a))
    data=DataWrapper.init_from_pickle(SOURCE);blocks=[]
    for name,c in data.synthetic_countries.items():
        if not str(name).startswith('CAN_'):continue
        h=c.population.household_data;s=c.scale
        blocks.append(pd.DataFrame(dict(region=str(name),household=np.arange(len(h)),weight=s,income=4*h.Income,wages=4*h['Employee Income'],self_employment=0.,investment=4*h['Income from Financial Assets'],government_transfers=4*(h['Regular Social Transfers']+h['Unemployment Benefits']),private_pensions=4*h['Income from Pensions'],taxes=np.nan,validated_income=s*h['Validated Income'])))
    pop=pd.concat(blocks,ignore_index=True);rows.append(summarize('retained_synthetic_population_post_matching',pop));v=pop.copy();v.income=v.validated_income;rows.append(summarize('retained_validated_income_before_rescale',v))
    pd.concat(rows).to_csv(OUT/'stage_deciles.csv',index=False)
    (BENCH/'cash_concept.json').write_text(json.dumps(dict(primary='CIS 2022 PUMF household custom tabulation, household PUMFID; unique EFID family incomes summed once; household weights, unequivalised after-tax household cash income. No published vector exists for this custom household table. Official 11-10-0192 economic-family and 11-10-0193 adjusted-person deciles are separate crosschecks, not relabelled as household deciles.',pumf=str(PUMF),pumf_sha256=sha(PUMF),source_catalogue='72M0003X, 2022',family_variables=money,year='2022 nominal dollars',cis_model_bridge='CIS subtracts income tax, but not loan interest or employee CPP/EI. Add back model net interest and employee SSC for a like-for-like cash comparison. DHEA cash DI remains separately reported.',source_adapter=str(source),source_adapter_sha256=sha(source),source_pickle_sha256=sha(SOURCE)),indent=2)+'\n')
    print(b[['decile','share','per_HH']].to_string(index=False));print(pd.concat(rows)[['stage','decile','share','per_HH']].to_string(index=False))
if __name__=='__main__':main()
