"""Phase A batches 2-4: transaction accounting fixes (validation-2022). Small stubs, no pickle."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from macromodel.agents.central_government.central_government import CentralGovernment
from macromodel.agents.firms.firms import Firms
from macromodel.agents.households.func.property import DefaultHouseholdDemandForProperty
from macromodel.agents.households.households import income_weighted_saving_rate
from macromodel.agents.individuals.func.income import DefaultIncomeSetter
from macromodel.agents.individuals.individual_properties import ActivityStatus
from macromodel.markets.housing_market.func.clearing import AutomaticHousingMarketClearer
from macromodel.markets.housing_market.housing_market import HousingMarket
from macromodel.timeseries import TimeSeries


# ---------------------------------------------------------------- A2: labour taxes on the gross base
def _gov(tau_inc=0.17, tau_ee=0.016, tau_er=0.15):
    states = {
        "Income Tax": tau_inc,
        "Employee Social Insurance Tax": tau_ee,
        "Employer Social Insurance Tax": tau_er,
        "Value-added Tax": 0.0,
        "Capital Formation Tax": 0.0,
        "Profit Tax": 0.0,
        "Export Tax": 0.0,
    }
    keys = ["taxes_production", "taxes_vat", "taxes_cf", "taxes_corporate_income", "taxes_exports",
            "gross_wages", "taxes_income", "taxes_rental_income", "taxes_employer_si", "taxes_employee_si"]
    return SimpleNamespace(states=states, ts=TimeSeries(**{k: [0.0] for k in keys}))


@pytest.mark.parametrize("cpi", [1.0, 1.15])
def test_firm_wage_bill_splits_exactly_into_net_wage_pit_and_ssc(cpi):
    g = _gov()
    w = np.array([10.0, 20.0, 5.0])  # real net wages of employed individuals
    act = np.array([ActivityStatus.EMPLOYED] * 3)
    CentralGovernment.compute_taxes(
        g, current_ind_employee_income=w, current_total_rent_paid=0.0,
        current_income_financial_assets=np.zeros(1), current_ind_activity=act,
        current_ind_realised_cons=np.zeros(1), current_bank_profits=np.zeros(1),
        current_firm_production=np.zeros(1), current_firm_price=np.zeros(1), current_firm_profits=np.zeros(1),
        current_firm_industries=np.zeros(1, dtype=int), current_household_new_real_wealth=np.zeros((1, 1)),
        taxes_less_subsidies_rates=np.zeros(1), current_total_exports=0.0, cpi=cpi,
    )
    s = g.states
    theta = (1 + s["Employer Social Insurance Tax"]) / (
        (1 - s["Employee Social Insurance Tax"]) * (1 - s["Income Tax"]))
    firm_wage_bill = cpi * theta * w.sum()  # Firms.update_total_wages_paid
    received = cpi * w.sum()  # household nominal net wage (country.py)
    booked = g.ts.current("taxes_income")[0] + g.ts.current("taxes_employee_si")[0] + g.ts.current("taxes_employer_si")[0]
    assert received + booked == pytest.approx(firm_wage_bill, rel=1e-12)


# ---------------------------------------------------------------- A3/E2: UB nominal, received
def test_unemployment_benefits_enter_income_without_cpi_or_inflation_factor():
    setter = DefaultIncomeSetter()
    act = np.array([ActivityStatus.UNEMPLOYED, ActivityStatus.EMPLOYED], dtype=object)  # as in the model
    ub = np.array([300.0, 0.0])
    common = dict(current_individual_activity_status=act, current_wage=np.array([0.0, 100.0]),
                  individual_social_benefits=ub, corr_invested_firms=np.zeros(2, dtype=int), corr_invested_banks=np.zeros(2, dtype=int),
                  dividend_payout_ratio=0.0, income_taxes=0.0, tau_firm=0.0)
    realised = setter.compute_income(firm_profits=np.zeros(1), bank_profits=np.zeros(1), cpi=1.2, **common)
    expected = setter.compute_expected_income(expected_firm_profits=np.zeros(1), expected_bank_profits=np.zeros(1),
                                              cpi=1.2, expected_inflation=0.05, **common)
    assert realised[0] == pytest.approx(300.0)
    assert expected[0] == pytest.approx(300.0)
    assert realised[1] == pytest.approx(120.0)  # wage: cpi * w
    assert expected[1] == pytest.approx(1.05 * 120.0)


def test_household_income_includes_unemployment_benefits():
    from macromodel.agents.households.households import Households
    hh = SimpleNamespace(ts=TimeSeries(income_employee=np.array([1.0, 2.0]),
                                       income_unemployment_benefits=np.array([0.5, 0.0]),
                                       income_social_transfers=np.array([0.1, 0.1]),
                                       income_rental=np.array([0.0, 0.3]),
                                       income_financial_assets=np.array([0.2, 0.0])))
    np.testing.assert_allclose(Households.compute_income(hh), [1.8, 2.4])


# ---------------------------------------------------------------- A10: firm deposits on a cash basis
def test_firm_deposits_debit_purchases_not_input_use():
    ts = TimeSeries(
        deposits=np.array([100.0]), nominal_amount_sold_in_lcu=np.array([50.0]), total_wage=np.array([20.0]),
        nominal_amount_spent_in_lcu=np.array([[7.0, 3.0]]), used_intermediate_inputs_costs=np.array([999.0]),
        used_capital_inputs_costs=np.array([999.0]), taxes_paid_on_production=np.array([1.0]),
        corporate_taxes_paid=np.array([2.0]), interest_paid=np.array([0.5]), itc_refunds=np.array([0.0]),
        received_credit=np.array([4.0]), debt_installments=np.array([1.5]),
    )
    out = Firms.compute_deposits(SimpleNamespace(ts=ts))
    assert out[0] == pytest.approx(100 + 50 - 20 - 10 - 1 - 2 - 0.5 + 4 - 1.5)


# ---------------------------------------------------------------- I-7
def test_income_weighted_saving_rate_reproduces_aggregate_consumption():
    s = np.array([0.5, 0.0, 0.1]); y = np.array([100.0, 10.0, 50.0])
    s_bar = income_weighted_saving_rate(s, y)
    assert ((1 - s_bar) * y.sum()) == pytest.approx(((1 - s) * y).sum())


# ---------------------------------------------------------------- housing: tenure codes
def test_property_demand_uses_model_tenure_codes():
    np.random.seed(0)
    rule = DefaultHouseholdDemandForProperty(
        probability_stay_in_rented_property=0.0, maximum_price_income_coefficient=5.0,
        maximum_price_income_exponent=1.0, maximum_price_noise_mean=0.0, maximum_price_noise_variance=0.0,
        psychological_pressure_of_renting=0.1, cost_comparison_temperature=1.0,
        maximum_rent_income_coefficient=0.2, maximum_rent_income_exponent=0.0,
        probability_stay_in_owned_property=0.0, price_initial_markup=0.0, price_decrease_probability=0.0,
        price_decrease_mean=0.0, price_decrease_variance=0.0, rent_initial_markup=0.0,
        rent_decrease_probability=0.0, rent_decrease_mean=0.0, rent_decrease_variance=0.0,
        partial_rent_inflation_indexation=0.0, partial_rent_inflation_delay=1,
    )
    tenure = np.array([1, 2, 3, 4, -1])
    max_price, max_rent, hoping = rule.compute_demand(
        housing_data=pd.DataFrame(), household_residence_tenure_status=tenure,
        household_income=np.full(5, 100.0), household_financial_wealth=np.zeros(5),
        observed_fraction_value_price=np.array([1.0, 0.0]), observed_fraction_rent_value=np.array([0.01, 0.0]),
        expected_hpi_growth=0.0, assumed_mortgage_maturity=120, rental_income_taxes=0.0,
    )
    # every household re-decides (stay probabilities 0): renters (3) and all owner codes take part
    decided = ~np.isnan(max_price) | ~np.isnan(max_rent)
    assert decided.all()
    assert list(hoping) == [0, 1, 3]  # ids of owners (codes 1, 2, 4) hoping to move


# ---------------------------------------------------------------- housing: feasible matching
def test_matching_is_feasible_and_excludes_own_property():
    np.random.seed(0)
    clearer = AutomaticHousingMarketClearer(random_assignment_shock_variance=0.0)
    housing = pd.DataFrame({
        "Value": [100.0, 200.0, 300.0], "Sale Price": [100.0, 200.0, 300.0],
        "Temporarily for Sale": [True, True, True], "Corresponding Owner Household ID": [0, 5, 6],
    })
    wtp = np.array([150.0, np.nan, 120.0, 50.0])  # hh0 owns property 0
    out = clearer.perform_matching(housing, np.zeros(4), wtp, is_rental_market=False)
    for _, r in out.iterrows():
        assert wtp[int(r.buyer_id)] >= r.price_or_rent
        assert int(r.buyer_id) != int(r.seller_id)
    assert 3 not in out.buyer_id.values  # cannot afford anything


# ---------------------------------------------------------------- A8: execution of sales
def _market(sales):
    props = pd.DataFrame({
        "Corresponding Owner Household ID": [0, 1, 9],
        "Corresponding Inhabitant Household ID": [0, 1, -1],
        "Value": [100.0, 100.0, 80.0], "Is Owner-Occupied": [1, 1, 0],
    })
    keys = ["total_number_of_houses_rented", "total_number_of_houses_owner_occupied",
            "total_number_of_houses_unoccupied", "total_number_of_bought_houses", "total_number_of_newly_rented_houses"]
    return SimpleNamespace(states={"properties": props, "current_sales": sales}, ts=TimeSeries(**{k: [0] for k in keys}))


def _hh_states(n=10):
    return {"Corresponding Inhabited House ID": np.array([0, 1] + [-1] * (n - 2)),
            "Tenure Status of the Main Residence": np.array([1, 1] + [3] * (n - 2)),
            "Corresponding Property Owner": np.full(n, -1), "corr_renters": [[] for _ in range(n)]}


def test_sale_of_residence_requires_seller_to_move_and_buyer_to_pay():
    # hh2 buys hh0's home (hh0 does not move -> cancelled); hh3 buys hh1's home and hh1 rents property 2
    sales = pd.DataFrame({"sales_types": ["Sell", "Sell", "Rental"], "property_id": [0, 1, 2],
                          "property_value": [100.0, 100.0, 80.0], "price_or_rent": [100.0, 100.0, 1.0],
                          "seller_id": [0, 1, 9], "buyer_id": [2, 3, 1]})
    mkt = _market(sales); st = _hh_states()
    fw = np.full(10, 1000.0)
    HousingMarket.process_housing_market_clearing(mkt, st, np.zeros(10), fw)
    ex = mkt.states["current_sales"]["executed"].values
    assert list(ex) == [False, True, True]
    P = mkt.states["properties"]
    assert P.at[0, "Corresponding Inhabitant Household ID"] == 0  # hh0 still home
    assert P.at[1, "Corresponding Owner Household ID"] == 3 and P.at[1, "Corresponding Inhabitant Household ID"] == 3
    assert P.at[2, "Corresponding Inhabitant Household ID"] == 1 and st["Corresponding Inhabited House ID"][1] == 2
    occ = P["Corresponding Inhabitant Household ID"].values
    assert len(occ[occ >= 0]) == len(set(occ[occ >= 0]))  # no double occupancy


def test_unaffordable_purchase_is_not_executed():
    sales = pd.DataFrame({"sales_types": ["Sell"], "property_id": [2], "property_value": [80.0],
                          "price_or_rent": [80.0], "seller_id": [9], "buyer_id": [4]})
    mkt = _market(sales); st = _hh_states()
    HousingMarket.process_housing_market_clearing(mkt, st, np.zeros(10), np.zeros(10))
    assert not mkt.states["current_sales"]["executed"].values[0]


# ---------------------------------------------------------------- bank deposit interest = customers' payments
def test_bank_deposit_interest_equals_customer_payments_plus_cb_interest():
    from macromodel.agents.banks.banks import Banks
    ts = TimeSeries(deposits=np.array([50.0, -10.0]), deposits_from_firms=np.array([0.0, 0.0]),
                    deposits_from_households=np.array([0.0, 0.0]))
    bank = SimpleNamespace(ts=ts)
    # bank 0: one customer overdrawn (pays 3), one with deposits (receives 1) -> nets to zero balance at bank level
    out = Banks.compute_interest_received_on_deposits(
        bank, central_bank_policy_rate=0.01,
        firm_interest_paid_on_deposits=np.array([3.0, -1.0]), firm_corresponding_bank=np.array([0, 0]),
        household_interest_paid_on_deposits=np.array([0.5]), households_corresponding_bank=np.array([1]),
    )
    np.testing.assert_allclose(out, [0.01 * 50 + 2.0, -0.01 * 10 + 0.5])


# ---------------------------------------------------------------- A14: write-offs are losses of the lending bank
def test_household_writeoff_is_queued_by_lending_bank_and_charged_to_equity():
    from macromodel.agents.banks.banks import Banks
    from macromodel.markets.credit_market.credit_market import CreditMarket
    # loans arrays: (fields, banks, borrowers); field 0 = principal
    cons = np.zeros((3, 2, 3)); mort = np.zeros((3, 2, 3))
    cons[0, 0, 1] = 10.0; mort[0, 1, 1] = 100.0; mort[0, 1, 2] = 50.0
    cm = SimpleNamespace(states={"cons_loans": cons, "mort_loans": mort})
    cm._record_writeoff = lambda amount, by_bank=None: CreditMarket._record_writeoff(cm, amount, by_bank)
    c, m_ = CreditMarket.remove_loans_to_households(cm, np.array([1]))
    assert (c, m_) == (10.0, 100.0)
    assert mort[0, 1, 2] == 50.0  # other borrowers untouched
    losses = CreditMarket.pop_pending_writeoffs_by_bank(cm, 2)
    np.testing.assert_allclose(losses, [10.0, 100.0])
    np.testing.assert_allclose(CreditMarket.pop_pending_writeoffs_by_bank(cm, 2), [0.0, 0.0])  # queue reset
    bank = SimpleNamespace(ts=TimeSeries(equity=np.array([500.0, 500.0]), profits=np.array([20.0, -5.0])))
    eq = Banks.compute_equity(bank, profit_taxes=0.25, loan_losses=losses)
    np.testing.assert_allclose(eq, [500 + 20 - 5 - 10, 500 - 5 - 100])


def test_firm_writeoff_is_queued_by_lending_bank():
    from macromodel.markets.credit_market.credit_market import CreditMarket
    st = np.zeros((3, 2, 4)); lt = np.zeros((3, 2, 4))
    st[0, 0, 2] = 3.0; lt[0, 1, 2] = 7.0; lt[0, 1, 3] = 9.0
    cm = SimpleNamespace(states={"st_loans": st, "lt_loans": lt})
    cm._record_writeoff = lambda amount, by_bank=None: CreditMarket._record_writeoff(cm, amount, by_bank)
    assert CreditMarket.remove_loans_to_firm(cm, 2) == pytest.approx(10.0)
    np.testing.assert_allclose(CreditMarket.pop_pending_writeoffs_by_bank(cm, 2), [3.0, 7.0])
    assert cm.states["cumulative_writeoffs"] == pytest.approx(10.0)
