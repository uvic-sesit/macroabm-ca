from types import SimpleNamespace as NS
import numpy as np
import pytest
from macromodel.timeseries import TimeSeries
from macromodel.configurations.bank_configuration import BankParameters
from macromodel.markets.credit_market.credit_market import CreditMarket
from macromodel.markets.credit_market.func.clearing import WaterBucketCreditMarketClearer
from macromodel.markets.credit_market.types_of_loans import LoanTypes
@pytest.mark.parametrize("income_periods,service,price,expected", [
    (4, 0, 100, 80), (1, 0, 100, 0), (4, 10, 100, 0), (4, 0, 90, 0)])
def test_active_waterbucket_enforces_annual_income_collateral_and_existing_service(income_periods, service, price, expected):
    params = BankParameters(mortgage_loan_to_income_ratio=4.5, household_income_periods_per_year=income_periods,
                             mortgage_loan_to_value_ratio=0.8, mortgage_debt_service_to_income_ratio=0.4,
                             mortgage_use_property_collateral=True, mortgage_maturity=100)
    bank = NS(parameters=params, ts=TimeSeries(n_banks=1, equity=np.array([100.]),
              total_outstanding_loans=np.array([0.]), interest_rates_on_mortgages=np.array([0.]),
              interest_rates_on_household_consumption_loans=np.array([0.])))
    hh = NS(states={"target_property_value": np.array([price]), "credit_existing_service": np.array([service])},
            ts=TimeSeries(income=np.array([10.]), debt=np.array([0.]), wealth_financial_assets=np.array([20.]),
                          wealth_deposits=np.zeros(1), target_mortgage=np.array([80.])))
    hh.ts.income.append(np.array([10.]))
    clearer = WaterBucketCreditMarketClearer(allow_short_term_firm_loans=True, allow_household_loans=True,
            firms_max_number_of_banks_visiting=1, households_max_number_of_banks_visiting=1,
            consider_loan_type_fractions=False, credit_supply_temperature=0, interest_rates_selection_temperature=0,
            creditor_selection_is_deterministic=True, creditor_minimum_fill=False, debtor_minimum_fill=False)
    loans = clearer.clear_loans(bank, None, hh, LoanTypes.MORTGAGE, np.zeros(1), np.zeros(1), np.zeros(1), np.array([1000.]))
    assert loans[0].sum() == pytest.approx(expected)


def test_cancelled_house_sale_cancels_only_new_mortgage_without_a_bank_loss():
    old = np.zeros((3, 1, 2)); old[0, 0] = [10, 20]
    new = np.zeros_like(old); new[0, 0] = [80, 90]
    cm = NS(states={"mort_loans": old + new, "mortgage_book_before_commitments": old,
                    "mortgage_commitments": new, "cons_loans": np.zeros_like(old),
                    "st_loans": np.zeros_like(old), "lt_loans": np.zeros_like(old)},
            ts=TimeSeries(total_newly_loans_granted_mortgages=[170.]))
    h = NS(ts=TimeSeries(price_paid_for_property=np.array([0., 100.]),
                         received_mortgages=np.array([80., 90.]), total_received_mortgages=[170.]))
    b = NS(ts=TimeSeries(new_loans_fraction_firms=np.zeros(1), new_loans_fraction_hh_cons=np.zeros(1),
                         new_loans_fraction_mortgages=np.ones(1)))
    CreditMarket.cancel_unexecuted_mortgages(cm, h, b)
    np.testing.assert_array_equal(cm.states["mort_loans"][0, 0], [10, 110])
    np.testing.assert_array_equal(h.ts.current("received_mortgages"), [0, 90])
    assert cm.ts.current("total_newly_loans_granted_mortgages")[0] == 90
    assert "pending_writeoffs_by_bank" not in cm.states




@pytest.mark.parametrize("overdraft,service,expected", [(0.,0.,100.),(100.,0.,80.),(0.,4.,0.),(100.,3.,49.)])
def test_D4_consumer_screen_counts_overdraft_and_existing_service(overdraft,service,expected):
    p=BankParameters(household_consumption_loans_loan_to_income_ratio=4.5,household_income_periods_per_year=4,
        mortgage_use_property_collateral=True,mortgage_debt_service_to_income_ratio=.4,household_consumption_loan_maturity=49)
    b=NS(parameters=p,ts=TimeSeries(n_banks=1,equity=np.array([100.]),total_outstanding_loans=np.zeros(1),
        interest_rates_on_household_consumption_loans=np.zeros(1)))
    h=NS(states={"credit_existing_service":np.array([service])},ts=TimeSeries(income=np.array([10.]),debt=np.zeros(1),
        wealth_deposits=np.array([-overdraft]),target_consumption_loans=np.array([100.])))
    h.ts.income.append(np.array([10.]))
    clearer=WaterBucketCreditMarketClearer(allow_short_term_firm_loans=True,allow_household_loans=True,
        firms_max_number_of_banks_visiting=1,households_max_number_of_banks_visiting=1,consider_loan_type_fractions=False,
        credit_supply_temperature=0,interest_rates_selection_temperature=0,creditor_selection_is_deterministic=True,
        creditor_minimum_fill=False,debtor_minimum_fill=False)
    loans=clearer.clear_loans(b,None,h,LoanTypes.HOUSEHOLD_CONSUMPTION_LOAN,np.zeros(1),np.zeros(1),np.zeros(1),np.array([1000.]))
    assert loans[0].sum()==pytest.approx(expected)


def test_D4_service_adds_overdraft_interest_and_caps_final_installment():
    from macromodel.country.household_closure import prepare_household_credit
    h=NS(states={"Corresponding Bank ID":np.array([0])},ts=TimeSeries(wealth_deposits=np.array([-100.])))
    b=NS(ts=TimeSeries(overdraft_rate_on_household_deposits=np.array([.02])))
    cm=NS(states={"cons_loans":np.array([[[2.]],[[.5]],[[10.]]]),"mort_loans":np.zeros((3,1,1))})
    prepare_household_credit(NS(households=h,banks=b,credit_market=cm))
    assert h.states["credit_existing_service"][0]==pytest.approx(4.5)
