import numpy as np
from macromodel.agents.firms.func.labour_productivity import WorkEffortLabourProductivitySetter
import pandas as pd
from macro_data.processing.synthetic_firms.zero_activity import floor_source_zero


def setter():
    return WorkEffortLabourProductivitySetter(max_increase_in_work_effort=1.1,consider_intermediate_inputs=1.,consider_capital_inputs=1.,work_effort_increase_speed=.5)


def test_zero_target_zero_capacity_stays_finite_for_two_quarters():
    fn=setter();contracts=np.array([100.,70.]);jobs=np.array([0,0])
    for _ in range(2):
        target=np.zeros(1);raw=np.ones(1);baseline=np.zeros(1)
        factor=fn.compute_labour_productivity_factor(target,np.zeros(1),np.zeros(1),raw,baseline)
        production=factor*raw*baseline
        np.testing.assert_array_equal(factor,[0.]);np.testing.assert_array_equal(production,[0.])
        assert np.isfinite(factor).all() and np.isfinite(production).all()
        np.testing.assert_array_equal(target,[0.])  # zero labour demand
    np.testing.assert_array_equal(contracts,[100.,70.]);np.testing.assert_array_equal(jobs,[0,0])


def test_positive_output_calculation_is_bit_identical():
    fn=setter();target=np.array([10.,20.,30.]);raw=np.array([2.,4.,5.]);baseline=np.array([4.,8.,12.]);limit=np.array([100.,100.,100.])
    old=1.+fn.work_effort_increase_speed*(np.minimum(fn.max_increase_in_work_effort,target/(raw*baseline))-1.)
    actual=fn.compute_labour_productivity_factor(target,limit,limit,raw,baseline)
    np.testing.assert_array_equal(actual,old)


def test_nl_c21_uses_the_existing_output_va_fcf_floor_path():
    cells=pd.MultiIndex.from_tuples([('CAN_NL','C21'),('TOTAL','Value Added'),('TOTAL','Output')])
    cols=pd.MultiIndex.from_tuples([('CAN_NL','C21'),('CAN_NL','Fixed Capital Formation'),('TOTAL','Output')])
    raw=pd.DataFrame(0.,index=cells,columns=cols);raw.at[('CAN_NL','C21'),('TOTAL','Output')]=.1
    source=pd.Series([0.],index=pd.MultiIndex.from_tuples([('CAN_NL','C21')]))
    result,zero=floor_source_zero(raw,source,['CAN_NL'],['C21'])
    assert zero==[('CAN_NL','C21')]
    assert result.at[('CAN_NL','C21'),('TOTAL','Output')]==1e6
    assert result.at[('TOTAL','Value Added'),('CAN_NL','C21')]==1e6
    assert result.at[('CAN_NL','C21'),('CAN_NL','Fixed Capital Formation')]==1e6
    again,_=floor_source_zero(result,source,['CAN_NL'],['C21'])
    pd.testing.assert_frame_equal(result,again)
