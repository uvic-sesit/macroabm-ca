"""Read-only C bank decomposition; demand exact original macro/distribution paths."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from closure_diagnostics import ROOT,AccountingBattery,IDENTITY_COLUMNS,cur
from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
from macromodel.simulation import Simulation
from qe_baseline import configuration
from qe_diagnostics import Headline
from b2_instrumentation import B2HouseholdDiagnosis
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/QE'


def main():
    for seed in range(3):
        target=OUT/'C_bank_replays'/f'C_s{seed}'
        if (target/'manifest.json').exists():continue
        original=OUT/'runs'/f'C_base_q12_s{seed}'
        m=json.loads((original/'manifest.json').read_text());data=DataWrapper.init_from_pickle(Path(m['pickle']))
        configs={n:CountryConfiguration.n_industry_default(n_industries=data.n_industries) for n in data.all_country_names if str(n).startswith('CAN_')}
        for c in configs.values():
            cfg=configuration()
            for flag in ['overdraft_limit_enabled','financial_asset_drawdown','consumption_before_investment','firm_payment_default_enabled','rent_offset_enabled','investment_benchmark_enabled']:setattr(cfg,flag,False)
            c.household_closure=cfg
        sim=Simulation.from_datawrapper(data,SimulationConfiguration(country_configurations=configs,t_max=12,seed=seed))
        target.mkdir(parents=True,exist_ok=True);headline=Headline(sim);dist=B2HouseholdDiagnosis(sim,data)
        battery=AccountingBattery();sim.posthooks.append(battery);rows=[]
        previous={str(n):c.credit_market.states.get('cumulative_writeoffs',0.) for n,c in sim.countries.items()}
        for t in range(12):
            sim.iterate(t)
            for n,c in sim.countries.items():
                name=str(n);cm=c.credit_market;bank=c.banks
                cumulative=cm.states.get('cumulative_writeoffs',0.);formal=cumulative-previous[name];previous[name]=cumulative
                hh=cm.states['household_writeoffs_current'];loss=np.asarray(bank.states.get('loan_losses_current',0.)).sum()
                assert formal-hh>=-1e-3 and loss-formal>=-1e-3
                rows.append(dict(seed=seed,quarter=t+1,region=name,household_writeoffs=hh,firm_loan_losses=formal-hh,overdraft_losses=loss-formal,bank_losses=loss,
                    recapitalisation=np.asarray(bank.states.get('recapitalisation_current',0.)).sum(),min_capital_ratio=np.min(cur(bank,'equity')/cur(bank,'total_outstanding_loans')),
                    min_resolution_ratio=np.min(cur(bank,'equity')/(cur(bank,'total_outstanding_loans')+cur(bank,'deposits')))))
            print(f'C bank replay seed{seed} Q{t+1}/12',flush=True)
        now=pd.DataFrame(headline.rows);old=pd.read_csv(original/'headline.csv')
        np.testing.assert_allclose(now.select_dtypes('number'),old.select_dtypes('number'),rtol=1e-12,atol=1e-3,equal_nan=True)
        dist.save(target);x=pd.read_csv(target/'consumption_quintiles.csv');y=pd.read_csv(original/'consumption_quintiles.csv')
        np.testing.assert_allclose(x.select_dtypes('number'),y.select_dtypes('number'),rtol=1e-12,atol=1e-3,equal_nan=True)
        frame=battery.frame();frame.to_csv(target/'accounting.csv',index=False)
        columns=IDENTITY_COLUMNS+['bank_hh_deposit_snapshot_gap','bank_firm_deposit_snapshot_gap','bank_equity_unexplained','goods_market_gap','firm_cash_identity_resid']
        assert np.isfinite(frame[columns].to_numpy()).all()
        error=frame[columns].abs().div(frame[['hh_income','firm_sales']].abs().max(axis=1).clip(lower=1),axis=0).max().max();assert error<=1e-8
        pd.DataFrame(rows).to_csv(target/'bank_components.csv',index=False)
        meta=dict(seed=seed,max_accounting_error=error,exact_macro_and_distribution_match=True,original_manifest_sha256=hashlib.sha256((original/'manifest.json').read_bytes()).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        (target/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')

if __name__=='__main__':main()
