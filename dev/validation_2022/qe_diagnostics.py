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
                if args.arm=='C':
                    cfg.household_closure.overdraft_limit_enabled=False
                    cfg.household_closure.financial_asset_drawdown=False
                    cfg.household_closure.consumption_before_investment=False
                    cfg.household_closure.firm_payment_default_enabled=False
                    cfg.household_closure.rent_offset_enabled=False
                    cfg.household_closure.investment_benchmark_enabled=False
            sim=Simulation.from_datawrapper(data,config)
            holder['sim']=sim;holder['headline']=Headline(sim)
            return sim
    holder={};base.Simulation=Factory
    source=PICKLE if args.arm in ['F_CFC','Q'] else ROOT/'dev/pkl_files/io2022_household_agreed_bankcap_firmdebt.pkl'
    if args.arm=='C':source=ROOT/'dev/pkl_files/io2022_household_agreed_bankcap.pkl'
    if source==PICKLE:assert hashlib.sha256(source.read_bytes()).hexdigest()==PICKLE_SHA256
    out=HERE/'outputs/QE/runs'
    params=SimpleNamespace(arm=args.arm,variant='base',household_base='F',quarters=args.quarters,seed=args.seed,
        pickle=source,output=out,kappa=.01,kappa_below=None,smoothing=.25,payout=False)
    base.run(params)
    target=out/f'{args.arm}_base_q{args.quarters}_s{args.seed}'
    pd.DataFrame(holder['headline'].rows).to_csv(target/'headline.csv',index=False)
    pd.DataFrame([dict(region=str(n),**c.households.states.get('quintile_consumption_calibration',{})) for n,c in holder['sim'].countries.items()]).to_csv(target/'Q_calibration.csv',index=False)
    m=json.loads((target/'manifest.json').read_text());m['QE_sources']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'qe_baseline.py',HERE/'benchmarks/QE/provenance.json']}
    (target/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['C','F','F_CFC','Q'],required=True)
    ap.add_argument('--seed',type=int,default=0);ap.add_argument('--quarters',type=int,default=12)
    run(ap.parse_args())
