from types import SimpleNamespace as NS
from macromodel.country.country import Country
from macromodel.configurations.country_configuration import CountryConfiguration


def test_country_reset_discards_previous_income_closure_before_reinstallation():
    names=['individuals','households','firms','central_government','government_entities','banks','central_bank',
           'economy','labour_market','credit_market','housing_market']
    c=NS(household_closure=object(),exogenous=NS(reset=lambda:None),
         **{name:NS(reset=lambda **kwargs:None) for name in names})
    Country.reset(c,CountryConfiguration())
    assert c.household_closure is None
