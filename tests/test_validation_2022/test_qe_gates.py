import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dev/validation_2022'))
from summarise_qe import share_gate


def test_distribution_gate_is_relative_share_not_raw_level():
    b=np.array([.1,.15,.2,.25,.3]);m=b*np.array([.85,1.15,1,1,1])
    assert share_gate(m,b)
    assert not share_gate(m*10,b)
    assert not share_gate(b*np.array([.8499,1,1,1,1]),b)
