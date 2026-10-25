"""Read-only t0 plans and pre/post-D2 snapshots, no iterate() and no RNG draws."""
import json,sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np,pandas as pd
from closure_diagnostics import ROOT,cur
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
from qe_baseline import configuration
from b2_instrumentation import consumption_units,fixed_groups,gross_wages_from_net
from macromodel.country.household_closure import liquidatable_household_assets
import macromodel.country.household_closure as module
from hi_income_audit import SOURCE,OUT,sha
from build_hi_cis import TARGET

def capture(countries,funded,arm):
    blocks=[]
    for name,c in countries.items():
        h=c.households;g=c.central_government;tax=g.states['Income Tax'];ssc=g.states['Employee Social Insurance Tax'];n=len(cur(h,'income'));wage=cur(h,'income_employee');gross=gross_wages_from_net(wage,tax,ssc)
        mixed=div=pension=np.zeros(n)
        if funded:mixed=c.household_closure.planned_mixed;div=c.household_closure.planned_dividends;pension=c.household_closure.planned_transfers
        income=cur(h,'income')
        if funded:income=income-cur(h,'income_financial_assets')+mixed+div+pension
        loan_interest=sum(c.credit_market.states[k][1].sum(axis=0) for k in ['cons_loans','mort_loans']);ids=h.states['Corresponding Bank ID'];dep=cur(h,'wealth_deposits')
        interest_received=np.maximum(0,dep)*cur(c.banks,'interest_rate_on_household_deposits')[ids];netinterest=loan_interest+np.maximum(0,-dep)*cur(c.banks,'overdraft_rate_on_household_deposits')[ids]-interest_received
        di=income-netinterest;units=consumption_units(c.individuals.states['Age'],c.individuals.states['Corresponding Household ID'],n)
        oldC=cur(h,'consumption')*(1+g.states['Value-added Tax'])+cur(h,'rent');C=oldC.copy()
        if funded:
            fn=h.functions['consumption'];Cgoods=fn.compute_target_consumption(expected_inflation=0.,current_cpi=1.,initial_cpi=1.,historic_consumption_sum=np.asarray(h.ts.historic('consumption')),saving_rates=np.full(n,h.states['average_saving_rate']),income=income,household_benefits=h.states['Number of Adults']*cur(g,'unemployment_benefits_by_individual')[0]+cur(h,'income_social_transfers'),consumption_weights=h.consumption_weights,consumption_weights_by_income=h.consumption_weights_by_income,exogenous_total_consumption=np.zeros(1),current_time=1,take_consumption_weights_by_income_quantile=h.use_consumption_weights_by_income,tau_vat=g.states['Value-added Tax'])
            props=c.housing_market.states['properties'];rented=props[(props['Is Owner-Occupied']==0)&(props['Corresponding Inhabitant Household ID']>=0)&(props['Corresponding Owner Household ID']>=0)];rent=np.zeros(n);np.add.at(rent,rented['Corresponding Inhabitant Household ID'].to_numpy(int),rented.Rent.to_numpy());rent=np.minimum(rent,cur(h,'rent'));Cgoods=Cgoods.copy();Cgoods[:,41]-=np.minimum(np.maximum(0,Cgoods[:,41]),rent/(1+g.states['Value-added Tax']));C=Cgoods.sum(axis=1)*(1+g.states['Value-added Tax'])+cur(h,'rent')
        principal=sum(np.minimum(c.credit_market.states[k][0],c.credit_market.states[k][2]).sum(axis=0) for k in ['cons_loans','mort_loans'])
        z=pd.DataFrame(dict(weight=c.scale,income=4*(income+ssc*gross),cash_DI=4*di,wages=4*(wage+ssc*gross),self_employment=4*mixed,investment=4*(div+cur(h,'income_rental')),private_pensions=4*pension,government_transfers=4*(cur(h,'income_social_transfers')+cur(h,'income_unemployment_benefits')),financial_proxy=4*cur(h,'income_financial_assets'),planned_C=4*C,historical_C=4*oldC,persistent=(C>di)*c.scale,unable=(dep+di+liquidatable_household_assets(h)<principal+cur(h,'rent'))*c.scale,networth=cur(h,'net_wealth'),DHEA_rank=di/c.scale/units,SHS_rank=(gross+cur(h,'income_unemployment_benefits')+cur(h,'income_social_transfers')+(cur(h,'income_rental')+mixed+div+pension)/(1-tax)+interest_received)/c.scale,region=str(name)))
        blocks.append(z)
    z=pd.concat(blocks,ignore_index=True);z['decile']=fixed_groups(z.income.to_numpy()/z.weight,z.weight,10)
    a=z.groupby('decile').sum(numeric_only=True).reset_index();a['stage']='after_D2_funded_plan' if funded else 'instantiated_before_D2_booked_proxy';a['arm']=arm;a['share']=a.income/a.income.sum();a['per_HH']=a.income/a.weight
    q=[]
    for scheme in ['DHEA','SHS']:
        z['quintile']=fixed_groups(z[scheme+'_rank'].to_numpy(),z.weight.to_numpy(),5)
        f=z.groupby('quintile')[['weight','planned_C','historical_C','cash_DI','networth']].sum().reset_index();f['scheme']=scheme;f['arm']=arm;f['funded']=funded;f['planned_share']=f.planned_C/f.planned_C.sum();f['historical_share']=f.historical_C/f.historical_C.sum();q.append(f)
    return a,pd.concat(q)

def main():
    rows=[];quints=[];params=[]
    for arm,path in [('F_CFC',SOURCE),('CIS_candidate',TARGET)]:
        d=DataWrapper.init_from_pickle(path);names=[n for n in d.all_country_names if str(n).startswith('CAN_')];cfg={n:CountryConfiguration.n_industry_default(n_industries=d.n_industries) for n in names}
        for c in cfg.values():c.household_closure=configuration()
        original=module.install_household_closures
        def inspect(countries):
            a,q=capture(countries,False,arm);rows.append(a);quints.append(q);original(countries);a,q=capture(countries,True,arm);rows.append(a);quints.append(q)
        module.install_household_closures=inspect
        try:sim=Simulation.from_datawrapper(d,SimulationConfiguration(country_configurations=cfg,t_max=2,seed=0))
        finally:module.install_household_closures=original
        for name,c in sim.countries.items():params.append(dict(arm=arm,region=str(name),consumption=type(c.households.functions['consumption']).__name__,transfer_setter=type(c.households.functions['social_transfers']).__name__,saving_rate=c.households.states['average_saving_rate'],source_sha256=sha(path)))
        print('t0 plan captured',arm,flush=True)
    pd.concat(rows).to_csv(OUT/'t0_stage_probe.csv',index=False);pd.concat(quints).to_csv(OUT/'t0_consumption_distribution.csv',index=False);pd.DataFrame(params).to_csv(OUT/'t0_rule_parameters.csv',index=False)
if __name__=='__main__':main()
