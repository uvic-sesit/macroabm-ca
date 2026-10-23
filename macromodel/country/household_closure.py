"""Opt-in household validation components, installed on fresh simulations."""
from copy import deepcopy
import numpy as np


def offset_private_rent(country, industry=41):
    """Remove only renters' duplicated L purchases, on the cash/VAT boundary.

    A household's residual L demand cannot be negative. Report rent exceeding
    that demand; do not shift the offset to other households or industries.
    """
    h = country.households
    properties = country.housing_market.states["properties"]
    rent = np.zeros(h.ts.current("n_households"))
    rented = properties[(properties["Is Owner-Occupied"] == 0)
                        & (properties["Corresponding Inhabitant Household ID"] >= 0)
                        & (properties["Corresponding Owner Household ID"] >= 0)]
    np.add.at(rent, rented["Corresponding Inhabitant Household ID"].to_numpy(int), rented["Rent"].to_numpy(float))
    rent = np.minimum(rent, h.ts.current("rent"))
    vat = country.central_government.states["Value-added Tax"]
    target = h.ts.current("target_consumption").copy()
    offset = np.minimum(np.maximum(0,target[:,industry]), rent/(1+vat))
    target[:,industry] -= offset
    h.ts.dicts["target_consumption"][-1] = target
    h.states["rent_L_offset_cash"] = offset*(1+vat)
    h.states["rent_L_unoffset_cash"] = rent-offset*(1+vat)


def prepare_household_credit(country):
    cm = country.credit_market
    h, b = country.households, country.banks
    scheduled = sum((cm.states[k][1] + np.minimum(cm.states[k][0],cm.states[k][2])).sum(axis=0)
                    for k in ("cons_loans", "mort_loans"))
    overdraft = np.maximum(0., -h.ts.current("wealth_deposits"))
    overdraft_interest = overdraft * b.ts.current("overdraft_rate_on_household_deposits")[h.states["Corresponding Bank ID"]]
    h.states["credit_existing_service"] = scheduled + overdraft_interest


def shares(x):
    x = np.maximum(0.0, np.asarray(x, float))
    return x / x.sum() if x.sum() else np.full(x.shape, 1 / x.size)


def add_series(agent, key, initial):
    agent.ts.dicts[key] = [np.asarray(initial, float).copy()]


def put(agent, key, value):
    agent.ts.dicts[key][-1] = np.asarray(value, float).copy()


def known_household_receipts(country):
    """Current net receipts, using settled labour/housing and declared D2 cash.

    Keep stock histories untouched: these are settlement memos, credited once
    by the normal end-quarter wealth update. D2 distributions are irrevocably
    declared from the existing opening-cash cap before goods clearing.
    """
    h, g, ind = country.households, country.central_government, country.individuals
    cpi = country.economy.ts.current('cpi')[0]
    # Nominal payroll/transfer declarations precede the purchase-dependent CPI.
    # Use this same index for the firm's wage debit and government withholding.
    h.states['budget_settlement_cpi'] = float(cpi)
    wages = h.compute_employee_income(cpi * ind.ts.current('employee_income'),
                                      ind.states['Corresponding Household ID'])
    benefits = h.compute_employee_income(ind.ts.current('income_from_unemployment_benefits'),
                                         ind.states['Corresponding Household ID'])
    transfers = h.compute_social_transfer_income(g.ts.current('total_other_benefits')[0], cpi)
    rent = h.compute_rental_income(country.housing_market.states['properties'], g.states['Income Tax'])
    closure = getattr(country, 'household_closure', None)
    if closure is not None:
        closure.commit_before_goods()
        distributions = closure.planned_mixed + closure.planned_dividends + closure.planned_transfers
        financial = np.zeros_like(wages)
    else:
        distributions = np.zeros_like(wages)
        financial = h.compute_income_from_financial_assets()
    components = dict(wages=wages, benefits=benefits, transfers=transfers,
                      rental=rent, distributions=distributions, financial=financial)
    h.states['budget_receipt_components'] = {k: np.asarray(v, float).copy() for k,v in components.items()}
    return sum(components.values())


def reserve_senior_cash(deposits, other_assets, projected_cash):
    """Do not invest cash already reserved for taxes and contractual payments."""
    redirect = np.minimum(np.maximum(0., other_assets), np.maximum(0., -projected_cash))
    return deposits + redirect, other_assets - redirect, redirect


def liquidatable_household_assets(h):
    """Existing OFA excluding the pension component, in model stock units."""
    return np.maximum(0., h.ts.current('wealth_other_financial_assets')
                      - np.maximum(0., h.states['protected_pension_assets']))


def needed_asset_liquidation(cash_after_payments, available):
    """Cash first; liquidate only existing non-pension assets needed to settle."""
    return np.minimum(np.maximum(0., -cash_after_payments), np.maximum(0., available))


def cap_household_goods_budget(country, net_receipts=None):
    """Zero-unobserved-capacity proxy approved for the main D diagnostic arm.

    Include current net wages, transfers, rent and funded declared D2 receipts,
    plus committed new loans and executed house-sale receipts. Do not use
    underwriting headroom or an additional credit-capacity parameter.
    Reserve senior payments first; scale every good and investment by one
    household factor, including consumption VAT and capital-formation tax.
    """
    h, g = country.households, country.central_government
    C = h.ts.current('target_consumption').copy()
    I = h.ts.current('target_investment').copy()
    vat = g.states['Value-added Tax']
    cf = g.states['Capital Formation Tax']
    if net_receipts is None:
        net_receipts = known_household_receipts(country)
    h.states['budget_net_receipts'] = np.asarray(net_receipts, float).copy()
    cash = (h.ts.current('wealth_deposits') + h.ts.current('received_consumption_loans')
            + h.ts.current('received_mortgages') + h.ts.current('property_sale_proceeds') + net_receipts)
    senior = (h.ts.current('debt_installments') + h.ts.current('rent')
              + h.ts.current('interest_paid') + h.ts.current('price_paid_for_property'))
    if not np.all(np.isfinite(cash)) or not np.all(np.isfinite(senior)):
        raise ValueError('Household cash budget requires finite settled cash and senior payments')
    resources = cash - senior
    planned = (1 + vat) * C.sum(axis=1) + (1 + cf) * I.sum(axis=1)
    if h.states.get('financial_asset_drawdown', False):
        available = liquidatable_household_assets(h)
        h.states['budget_available_nonpension_assets'] = available.copy()
        h.states['budget_planned_asset_liquidation'] = needed_asset_liquidation(resources - planned, available)
        resources = resources + available
    factor = np.minimum(1., np.divide(np.maximum(0., resources), planned,
                                     out=np.ones_like(planned), where=planned > 0))
    h.states['overdraft_unused_capacity'] = np.zeros_like(planned)
    h.states['overdraft_constrained'] = factor < 1 - 1e-12
    h.states['overdraft_consumption_cut'] = (1 + vat) * C.sum(axis=1) * (1 - factor)
    h.states['payment_distress_before_goods'] = np.maximum(0., -resources)
    put(h, 'target_consumption', C * factor[:, None])
    put(h, 'target_investment', I * factor[:, None])


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
        self.committed_firm_payments = None
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
        prepare_household_credit(self.c)
        # The default wage is already after tax. Do not tax it a second time.
        put(h, "expected_income_financial_assets", np.zeros_like(self.planned_mixed))
        put(h, "expected_income", h.compute_expected_income()
            + self.planned_mixed + self.planned_dividends + self.planned_transfers)

    def commit_before_goods(self):
        """Declare cash-funded D2 payments at the earlier settlement date.

        firm_requests already respects each payer's opening positive cash.
        Do not re-clip this irrevocable payment against cash after goods; that
        would budget a receipt that could disappear later in the same quarter.
        Book its cash debit, taxes and HH credit once through firm_payments and
        realised_income. Later operating deficits remain firm obligations.
        """
        self.committed_firm_payments = self.firm_requests.copy()

    def firm_payments(self):
        f = self.c.firms
        requested = self.firm_requests.sum(axis=0)
        available = np.maximum(0, f.ts.current("deposits"))
        factor = np.minimum(1, np.divide(available, requested, out=np.ones_like(requested), where=requested > 0))
        self.actual_firm_payments = (self.firm_requests * factor if self.committed_firm_payments is None
                                    else self.committed_firm_payments.copy())
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
        c.households.states["closure_deposit_only_saving"] = cfg.deposit_only_saving
        c.households.states['overdraft_limit_enabled'] = cfg.overdraft_limit_enabled
        c.households.states['financial_asset_drawdown'] = cfg.financial_asset_drawdown
        if cfg.distress_enabled:
            from macromodel.agents.households.func.insolvency import PersistentDistressHouseholdInsolvencyHandler
            c.households.functions["insolvency"] = PersistentDistressHouseholdInsolvencyHandler(cfg.distress_periods,cfg.collateral_haircut)
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
    recalibrate_d2_saving(enabled)


def recalibrate_d2_saving(countries):
    """Keep the existing income-weighted constant-propensity calibration.

    C=(1-s)Y at purchasers' prices; replace the income base by initial income
    without the unfunded financial-income proxy plus funded expected D2 flows.
    Preserve regional consumption shares; use the specified national benchmark.
    No fit to simulated outcomes, new income redistribution or new saving rule.
    """
    enabled = [c for c in countries if c.configuration.household_closure.recalibrate_saving_with_d2]
    if not enabled:
        return
    total_c = sum(c.households.ts.current('total_consumption')[0] for c in countries)
    for c in enabled:
        h, closure = c.households, c.household_closure
        cfg = c.configuration.household_closure
        initial_c = h.ts.current('total_consumption')[0]
        new_income = (h.ts.initial('income') - h.ts.initial('income_financial_assets')
                      + closure.planned_mixed + closure.planned_dividends + closure.planned_transfers)
        if not np.all(np.isfinite(new_income)) or new_income.sum() <= 0:
            raise ValueError('D2 saving calibration requires finite positive aggregate income')
        target = cfg.initial_annual_consumption_benchmark / cfg.periods_per_year * initial_c / total_c
        old = h.states['average_saving_rate']
        new = 1 - target / new_income.sum()
        h.states['saving_calibration'] = dict(old_propensity=old, new_propensity=new,
                                            old_income=float(h.ts.initial('income').sum()),
                                            d2_income=float(new_income.sum()), target=float(target))
        h.states['average_saving_rate'] = new
