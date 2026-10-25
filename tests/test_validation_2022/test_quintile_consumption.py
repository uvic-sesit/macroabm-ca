import numpy as np
import pytest
from macromodel.country.quintile_consumption import ranked_propensities


def test_dhea_midpoints_and_linear_interpolation():
    x=np.arange(10.); p=ranked_propensities(x,np.ones(10),[2,1.6,1.2,1,.8])
    np.testing.assert_allclose(p,[2,1.9,1.7,1.5,1.3,1.15,1.05,.95,.85,.8])


def test_national_rank_invariant_to_uniform_weight_units():
    x=[3,1,4,2]; w=np.array([1000,10,1000,10])
    np.testing.assert_allclose(ranked_propensities(x,w,[2,1.5,1,.9,.7]),ranked_propensities(x,3*w,[2,1.5,1,.9,.7]))


def test_reject_bad_ratio_schedule():
    with pytest.raises(ValueError):ranked_propensities([1],[1],[2,1])
