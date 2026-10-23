import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import numpy as np
import pytest
from macromodel.timeseries import TimeSeries

HERE=Path(__file__).resolve().parents[2]/'dev/validation_2022'
sys.path.insert(0,str(HERE))
from afe_instrumentation import household_cash_flows


def test_household_consumption_uses_individual_series_and_reconciles_total():
    h=NS(ts=TimeSeries(income=np.array([30.,80.]),interest_paid=np.array([2.,3.]),
        consumption=np.array([10.,50.]),rent=np.array([5.,0.]),total_consumption=np.array([66.])))
    income,consumption=household_cash_flows(h,.1)
    np.testing.assert_array_equal(income,[28.,77.])
    np.testing.assert_allclose(consumption,[16.,55.])
    assert consumption.sum()==pytest.approx(71.)
    h.ts.dicts['total_consumption'][-1]=np.array([60.])
    with pytest.raises(AssertionError):household_cash_flows(h,.1)
