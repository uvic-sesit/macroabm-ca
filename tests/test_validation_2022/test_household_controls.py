"""Phase A batch 1: Canadian household counts and tenure stratification (CAN-2022 build)."""
import numpy as np
import pandas as pd
import pytest

from macro_data.processing.synthetic_population.hfcs_synthetic_population import (
    OWNER_TENURE_CODES,
    tenure_stratified_weights,
)
from macro_data.readers.default_readers import _load_can_2022_household_controls


def test_controls_cover_13_regions_and_chs_total():
    c = _load_can_2022_household_controls()
    assert len(c) == 13
    provinces = [r for r in c if r not in ("CAN_YT", "CAN_NT", "CAN_NU")]
    # CHS 2022 46-10-0083, Canada (provinces only), number of households
    assert sum(c[r]["households"] for r in provinces) == pytest.approx(15_455_000)
    assert all(0.0 < v["owner_rate"] < 1.0 for v in c.values())
    assert c["CAN_ON"]["owner_rate"] == pytest.approx(0.663543, abs=1e-6)


def _toy():
    return pd.DataFrame(
        {"Weight": [1.0, 2.0, 3.0, 4.0, 5.0], "Tenure Status of the Main Residence": [1, 2, 3, 4, 3]}
    )


def test_tenure_weights_hit_target_and_preserve_within_tenure_structure():
    df = _toy()
    w = tenure_stratified_weights(df, 0.6)
    own = df["Tenure Status of the Main Residence"].isin(OWNER_TENURE_CODES)
    assert w.sum() == pytest.approx(1.0)
    assert w[own].sum() == pytest.approx(0.6)
    # relative weights within each tenure group unchanged
    np.testing.assert_allclose(w[own] / w[own].sum(), df.Weight[own] / df.Weight[own].sum())
    np.testing.assert_allclose(w[~own] / w[~own].sum(), df.Weight[~own] / df.Weight[~own].sum())


def test_tenure_weights_without_target_is_legacy():
    df = _toy()
    np.testing.assert_allclose(tenure_stratified_weights(df, None), df.Weight / df.Weight.sum())


def test_tenure_weights_reject_degenerate_target():
    with pytest.raises(ValueError):
        tenure_stratified_weights(_toy(), 1.0)
