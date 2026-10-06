"""Unit tests for the capital formation tax rate, including its absent-country fallback.

find_value answers for a country absent from a table with the cross-country mean for
that year, so the rate became one currency-mixed mean divided by another, over two
possibly different sets of countries.
"""

import pytest


def _own_ratio_range(readers, year):
    """The range of taxes/capital-formation ratios formed inside a single country."""
    capform_df = readers.eurostat.data["capital_formation"]
    iot = readers.eurostat.data["iot_tables"]
    taxes_df = iot[(iot["induse"] == "P5") & (iot["prod_na"] == "D21X31")]
    taxes = taxes_df.loc[taxes_df["TIME_PERIOD"] == year].groupby("geo")["OBS_VALUE"].first()
    capform = capform_df.loc[capform_df["TIME_PERIOD"] == year].groupby("geo")["OBS_VALUE"].first()
    ratios = (taxes / capform).dropna()

    return ratios.min(), ratios.max()


class TestCapitalFormationTaxRate:
    def test_a_country_reporting_both_tables_is_unchanged(self, readers):
        assert readers.eurostat.taxrate_on_capital_formation("AUT", 2010) == pytest.approx(0.2318, abs=1e-4)

    @pytest.mark.parametrize("country,year", [("CAN", 2014), ("CAN", 2020), ("NLD", 2014)])
    def test_a_country_missing_a_table_stays_within_the_reported_range(self, readers, country, year):
        # A rate formed from two cross-country means need not resemble any country's own
        # rate: Canada's 2020 value was 1.97 where no reporting country exceeded 0.56.
        lowest, highest = _own_ratio_range(readers, year)

        rate = readers.eurostat.taxrate_on_capital_formation(country, year)

        assert lowest <= rate <= highest

    def test_the_fallback_is_a_rate_below_one(self, readers):
        assert readers.eurostat.taxrate_on_capital_formation("CAN", 2020) < 1.0
