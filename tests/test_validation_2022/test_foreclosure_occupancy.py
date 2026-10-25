from types import SimpleNamespace
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
from macromodel.markets.housing_market.housing_market import HousingMarket


def test_foreclosure_does_not_overwrite_unmoved_third_party_tenant():
    props=pd.DataFrame({'Corresponding Owner Household ID':[0],
        'Corresponding Inhabitant Household ID':[1],'Is Owner-Occupied':[0],
        'E foreclosure':[True],'Value':[100.]})
    sales=pd.DataFrame([dict(sales_types='Sell',property_id=0,seller_id=0,buyer_id=2,price_or_rent=80.)])
    market=SimpleNamespace(states={'properties':props,'current_sales':sales},ts=MagicMock())
    states={'Corresponding Inhabited House ID':np.array([-1,0,-1]),
        'Tenure Status of the Main Residence':np.array([1,3,3]),'Corresponding Property Owner':np.array([0,0,-1]),
        'corr_renters':[[1],[],[]]}
    HousingMarket.process_housing_market_clearing(market,states,np.zeros(3),np.array([0.,0.,100.]))
    assert not sales.executed.iloc[0]
    assert props.loc[0,'Corresponding Inhabitant Household ID']==1
    np.testing.assert_array_equal(states['Corresponding Inhabited House ID'],[-1,0,-1])
