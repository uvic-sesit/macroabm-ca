from types import SimpleNamespace as NS
import numpy as np
import pytest
from macromodel.configurations.bank_configuration import BankParameters
from macromodel.markets.credit_market.func.clearing import WaterBucketCreditMarketClearer
from macromodel.timeseries import TimeSeries


@pytest.mark.parametrize('unit', [1., 1000.])
def test_default_category_budgets_are_currency_and_scale_with_balance_sheets(unit):
    p=BankParameters(capital_adequacy_ratio=.1, household_consumption_loans_loan_to_income_ratio=.5)
    b=NS(parameters=p,ts=TimeSeries(n_banks=1,equity=np.array([100.*unit]),total_outstanding_loans=np.zeros(1),
        new_loans_fraction_firms=np.array([.2]),new_loans_fraction_hh_cons=np.array([.4]),
        new_loans_fraction_mortgages=np.array([.4]),interest_rates_on_short_term_firm_loans=np.array([.01]),
        interest_rates_on_long_term_firm_loans=np.array([.01]),interest_rates_on_household_consumption_loans=np.array([.01]),
        interest_rates_on_mortgages=np.array([.01])))
    f=NS(ts=TimeSeries(n_firms=1,target_short_term_credit=np.zeros(1),target_long_term_credit=np.zeros(1),
        capital_inputs_stock_value=np.zeros(1),deposits=np.zeros(1),debt=np.zeros(1),expected_profits=np.zeros(1)))
    h=NS(ts=TimeSeries(n_households=1,income=np.array([1000.*unit]),debt=np.zeros(1),
        wealth_financial_assets=np.zeros(1),target_mortgage=np.zeros(1),target_consumption_loans=np.array([100.*unit])))
    h.ts.income.append(np.array([1000.*unit]))
    clearer=WaterBucketCreditMarketClearer(allow_short_term_firm_loans=True,allow_household_loans=True,
        firms_max_number_of_banks_visiting=1,households_max_number_of_banks_visiting=1,
        consider_loan_type_fractions=True,credit_supply_temperature=0,interest_rates_selection_temperature=0,
        creditor_selection_is_deterministic=True,creditor_minimum_fill=False,debtor_minimum_fill=False)
    loans=clearer.clear(b,f,h,0,0,0)
    assert loans[2][0].sum()==pytest.approx(100.*unit)
    assert sum(x[0].sum() for x in loans)<=1000.*unit
