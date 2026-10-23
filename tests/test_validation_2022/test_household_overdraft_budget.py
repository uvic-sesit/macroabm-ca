from types import SimpleNamespace as NS

import numpy as np
import pytest

from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration
from macromodel.country.household_closure import cap_household_goods_budget
from macromodel.timeseries import TimeSeries


def test_zero_unused_capacity_reserves_senior_payments_and_scales_goods_proportionally():
    C = np.array([[40., 20.], [50., 10.], [10., 10.]])
    I = np.array([[10., 10.], [5., 5.], [0., 0.]])
    h = NS(states={}, ts=TimeSeries(target_consumption=C, target_investment=I,
        wealth_deposits=np.array([100., 10., -5.]), received_consumption_loans=np.zeros(3),
        received_mortgages=np.zeros(3), property_sale_proceeds=np.zeros(3),
        debt_installments=np.array([20., 20., 1.]), rent=np.array([10., 5., 0.]),
        interest_paid=np.array([2., 1., 1.]), price_paid_for_property=np.zeros(3)))
    c = NS(households=h, central_government=NS(states={'Value-added Tax': .1, 'Capital Formation Tax': .2}))
    cap_household_goods_budget(c)
    factor = 68 / (66 + 24)
    np.testing.assert_allclose(h.ts.current('target_consumption')[0], C[0] * factor)
    np.testing.assert_allclose(h.ts.current('target_investment')[0], I[0] * factor)
    np.testing.assert_array_equal(h.ts.current('target_consumption')[1:], 0.)
    np.testing.assert_allclose(h.states['overdraft_senior_shortfall_before_receipts'], [0., 16., 7.])
    assert h.states['overdraft_consumption_cut'][0] == pytest.approx(66 * (1 - factor))
    np.testing.assert_array_equal(h.ts.current('wealth_deposits'), [100., 10., -5.])
    assert HouseholdClosureConfiguration().overdraft_limit_enabled is False
