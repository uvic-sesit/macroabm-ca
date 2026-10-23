"""Opt-in household validation components, installed on fresh simulations."""
from copy import deepcopy
import numpy as np


def prepare_household_credit(country):
    cm = country.credit_market
    country.households.states["credit_existing_service"] = sum(
        cm.states[k][1:].sum(axis=(0, 1)) for k in ("cons_loans", "mort_loans"))


def shares(x):
    x = np.maximum(0.0, np.asarray(x, float))
    return x / x.sum() if x.sum() else np.full(x.shape, 1 / x.size)


def add_series(agent, key, initial):
    agent.ts.dicts[key] = [np.asarray(initial, float).copy()]


def put(agent, key, value):
    agent.ts.dicts[key][-1] = np.asarray(value, float).copy()


class HouseholdClosure:
    def __init__(self, country, config, national_income_share):
        self.c, self.cfg = country, config
        h, f, b, g = country.households, country.firms, country.banks, country.central_government
        self.annual_share = national_income_share
        private = ~np.isin(np.asarray(f.states["Industry"], int), [44,45,46,49])
        output = f.ts.current("production") * f.ts.current("price") * private
        self.private_payers = private
        self.firm_weights = shares(output)
        self.mixed_payer_weights = shares(output * (f.states["Industry"] != 41))
        self.mixed_weights = shares(h.states["self_employment_business_value"])
        self.equity_weights = shares(h.states["distribution_equity_value"])
        self.transfer_weights = shares(h.states["distribution_pension_value"])
        profits = (np.maximum(0,f.ts.current("profits"))*private).sum() + np.maximum(0,b.ts.current("profits")).sum()
        capacity = profits * (1-g.states["Profit Tax"])
        target = config.dividends_by_region[str(country.country_name)] / config.periods_per_year
        self.required_payout_ratio = target/capacity if capacity>0 else float("inf")
        self.payout_ratio = min(1., self.required_payout_ratio)
        self.benchmark_shortfall = max(0.,target-capacity)
        # Above-100% targets are reported as infeasible, never silently fitted.
        h.states["coefficient_fa_income"] = 0.
        country.individuals.states["Dividend Payout Ratio"] = 0.
        for k in ("income_mixed","income_dividends","income_corporate_transfers","taxes_distributions"):
            add_series(h,k,np.zeros(h.ts.current("n_households")))
        add_series(f,"household_distributions",np.zeros_like(f.ts.current("deposits")))
        add_series(f,"household_distribution_requests",np.zeros((3,len(f.ts.current("deposits")))))
        add_series(b,"household_dividends",np.zeros_like(b.ts.current("equity")))
        add_series(g,"taxes_household_distributions",[0.])
        self.plan_payments()

    def plan_payments(self):
        c, cfg = self.c, self.cfg
        h, f, b, g = c.households, c.firms, c.banks, c.central_government
        tax = g.states["Income Tax"]
        cpi = c.economy.ts.current("cpi")[0] / c.economy.ts.initial("cpi")[0]
        scale = self.annual_share * cpi / cfg.periods_per_year
        mixed = cfg.nonrental_mixed_income * scale
        transfers = cfg.corporate_transfers * scale
        profits = np.maximum(0, f.ts.current("profits")) * (1 - g.states["Profit Tax"])
        div = self.payout_ratio * profits * self.private_payers
        requests = np.stack([mixed * self.mixed_payer_weights, transfers * self.firm_weights, div])
        self.requested_firm_payments = requests.copy()
        # Liquidity cap prevents payouts creating a firm overdraft. It applies to
        # each payer, not just the aggregate; missed payouts are reported.
        requested = requests.sum(axis=0)
        capacity = np.maximum(0, f.ts.current("deposits"))
        factor = np.minimum(1, np.divide(capacity, requested, out=np.ones_like(requested), where=requested > 0))
        self.firm_requests = requests * factor
        bank_profit = np.maximum(0, b.ts.current("profits")) * (1 - g.states["Profit Tax"])
        buffer = np.maximum(0, b.ts.current("equity")
                            - b.parameters.capital_adequacy_ratio * b.ts.current("total_outstanding_loans"))
        self.bank_payout = np.minimum(self.payout_ratio * bank_profit, buffer)
        self.planned_mixed = (1 - tax) * self.firm_requests[0].sum() * self.mixed_weights
        self.planned_transfers = (1 - tax) * self.firm_requests[1].sum() * self.transfer_weights
        self.planned_dividends = (1 - tax) * (self.firm_requests[2].sum() + self.bank_payout.sum()) * self.equity_weights

    def expected_income(self):
        self.plan_payments()
        h = self.c.households
        cm = self.c.credit_market
        h.states["credit_existing_service"] = sum(
            cm.states[k][1:].sum(axis=(0, 1)) for k in ("cons_loans", "mort_loans"))
        # The default wage is already after tax. Do not tax it a second time.
        put(h, "expected_income_financial_assets", np.zeros_like(self.planned_mixed))
        put(h, "expected_income", h.compute_expected_income()
            + self.planned_mixed + self.planned_dividends + self.planned_transfers)

    def firm_payments(self):
        f = self.c.firms
        requested = self.firm_requests.sum(axis=0)
        available = np.maximum(0, f.ts.current("deposits"))
        factor = np.minimum(1, np.divide(available, requested, out=np.ones_like(requested), where=requested > 0))
        self.actual_firm_payments = self.firm_requests * factor
        f.ts.household_distribution_requests.append(self.requested_firm_payments.copy())
        paid = self.actual_firm_payments.sum(axis=0)
        # The mixed-income portion belongs to unincorporated owners, rather
        # than the corporation-tax base of the representative industry firm.
        self.corporate_tax_rebate = np.minimum(
            f.ts.current("corporate_taxes_paid"),
            self.c.central_government.states["Profit Tax"] * self.actual_firm_payments[0])
        put(f, "corporate_taxes_paid", f.ts.current("corporate_taxes_paid") - self.corporate_tax_rebate)
        f.ts.household_distributions.append(paid)
        put(f, "deposits", f.ts.current("deposits") - paid + self.corporate_tax_rebate)

    def realised_income(self):
        c = self.c
        h, g = c.households, c.central_government
        tax = g.states["Income Tax"]
        mixed, transfers, div = self.actual_firm_payments.sum(axis=1)
        gross = [mixed * self.mixed_weights,
                 (div + self.bank_payout.sum()) * self.equity_weights,
                 transfers * self.transfer_weights]
        for k, value in zip(("income_mixed", "income_dividends", "income_corporate_transfers"), gross):
            h.ts.dicts[k].append((1 - tax) * value)
        h.ts.taxes_distributions.append(tax * sum(gross))
        put(h, "income_financial_assets", np.zeros_like(gross[0]))
        put(h, "total_income_financial_assets", [0.0])
        put(h, "income", h.compute_income() + (1 - tax) * sum(gross))
    def bank_payments(self):
        b = self.c.banks
        b.ts.household_dividends.append(self.bank_payout.copy())
        put(b, "equity", b.ts.current("equity") - self.bank_payout)

    def distribution_taxes(self):
        h, g = self.c.households, self.c.central_government
        value = h.ts.current("taxes_distributions").sum()
        g.ts.taxes_household_distributions.append([value])
        put(g, "taxes_income", g.ts.current("taxes_income") + value)
        put(g, "taxes_corporate_income", g.ts.current("taxes_corporate_income") - self.corporate_tax_rebate.sum())


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

    enabled = [c for c in countries.values() if c.configuration.household_closure.income_enabled]
    national_income = sum(np.maximum(0,c.households.ts.current("income")).sum() for c in countries.values() if str(c.country_name).startswith("CAN"))
    for c in enabled:
        weight = np.maximum(0,c.households.ts.current("income")).sum()/national_income
        c.household_closure = HouseholdClosure(c,c.configuration.household_closure,weight)
