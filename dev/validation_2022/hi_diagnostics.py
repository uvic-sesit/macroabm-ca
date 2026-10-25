"""Serial HI two-quarter gates, using the established accounting battery."""
import argparse,sys
from pathlib import Path
import numpy as np,pandas as pd
import ih_diagnostics as ih
from hi_income_audit import summarize,sha,SOURCE
from closure_diagnostics import cur
from b2_instrumentation import B2HouseholdDiagnosis,gross_wages_from_net,fixed_groups
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/HI'
class HI(ih.Diagnosis):
    def __init__(self,sim):self.cash_rows=[];super().__init__(sim)
    def capture(self,sim,t):
        super().capture(sim,t);blocks=[]
        for name,c in sim.countries.items():
            h=c.households;tax=c.central_government.states['Income Tax'];ssc=c.central_government.states['Employee Social Insurance Tax'];income,di,_=B2HouseholdDiagnosis.income(self,c,t);wage=cur(h,'income_employee');gross=gross_wages_from_net(wage,tax,ssc)
            d2=c.household_closure
            mixed=d2.planned_mixed if t==0 else cur(h,'income_mixed');div=d2.planned_dividends if t==0 else cur(h,'income_dividends');pens=d2.planned_transfers if t==0 else cur(h,'income_corporate_transfers')
            n=len(income);government=cur(h,'income_social_transfers')+cur(h,'income_unemployment_benefits')
            z=pd.DataFrame(dict(weight=c.scale,income=4*(income+ssc*gross),wages=4*(wage+ssc*gross),self_employment=4*mixed,investment=4*(div+cur(h,'income_rental')),private_pensions=4*pens,government_transfers=4*government,taxes=4*(gross-wage-ssc*gross),cash_DI=4*di,government_recipients=(government>1e-8)*c.scale,deposits=cur(h,'wealth_deposits'),mortgages=cur(h,'mortgage_debt'),net_worth=cur(h,'net_wealth'),region=str(name),household=np.arange(n)))
            if t==0:
                from macromodel.country.household_closure import liquidatable_household_assets
                principal=sum(c.credit_market.states[k][2].sum(axis=0) for k in ['cons_loans','mort_loans']);C=cur(h,'consumption')*(1+c.central_government.states['Value-added Tax'])+cur(h,'rent')
                z['planned_dissavers']=(C>di)*c.scale;z['unable_t0']=(cur(h,'wealth_deposits')+di+liquidatable_household_assets(h)<principal+cur(h,'rent'))*c.scale
            blocks.append(z)
        z=pd.concat(blocks,ignore_index=True);z['decile']=fixed_groups(z.income.to_numpy()/z.weight.to_numpy(),z.weight.to_numpy(),10)
        a=z.groupby('decile').sum(numeric_only=True).reset_index();a['share']=a.income/a.income.sum();a['per_HH']=a.income/a.weight;a['quarter']=t;self.cash_rows.extend(a.to_dict('records'))
    def save(self,out):super().save(out);pd.DataFrame(self.cash_rows).to_csv(out/'CIS_deciles.csv',index=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--pickle',type=Path,default=SOURCE);p.add_argument('--variant',required=True);p.add_argument('--arm',default='F_CFC');p.add_argument('--quarters',type=int,default=2);p.add_argument('--seed',type=int,default=0);a=p.parse_args()
    ih.qe.PICKLE=a.pickle;ih.qe.PICKLE_SHA256=sha(a.pickle);ih.Diagnosis=HI
    sys.argv=[sys.argv[0],'--arm',a.arm,'--variant',a.variant,'--output',str(OUT/'runs'),'--quarters',str(a.quarters),'--seed',str(a.seed)];ih.main()
if __name__=='__main__':main()
