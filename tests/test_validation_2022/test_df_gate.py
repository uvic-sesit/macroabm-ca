import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'dev/validation_2022'))
from df_diagnostics import consumption_gate


@pytest.mark.parametrize('fraction, passed', [(.94,False),(.95,True),(1.,True)])
def test_gate_boundary_and_numpy_measurement_serialization(fraction, passed):
    result = consumption_gate(np.float64(377845500000.*fraction), np.float64(377845500000.))
    assert json.loads(json.dumps(result))['household_gate_passed'] is passed
