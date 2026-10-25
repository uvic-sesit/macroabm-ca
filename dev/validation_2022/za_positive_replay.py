"""Serial before/after guard replay, comparing every numeric firm state by bits."""
import subprocess,json,hashlib
import numpy as np
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
from macromodel.agents.firms.func.labour_productivity import WorkEffortLabourProductivitySetter as Setter
from qe_baseline import PICKLE,configuration
from prepare_za import ROOT,OUT
from closure_diagnostics import AccountingBattery,IDENTITY_COLUMNS
def main():
    OUT.mkdir(exist_ok=True)
    source=subprocess.check_output(['git','show','ca33da2:macromodel/agents/firms/func/labour_productivity.py'],cwd=ROOT).decode();space={};exec(compile(source,'ca33da2_labour_productivity.py','exec'),space)
    old=space['WorkEffortLabourProductivitySetter'].compute_labour_productivity_factor;new=Setter.compute_labour_productivity_factor;reference={};counts=[]
    for label,method in [('before',old),('after',new)]:
        Setter.compute_labour_productivity_factor=method;d=DataWrapper.init_from_pickle(PICKLE);names=[n for n in d.all_country_names if str(n).startswith('CAN_')];cfg={n:CountryConfiguration.n_industry_default(n_industries=d.n_industries) for n in names}
        for c in cfg.values():c.household_closure=configuration()
        sim=Simulation.from_datawrapper(d,SimulationConfiguration(country_configurations=cfg,t_max=2,seed=0));battery=AccountingBattery();sim.posthooks.append(battery);checked=0
        for t in range(2):
            sim.iterate(t)
            for name,c in sim.countries.items():
                for field in c.firms.ts.dicts:
                    try:a=np.asarray(c.firms.ts.current(field))
                    except (TypeError,ValueError):continue
                    if not np.issubdtype(a.dtype,np.number) or a.ndim==0 or a.shape[0]!=len(c.firms.states['Industry']):continue
                    payload=(str(a.dtype),a.shape,a.tobytes());key=(t,str(name),field)
                    if label=='before':reference[key]=payload
                    else:assert payload==reference[key],key
                    checked+=1
            print(label,'F_CFC seed0 Q',t+1,flush=True)
        frame=battery.frame();checks=IDENTITY_COLUMNS+['bank_hh_deposit_snapshot_gap','bank_firm_deposit_snapshot_gap','bank_equity_unexplained','goods_market_gap','firm_cash_identity_resid'];assert np.isfinite(frame[checks]).all().all();error=float(frame[checks].abs().div(frame[['hh_income','firm_sales']].abs().max(axis=1).clip(lower=1),axis=0).max().max());assert error<1e-8
        counts.append(dict(version=label,numeric_state_arrays_compared=checked,max_accounting_error=error));frame.to_csv(OUT/f'F_CFC_guard_{label}_accounting.csv',index=False)
    Setter.compute_labour_productivity_factor=new
    (OUT/'positive_output_bit_replay.json').write_text(json.dumps(dict(passed=True,source_before_commit='ca33da2',F_CFC_seed=0,quarters=2,method='All numeric per-firm time-series current fields (first axis number of firms), dtype+shape+raw bytes; every firm including inherited floors. Aggregate descriptive tail estimators are excluded, not economic per-firm states. Original/new methods on fresh identical inputs, serial runs.',runs=counts),indent=2)+'\n')
if __name__=='__main__':main()
