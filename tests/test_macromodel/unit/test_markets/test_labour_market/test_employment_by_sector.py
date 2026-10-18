"""Unit tests for the by-sector employment count the labour market records each step."""

from types import SimpleNamespace

import numpy as np

from macromodel.agents.individuals.individual_properties import ActivityStatus
from macromodel.configurations import LabourMarketConfiguration
from macromodel.markets.labour_market.func.clearing import NoLabourMarketClearer
from macromodel.markets.labour_market.labour_market import LabourMarket, create_labour_market_timeseries

N_INDUSTRIES = 2
# Firm 0 produces in industry 1, firm 1 in industry 0.
FIRM_INDUSTRY = np.array([1, 0])
# Three employed individuals, at firms 0, 0 and 1, and one unemployed.
CORRESPONDING_FIRM = np.array([0, 0, 1, -1])
ACTIVITY = np.array(
    [ActivityStatus.EMPLOYED, ActivityStatus.EMPLOYED, ActivityStatus.EMPLOYED, ActivityStatus.UNEMPLOYED],
    dtype=object,
)


class _DummyTS:
    def __init__(self, values):
        self._values = values

    def current(self, name):
        return self._values[name]


def _market(employment_industry):
    ts = create_labour_market_timeseries(
        initial_individual_activity=ACTIVITY,
        initial_individual_employment_industry=employment_industry,
        n_industries=N_INDUSTRIES,
    )

    return LabourMarket(
        country_name="TST",
        n_industries=N_INDUSTRIES,
        functions={"clearing": NoLabourMarketClearer(**LabourMarketConfiguration().functions.clearing.parameters)},
        ts=ts,
    )


def _clear(employment_industry):
    market = _market(employment_industry)
    firms = SimpleNamespace(ts=_DummyTS({"n_firms": 2}), states={"Industry": FIRM_INDUSTRY})
    individuals = SimpleNamespace(
        states={
            "Activity Status": ACTIVITY,
            "Corresponding Firm ID": CORRESPONDING_FIRM,
            "Employment Industry": employment_industry,
        }
    )
    market.clear(firms=firms, households=SimpleNamespace(), individuals=individuals)

    return market.ts.current("num_employed_individuals_by_sector")


class TestEmploymentBySector:
    def test_a_stale_employment_industry_does_not_decide_the_count(self):
        # Every individual started in industry 0; two of them now work for a firm in industry 1.
        counts = _clear(np.array([0, 0, 0, 0]))

        assert list(counts) == [1.0, 2.0]

    def test_a_current_employment_industry_gives_the_same_count(self):
        counts = _clear(np.array([1, 1, 0, 0]))

        assert list(counts) == [1.0, 2.0]

    def test_the_count_sums_to_total_employment(self):
        counts = _clear(np.array([0, 0, 0, 0]))

        assert counts.sum() == np.sum(ACTIVITY == ActivityStatus.EMPLOYED)
