import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dev/validation_2022'))
from be_instrumentation import price_components
from summarise_be import gate


def test_price_decomposition_reconstructs_multiplicative_noise_without_rng():
    deterministic,noise,floor=price_components(np.array([2.,1.]),np.array([2.31,.01]),1.05,1.,1.)
    assert deterministic[0]==pytest.approx(2.1)
    assert noise[0]==pytest.approx(.1)
    np.testing.assert_allclose(deterministic*(1+noise),[2.31,.01])
    assert floor.tolist()==[False,True]


def test_buffer_gate_uses_percentage_point_boundaries_and_all_accounting():
    assert gate(.25,4.4,1e-8)
    assert gate(-.1,-5.6,0.)
    assert not gate(.25001,0.,0.)
    assert not gate(0.,4.40001,0.)
    assert not gate(0.,0.,1.01e-8)
