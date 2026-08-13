from typing import Tuple

import numpy as np

from macromodel.agents.agent import Agent
from macromodel.markets.goods_market.value_type import ValueType
from macromodel.timeseries import TimeSeries


def create_test_transactor(
    country_name: str,
    buy_value_type: ValueType,
    sell_value_type: ValueType,
    buy_priority: int,
    sell_priority: int,
    n_transactors_buy: int,
    n_transactors_sell: int,
) -> Agent:
    return Agent(
        country_name=country_name,
        all_country_names=["FRA", "ROW"],
        n_industries=18,
        n_transactors_buy=n_transactors_buy,
        n_transactors_sell=n_transactors_sell,
        ts=TimeSeries(),
        states={},
        transactor_settings={
            "Buyer Value Type": buy_value_type,
            "Seller Value Type": sell_value_type,
            "Buyer Priority": buy_priority,
            "Seller Priority": sell_priority,
        },
    )


def create_test_transactors() -> Tuple[Agent, Agent, Agent]:
    # A few firms
    firms = create_test_transactor(
        country_name="FRA",
        buy_value_type=ValueType.REAL,
        sell_value_type=ValueType.REAL,
        buy_priority=1,
        sell_priority=1,
        n_transactors_buy=3,
        n_transactors_sell=3,
    )
    firms.set_goods_to_buy(np.array([[5.0, 2.0], [5.0, 3.0], [0.0, 0.0]]))
    firms.set_goods_to_sell(np.array([35.0, 5.0, 10.0]))
    firms.set_prices(np.array([1.0, 1.0, 2.0]))
    firms.ts["price_offered"] = np.array([1.0, 2.0])
    firms.set_seller_industries(np.array([0, 0, 1]))
    firms.set_maximum_excess_demand(np.array([np.inf, np.inf, np.inf]))
    firms.set_exchange_rate(1.0)

    # A few households
    households = create_test_transactor(
        country_name="FRA",
        buy_value_type=ValueType.NOMINAL,
        sell_value_type=ValueType.NONE,
        buy_priority=0,
        sell_priority=0,
        n_transactors_buy=3,
        n_transactors_sell=3,
    )
    households.set_goods_to_buy(np.array([[5.0, 5.0], [3.0, 2.0], [2.0, 3.0]]))
    households.set_goods_to_sell(np.array([0.0, 0.0, 0.0]))
    households.set_prices(np.array([0.0, 0.0, 0.0]))
    households.set_exchange_rate(1.0)

    # ROW
    row = create_test_transactor(
        country_name="ROW",
        buy_value_type=ValueType.NOMINAL,
        sell_value_type=ValueType.REAL,
        buy_priority=0,
        sell_priority=0,
        n_transactors_buy=1,
        n_transactors_sell=1,
    )
    row.set_goods_to_buy(np.array([[0.0, 0.0]]))
    row.set_goods_to_sell(np.array([0.0, 0.0]))
    row.set_prices(np.array([1.0, 2.0]))
    row.ts["price_offered"] = np.array([1.0, 2.0])
    row.set_seller_industries(np.array([0, 1]))
    row.set_maximum_excess_demand(np.array([np.inf, np.inf]))
    row.set_exchange_rate(1.0)

    return firms, households, row


def check_things_adding_up(firms: Agent, households: Agent) -> None:
    nominal_sold = firms.ts.current("nominal_amount_sold_in_lcu").sum()
    nominal_bought = (
        firms.ts.current("nominal_amount_spent_in_lcu").sum()
        + households.ts.current("nominal_amount_spent_in_lcu").sum()
    )
    assert np.isclose(nominal_sold, nominal_bought, atol=1e-1)


def check_excess_demand(firms: Agent, households: Agent) -> None:
    prices = np.array([1.0, 2.0])
    for g in [0, 1]:
        nominal_excess_demand = (
            prices[g] * firms.ts.current("real_excess_demand")[firms.transactor_seller_states["Industries"] == g].sum()
        )
        nominal_supply = prices[g] * (
            firms.transactor_seller_states["Initial Goods"][firms.transactor_seller_states["Industries"] == g].sum()
        )
        nominal_demand = (
            prices[g] * firms.transactor_buyer_states["Initial Goods"][:, g].sum()
            + households.transactor_buyer_states["Initial Goods"][:, g].sum()
        )
        if nominal_demand > nominal_supply:
            assert np.allclose(
                nominal_excess_demand,
                nominal_demand - nominal_supply,
                atol=1e-1,
            )
        else:
            assert np.allclose(nominal_excess_demand, 0.0, atol=1e-1)


class TestGoodsMarket:
    def test__transaction(self, test_goods_market):
        # Add agents
        firms, households, row = create_test_transactors()
        test_goods_market.n_industries = 2
        test_goods_market.goods_market_participants = {
            "FRA": [firms, households],
            "ROW": [row],
        }
        test_goods_market.functions["clearing"].consider_trade_proportions = False

        # Clear
        test_goods_market.prepare()
        test_goods_market.clear()
        test_goods_market.record()

        # Check basics
        check_things_adding_up(firms, households)
        check_excess_demand(firms, households)


def test_set_trade_proportions_diagonal_is_the_domestic_share(test_goods_market):
    """The (c, c) cell is country c's share of output kept AT HOME, not a trade share.

    Worth pinning down explicitly, because the obvious source for these matrices is an
    interchange dataset -- CER's interprovincial electricity flows, for one -- and an
    interchange matrix records only what CROSSES a border, so its diagonal is zero.
    Passing one straight in therefore reads as "this province keeps none of its own
    output", which is not what the dataset says and is not a small effect.
    """
    n_countries, n_industries, good = 3, 2, 1
    test_goods_market.states["origin_trade_proportions"] = np.full(
        (n_countries, n_countries, n_industries), 1.0 / n_countries
    )
    test_goods_market.states["destin_trade_proportions"] = np.full(
        (n_countries, n_countries, n_industries), 1.0 / n_countries
    )

    # Trade-only matrix: country 0 ships to 1, country 1 ships to 0, nobody "ships" to
    # themselves.
    flows = np.zeros((n_countries, n_countries))
    flows[0, 1] = flows[1, 0] = 1.0
    test_goods_market.set_trade_proportions(good, flows)

    origin = test_goods_market.states["origin_trade_proportions"]
    assert origin[0, 0, good] == 0.0
    assert origin[0, 1, good] == 1.0
    # Country 2 trades in neither direction, so it keeps whatever it had rather than
    # being barred from the market.
    assert origin[2, :, good].tolist() == [1 / 3, 1 / 3, 1 / 3]
    # Other goods are untouched.
    assert origin[0, 0, 0] == 1 / 3

    # Give the diagonal a weight and the domestic share comes back, proportionally.
    np.fill_diagonal(flows, 3.0)
    test_goods_market.set_trade_proportions(good, flows)
    origin = test_goods_market.states["origin_trade_proportions"]
    assert origin[0, 0, good] == 0.75
    assert origin[0, 1, good] == 0.25
    # Columns normalise independently: country 1's imports come 1/(1+3) from country 0.
    destin = test_goods_market.states["destin_trade_proportions"]
    assert destin[0, 1, good] == 0.25
    assert destin[1, 1, good] == 0.75
