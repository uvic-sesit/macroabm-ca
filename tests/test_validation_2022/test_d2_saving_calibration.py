from types import SimpleNamespace as NS

import numpy as np
import pytest

from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration
from macromodel.country.household_closure import recalibrate_d2_saving
from macromodel.timeseries import TimeSeries


def fixture(on=True):
    h = NS(states={'average_saving_rate': -.1},
           ts=TimeSeries(income=np.array([80., 20.]), income_financial_assets=np.array([10., 0.]),
                         total_consumption=np.array([110.])))
    cfg = HouseholdClosureConfiguration(income_enabled=True, recalibrate_saving_with_d2=on,
                                         initial_annual_consumption_benchmark=440.)
    return NS(households=h, configuration=NS(household_closure=cfg), household_closure=NS(
        planned_mixed=np.array([20., 0.]), planned_dividends=np.array([0., 10.]), planned_transfers=np.array([5., 5.])))


def test_d2_income_base_reproduces_consumption_with_the_same_weighting():
    c = fixture()
    recalibrate_d2_saving([c])
    assert c.households.states['average_saving_rate'] == pytest.approx(1 - 110 / 130)
    z = c.households.states['saving_calibration']
    assert (1-z['new_propensity']) * z['d2_income'] == pytest.approx(z['target'])


def test_no_recalibration_for_control_or_empty_d2_set():
    c = fixture(False)
    recalibrate_d2_saving([c])
    recalibrate_d2_saving([])
    assert c.households.states['average_saving_rate'] == -.1
