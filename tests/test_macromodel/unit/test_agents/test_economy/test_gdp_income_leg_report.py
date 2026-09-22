"""Unit tests for the runtime report on the GDP income leg.

The output and expenditure legs are tied together by the trade adjustment and then
asserted equal; the income leg is not compared with either, so a divergence there
passes unremarked.
"""

import logging

import numpy as np

OUTPUT = 2.0e6


def _compute_gdp(economy, wages):
    """Drive compute_gdp so that the output leg is OUTPUT and the income leg is wages."""
    n_industries = economy.n_industries

    economy.compute_gdp(
        total_output=OUTPUT,
        sectoral_sales=np.zeros(n_industries),
        sectoral_intermediate_consumption=np.zeros((n_industries, n_industries)),
        taxes_on_products=0.0,
        taxes_on_production=0.0,
        rent_paid=0.0,
        rent_imputed=0.0,
        hh_consumption=0.0,
        gov_consumption=0.0,
        change_in_inventories=0.0,
        gross_fixed_capital_formation=0.0,
        exports=0.0,
        imports=0.0,
        operating_surplus=0.0,
        wages=wages,
        rent_received=0.0,
        central_government_rent_received=0.0,
        running_multiple_countries=False,
    )


class TestGdpIncomeLegReport:
    def test_matching_legs_are_not_reported(self, test_economy, caplog):
        with caplog.at_level(logging.WARNING):
            _compute_gdp(test_economy, wages=OUTPUT)

        assert test_economy.ts.current("gdp_income")[0] == OUTPUT
        assert caplog.records == []

    def test_a_diverging_income_leg_is_reported(self, test_economy, caplog):
        # A quarter of output missing from the income leg, well past the one per cent
        # tolerance, while the output and expenditure legs still agree.
        with caplog.at_level(logging.WARNING):
            _compute_gdp(test_economy, wages=0.75 * OUTPUT)

        assert [record for record in caplog.records if "output/income GDP" in record.getMessage()]

    def test_a_small_divergence_is_not_reported(self, test_economy, caplog):
        # Half a per cent, inside the tolerance.
        with caplog.at_level(logging.WARNING):
            _compute_gdp(test_economy, wages=0.995 * OUTPUT)

        assert caplog.records == []
