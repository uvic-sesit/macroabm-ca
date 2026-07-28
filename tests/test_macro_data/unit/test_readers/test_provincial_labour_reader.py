"""Tests for the labour-compensation calibration reader.

Firms' initial wage bills come from WIOD SEA, whose Canadian rows are effectively empty and
are filled from the French proxy, while value added comes from the accurate provincial IO
table. Uncorrected that gives an 84.4% labour share against Canada's observed 49.8%, and
firms are loss-making from the first simulated year.
"""

import numpy as np
import pandas as pd
import pytest

from macro_data.readers.economic_data.provincial_labour_reader import ProvincialLabourReader

# Canada 2014, StatCan supply-use extract ($ thousands): wages/VA = 49.76%.
_ROWS = {
    "Wages and salaries": 861_052_898,
    "Gross mixed income": 227_170_359,
    "Gross operating surplus": 557_797_503,
    "Taxes on production": 89_918_751,
    "Subsidies on production": -5_597_127,
}


def _write_source(tmp_path, rows=None, column="Total use", name="3610000101_customizedLayoutData - 2014 - processed.csv"):
    frame = pd.DataFrame({column: pd.Series(rows if rows is not None else _ROWS)})
    frame.index.name = ""
    path = tmp_path / name
    frame.to_csv(path)
    return path


def test_reads_the_observed_canadian_labour_share(tmp_path):
    _write_source(tmp_path)
    reader = ProvincialLabourReader.from_default(raw_data_path=tmp_path)
    assert reader.available
    assert reader.labour_share == pytest.approx(861_052_898 / 1_730_342_384, rel=1e-9)
    assert 0.49 < reader.labour_share < 0.51


def test_missing_source_is_a_noop(tmp_path):
    reader = ProvincialLabourReader.from_default(raw_data_path=tmp_path)
    assert not reader.available
    lc = np.array([80.0, 20.0])
    np.testing.assert_allclose(reader.rescale(lc, np.array([100.0, 100.0])), lc)


def test_rescale_hits_the_target_share_and_preserves_distribution(tmp_path):
    _write_source(tmp_path)
    reader = ProvincialLabourReader.from_default(raw_data_path=tmp_path)
    lc = np.array([80.0, 20.0])           # 50% share, wrong level
    va = np.array([100.0, 100.0])
    out = reader.rescale(lc, va)
    assert out.sum() / va.sum() == pytest.approx(reader.labour_share, rel=1e-9)
    # Only the level changes; relative industry weights are untouched.
    np.testing.assert_allclose(out / out.sum(), lc / lc.sum())


def test_rescale_corrects_an_inflated_share_downwards(tmp_path):
    """The real case: an 84% labour share must come down to ~50%."""
    _write_source(tmp_path)
    reader = ProvincialLabourReader.from_default(raw_data_path=tmp_path)
    va = np.array([1000.0])
    lc = np.array([844.0])
    out = reader.rescale(lc, va)
    assert out[0] < lc[0]
    assert out.sum() / va.sum() == pytest.approx(reader.labour_share, rel=1e-9)


def test_implausible_share_is_refused(tmp_path):
    """A wrong file/column/units must not silently recalibrate the model."""
    rows = dict(_ROWS)
    rows["Wages and salaries"] = 1  # ~0% share
    _write_source(tmp_path, rows=rows)
    assert not ProvincialLabourReader.from_default(raw_data_path=tmp_path).available


def test_missing_value_added_rows_are_refused(tmp_path):
    rows = {k: v for k, v in _ROWS.items() if k != "Gross operating surplus"}
    _write_source(tmp_path, rows=rows)
    assert not ProvincialLabourReader.from_default(raw_data_path=tmp_path).available


def test_missing_total_column_is_refused(tmp_path):
    _write_source(tmp_path, column="Something Else")
    assert not ProvincialLabourReader.from_default(raw_data_path=tmp_path).available


def test_degenerate_inputs_leave_the_vector_untouched(tmp_path):
    _write_source(tmp_path)
    reader = ProvincialLabourReader.from_default(raw_data_path=tmp_path)
    lc = np.array([0.0, 0.0])
    np.testing.assert_allclose(reader.rescale(lc, np.array([100.0, 100.0])), lc)
    lc2 = np.array([10.0, 10.0])
    np.testing.assert_allclose(reader.rescale(lc2, np.array([0.0, 0.0])), lc2)
