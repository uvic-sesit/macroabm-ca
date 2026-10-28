"""An industry with an exogenous ANNUAL (emissions, limit) schedule on the OBPS is
charged on it -- quartered, at the current price -- and nothing else about it (model
emissions, baseline intensity, benchmark row, coverage threshold) is consulted. The
M3-linkages policy prehook writes such a schedule for electricity (per-fuel generation
standards on COPPER's generation)."""
import numpy as np
import pandas as pd
import pytest

from macro_data.readers.policy_data.obps_can_reader import OBPSCANData
from macromodel.policy.output_based_price_system_can import OutputBasedPriceSystemCAN

INDUSTRIES = ["C24a", "A01"]
PRICE = 50.0


def _obps(year: int = 2020, threshold: float = 0.0) -> OutputBasedPriceSystemCAN:
    data = OBPSCANData(
        df_rates=pd.DataFrame({"Date": list(range(2014, 2052)), "CAN": [PRICE] * 38}),
        df_policy=pd.DataFrame({"Industry": ["C24a"], "reduction_factor": [0.8],
                                "tightening_rate": [0.02]}),
    )
    obps = OutputBasedPriceSystemCAN(country_name="CAN", industries=INDUSTRIES,
                                     obps_data=data, coverage_threshold_tco2_per_year=threshold)
    obps.current_year = year
    obps.current_t = year - 2014
    obps.baseline_emission_intensity[0] = 0.5   # limit = 100 x 0.5 x 0.8 = 40 in 2020
    return obps


def _call(obps, input_em):
    return obps.compute_obps(use_obps_reg=True, record_obps_reference=False,
                             production=np.array([100.0, 50.0]),
                             input_em=np.array(input_em), capital_em=np.zeros(2))


def test_schedule_year_overrides_model_emissions():
    obps = _obps()
    obps.exogenous_emissions = {"C24a": {2020: (4000.0, 1000.0)}}
    # the model's own arithmetic would give (60 - 40) x 50 = 1000; the schedule gives
    # (4000 - 1000) / 4 x 50 = 37,500
    cost = _call(obps, [60.0, 0.0])
    assert cost[0] == pytest.approx(37_500.0)
    assert obps.emission_limit[0] == pytest.approx(250.0)
    assert obps.charged_emissions[0] == pytest.approx(1000.0)
    assert cost[1] == 0.0


def test_year_outside_schedule_falls_back_to_model():
    obps = _obps()
    obps.exogenous_emissions = {"C24a": {2021: (4000.0, 1000.0)}}
    cost = _call(obps, [60.0, 0.0])
    assert cost[0] == pytest.approx(1000.0)
    assert obps.charged_emissions[0] == pytest.approx(60.0)


def test_schedule_bypasses_coverage_threshold_and_can_rebate():
    obps = _obps(threshold=1e9)   # nothing in the model would clear this
    obps.exogenous_emissions = {"C24a": {2020: (0.0, 400.0)}}
    cost = _call(obps, [0.0, 0.0])   # a clean fleet under its limit: a rebate
    assert cost[0] == pytest.approx(-100.0 * PRICE)


def test_not_charged_before_charging_starts():
    obps = _obps(year=2016)
    obps.exogenous_emissions = {"C24a": {2016: (4000.0, 1000.0)}}
    assert np.all(_call(obps, [60.0, 0.0]) == 0.0)


def test_compute_charge_matches_and_reset_keeps_schedule():
    obps = _obps()
    obps.exogenous_emissions = {"C24a": {2020: (4000.0, 1000.0)}}
    direct = obps.compute_charge(np.array([100.0, 50.0]), np.array([60.0, 0.0]), np.zeros(2))
    assert direct[0] == pytest.approx(37_500.0)
    obps.reset()
    assert obps.exogenous_emissions == {"C24a": {2020: (4000.0, 1000.0)}}
    assert np.all(obps.charged_emissions == 0.0)


def test_object_without_attribute_still_computes():
    """OBPS objects restored from checkpoints saved before the attribute existed."""
    obps = _obps()
    del obps.exogenous_emissions
    assert _call(obps, [60.0, 0.0])[0] == pytest.approx(1000.0)
