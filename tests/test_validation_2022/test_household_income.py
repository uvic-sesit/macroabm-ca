from types import SimpleNamespace as NS
import numpy as np
import pytest
from macromodel.timeseries import TimeSeries
from macromodel.configurations.bank_configuration import BankParameters
from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration
from macromodel.country.household_closure import HouseholdClosure
def closure_fixture():
    h = NS(n_industries=3, consumption_weights=np.array([0.4, 0.2, 0.4]),
           use_consumption_weights_by_income=False, functions={}, states={"self_employment_business_value": np.array([10.,0.]), "distribution_equity_value":np.array([0.,10.]), "distribution_pension_value":np.array([10.,0.])},
           ts=TimeSeries(n_households=2, income=np.array([60., 40.]),
                         income_financial_assets=np.array([5., 5.]),
                         wealth_other_real_assets=np.array([10., 0.]),
                         wealth_other_financial_assets=np.array([0., 10.]), rent=np.array([0., 10.]),
                         consumption=np.array([40., 20.]), target_consumption=np.ones((2, 3)),
                         industry_consumption=np.array([24., 12., 24.]), total_consumption=[66.],
                         total_consumption_before_vat=[60.]))
    f = NS(states={"Industry": np.array([0, 2])}, ts=TimeSeries(production=np.array([100., 100.]), price=np.ones(2),
                         deposits=np.array([100., 100.]), profits=np.array([10., 10.]),
                         corporate_taxes_paid=np.array([2., 2.])))
    b = NS(parameters=BankParameters(), ts=TimeSeries(equity=np.array([100.]),
                                                      total_outstanding_loans=np.array([100.]), profits=np.array([10.])))
    g = NS(states={"Income Tax": 0.2, "Profit Tax": 0.2, "Value-added Tax": 0.1},
           ts=TimeSeries(taxes_income=[0.], taxes_corporate_income=[4.]))
    c = NS(country_name="CAN_ON", individuals=NS(states={}), households=h, firms=f, banks=b, central_government=g,
           economy=NS(ts=TimeSeries(cpi=[1.])), housing_services_in_household_io=True)
    cfg = HouseholdClosureConfiguration(dividends_by_region={"CAN_ON":24.}, nonrental_mixed_income=40,
                                         corporate_transfers=20)
    return c, HouseholdClosure(c, cfg, 1)


def test_distribution_income_is_funded_and_tax_is_withheld_exactly_once():
    c, closure = closure_fixture()
    h, f, b, g = c.households, c.firms, c.banks, c.central_government
    before = f.ts.current("deposits").copy()
    closure.firm_payments()
    h.ts.income_financial_assets.append(np.zeros(2))
    h.ts.dicts["total_income_financial_assets"] = [np.array([0.])]
    h.ts.dicts["rent_imputed"] = [np.array([12., 0.])]
    h.ts.dicts["interest_paid"] = [np.zeros(2)]
    h.ts.income.append(np.array([0., 0.]))
    h.compute_income = lambda: np.zeros(2)
    closure.realised_income()
    equity_before = b.ts.current("equity").copy()
    closure.bank_payments()
    closure.distribution_taxes()
    paid = ((before - f.ts.current("deposits")).sum() + closure.corporate_tax_rebate.sum()
            + (equity_before - b.ts.current("equity")).sum())
    received = h.ts.current("income").sum()
    tax = g.ts.current("taxes_household_distributions")[0]
    assert received + tax == pytest.approx(paid)
    assert tax == pytest.approx(0.2 * paid)
    assert g.ts.current("taxes_corporate_income")[0] == pytest.approx(f.ts.current("corporate_taxes_paid").sum())


def test_payouts_cannot_create_payer_overdraft():
    c, closure = closure_fixture()
    c.firms.ts.dicts["deposits"][-1] = np.array([0., 0.1])
    closure.firm_payments()
    assert np.all(c.firms.ts.current("deposits") >= -1e-12)
    assert c.firms.ts.current("household_distributions").sum() <= 0.1 + 1e-12



def test_payout_rate_matches_observed_receipts_without_changing_consumption():
    c,k=closure_fixture()
    assert k.payout_ratio == pytest.approx(.25)
    assert k.firm_requests[2].sum()+k.bank_payout.sum() == pytest.approx(6.)
    np.testing.assert_allclose(c.households.consumption_weights,[.4,.2,.4])
    assert c.housing_services_in_household_io
