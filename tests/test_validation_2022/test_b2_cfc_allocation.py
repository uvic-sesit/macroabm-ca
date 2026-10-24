"""Conservation and explicit missing-output treatment in the CFC mapping."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

path=Path(__file__).parents[2]/'dev/validation_2022/build_firm_cfc_b2.py'
spec=importlib.util.spec_from_file_location('b2_cfc_build',path)
build=importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

def test_observed_aggregate_allocation_preserves_total_and_output_shares():
    actual=build.output_split(120.,[1.,3.,0.])
    np.testing.assert_allclose(actual,[30.,90.,0.])
    assert actual.sum()==pytest.approx(120.)

def test_no_output_does_not_invent_activity_to_absorb_CFC():
    np.testing.assert_array_equal(build.output_split(120.,[0.,0.]),[0.,0.])
