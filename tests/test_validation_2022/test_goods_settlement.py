"""D6: goods-market payments settled at the sellers' realised prices (validation-2022)."""
from types import SimpleNamespace

import numpy as np
import pytest

from macromodel.markets.goods_market.func.settlement import bilateral_flows, settle_at_seller_prices

COUNTRIES = ["A", "B"]


def _seller(prices, industries, sold_to):
    s = {"Prices": np.array(prices, float), "Industries": np.array(industries), "Real Amount sold": sum(sold_to.values())}
    for c in COUNTRIES:
        s["Real Amount sold to " + c] = np.array(sold_to.get(c, np.zeros(len(prices))), float)
    return SimpleNamespace(transactor_seller_states=s, transactor_buyer_states={})


def _buyer(spent_from, bought_from, n_ind=2):
    b = {}
    for c in COUNTRIES:
        b["Nominal Amount spent on Goods from " + c] = np.array(spent_from.get(c, np.zeros((1, n_ind))), float)
        b["Real Amount bought from " + c] = np.array(bought_from.get(c, np.zeros((1, n_ind))), float)
    b["Nominal Amount spent"] = sum(b["Nominal Amount spent on Goods from " + c] for c in COUNTRIES)
    b["Real Amount bought"] = sum(b["Real Amount bought from " + c] for c in COUNTRIES)
    return SimpleNamespace(transactor_seller_states={}, transactor_buyer_states=b)


def _market():
    # country A: two industry-0 firms with prices 1.0 and 2.0 selling 3 and 1 units to A and 0 / 1 to B;
    # buyers pay the supply-weighted average price (1.25 for A, as the clearer does), real allocation fixed.
    firms_a = _seller([1.0, 2.0], [0, 0], {"A": np.array([3.0, 1.0]), "B": np.array([0.0, 1.0])})
    hh_a = _buyer({"A": [[5.0, 0.0]]}, {"A": [[4.0, 0.0]]})
    gov_b = _buyer({"A": [[1.25, 0.0]]}, {"A": [[1.0, 0.0]]})
    return {"A": [firms_a, hh_a], "B": [gov_b]}, hh_a, gov_b


def test_payments_equal_seller_receipts_after_settlement():
    m, hh_a, gov_b = _market()
    before = bilateral_flows(m, 2)
    assert before[("A", "A")]["payments"][0] == pytest.approx(5.0)
    assert before[("A", "A")]["receipts"][0] == pytest.approx(3.0 * 1.0 + 1.0 * 2.0)
    diag = settle_at_seller_prices(m, 2)
    after = bilateral_flows(m, 2)
    for f in after.values():
        np.testing.assert_allclose(f["payments"], f["receipts"])
    assert diag["payments_minus_receipts_before"] == pytest.approx((5.0 - 5.0) + (1.25 - 2.0))
    assert gov_b.transactor_buyer_states["Nominal Amount spent"][0, 0] == pytest.approx(2.0)


def test_settlement_keeps_real_allocation():
    m, hh_a, gov_b = _market()
    real = {id(b): b.transactor_buyer_states["Real Amount bought from A"].copy() for b in (hh_a, gov_b)}
    settle_at_seller_prices(m, 2)
    for b in (hh_a, gov_b):
        np.testing.assert_array_equal(b.transactor_buyer_states["Real Amount bought from A"], real[id(b)])


def test_payment_split_across_buyers_is_proportional():
    m, hh_a, _ = _market()
    hh2 = _buyer({"A": [[2.5, 0.0]]}, {"A": [[2.0, 0.0]]})
    m["A"].append(hh2)  # A buyers now pay 7.5 for goods sold for 5.0
    settle_at_seller_prices(m, 2)
    a1 = hh_a.transactor_buyer_states["Nominal Amount spent"][0, 0]
    a2 = hh2.transactor_buyer_states["Nominal Amount spent"][0, 0]
    assert a1 + a2 == pytest.approx(5.0)
    assert a1 / a2 == pytest.approx(2.0)


def test_negative_household_investment_weights_are_removed():
    from macromodel.agents.households.households import nonnegative_weights
    w = nonnegative_weights(np.array([0.5, -0.01, 0.51]))
    assert (w >= 0).all() and w.sum() == pytest.approx(1.0)
    assert w[0] / w[2] == pytest.approx(0.5 / 0.51)


def test_settlement_reports_negative_buyer_spending():
    m, hh_a, _ = _market()
    hh_a.transactor_buyer_states["Nominal Amount spent"][0, 1] = -0.3
    assert settle_at_seller_prices(m, 2)["negative_buyer_spending"] == pytest.approx(-0.3)
