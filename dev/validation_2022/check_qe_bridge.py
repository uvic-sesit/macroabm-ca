"""Execute each region's unchanged GDP initialisation assertion, never bypass it.

Diagnostic construction attempts are serial. Failed countries are not used
in a simulation: collect the failure, continue independent regional attempts,
then deliberately abort before a Simulation can be returned.
"""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from closure_diagnostics import ROOT
from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
from macromodel.simulation import Simulation
from macromodel.country.country import Country
import macromodel.economy.economy as economy
from qe_baseline import configuration
from build_qe_bridge import TARGET,OUT


def main():
    data=DataWrapper.init_from_pickle(TARGET);names=[n for n in data.all_country_names if str(n).startswith('CAN_')]
    configs={n:CountryConfiguration.n_industry_default(n_industries=data.n_industries) for n in names}
    for c in configs.values():c.household_closure=configuration()
    rows=[];captured={};original=economy.create_economy_timeseries;original_country=Country.from_pickled_country
    def capture(**k):
        housing=np.asarray(k['initial_real_rent_paid']).sum()+np.asarray(k['initial_imp_rent_paid']).sum()
        output=k['initial_firm_total_sales']-np.asarray(k['initial_sectoral_firm_used_ii']).sum()+k['initial_total_taxes_on_products']-k['initial_total_taxes_on_production']+housing
        expenditure=k['initial_change_in_firm_stock_inventories']+k['initial_gross_fixed_capital_formation']+k['initial_hh_consumption']+k['initial_gov_consumption']+(1+k['export_taxes'])*np.asarray(k['initial_exports']).sum()-np.asarray(k['initial_imports']).sum()+housing
        income=k['initial_total_operating_surplus']+k['initial_total_wages']+k['initial_total_taxes_on_products']+np.asarray(k['initial_hh_rental_income']).sum()+k['initial_cg_rent_received']+k['initial_cg_taxes_rental_income']+np.asarray(k['initial_imp_rent_paid']).sum()
        captured[str(k['country_name'])]=dict(output=float(output),expenditure=float(expenditure),income=float(income),output_expenditure_ratio=float(output/expenditure),output_income_ratio=float(output/income))
        return original(**k)
    economy.create_economy_timeseries=capture
    def attempt(**k):
        name=str(k['country_name'])
        try:
            country=original_country(**k)
            rows.append(dict(region=name,initialisation_passed=True,failure='',**captured[name]))
        except AssertionError as e:
            if name not in captured:raise
            rows.append(dict(region=name,initialisation_passed=False,failure=str(e),**captured[name]));country=None
        if len(rows)==len(names):raise RuntimeError('REGIONAL_DIAGNOSTICS_COMPLETE_NO_SIMULATION_RETURNED')
        return country
    Country.from_pickled_country=staticmethod(attempt)
    try:Simulation.from_datawrapper(data,SimulationConfiguration(country_configurations=configs,t_max=2,seed=0))
    except RuntimeError as e:
        if str(e)!='REGIONAL_DIAGNOSTICS_COMPLETE_NO_SIMULATION_RETURNED':raise
    finally:economy.create_economy_timeseries=original;Country.from_pickled_country=original_country
    assert len(rows)==13
    pd.DataFrame(rows).to_csv(OUT/'unchanged_GDP_checks.csv',index=False)
    f=pd.read_csv(OUT/'firm_bridge.csv')
    gates=dict(every_regional_GDP=all(r['initialisation_passed'] for r in rows),margin=bool(f.margin_gap_pp.abs().max()<=1),no_above_price_nonnegative_GOS=bool(not f.above_price_nonnegative_GOS.any()),accounting='not run: initialization/cost gates fail; invalid input is not iterated')
    gates['passed']=all(gates[k] for k in ['every_regional_GDP','margin','no_above_price_nonnegative_GOS'])
    gates['assertion_source_sha256']=hashlib.sha256((ROOT/'macromodel/economy/economy_ts.py').read_bytes()).hexdigest()
    (OUT/'gates.json').write_text(json.dumps(gates,indent=2)+'\n');print(json.dumps(gates),flush=True)

if __name__=='__main__':main()
