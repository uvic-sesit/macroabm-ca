"""Opt-in household validation components, installed on fresh simulations."""
from copy import deepcopy


def prepare_household_credit(country):
    cm = country.credit_market
    country.households.states["credit_existing_service"] = sum(
        cm.states[k][1:].sum(axis=(0, 1)) for k in ("cons_loans", "mort_loans"))


def install_household_closures(countries):
    for c in countries.values():
        cfg = c.configuration.household_closure
        if not cfg.credit_enabled:
            continue
        c.banks.parameters = deepcopy(c.banks.parameters)
        p = c.banks.parameters
        p.household_income_periods_per_year = cfg.periods_per_year
        p.household_consumption_loans_loan_to_income_ratio = cfg.consumer_total_debt_to_annual_income
        p.mortgage_loan_to_income_ratio = cfg.mortgage_total_debt_to_annual_income
        p.mortgage_loan_to_value_ratio = cfg.mortgage_ltv
        p.mortgage_debt_service_to_income_ratio = cfg.debt_service_to_disposable_income
        p.mortgage_use_property_collateral = True
        p.household_consumption_loan_maturity = cfg.new_consumer_loan_maturity
        p.mortgage_maturity = cfg.new_mortgage_maturity
