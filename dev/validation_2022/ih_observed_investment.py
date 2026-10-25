"""Read-only observed GFCF concordance using the accepted CFC output-share mapping."""
import sys
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent
from build_firm_cfc_b2 import GEO
raw=pd.read_csv(HERE/'benchmarks/IH/nonres_investment_CFC_2022.csv');raw=raw[raw['Flows and stocks']=='Investment'].set_index(['GEO','Industry'])
a=pd.read_csv(HERE/'outputs/B2/firm_data/cfc_allocation.csv').fillna('');va=pd.read_csv(HERE/'outputs/B2/firm_data/observed_VA_2022.csv',index_col=0);rows=[]
for (region,group),z in a.groupby(['region','source_industry'],sort=False):
    codes=z.industry.tolist();total=0.;vectors=[];fallback=[]
    for label in group.split(' + '):
        sign=-1 if label.startswith('-') else 1;label=label.lstrip('-');r=raw.loc[(GEO[region],label)];v=float(r.VALUE)
        if not np.isfinite(v):
            r=raw.loc[('Canada',label)];den=va.loc[[n+'|'+j for n in GEO for j in codes],'output_basic'].sum();num=va.loc[[region+'|'+j for j in codes],'output_basic'].sum();v=float(r.VALUE)*num/den if den else 0.;fallback.append(label+' national x regional output share')
        if not np.isfinite(v):raise ValueError((region,label))
        total+=sign*v*1e6/4;vectors.append(str(r.VECTOR))
    for r in z.itertuples():rows.append(dict(region=region,industry_code=r.industry,source_group=group,quarterly_group_investment=total,allocated_observed_investment=total*float(r.output_share),output_share=r.output_share,vectors=';'.join(vectors),fallback=';'.join(fallback)))
f=pd.DataFrame(rows);f.to_csv(HERE/'outputs/IH/observed_investment_concordance.csv',index=False)
obs=f.groupby(['region','industry_code']).allocated_observed_investment.sum().reset_index();cfc=pd.read_csv(HERE/'outputs/B2/firm_data/cfc_cost_bridge.csv').rename(columns={'industry':'industry_code'});cfc=cfc.groupby(['region','industry_code'])[['new_CFC','old_CFC']].sum().reset_index();obs=obs.merge(cfc,on=['region','industry_code'],how='outer').fillna(0.)
observed_cfc=a.groupby(['region','industry']).allocated_CFC.sum().rename('allocated_observed_CFC').reset_index().rename(columns={'industry':'industry_code'});obs=obs.merge(observed_cfc,on=['region','industry_code'],how='left').fillna(0.);obs['observed_mapped_net_investment']=obs.allocated_observed_investment-obs.allocated_observed_CFC
obs['model_initial_investment']=obs.old_CFC;obs['observed_net_after_model_CFC']=obs.allocated_observed_investment-obs.new_CFC;obs['initial_model_net']=obs.model_initial_investment-obs.new_CFC;obs.to_csv(HERE/'outputs/IH/initial_investment_observed_comparison.csv',index=False)
print(obs[['allocated_observed_investment','model_initial_investment','new_CFC']].sum()/1e9)
