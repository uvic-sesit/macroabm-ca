import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dev/io2022/household_prototype'))
from prepare_household_canadianization import calibrate_mortgages_pro_rata


def data_and_controls(target=1350.):
    d=pd.DataFrame({'Weight':[1.,1.,1.],'Value of the Main Residence':[100.,200.,300.],
        'Value of other Properties':[0.,0.,100.],'Outstanding Balance of HMR Mortgages':[50.,180.,350.],
        'Outstanding Balance of Mortgages on other Properties':[0.,0.,50.]})
    t={'groups':{'housing':{'fields':list(d.columns[1:3]),'target':.0014},
                 'mortgages':{'fields':list(d.columns[3:5]),'target':target/1e6}}}
    return d,t


def test_common_scale_plus_capped_topup_keeps_weights_and_underwater_records():
    d,t=data_and_controls(); r=calibrate_mortgages_pro_rata(d,t)
    np.testing.assert_array_equal(d.Weight,r.Weight)
    assert r.iloc[:,1:3].sum().sum()==pytest.approx(1400.)
    assert r.iloc[:,3:5].sum().sum()==pytest.approx(1350.)
    assert r.iloc[2,3]==700.  # originally underwater: no top-up
    for p,m in zip(d.columns[1:3],d.columns[3:5]):
        np.testing.assert_array_equal(d[m]>d[p],r[m]>r[p])
        added=r[m]>2*d[m]+1e-9
        assert np.all(r.loc[added,m]<=.95*r.loc[added,p]+1e-9)
    assert r.attrs['mortgage_calibration']['weights_unchanged']


def test_infeasible_topup_fails_instead_of_reweighting_or_exceeding_ltv_cap():
    d,t=data_and_controls(3000.)
    with pytest.raises(ValueError,match='capacity'): calibrate_mortgages_pro_rata(d,t)
