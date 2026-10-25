"""Independent investor concordance despite signed-product build failure.

These are diagnostic targets, not acquisitions in an executable FSG pickle.
"""
import json
import numpy as np,pandas as pd
from macro_data import DataWrapper
from build_firm_cfc_b2 import GEO,GROUPS
from build_za import target
from prepare_za import BENCH,OUT

def main():
    assert json.loads((OUT/'FSG_build_gate.json').read_text())['pickle_built'] is False
    data=DataWrapper.init_from_pickle(target('FS_T'));codes=list(data.industries)
    raw=pd.read_csv(BENCH/'nonres_investment_2022.csv').set_index(['GEO','Industry'])
    scope=pd.read_csv(OUT/'FSG_source_scope.csv').set_index(['region','sector'])
    bridge=pd.read_csv(OUT/'FS_T_firm_bridge.csv');out={n:z.set_index('industry').source_output.reindex(codes).to_numpy() for n,z in bridge.groupby('region')}
    national=sum(out.values());details=[];summary=[];valuation=[]
    for name,c in data.synthetic_countries.items():
        n=str(name);f=c.firms;ids=f.firm_data.Industry.to_numpy(int)
        hh_basic=float(scope.loc[(n,'residential'),'normalized_IO_basic_CAD'])
        hh_source=float(scope.loc[(n,'residential'),'observed_quarterly_purchaser_CAD'])
        cf=float(c.tax_data.capital_formation_tax)
        valuation.append(dict(region=n,legacy_capital_formation_tax=cf,diagnostic_residential_basic=hh_basic,
            observed_residential_purchaser=hh_source,residential_with_legacy_tax=hh_basic*(1+cf),
            purchaser_gap_if_legacy_tax_reused=hh_basic*(1+cf)-hh_source,
            no_new_rate_or_fiscal_flow=True))
        support=(np.maximum(0,f.initial_capital_purchases).sum(axis=1)+np.maximum(0,f.capital_inputs_stock).sum(axis=1))>0
        def get(label,model):
            r=raw.loc[(GEO[n],label)];v=float(r.VALUE);fallback=''
            if not np.isfinite(v):
                r=raw.loc[('Canada',label)];idx=[codes.index(g) for g in model]
                v=float(r.VALUE)*out[n][idx].sum()/national[idx].sum() if national[idx].sum() else 0.
                fallback='Canada investment x regional source-output share'
            if not np.isfinite(v):raise ValueError((n,label))
            return v*1e6/4,str(r.VECTOR),fallback
        groups=[]
        for labels,model in GROUPS:
            if labels==['Non-profit institutions serving households']:continue
            if model==['P']:labels=['Educational services']
            if model==['Q']:labels=['Health care and social assistance']
            parts=[get(label,model) for label in labels]
            groups.append(('business',' + '.join(labels),model,sum(v[0] for v in parts),';'.join(v[1] for v in parts),';'.join(v[2] for v in parts if v[2])))
        gov=get('Government sector',['O','P','Q']);edu=get('Government educational services',['P'])
        hospital=get('Hospitals',['Q']);care=get('Nursing and residential care facilities',['Q'])
        npish=get('Non-profit institutions serving households',['P','Q','R','S'])
        groups += [('government','Government residual',['O'],gov[0]-edu[0]-hospital[0]-care[0],';'.join([gov[1],edu[1],hospital[1],care[1]]),''),
                   ('government','Government educational services',['P'],*edu),
                   ('government','Hospitals + Nursing and residential care facilities',['Q'],hospital[0]+care[0],hospital[1]+';'+care[1],hospital[2]+';'+care[2]),
                   ('NPISH','Non-profit institutions serving households',['P','Q','R','S'],*npish)]
        denom={sector:sum(g[3] for g in groups if g[0]==sector) for sector in ['business','government','NPISH']}
        for sector,label,model,value,vectors,fallback in groups:
            assert value>=0
            budget=float(scope.loc[(n,sector),'normalized_IO_basic_CAD'])
            desired=budget*value/denom[sector] if denom[sector] else 0.
            selected=np.isin(ids,[codes.index(g) for g in model]);w=np.where(selected,out[n][ids],0.)
            allocated=desired*w/w.sum() if w.sum() else np.zeros(len(ids))
            supported=np.where(support,allocated,0.);unallocated=desired-supported.sum()
            summary.append(dict(region=n,sector=sector,source_group=label,source_quarterly_CAD=value,source_sector_group_sum=denom[sector],
                normalized_IO_target=desired,supported_diagnostic_target=supported.sum(),unallocated=unallocated,
                material=desired>50e6,relative_support_gap=unallocated/desired if desired else 0.,vectors=vectors,fallback=fallback))
            for i in np.flatnonzero(selected):
                details.append(dict(region=n,sector=sector,source_group=label,industry=codes[ids[i]],firm=int(i),output_share=w[i]/w.sum() if w.sum() else 0.,
                    diagnostic_target=allocated[i],has_existing_capital_good_support=bool(support[i]),unallocated=allocated[i]-supported[i],vectors=vectors,fallback=fallback))
    s=pd.DataFrame(summary);d=pd.DataFrame(details)
    s.to_csv(OUT/'FSG_investor_groups_diagnostic.csv',index=False);d.to_csv(OUT/'FSG_investor_industries_diagnostic.csv',index=False)
    d[d.unallocated>1e-5].to_csv(OUT/'FSG_unsupported_investors.csv',index=False)
    pd.DataFrame(valuation).to_csv(OUT/'FSG_legacy_tax_scope_diagnostic.csv',index=False)
    result=dict(executable_candidate=False,method='Existing36-10-0096 concordance; separate business/public/NPISH labels; regional IO sector totals; within mapped group positive canonical source-output shares. Missing regional source observations use national amount x regional group-output share, with exact fallback and vector logged. No stock/composition invented.',
        note='Independent data reconciliation only; signed product budget blocker remains, no numerical adoption gate declared passed.',
        annual_normalized_nonres_target=float(4*s.normalized_IO_target.sum()),annual_unsupported=float(4*s.unallocated.sum()),
        material_groups=int(s.material.sum()),material_support_gap_over_2pct=int((s.material&(s.relative_support_gap>.02)).sum()),
        max_material_support_gap=float(s.loc[s.material,'relative_support_gap'].max()),unsupported_records=int((d.unallocated>1e-5).sum()))
    (OUT/'FSG_investor_diagnostic.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
