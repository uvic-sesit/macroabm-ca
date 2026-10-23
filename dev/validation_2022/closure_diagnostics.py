"""Read-only instrumentation for the four pre-D3 checks; fresh, serial runs.

No RNG calls and no changes to model arguments or return values. Individual
borrower/cohort records stay in ignored micro/; aggregate panels are reviewable.
"""
import argparse
import hashlib
import itertools
import json
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).parent/'battery'))
from accounting import AccountingBattery, IDENTITY_COLUMNS
from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.simulation import Simulation


def cur(a,k,default=0.):
    try:return np.asarray(a.ts.current(k),float)
    except (KeyError,IndexError):return np.asarray(default,float)


class Diagnostics:
    def __init__(self,sim,data,out):
        self.sim,self.out=sim,out
        self.t=0;self.firm=[];self.bank=[];self.flows=[];self.L=[];self.cohort=[];self.loans=[];self.vintages=[]
        self.initial={};self.payout={};self.orig={};self.nextid=0
        for n,c in sim.countries.items():
            h=c.households;name=str(n)
            age=np.zeros(len(cur(h,'income')))
            np.maximum.at(age,c.individuals.states['Corresponding Household ID'],c.individuals.states['Age'])
            self.initial[name]={k:cur(h,k).copy() for k in ['income','wealth_deposits','wealth_other_financial_assets','net_wealth','debt','wealth_real_assets']}
            self.initial[name]['age']=age
            self.install(c)
            self.flow(c,0)
            for i in range(len(cur(c.banks,'equity'))):self.bankrow(c,i,0,'initial')
        allincome=np.concatenate([z['income']/sim.countries[n].scale for n,z in self.initial.items()])
        weights=np.concatenate([np.full(len(z['income']),sim.countries[n].scale) for n,z in self.initial.items()])
        order=np.argsort(allincome,kind='stable');ranks=np.empty(len(order));ranks[order]=np.cumsum(weights[order])/weights.sum()
        dec=np.minimum(10,np.ceil(10*ranks)).astype(int);start=0
        for n,z in self.initial.items():z['decile']=dec[start:start+len(z['income'])];start+=len(z['income'])

    def wrap(self,obj,name,before=None,after=None):
        original=getattr(obj,name)
        def call(*args,**kwargs):
            state=before(*args,**kwargs) if before else None
            result=original(*args,**kwargs)
            if after:after(state,result,*args,**kwargs)
            return result
        setattr(obj,name,call)

    def install(self,c):
        h,f,b,cm=c.households,c.firms,c.banks,c.credit_market;n=str(c.country_name)
        def before_credit(*args,**kwargs):
            self.orig[n]={k:cur(h,k).copy() for k in ['wealth_deposits','net_wealth','income','debt','interest_paid_on_deposits']}
            self.orig[n]['service']=np.asarray(h.states.get('credit_existing_service',np.zeros(len(cur(h,'income'))))).copy()
            self.orig[n]['books']={k:cm.states[k].copy() for k in ['cons_loans','mort_loans']}
        self.wrap(c,'clear_credit_market',before_credit)
        def commitments(*args,**kwargs):
            z=self.orig[n]
            for key in ['cons_loans','mort_loans']:
                new=cm.states[key]-z['books'][key]
                for bank,i in zip(*np.where(new[0]>1e-6)):
                    row=dict(loan_id=self.nextid,region=n,quarter=self.t,bank=int(bank),household=int(i),kind=key,
                             value=float(new[0,bank,i]),deposit=float(z['wealth_deposits'][i]),overdraft=float(max(0,-z['wealth_deposits'][i])),
                             net_worth=float(z['net_wealth'][i]),income=float(z['income'][i]),installment_debt=float(z['debt'][i]),
                             existing_service=float(z['service'][i]),loss=0.,ever_loss=False)
                    self.nextid+=1;self.loans.append(row)
                    self.vintages.append(dict(row=row,principal=row['value'],payment=float(new[2,bank,i])))
        self.wrap(c,'process_credit_market_clearing',commitments)
        def paid(*args,**kwargs):
            for v in self.vintages:
                if v['row']['region']==n:v['principal']=max(0,v['principal']-v['payment'])
        self.wrap(cm,'pay_household_installments',after=lambda *args,**kwargs:paid())
        def hh_before(*args,**kwargs):
            before={k:cm.states[k][0].copy() for k in ['cons_loans','mort_loans']}
            if self.t==1:self.capture_cohort(c,before)
            return before
        def hh_after(before,result,*args,**kwargs):
            for v in self.vintages:
                r=v['row']
                if r['region']!=n:continue
                j,i,k=r['bank'],r['household'],r['kind'];p=before[k][j,i]
                fraction=max(0,1-cm.states[k][0,j,i]/p) if p>0 else 0.
                loss=v['principal']*fraction;r['loss']+=loss;r['ever_loss']|=loss>1e-6
                v['principal']*=1-fraction;v['payment']*=1-fraction
        self.wrap(h,'handle_insolvency',hh_before,hh_after)
        def firm_before(*args,**kwargs):
            return {k:cur(f,k).copy() for k in ['deposits','equity','debt','profits','corporate_taxes_paid','received_credit','total_wage']}
        def firm_after(z,result,*args,**kwargs):
            failed=f.states['is_insolvent'].copy();p=self.payout.get(n,{})
            for i in range(len(failed)):
                r=dict(region=n,quarter=self.t,firm=i,industry=int(f.states['Industry'][i]),failed=bool(failed[i]),
                       loan_debt=float(z['debt'][i]),overdraft_cancelled=float(max(0,-z['deposits'][i])) if failed[i] else 0.)
                r.update({k:float(v[i]) for k,v in z.items()})
                for k,v in p.items():r[k]=float(v[i])
                self.firm.append(r)
        self.wrap(f,'handle_insolvency',firm_before,firm_after)
        closure=getattr(c,'household_closure',None)
        if closure:
            def payout_before(*args,**kwargs):return cur(f,'deposits').copy()
            def payout_after(z,result,*args,**kwargs):
                self.payout[n]=dict(cash_before_payout=z,cash_after_payout=cur(f,'deposits').copy(),
                    requested_mixed=closure.requested_firm_payments[0].copy(),requested_transfers=closure.requested_firm_payments[1].copy(),
                    requested_dividends=closure.requested_firm_payments[2].copy(),paid_mixed=closure.actual_firm_payments[0].copy(),
                    paid_transfers=closure.actual_firm_payments[1].copy(),paid_dividends=closure.actual_firm_payments[2].copy(),
                    payout_tax_rebate=closure.corporate_tax_rebate.copy(),lagged_profits=np.asarray(f.ts.prev('profits')).copy())
            self.wrap(closure,'firm_payments',payout_before,payout_after)
        self.wrap(b,'handle_insolvency',before=lambda *args,**kwargs:[self.bankrow(c,i,self.t,'before_rescue') for i in range(len(cur(b,'equity')))])

    def capture_cohort(self,c,books):
        h=c.households;n=str(c.country_name);z=self.initial[n]
        bad=(cur(h,'net_wealth')<0)&(cur(h,'wealth_deposits')<0)
        goods=cur(h,'nominal_amount_spent_in_lcu').sum(axis=1)+cur(h,'vat_paid')
        loanint=cur(h,'interest_paid_on_loans');depint=cur(h,'interest_paid_on_deposits')
        service=cur(h,'debt_installments')+loanint+np.maximum(0,depint)
        blocks=np.array([goods,service,cur(h,'rent')])
        resource=cur(h,'wealth_deposits')+blocks.sum(axis=0)
        effect=np.zeros_like(blocks)
        for perm in itertools.permutations(range(3)):
            balance=resource.copy()
            for j in perm:
                effect[j]+=(np.maximum(0,-(balance-blocks[j]))-np.maximum(0,-balance))/6;balance-=blocks[j]
        totaldebt=sum(x.sum(axis=0) for x in books.values())
        for i in range(len(bad)):
            self.cohort.append(dict(region=n,household=i,represented=c.scale,decile=int(z['decile'][i]),tenure=int(h.states['Tenure Status of the Main Residence'][i]),
                oldest_age=z['age'][i],written_off=bool(bad[i]),debt=totaldebt[i],cons_debt=books['cons_loans'][:,i].sum(),mort_debt=books['mort_loans'][:,i].sum(),
                t0_income=z['income'][i],t0_deposit=z['wealth_deposits'][i],t0_net_worth=z['net_wealth'][i],t0_debt=z['debt'][i],
                deposit=cur(h,'wealth_deposits')[i],net_worth=cur(h,'net_wealth')[i],income=cur(h,'income')[i],goods=goods[i],service=service[i],rent=cur(h,'rent')[i],
                main_cause=['spending','debt_service','rent'][int(np.argmax(effect[:,i]))],
                spending_OD=effect[0,i],service_OD=effect[1,i],rent_OD=effect[2,i],
                other_OD=max(0,-resource[i]),real_asset_change=cur(h,'wealth_real_assets')[i]-z['wealth_real_assets'][i]))

    def bankrow(self,c,i,t,stage):
        b=c.banks;e=float(cur(b,'equity')[i]);loans=float(cur(b,'total_outstanding_loans')[i])
        self.bank.append(dict(region=str(c.country_name),bank=i,quarter=t,stage=stage,equity=e,loans=loans,
                             capital_ratio=e/loans if loans>0 else np.nan,loan_losses=float(np.asarray(b.states.get('loan_losses_current',np.zeros(len(cur(b,'equity')))))[i])))

    def flow(self,c,t):
        h,f,g,b=c.households,c.firms,c.central_government,c.banks
        tax=g.states['Income Tax'];ee=g.states['Employee Social Insurance Tax'];er=g.states['Employer Social Insurance Tax']
        comp=cur(f,'total_wage').sum();gross=comp/(1+er)
        prev=cur(h,'wealth_deposits') if t==0 else np.asarray(h.ts.prev('wealth_deposits'))
        bi=h.states['Corresponding Bank ID'];deposit_interest=(np.maximum(0,prev)*cur(b,'interest_rate_on_household_deposits')[bi]).sum()
        od_interest=(-np.minimum(0,prev)*cur(b,'overdraft_rate_on_household_deposits')[bi]).sum()
        r=dict(region=str(c.country_name),quarter=t,compensation=comp,mixed=cur(h,'income_mixed').sum()/(1-tax),
               dividends=cur(h,'income_dividends').sum()/(1-tax),cash_rent=cur(h,'income_rental').sum()/(1-tax),
               imputed_rent_memo=cur(h,'rent_imputed').sum(),deposit_interest=deposit_interest,
               financial_income_proxy=cur(h,'income_financial_assets').sum(),gov_transfers=cur(h,'income_unemployment_benefits').sum()+cur(h,'income_social_transfers').sum(),
               corporate_transfers=cur(h,'income_corporate_transfers').sum()/(1-tax),
               income_taxes=cur(g,'taxes_income').sum() if t else gross*(1-ee)*tax+cur(h,'income_rental').sum()*tax/(1-tax),
               social_contributions=gross*(ee+er),interest_paid=cur(h,'interest_paid_on_loans').sum()+od_interest,
               consumption=cur(h,'total_consumption').sum()+cur(h,'rent').sum(),income_booked=cur(h,'income').sum(),
               cash_DI=cur(h,'income').sum()-cur(h,'interest_paid').sum(),net_wages=cur(h,'income_employee').sum(),
               interest_deposits_booked=-cur(h,'interest_paid_on_deposits').sum(),rent_paid=cur(h,'rent').sum())
        self.flows.append(r)

    def post(self,sim,t,year,month):
        for n,c in sim.countries.items():
            self.flow(c,self.t)
            for i in range(len(cur(c.banks,'equity'))):self.bankrow(c,i,self.t,'end')
            f=c.firms;mask=f.states['Industry']==41;p=cur(f,'price')[mask];q=cur(f,'real_amount_sold')[mask]
            self.L.append(dict(region=str(n),quarter=self.t,quantity=q.sum(),sales=cur(f,'nominal_amount_sold_in_lcu')[mask].sum(),
                               price_weighted=(p*q).sum()/q.sum() if q.sum()>0 else np.nan,price_min=p.min(),price_max=p.max(),
                               inventory=cur(f,'inventory')[mask].sum(),production=cur(f,'production')[mask].sum(),
                               employment=cur(f,'number_of_employees')[mask].sum()*c.scale,
                               HH_L=cur(c.households,'nominal_amount_spent_in_lcu')[:,41].sum(),
                               firms_L=cur(f,'nominal_amount_spent_in_lcu')[:,41].sum(),
                               rent_offset=np.asarray(c.households.states.get('rent_L_offset_cash',0.)).sum()))

    def save(self):
        self.out.mkdir(parents=True,exist_ok=True);(self.out/'micro').mkdir(exist_ok=True)
        for name,rows in [('firms',self.firm),('banks',self.bank),('income_flows',self.flows),('L',self.L)]:pd.DataFrame(rows).to_csv(self.out/f'{name}.csv',index=False)
        for name,rows in [('cohort',self.cohort),('originations',self.loans)]:pd.DataFrame(rows).to_csv(self.out/'micro'/f'{name}.csv',index=False)


def run(args):
    warnings.filterwarnings('ignore')
    data=DataWrapper.init_from_pickle(args.pickle);names=[n for n in data.all_country_names if str(n).startswith('CAN_')]
    configs={n:CountryConfiguration.n_industry_default(n_industries=data.n_industries) for n in names}
    for c in configs.values():
        c.household_closure.credit_enabled=True;c.household_closure.income_enabled=args.arm!='iii'
        c.household_closure.rent_offset_enabled=args.arm=='d1';c.household_closure.distress_enabled=args.arm=='v'
    sim=Simulation.from_datawrapper(data,SimulationConfiguration(country_configurations=configs,t_max=args.quarters,seed=args.seed))
    out=args.output/f'{args.label}_{args.arm}_q{args.quarters}_s{args.seed}'
    diag=Diagnostics(sim,data,out);battery=AccountingBattery();sim.posthooks.extend([battery,diag.post]);rows=[]
    for t in range(args.quarters):
        diag.t=t+1;sim.iterate(t)
        for n,c in sim.countries.items():
            h=c.households;rows.append(dict(region=str(n),quarter=t+1,writeoffs=c.credit_market.states.get('household_writeoffs_current',0.),
                bank_losses=np.asarray(c.banks.states.get('loan_losses_current',0.)).sum(),new_loans=cur(h,'received_consumption_loans').sum()+cur(h,'received_mortgages').sum(),
                debt=sum(c.credit_market.states[k][0].sum() for k in ['cons_loans','mort_loans']),gdp=cur(c.economy,'gdp_output').sum()))
        print(f'{args.label} {args.arm} seed{args.seed} Q{t+1}/{args.quarters}',flush=True)
    diag.save();frame=battery.frame();frame.to_csv(out/'accounting.csv',index=False);pd.DataFrame(rows).to_csv(out/'outcomes.csv',index=False)
    checks=IDENTITY_COLUMNS+['bank_hh_deposit_snapshot_gap','bank_firm_deposit_snapshot_gap','bank_equity_unexplained','goods_market_gap']
    err=frame[checks].abs().div(frame[['hh_income','firm_sales']].abs().max(axis=1).clip(lower=1),axis=0).max().max()
    meta=dict(label=args.label,arm=args.arm,seed=args.seed,quarters=args.quarters,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              pickle=str(args.pickle),pickle_sha256=hashlib.sha256(args.pickle.read_bytes()).hexdigest(),max_accounting_error=err,
              source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((ROOT/'macromodel').rglob('*.py'))+[Path(__file__)]})
    (out/'manifest.json').write_text(json.dumps(meta,indent=2));print('accounting error',err,flush=True)
    if not np.isfinite(err) or err>1e-8:raise RuntimeError('Accounting diagnostic failed')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['iii','iv','v','d1'],required=True);ap.add_argument('--label',default='review')
    ap.add_argument('--quarters',type=int,default=12);ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--pickle',type=Path,default=ROOT/'dev/pkl_files/io2022_household_agreed.pkl')
    ap.add_argument('--output',type=Path,default=Path(__file__).parent/'outputs/pre_D3_checks');run(ap.parse_args())
