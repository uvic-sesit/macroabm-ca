"""ZA serial measurements, existing battery plus explicit floor-state checks."""
import sys,argparse,json
import numpy as np,pandas as pd
import ih_diagnostics as ih
from closure_diagnostics import cur
from build_za import target
from prepare_za import OUT,sha
from za_state_schema import defined_floor_states
class ZA(ih.Diagnosis):
    def __init__(self,sim):self.floor_rows=[];super().__init__(sim)
    def capture(self,sim,t):
        super().capture(sim,t)
        for name,c in sim.countries.items():
            mask=FLOORS[str(name)]
            for field in ['production','target_production','price','unit_costs','profits','deposits','equity','debt','labour_inputs','labour_productivity','total_wage']:
                if field not in c.firms.ts.dicts:continue
                value=cur(c.firms,field)
                for i in np.flatnonzero(mask):
                    self.floor_rows.append(dict(region=str(name),quarter=t,firm=int(i),industry=int(c.firms.states['Industry'][i]),field=field,value=float(value[i]),finite=bool(np.isfinite(value[i])),defined=not(t==0 and field=='target_production')))
    def save(self,out):
        super().save(out)
        z=pd.DataFrame(self.floor_rows);z['defined']=defined_floor_states(z)
        z.to_csv(out/'floor_states.csv',index=False)
        assert z.loc[z.defined,'finite'].all()
def main():
    global FLOORS
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['FS_T','FS','FSG'],required=True);p.add_argument('--quarters',type=int,default=2);p.add_argument('--seed',type=int,default=0);p.add_argument('--variant');a=p.parse_args()
    path=target(a.arm)
    if a.arm=='FSG':
        from pathlib import Path
        path=Path((OUT/'FSG_pickle_path.txt').read_text().strip())
    f=pd.read_csv(OUT/'FS_T_firm_bridge.csv');FLOORS={str(n):g.sort_values('firm').floor_cell.to_numpy(bool) for n,g in f.groupby('region')}
    ih.qe.PICKLE=path;ih.qe.PICKLE_SHA256=sha(path);ih.Diagnosis=ZA
    sys.argv=[sys.argv[0],'--arm','F_CFC','--variant',a.variant or 'ZA_'+a.arm,'--quarters',str(a.quarters),'--seed',str(a.seed),'--output',str(OUT/'runs')];ih.main()
if __name__=='__main__':main()
