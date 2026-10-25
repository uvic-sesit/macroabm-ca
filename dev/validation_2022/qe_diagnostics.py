"""Serial QE arms using the established accounting/loss diagnostics."""
import argparse,hashlib,json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import b2_diagnostics as base
from closure_diagnostics import ROOT,cur
from macromodel.simulation import Simulation
from qe_baseline import configuration,PICKLE,PICKLE_SHA256
from b2_instrumentation import B2HouseholdDiagnosis
from closure_diagnostics import AccountingBattery,IDENTITY_COLUMNS
from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
from macromodel.agents.individuals.individual_properties import ActivityStatus
HERE=Path(__file__).resolve().parent


class Headline:
    def __init__(self,sim):
        self.rows=[];self.capture(sim,0)
        sim.posthooks.append(lambda s,t,y,m:self.capture(s,t+1))
    def capture(self,sim,t):
        for name,c in sim.countries.items():
            e=c.economy
            def v(k):return float(cur(e,k).sum())
            row=dict(region=str(name),quarter=t,gdp=v('gdp_output'),gdp_income=v('gdp_income'),gdp_expenditure=v('gdp_expenditure'),
                ppi=v('ppi'),cpi=v('cpi'),cfpi=v('cfpi'),
                C=v('total_household_fce'),G=v('total_government_fce'),I=v('total_gross_fixed_capital_formation'),
                inventories=v('total_changes_in_inventories'),X=v('total_exports'),M=v('total_imports'),
                real_rent=v('total_real_rent_paid'),imputed_rent=v('total_imp_rent_paid'),
                household_account_C=float(cur(c.households,'total_consumption').sum()+cur(c.households,'rent').sum()),
                employment=float((np.asarray(c.individuals.states['Activity Status'])==ActivityStatus.EMPLOYED).sum()*c.scale))
            cm=c.credit_market;h=c.households
            if c.configuration.household_closure.household_payment_default_enabled:
                days=cm.states.get('E_days_past_due',np.zeros((2,len(cur(h,'income')))))
                mort=cm.states['mort_loans'][0].sum(axis=0)>1e-8
                row.update(mortgage_borrowers=mort.sum()*c.scale,
                    mortgage_30plus=((days[1]>=30)&mort).sum()*c.scale,
                    mortgage_60plus=((days[1]>=60)&mort).sum()*c.scale,
                    mortgage_90plus=((days[1]>=90)&mort).sum()*c.scale,
                    defaults=np.asarray(h.states.get('E_new_defaults',0.)).sum()*c.scale,
                    foreclosure_pending=np.asarray(h.states.get('E_foreclosure_queue',0.)).sum()*c.scale,
                    foreclosure_sales=(np.asarray(h.states.get('E_foreclosure_repayment',0.))>0).sum()*c.scale,
                    mortgage_writeoffs=np.asarray(h.states.get('E_mortgage_writeoff',0.)).sum(),
                    unsecured_writeoffs=np.asarray(h.states.get('E_unsecured_writeoff',0.)).sum(),
                    household_overdraft_writeoffs=np.asarray(h.states.get('overdraft_writeoff_current',0.)).sum(),
                    foreclosure_recoveries=np.asarray(h.states.get('E_foreclosure_repayment',0.)).sum(),
                    foreclosure_surplus=np.asarray(h.states.get('E_foreclosure_surplus',0.)).sum(),
                    interest_nonaccrual_memo=np.asarray(cm.states.get('E_interest_arrears',0.)).sum(),
                    household_debt=cm.states['mort_loans'][0].sum()+cm.states['cons_loans'][0].sum())
            # Explicit PPI-deflated diagnostic, not a chained-volume national account.
            row['gdp_PPI_deflated']=row['gdp']/row['ppi']
            row['C_CPI_deflated']=row['C']/row['cpi'];row['I_CFPI_deflated']=row['I']/row['cfpi']
            row['expenditure_unallocated']=row['gdp_expenditure']-(row['C']+row['G']+row['I']+row['inventories']+row['X']-row['M'])
            self.rows.append(row)


def run(args):
    qmeta=json.loads((HERE/'benchmarks/QE/provenance.json').read_text())
    class Factory:
        @staticmethod
        def from_datawrapper(data,config):
            for cfg in config.country_configurations.values():
                cfg.household_closure=configuration()
                if args.arm=='Q':
                    cfg.household_closure.quintile_propensity_enabled=True
                    cfg.household_closure.quintile_consumption_income_ratios=qmeta['ratios']
                if args.arm=='E':cfg.household_closure.household_payment_default_enabled=True
                if args.arm=='C':
                    cfg.household_closure.overdraft_limit_enabled=False
                    cfg.household_closure.financial_asset_drawdown=False
                    cfg.household_closure.consumption_before_investment=False
                    cfg.household_closure.firm_payment_default_enabled=False
                    cfg.household_closure.rent_offset_enabled=False
                    cfg.household_closure.investment_benchmark_enabled=False
            sim=Simulation.from_datawrapper(data,config)
            holder['sim']=sim;holder['headline']=Headline(sim)
            if args.arm in ['F_CFC','Q']:
                from qe_wealth_audit import capture
                holder['wealth']=capture(sim)
            if args.arm=='E' and args.variant.startswith('rent_debug'):
                def debug(s,t,y,m):
                    if t!=3:return
                    out=HERE/'outputs/QE'/args.variant/'micro';out.mkdir(parents=True,exist_ok=True)
                    for name,c in s.countries.items():
                        h=c.households
                        pd.DataFrame(dict(rent=cur(h,'rent'),rental_income=cur(h,'income_rental'),house=h.states['Corresponding Inhabited House ID'],tenure=h.states['Tenure Status of the Main Residence'])).to_csv(out/(str(name)+'_households.csv'),index=False)
                        c.housing_market.states['properties'].to_csv(out/(str(name)+'_properties.csv'),index=False)
                sim.posthooks.append(debug)
            return sim
    holder={};base.Simulation=Factory
    source=PICKLE if args.arm in ['F_CFC','Q','E'] else ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt.pkl'
    if args.arm=='C':source=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap.pkl'
    if source==PICKLE:assert hashlib.sha256(source.read_bytes()).hexdigest()==PICKLE_SHA256
    out=getattr(args,'output',HERE/'outputs/QE/runs')
    params=SimpleNamespace(arm=args.arm,variant=args.variant,household_base='F',quarters=args.quarters,seed=args.seed,
        pickle=source,output=out,kappa=.01,kappa_below=None,smoothing=.25,payout=False)
    target=out/f'{args.arm}_{args.variant}_q{args.quarters}_s{args.seed}'
    if args.arm=='C':
        data=DataWrapper.init_from_pickle(source)
        configs={n:CountryConfiguration.n_industry_default(n_industries=data.n_industries) for n in data.all_country_names if str(n).startswith('CAN_')}
        sim=Factory.from_datawrapper(data,SimulationConfiguration(country_configurations=configs,t_max=args.quarters,seed=args.seed))
        target.mkdir(parents=True,exist_ok=True)
        diag=B2HouseholdDiagnosis(sim,data);battery=AccountingBattery();sim.posthooks.append(battery)
        for t in range(args.quarters):
            sim.iterate(t);print(f'C seed{args.seed} Q{t+1}/{args.quarters}',flush=True)
        diag.save(target);frame=battery.frame();frame.to_csv(target/'accounting.csv',index=False)
        checks=IDENTITY_COLUMNS+['bank_hh_deposit_snapshot_gap','bank_firm_deposit_snapshot_gap','bank_equity_unexplained','goods_market_gap','firm_cash_identity_resid']
        assert np.isfinite(frame[checks].to_numpy()).all()
        error=frame[checks].abs().div(frame[['hh_income','firm_sales']].abs().max(axis=1).clip(lower=1),axis=0).max().max()
        assert error<=1e-8
        meta=dict(arm='C',seed=args.seed,quarters=args.quarters,pickle=str(source),pickle_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),max_accounting_error=error)
        (target/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    else:base.run(params)
    pd.DataFrame(holder['headline'].rows).to_csv(target/'headline.csv',index=False)
    if 'wealth' in holder:holder['wealth'].to_csv(target/'wealth_definition_audit.csv',index=False)
    pd.DataFrame([dict(region=str(n),**c.households.states.get('quintile_consumption_calibration',{})) for n,c in holder['sim'].countries.items()]).to_csv(target/'Q_calibration.csv',index=False)
    m=json.loads((target/'manifest.json').read_text());m['QE_sources']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'qe_baseline.py',HERE/'benchmarks/QE/provenance.json']}
    (target/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['C','F','F_CFC','Q','E'],required=True)
    ap.add_argument('--seed',type=int,default=0);ap.add_argument('--quarters',type=int,default=12)
    ap.add_argument('--variant',default='base')
    run(ap.parse_args())
