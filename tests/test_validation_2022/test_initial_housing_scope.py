import inspect
import numpy as np
from macromodel.economy.economy_ts import create_economy_timeseries
from macromodel.agents.individuals.individual_properties import ActivityStatus

def make(io):
    k={n:0. for n,p in inspect.signature(create_economy_timeseries).parameters.items() if p.default is inspect.Parameter.empty}
    k.update(country_name='X',all_country_names=['X'],n_industries=20,initial_firm_prices=np.ones(20),initial_sectoral_firm_sales=np.r_[100.,np.zeros(19)],initial_sectoral_firm_used_ii=np.r_[20.,np.zeros(19)],initial_firm_total_sales=100.,initial_hh_consumption=80.,initial_total_operating_surplus=50.,initial_total_wages=30.,initial_individual_activity=np.array([ActivityStatus.EMPLOYED]),initial_real_rent_paid=np.array([20.]),initial_imp_rent_paid=np.array([30.]),initial_hh_rental_income=np.array([10.]),initial_cg_rent_received=5.,initial_cg_taxes_rental_income=5.,initial_imports=np.zeros(1),initial_exports=np.zeros(1),initial_imports_by_country={'X':np.zeros(1)},initial_exports_by_country={'X':np.zeros(1)},housing_services_in_household_io=io)
    return create_economy_timeseries(**k)

def test_io_housing_removed_from_all_gdp_measures_but_memos_unchanged():
    old,new=make(False),make(True)
    for key in ['gdp_output','gdp_expenditure']:
        assert old.current(key)[0]-new.current(key)[0]==50.
        assert new.current(key)[0]==80.
    assert old.current('gdp_income')[0]-new.current('gdp_income')[0]==50.
    for key in ['total_real_rent_paid','total_imp_rent_paid','total_real_rent_rec','total_household_fce','total_gross_fixed_capital_formation','total_exports','total_imports']:
        np.testing.assert_array_equal(old.current(key),new.current(key))


def test_gdp_debug_report_addends_obey_scope_and_keep_rent_memos():
    from types import SimpleNamespace
    from macromodel.country.country import Country
    agent=SimpleNamespace(ts=SimpleNamespace(get_aggregate=lambda key:np.ones(2)))
    for io in [True,False]:
        c=SimpleNamespace(economy=agent,households=agent,firms=agent,government_entities=agent,central_government=agent,housing_services_in_household_io=io)
        for report in [Country.gdp_debug_output(c),Country.gdp_components_df.fget(c)]:
            for key in ['+Rent_Paid','+Rent_Imputed','+Rent_Received','+Central_Government_Rent_Received','+Central_Government_Rental_Taxes']:
                np.testing.assert_array_equal(report[key],np.full(2,0. if io else 1.))
            np.testing.assert_array_equal(report.Memo_Real_Rent_Paid,np.ones(2))
