import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dev/validation_2022'))
from fe_gates import constrained_slope,firm_gate,planned_investment_gate


def test_household_check_uses_q4_through_q12_and_strict_sign():
    assert constrained_slope([.2]*12)==0
    assert constrained_slope([1,1,1]+list(np.linspace(.2,.4,9)))>0
    assert constrained_slope([0,0,0]+list(np.linspace(.4,.2,9)))<0
    with pytest.raises(ValueError):constrained_slope([.1]*11)


def test_initial_gate_uses_plan_not_realised_affordability():
    assert planned_investment_gate(60.59825e9)
    assert not planned_investment_gate(50e9)
    assert firm_gate(1e-14,50,100)
    assert not firm_gate(1e-7,50,100)
