import numpy as np
from macro_data.processing.synthetic_firms.observed_gfcf_init import observed_acquisitions

def test_observed_initial_acquisitions_preserve_composition_and_exact_value():
    old=np.array([[1.,3.],[0.,0.]]);stock=np.array([[9.,4.],[2.,0.]]);old_copy=old.copy();stock_copy=stock.copy()
    result=observed_acquisitions(old,stock,np.array([70.,20.]),np.array([2.,4.]))
    np.testing.assert_allclose(result@np.array([2.,4.]),[70.,20.]);assert result[0,1]/result[0,0]==3
    np.testing.assert_array_equal(old,old_copy);np.testing.assert_array_equal(stock,stock_copy)
