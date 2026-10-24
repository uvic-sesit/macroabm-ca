"""Serial read-only distribution replays; require identical recorded macro paths."""
import hashlib
import json
from pathlib import Path
import subprocess
import warnings
import numpy as np
import pandas as pd
from closure_diagnostics import ROOT,cur,AccountingBattery
from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration
from macromodel.simulation import Simulation
from b2_instrumentation import B2HouseholdDiagnosis
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/B2'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    warnings.filterwarnings('ignore')
    ref=pd.read_csv(HERE/'benchmarks/BE/sfs_liquid_buffers.csv')
    buffers={f'{int(r.income_decile)}:{int(r.age_band)}':[float(r.b_quarters),float(r.fallback_buffer_CAD)] for r in ref.itertuples()}
    for manifest in sorted((OUT/'final').glob('*/manifest.json')):
        m=json.loads(manifest.read_text())
        if m['quarters']!=12:continue
        out=OUT/'distribution_replays'/manifest.parent.name
        if (out/'manifest.json').exists():continue
        data=DataWrapper.init_from_pickle(Path(m['pickle']))
        names=[n for n in data.all_country_names if str(n).startswith('CAN_')]
        configs={n:CountryConfiguration.n_industry_default(n_industries=data.n_industries) for n in names}
        for c in configs.values():
            cfg=HouseholdClosureConfiguration.cashflow_candidate()
            cfg.financial_asset_drawdown=True;cfg.investment_benchmark_enabled=True
            cfg.consumption_before_investment=True;cfg.firm_payment_default_enabled=True
            cfg.buffer_stock_enabled=m['household_base']=='B2';cfg.buffer_stock_reanchor_enabled=cfg.buffer_stock_enabled
            cfg.buffer_stock_kappa=m['kappa'];cfg.buffer_stock_kappa_below=m['kappa_below']
            cfg.buffer_stock_smoothing=m['smoothing'];cfg.buffer_stock_reference=buffers
            cfg.prudent_firm_payout_enabled=m['payout'];c.household_closure=cfg
        sim=Simulation.from_datawrapper(data,SimulationConfiguration(country_configurations=configs,t_max=12,seed=m['seed']))
        out.mkdir(parents=True,exist_ok=True)
        diagnosis=B2HouseholdDiagnosis(sim,data,micro_out=out/'micro')
        old=pd.read_csv(manifest.parent/'outcomes.csv').set_index(['region','quarter'])
        checks=[]
        for t in range(12):
            sim.iterate(t)
            for n,c in sim.countries.items():
                h=c.households
                values=dict(gdp=cur(c.economy,'gdp_output').sum(),consumption=cur(h,'total_consumption').sum()+cur(h,'rent').sum(),
                    household_income=cur(h,'income').sum(),cash_DI=cur(h,'income').sum()-cur(h,'interest_paid').sum(),
                    constrained_households=np.asarray(h.states['overdraft_constrained']).sum()*c.scale,
                    household_writeoffs=c.credit_market.states['household_writeoffs_current'],
                    bank_losses=np.asarray(c.banks.states['loan_losses_current']).sum())
                for key,value in values.items():
                    reference=float(old.loc[(str(n),t+1),key])
                    if not np.isclose(value,reference,rtol=1e-12,atol=1e-3):
                        raise AssertionError(f'Replay changed {manifest.parent.name} {n} Q{t+1} {key}: {value} != {reference}')
                    checks.append(dict(region=str(n),quarter=t+1,field=key,difference=value-reference))
        diagnosis.save(out)
        pd.DataFrame(checks).to_csv(out/'macro_path_comparison.csv',index=False)
        meta=dict(original_manifest=str(manifest.relative_to(ROOT)),original_manifest_sha256=sha(manifest),
            original_pickle_sha256=m['pickle_sha256'],seed=m['seed'],quarters=12,
            correction='National income ranks use income per household, dividing aggregate balances by each regional expansion factor. Weights and consumption totals unchanged.',
            all_macro_paths_match=True,head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),HERE/'b2_instrumentation.py']})
        (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
        print('Corrected distributions, identical macro paths:',manifest.parent.name,flush=True)

if __name__=='__main__':main()
