import numpy as np
from macromodel.country.household_closure import private_rent_tax_base


def test_social_rent_of_foreclosed_renter_is_not_private_landlord_income():
    private_rent=np.array([100.,200.]);social_rent=50.;tax=.2
    landlord_net=private_rent*(1-tax)
    base=private_rent_tax_base(landlord_net,tax)
    assert base==300
    assert private_rent.sum()+social_rent==landlord_net.sum()+base*tax+social_rent
