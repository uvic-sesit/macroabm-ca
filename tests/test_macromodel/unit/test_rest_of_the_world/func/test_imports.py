"""Unit tests for the rest-of-world import setter base class.

`consistency` is documented as a two-valued switch and asserted to be 0 or 1, so a
value outside the contract has to reach the assertion rather than be coerced past it.
"""

import numpy as np
import pytest

from macromodel.rest_of_the_world.func.exports import RoWExportsSetter
from macromodel.rest_of_the_world.func.imports import RoWImportsSetter

OUT_OF_CONTRACT = [2.0, -1.0, 0.5, float("nan")]


class _ImportsSetter(RoWImportsSetter):
    """Concrete subclass, so the base class constructor can be exercised."""

    def compute_imports(self, *args, **kwargs) -> np.ndarray:
        raise NotImplementedError


class _ExportsSetter(RoWExportsSetter):
    def compute_exports(self, *args, **kwargs) -> np.ndarray:
        raise NotImplementedError


class TestConsistencyContract:
    @pytest.mark.parametrize("consistency", [0.0, 1.0])
    def test_the_documented_values_are_stored(self, consistency):
        assert _ImportsSetter(consistency=consistency).consistency == consistency

    @pytest.mark.parametrize("consistency", OUT_OF_CONTRACT)
    def test_a_value_outside_the_contract_is_rejected(self, consistency):
        with pytest.raises(AssertionError):
            _ImportsSetter(consistency=consistency)

    @pytest.mark.parametrize("consistency", OUT_OF_CONTRACT)
    def test_the_import_side_rejects_what_the_export_side_rejects(self, consistency):
        with pytest.raises(AssertionError):
            _ExportsSetter(consistency=consistency)

        with pytest.raises(AssertionError):
            _ImportsSetter(consistency=consistency)
