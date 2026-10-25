import pandas as pd
from macro_data.processing.synthetic_firms.zero_activity import restated_cost_checks


def cases(positive_gap):
    return pd.DataFrame({'source_output':[100.,0.],'floor_cell':[False,True],'margin_gap_pp':[positive_gap,100.],'above_price_nonnegative_NOS':[False,False]})


def test_floor_margin_reported_separately_not_as_a_source_margin():
    result=restated_cost_checks(cases(.9))
    assert result['positive_source_margin_exceptions']==0
    assert result['old_universal_margin_exceptions']==1
    assert result['old_universal_max_gap_pp']==100.


def test_positive_source_keeps_the_one_percentage_point_threshold():
    result=restated_cost_checks(cases(1.01))
    assert result['positive_source_margin_exceptions']==1
    tiny=cases(1.01);tiny.loc[0,'source_output']=.000001
    assert restated_cost_checks(tiny)['positive_source_margin_exceptions']==1
