from types import SimpleNamespace as NS
import numpy as np
import pandas as pd
from macromodel.timeseries import TimeSeries
from macromodel.country.household_closure import offset_private_rent


def test_rent_offset_retains_L_for_owners_and_caps_each_renter_without_spillovers():
    h=NS(states={},ts=TimeSeries(n_households=3,target_consumption=np.array([[10.,20.],[10.,2.],[10.,20.]]),rent=np.array([11.,11.,0.])))
    c=NS(households=h,central_government=NS(states={"Value-added Tax":.1}),
         housing_market=NS(states={"properties":pd.DataFrame({"Is Owner-Occupied":[0,0,1],
             "Corresponding Inhabitant Household ID":[0,1,2],"Corresponding Owner Household ID":[2,2,2],"Rent":[11.,11.,11.]})}))
    offset_private_rent(c,industry=1)
    np.testing.assert_allclose(h.ts.current("target_consumption"),[[10.,10.],[10.,0.],[10.,20.]])
    np.testing.assert_allclose(h.states["rent_L_unoffset_cash"],[0.,8.8,0.],atol=1e-12)
