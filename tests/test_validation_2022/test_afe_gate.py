import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('afe_gate',Path(__file__).resolve().parents[2]/'dev/validation_2022/afe_gate.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_gate_requires_saving_and_no_upward_trend():
    q=np.arange(1,13)
    assert m.asset_gate(q,np.linspace(.3,.2,12),np.full(12,m.BENCHMARK_SAVING))['gate_pass']
    assert not m.asset_gate(q,np.linspace(.2,.3,12),np.full(12,m.BENCHMARK_SAVING))['gate_pass']
    assert not m.asset_gate(q,np.linspace(.3,.2,12),np.full(12,.13))['gate_pass']


def test_gate_excludes_q1_q3_transient_and_rejects_missing_or_nonfinite():
    q=np.arange(1,13)
    result=m.asset_gate(q,[0.,0.,0.,.9,.8,.7,.6,.5,.4,.3,.2,.1],np.full(12,-.006))
    assert result['gate_pass']
    with pytest.raises(ValueError):m.asset_gate(q[:11],np.zeros(11),np.zeros(11))
    with pytest.raises(ValueError):m.asset_gate(q,np.full(12,np.nan),np.zeros(12))
