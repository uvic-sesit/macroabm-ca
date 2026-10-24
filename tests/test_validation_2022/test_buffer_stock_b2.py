import numpy as np
import pytest
from macromodel.country.buffer_stock import reanchored_spending,wealth_adjustment,propensity_rescale,spending
from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration


def test_b2_has_no_additive_intercept_and_keeps_income_heterogeneity():
    np.testing.assert_allclose(reanchored_spending(np.array([100.,200.]),[200.,400.],[2.,2.],[0.,0.],.9,.01),[90.,180.])
    assert not HouseholdClosureConfiguration().buffer_stock_reanchor_enabled
    assert spending([100.],[300.],[2.],[0.],.1,level=-1)[0]==109. # retained B


def test_b2_fixed_symmetric_and_asymmetric_wealth_response():
    np.testing.assert_allclose(reanchored_spending([100.,100.],[100.,300.],[2.,2.],[0.,0.],1.,.01),[99.,101.])
    gap,response=wealth_adjustment([100.,100.],[100.,300.],[2.,2.],[0.,0.],.005,.02)
    np.testing.assert_allclose(gap,[-100.,100.]);np.testing.assert_allclose(response,[-2.,.5])
    assert reanchored_spending([-10.],[0.],[2.],[20.],1.,.01)[0]==0.


def test_b2_one_propensity_rescale_matches_target_without_changing_wealth_term():
    income=np.array([90.,180.]);wealth=np.array([1.,-2.]);wL=np.array([.2,.2]);dup=np.array([4.,8.]);rent=np.array([4.,8.])
    factor=propensity_rescale(income,wealth,wL,dup,rent,300.)
    C=np.maximum(0.,factor*income+wealth)
    assert (C-np.minimum(C*wL,dup)+rent).sum()==pytest.approx(300.)
    np.testing.assert_array_equal(wealth,[1.,-2.])
    assert factor>1.


def test_b2_infeasible_wealth_floor_is_reported_not_hidden_with_negative_propensity():
    with pytest.raises(ValueError,match='Wealth term alone'):
        propensity_rescale(np.array([1.]),np.array([200.]),np.array([0.]),np.array([0.]),np.array([0.]),100.)
