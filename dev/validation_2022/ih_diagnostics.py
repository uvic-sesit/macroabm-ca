"""IH read-only investment, income and arrears instrumentation. No RNG calls."""
import argparse,hashlib,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import qe_diagnostics as qe
from closure_diagnostics import cur,ROOT
from macromodel.country.household_closure import liquidatable_household_assets
from b2_instrumentation import B2HouseholdDiagnosis,consumption_units,fixed_groups,gross_wages_from_net
HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/IH'
def entrant_trigger(unable_t0,income_decline,initial_dissaver):
    """Exclusive descriptive hierarchy; existing contracts have no rate reset."""
    if unable_t0:return 'unable_from_t0'
    if income_decline:return 'income_loss'
    if initial_dissaver:return 'persistent_dissaver'
    return 'other'

class Diagnosis(qe.Headline):
    instances=[]
    def __init__(self,sim):
        self.firms=[];self.incomes=[];self.arrears=[];self.initial={};self.parts={};self.previous={};self.units={};self.sim=sim;self.service_data={}
        for name,c in sim.countries.items():
            f=c.firms;h=c.households;n=len(cur(h,'income'))
            self.units[str(name)]=consumption_units(np.asarray(c.individuals.states['Age']),np.asarray(c.individuals.states['Corresponding Household ID'],int),n)
            self.initial[str(name)]=dict(income=B2HouseholdDiagnosis.income(self,c,0)[1].copy(),employment=cur(h,'income_employee').copy(),assets=cur(h,'wealth_deposits')+cur(h,'wealth_other_financial_assets') if 'wealth_other_financial_assets' in h.ts.dicts else cur(h,'wealth_financial_assets').copy())
            loans=np.stack([c.credit_market.states[k] for k in ('cons_loans','mort_loans')])
            initial_service=loans[:,2].sum(axis=(0,1))
            self.initial[str(name)]['unable']=cur(h,'wealth_deposits')+self.initial[str(name)]['income']+liquidatable_household_assets(h)<initial_service+cur(h,'rent')
            self.initial[str(name)]['dissaver']=cur(h,'consumption')*(1+c.central_government.states['Value-added Tax'])+cur(h,'rent')>self.initial[str(name)]['income']
            self.initial[str(name)]['rates']=np.divide(loans[:,1].sum(axis=1),loans[:,0].sum(axis=1),out=np.zeros((2,n)),where=loans[:,0].sum(axis=1)>0)
            fn=f.functions['target_capital_inputs'];original=fn.compute_unconstrained_target_capital_inputs
            def wrapped(*a,_original=original,_fn=fn,_n=str(name),**k):
                result=_original(*a,**k)
                replacement=k['current_target_production'][:,None]*k['capital_inputs_depreciation_matrix']
                self.parts[_n]=(replacement.copy(),np.asarray(result).copy(),np.asarray(k['previous_good_prices']).copy())
                return result
            fn.compute_unconstrained_target_capital_inputs=wrapped
        import macromodel.country.household_payment_default as payment
        old_service=payment.service
        def servicing(c):
            cm=c.credit_market;name=str(c.country_name);n=len(cur(c.households,'income'))
            prior=cm.states.get('E_days_past_due',np.zeros((2,n),int)).copy()
            loans=np.stack([cm.states[k] for k in ('cons_loans','mort_loans')])
            self.initial[name]['current_rates']=np.divide(loans[:,1].sum(axis=1),loans[:,0].sum(axis=1),out=np.zeros((2,n)),where=loans[:,0].sum(axis=1)>0)
            result=old_service(c)
            self.service_data[name]=(prior,cm.states['E_days_past_due'].copy())
            return result
        payment.service=servicing
        super().__init__(sim);self.instances.append(self)
    def capture(self,sim,t):
        super().capture(sim,t)
        blocks=[]
        for name,c in sim.countries.items():
            f=c.firms;h=c.households;n=len(cur(h,'income'));name=str(name)
            def value(k,default=0.):
                return cur(f,k) if k in f.ts.dicts else np.full(len(cur(f,'production')),default)
            price=cur(c.economy,'good_prices');target=value('target_capital_inputs');uncon=value('unconstrained_target_capital_inputs')
            replacement,raw,lagprice=self.parts.get(name,(np.zeros_like(target),uncon,price))
            if t==0:replacement=f.compute_used_capital_inputs();lagprice=price
            repl=(replacement*lagprice).sum(axis=1);un=(raw*lagprice).sum(axis=1);plan=(target*lagprice).sum(axis=1)
            cfc=value('used_capital_inputs_costs');actual=value('total_capital_inputs_bought_costs')
            if t==0:un=actual.copy();plan=actual.copy()
            for i in range(len(actual)):
                self.firms.append(dict(region=name,quarter=t,firm=i,industry=int(f.states['Industry'][i]),replacement_planned=repl[i],stock_adjustment_and_clipping=un[i]-repl[i],unconstrained=un[i],planned=plan[i],credit_cut=un[i]-plan[i],realised=actual[i],clearing_price_residual=plan[i]-actual[i],CFC=cfc[i],net_investment=actual[i]-cfc[i],output=value('production')[i],target_production=value('target_production')[i],capital_target_production=value('target_capital_inputs_production')[i],wages=value('total_wage')[i],deposits=value('deposits')[i],long_credit_target=value('target_long_term_credit')[i],long_credit_received=value('received_long_term_credit')[i]))
            inc,di,gross=B2HouseholdDiagnosis.income(self,c,t);tax=c.central_government.states['Income Tax'];ssc=c.central_government.states['Employee Social Insurance Tax']
            mixed=c.household_closure.planned_mixed if t==0 else cur(h,'income_mixed')
            dividends=c.household_closure.planned_dividends if t==0 else cur(h,'income_dividends')
            corp=c.household_closure.planned_transfers if t==0 else cur(h,'income_corporate_transfers')
            wage=cur(h,'income_employee');grossw=gross_wages_from_net(wage,tax,ssc)
            pension=cur(h,'income_social_transfers');benefit=cur(h,'income_unemployment_benefits');rent=cur(h,'income_rental')
            z=pd.DataFrame(dict(region=name,household=np.arange(n),weight=c.scale,units=self.units[name],DI=di,wages_net=wage,wages_gross=grossw,mixed_net=mixed,dividends_net=dividends,rent_net=rent,government_transfers=pension+benefit,corporate_transfers_net=corp,taxes_contributions=grossw-wage+(mixed+dividends+rent+corp)*tax/(1-tax),net_interest=inc-di,consumption=cur(h,'consumption')*(1+c.central_government.states['Value-added Tax'])+cur(h,'rent'),deposits=cur(h,'wealth_deposits'),assets=cur(h,'wealth_financial_assets'),tenure=h.states['Tenure Status of the Main Residence'],initial_DI=self.initial[name]['income'],initial_wages=self.initial[name]['employment']))
            z['rank_income']=di/c.scale/self.units[name];blocks.append(z)
            if t and c.configuration.household_closure.household_payment_default_enabled:
                cm=c.credit_market;prior,days=self.service_data[name];metrics=cm.states.get('E2_metrics',{})
                headline=next(r for r in reversed(self.rows) if r['region']==name and r['quarter']==t)
                for j,kind in enumerate(['consumer','mortgage']):
                    entrants=(prior[j]==0)&(days[j]>0)
                    for i in np.flatnonzero(entrants):
                        # Stock interest/principal ratios are NOT contractual reset rates.
                        reason=entrant_trigger(self.initial[name]['unable'][i],di[i]<self.initial[name]['income'][i]-1e-8*c.scale,self.initial[name]['dissaver'][i])
                        self.arrears.append(dict(region=name,quarter=t,kind=kind,household=i,weight=c.scale,tenure=z.tenure.iloc[i],initial_DI=self.initial[name]['income'][i]/c.scale,DI=di[i]/c.scale,trigger=reason,income_decline=bool(di[i]<self.initial[name]['income'][i]-1e-8*c.scale),initial_dissaver=bool(self.initial[name]['dissaver'][i]),unable_t0=bool(self.initial[name]['unable'][i])))
                self.previous[name]=days.copy()
                for key,val in metrics.items():headline[key]=float(np.asarray(val).sum())
                for j,kind in enumerate(['consumer','mortgage']):
                    headline[kind+'_cures']=float(((prior[j]>0)&(days[j]==0)).sum()*c.scale)
                    headline[kind+'_prior_arrears']=float((prior[j]>0).sum()*c.scale)
                    for a,b in [(30,60),(60,90)]:
                        mask=(prior[j]>=a)&(prior[j]<b)
                        headline[f'{kind}_{a}_exposed']=float(mask.sum()*c.scale)
                        headline[f'{kind}_{a}_to_{b}']=float((mask&(days[j]>=b)).sum()*c.scale)
        z=pd.concat(blocks,ignore_index=True);z['quintile']=fixed_groups(z.rank_income.to_numpy(),z.weight.to_numpy(),5)
        z['zero_DI_households']=z.weight*(z.DI<=1e-8);z['negative_DI_households']=z.weight*(z.DI< -1e-8)
        z['equivalised_DI_weighted']=z.DI/z.units
        z['DI_reconciliation_residual']=z.DI-(z.wages_net+z.mixed_net+z.dividends_net+z.rent_net+z.government_transfers+z.corporate_transfers_net-z.net_interest)
        cols=['weight','DI','equivalised_DI_weighted','wages_net','wages_gross','mixed_net','dividends_net','rent_net','government_transfers','corporate_transfers_net','taxes_contributions','net_interest','consumption','deposits','assets','zero_DI_households','negative_DI_households','DI_reconciliation_residual']
        a=z.groupby('quintile')[cols].sum().reset_index();a['quarter']=t;self.incomes.extend(a.to_dict('records'))
        if t==0:
            z['decile']=fixed_groups(z.rank_income.to_numpy(),z.weight.to_numpy(),10)
            self.initial_ranks=z[['region','household','quintile','decile','rank_income']].copy()
    def save(self,out):
        pd.DataFrame(self.firms).to_csv(out/'investment_cells.csv',index=False);pd.DataFrame(self.incomes).to_csv(out/'income_quintiles.csv',index=False)
        if self.arrears:
            z=pd.DataFrame(self.arrears).merge(self.initial_ranks,on=['region','household']);z.groupby(['quarter','kind','decile','tenure','trigger','income_decline','initial_dissaver','unable_t0']).agg(households=('weight','sum'),initial_DI=('initial_DI','mean'),DI=('DI','mean')).reset_index().to_csv(out/'arrears_entrants.csv',index=False)
        pd.DataFrame(self.rows).to_csv(out/'headline.csv',index=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['F_CFC','E','E2'],required=True);p.add_argument('--seed',type=int,default=0);p.add_argument('--quarters',type=int,default=12);p.add_argument('--output',type=Path);p.add_argument('--variant');a=p.parse_args()
    variant=a.variant or 'IH_'+a.arm;a.output=a.output or OUT/'runs';a.variant=variant
    if a.arm=='E2':
        original=qe.configuration
        def config():
            c=original();c.household_arrears_cure_enabled=True;return c
        qe.configuration=config;a.arm='E'
    qe.Headline=Diagnosis
    qe.run(a)
    target=a.output/f'{a.arm}_{variant}_q{a.quarters}_s{a.seed}';Diagnosis.instances[-1].save(target)
    print('IH_COMPLETE',target,flush=True)
if __name__=='__main__':main()
