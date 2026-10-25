"""Correct secondary SHS gross-wage ranks; require unchanged primary/macro paths."""
import gc,hashlib,json,subprocess
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
from closure_diagnostics import ROOT,cur,AccountingBattery,IDENTITY_COLUMNS
from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
from macromodel.simulation import Simulation
from qe_baseline import configuration
from qe_diagnostics import Headline
from b2_instrumentation import B2HouseholdDiagnosis
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/QE'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    warnings.filterwarnings('ignore')
    ratios=json.loads((HERE/'benchmarks/QE/provenance.json').read_text())['ratios']
    selected=[]
    for p in sorted((OUT/'runs').glob('*/manifest.json')):
        m=json.loads(p.read_text())
        if m['quarters']!=12 or m['max_accounting_error']>1e-8:continue
        if m['arm']=='E' and m.get('variant')!='complete':continue
        selected.append((p,m))
    assert len(selected)==15
    for p,m in selected:
        out=OUT/'distribution_corrected'/p.parent.name
        if (out/'manifest.json').exists():continue
        data=DataWrapper.init_from_pickle(Path(m['pickle']))
        assert sha(Path(m['pickle']))==m['pickle_sha256']
        configs={n:CountryConfiguration.n_industry_default(n_industries=data.n_industries) for n in data.all_country_names if str(n).startswith('CAN_')}
        for cfg in configs.values():
            cfg.household_closure=configuration();c=cfg.household_closure
            if m['arm']=='C':
                for flag in ['overdraft_limit_enabled','financial_asset_drawdown','consumption_before_investment','firm_payment_default_enabled','rent_offset_enabled','investment_benchmark_enabled']:setattr(c,flag,False)
            if m['arm']=='Q':c.quintile_propensity_enabled=True;c.quintile_consumption_income_ratios=ratios
            if m['arm']=='E':c.household_payment_default_enabled=True
        sim=Simulation.from_datawrapper(data,SimulationConfiguration(country_configurations=configs,t_max=12,seed=m['seed']))
        out.mkdir(parents=True,exist_ok=True)
        headline=Headline(sim);diagnosis=B2HouseholdDiagnosis(sim,data);battery=AccountingBattery();sim.posthooks.append(battery)
        old=pd.read_csv(p.parent/'outcomes.csv').set_index(['region','quarter']) if m['arm']!='C' else None
        comparisons=[]
        for t in range(12):
            sim.iterate(t)
            if old is not None:
                for n,c in sim.countries.items():
                    h=c.households
                    fields=dict(gdp=cur(c.economy,'gdp_output').sum(),consumption=cur(h,'total_consumption').sum()+cur(h,'rent').sum(),
                        cash_DI=cur(h,'income').sum()-cur(h,'interest_paid').sum(),
                        constrained_households=np.asarray(h.states['overdraft_constrained']).sum()*c.scale,
                        household_writeoffs=c.credit_market.states['household_writeoffs_current'],
                        bank_losses=np.asarray(c.banks.states['loan_losses_current']).sum(),
                        recapitalisation=np.asarray(c.banks.states['recapitalisation_current']).sum())
                    for key,value in fields.items():
                        reference=old.loc[(str(n),t+1),key]
                        assert np.isclose(value,reference,rtol=1e-12,atol=1e-3),(p.parent.name,n,t,key,value,reference)
                        comparisons.append(dict(region=str(n),quarter=t+1,field=key,difference=value-reference))
            print('Read-only corrected ranks',p.parent.name,f'Q{t+1}/12',flush=True)
        now=pd.DataFrame(headline.rows);reference=pd.read_csv(p.parent/'headline.csv')
        np.testing.assert_allclose(now[reference.select_dtypes('number').columns],reference.select_dtypes('number'),rtol=1e-12,atol=1e-3,equal_nan=True)
        diagnosis.save(out)
        a=pd.read_csv(out/'consumption_quintiles.csv');b=pd.read_csv(p.parent/'consumption_quintiles.csv')
        a=a[a.scheme=='DHEA_equivalised_DI'].reset_index(drop=True);b=b[b.scheme=='DHEA_equivalised_DI'].reset_index(drop=True)
        np.testing.assert_allclose(a.select_dtypes('number'),b.select_dtypes('number'),rtol=1e-12,atol=1e-3,equal_nan=True)
        frame=battery.frame();frame.to_csv(out/'accounting.csv',index=False)
        columns=IDENTITY_COLUMNS+['bank_hh_deposit_snapshot_gap','bank_firm_deposit_snapshot_gap','bank_equity_unexplained','goods_market_gap','firm_cash_identity_resid']
        assert np.isfinite(frame[columns].to_numpy()).all()
        error=frame[columns].abs().div(frame[['hh_income','firm_sales']].abs().max(axis=1).clip(lower=1),axis=0).max().max();assert error<=1e-8
        pd.DataFrame(comparisons).to_csv(out/'macro_path_comparison.csv',index=False)
        meta=dict(arm=m['arm'],seed=m['seed'],original_manifest=str(p.relative_to(ROOT)),original_manifest_sha256=sha(p),
            pickle_sha256=m['pickle_sha256'],all_macro_paths_match=True,primary_DHEA_unchanged=True,max_accounting_error=float(error),
            correction='Secondary SHS gross wages invert payroll using (1-PIT)*(1-SSC), replacing the legacy additive denominator. No model argument/state/RNG changed.',
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            source_sha256={str(f.relative_to(ROOT)):sha(f) for f in [Path(__file__),HERE/'b2_instrumentation.py',HERE/'qe_baseline.py',HERE/'qe_diagnostics.py']})
        (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
        del sim,headline,diagnosis,battery,data;gc.collect()

if __name__=='__main__':main()
