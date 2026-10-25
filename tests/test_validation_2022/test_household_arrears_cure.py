import numpy as np
from macromodel.country.household_payment_default import cure_transition

def test_partial_catchup_holds_bucket_and_distress_clock_without_forgiveness():
    days,periods,partial,cured=cure_transition(np.array([60,60,60,0]),np.array([1,1,1,0]),np.array([20.,20.,20.,0.]),np.array([10.,0.,25.,10.]),np.array([40.,50.,25.,20.]),np.array([30.,30.,30.,30.]))
    np.testing.assert_array_equal(days,[60,0,150,30])
    np.testing.assert_array_equal(periods,[1,0,2,1])
    np.testing.assert_array_equal(partial,[True,False,False,False])
    np.testing.assert_array_equal(cured,[False,True,False,False])

def test_payment_below_current_schedule_cannot_freeze_age():
    days,periods,partial,_=cure_transition(np.array([90]),np.array([2]),np.array([20.]),np.array([10.]),np.array([25.]),np.array([30.]))
    assert days[0]==180 and periods[0]==3 and not partial[0]

