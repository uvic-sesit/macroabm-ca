"""Unit tests for the order in which firms are served when hiring.

When total hiring demand exceeds the unemployed pool, the pool runs out partway
through, so the order firms are visited in decides which of them go short.
"""

import numpy as np

from macromodel.markets.labour_market.func.clearing import hiring

N_FIRMS = 6
WANTED_PER_FIRM = 10
CALLS = 200


def _hire(pool_size):
    """Call hiring with every firm in one industry wanting WANTED_PER_FIRM employees."""
    individuals_corresponding_firm = np.full(pool_size, -1, dtype=np.int64)

    _, _, new_hires = hiring(
        np.zeros(N_FIRMS, dtype=np.int64),
        np.zeros(pool_size, dtype=np.int64),
        individuals_corresponding_firm,
        np.ones(pool_size),
        np.ones(pool_size, dtype=np.bool_),
        np.full(N_FIRMS, float(WANTED_PER_FIRM)),
        np.zeros(N_FIRMS),
        np.zeros(pool_size),
        np.zeros(pool_size),
        np.zeros(pool_size),
        np.ones(1),
        1.0,
        0.0,
    )

    return np.array([len(new_hires[firm]) for firm in range(N_FIRMS)])


class TestHiringOrder:
    def test_the_shortfall_does_not_follow_the_firm_index(self):
        # A pool of 30 against demand of 60 leaves three firms short in every call.
        # In index order those are always firms 3, 4 and 5.
        times_short = np.zeros(N_FIRMS, dtype=int)
        for _ in range(CALLS):
            times_short += _hire(pool_size=30) < WANTED_PER_FIRM

        assert times_short.min() > 0, "a firm was served in every call"
        assert times_short.max() < CALLS, "a firm went short in every call"

    def test_a_pool_that_covers_demand_serves_every_firm(self):
        hired = _hire(pool_size=N_FIRMS * WANTED_PER_FIRM)

        assert list(hired) == [WANTED_PER_FIRM] * N_FIRMS
