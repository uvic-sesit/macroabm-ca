from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dev/validation_2022'))
from b2_gates import assess
from b2_instrumentation import fixed_groups,consumption_units,weighted_median,income_per_household,gross_wages_from_net


def test_B2_gates_zero_share_strict_and_quintile_relative_share_thresholds():
    args=dict(zero_shares=[.019],slope_pp=.25,q12_saving_pct=4.4,q1_C=95.,C_target=100.,
        quintile_relative_deviation=[.15],q12_C=100.,q12_GDP=100.,ref_C=100.,ref_GDP=100.,error=1e-8)
    assert assess(**args)['pass_all']
    assert not assess(**dict(args,zero_shares=[.02]))['G1']
    assert not assess(**dict(args,quintile_relative_deviation=[-.15001]))['G3']
    assert not assess(**dict(args,q12_GDP=106.))['G4']
    assert not assess(**dict(args,q1_C=94.99))['G2']


def test_source_specific_OECD_units_and_weighted_household_ranks():
    units=consumption_units(np.array([45.,40.,13.,14.,30.]),np.array([0,0,0,0,1]),3)
    np.testing.assert_allclose(units,[2.3,1.,1.])
    np.testing.assert_array_equal(fixed_groups(np.array([10.,20.,30.,40.]),np.ones(4),2),[1,1,2,2])
    assert weighted_median(np.array([0.,1.,10.]),np.array([1.,1.,8.]))==10.


def test_national_income_rank_is_invariant_to_regional_expansion_factors():
    a=income_per_household(np.array([10000.,30000.])*1000,1000)
    b=income_per_household(np.array([10000.,30000.])*10,10)
    np.testing.assert_array_equal(a,b)
    values=np.r_[a,b]
    np.testing.assert_array_equal(fixed_groups(values,np.ones(4),2),[1,2,1,2])


def test_SHS_gross_income_inverts_the_multiplicative_payroll_identity():
    gross=np.array([100.,200.]);pit=.2;ssc=.1
    np.testing.assert_allclose(gross_wages_from_net(gross*(1-ssc)*(1-pit),pit,ssc),gross)
