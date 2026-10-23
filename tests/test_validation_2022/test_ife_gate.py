from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dev/validation_2022'))
from ife_gates import investment_gate


def test_investment_gate_checks_both_ten_percent_bounds():
    assert investment_gate(90.,100.)['gate1_pass']
    assert investment_gate(110.,100.)['gate1_pass']
    assert not investment_gate(89.,100.)['gate1_pass']
    assert not investment_gate(111.,100.)['gate1_pass']
    with pytest.raises(ValueError):investment_gate(float('nan'))
