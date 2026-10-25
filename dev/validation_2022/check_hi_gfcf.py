"""Execute unchanged GDP initialization checks for all 13 GFCF regions; never iterate invalid input."""
import json
from pathlib import Path
import numpy as np,pandas as pd
from closure_diagnostics import ROOT
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from macromodel.country.country import Country
from macromodel.configurations import CountryConfiguration,SimulationConfiguration
import macromodel.economy.economy as economy
from qe_baseline import configuration
from build_hi_gfcf import TARGET,OUT

def main():
    d=DataWrapper.init_from_pickle(TARGET);names=[n for n in d.all_country_names if str(n).startswith('CAN_')];configs={n:CountryConfiguration.n_industry_default(n_industries=d.n_industries) for n in names}
    for c in configs.values():c.household_closure=configuration()
    original=economy.create_economy_timeseries;country=Country.from_pickled_country;rows=[];values={}
    def capture(**k):
        scoped=k.get('housing_services_in_household_io',False)
        rent=0. if scoped else np.asarray(k['initial_real_rent_paid']).sum()+np.asarray(k['initial_imp_rent_paid']).sum()
        output=k['initial_firm_total_sales']-np.asarray(k['initial_sectoral_firm_used_ii']).sum()+k['initial_total_taxes_on_products']-k['initial_total_taxes_on_production']+rent
        expenditure=k['initial_change_in_firm_stock_inventories']+k['initial_gross_fixed_capital_formation']+k['initial_hh_consumption']+k['initial_gov_consumption']+(1+k['export_taxes'])*np.asarray(k['initial_exports']).sum()-np.asarray(k['initial_imports']).sum()+rent
        income=k['initial_total_operating_surplus']+k['initial_total_wages']+k['initial_total_taxes_on_products']
        if not scoped:income+=np.asarray(k['initial_hh_rental_income']).sum()+k['initial_cg_rent_received']+k['initial_cg_taxes_rental_income']+np.asarray(k['initial_imp_rent_paid']).sum()
        values[str(k['country_name'])]=dict(output=output,expenditure=expenditure,income=income,expenditure_gap=expenditure-output,income_gap=income-output)
        return original(**k)
    def attempt(**k):
        name=str(k['country_name'])
        try:result=country(**k);passed=True;error=''
        except AssertionError as e:result=None;passed=False;error=str(e)
        rows.append(dict(region=name,passed=passed,error=error,**values[name]))
        if len(rows)==len(names):raise RuntimeError('HI_INITIALIZATION_AUDIT_COMPLETE')
        return result
    economy.create_economy_timeseries=capture;Country.from_pickled_country=staticmethod(attempt)
    try:Simulation.from_datawrapper(d,SimulationConfiguration(country_configurations=configs,t_max=2,seed=0))
    except RuntimeError as e:
        if str(e)!='HI_INITIALIZATION_AUDIT_COMPLETE':raise
    finally:economy.create_economy_timeseries=original;Country.from_pickled_country=country
    assert len(rows)==13;f=pd.DataFrame(rows);f.to_csv(OUT/'gfcf_GDP_initialization.csv',index=False)
    print(f[['region','passed','expenditure_gap']].to_string(index=False),flush=True)
if __name__=='__main__':main()
