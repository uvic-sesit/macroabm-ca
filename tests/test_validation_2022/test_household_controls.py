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


def test_renter_is_never_matched_to_a_unit_it_owns():
    from types import SimpleNamespace
    import numpy as np
    import pandas as pd
    from macro_data.processing.synthetic_matching.matching_households_with_houses import match_renters_to_properties

    # hh 0 and hh 1 rent; hh 2 owns both rental units. hh 0 also owns rental unit 1, whose rent is the
    # closest to what hh 0 pays (so the unconstrained matching would put hh 0 in its own unit).
    hh = pd.DataFrame({
        "Tenure Status of the Main Residence": [3, 3, 1],
        "Rent Paid": [10.0, 50.0, 0.0],
        "Rental Income from Real Estate": [0.0, 0.0, 1.0],
        "Corresponding Additionally Owned Houses ID": [[1], [], [0]],
    })
    houses = pd.DataFrame({
        "House ID": [0, 1, 2], "Is Owner-Occupied": [False, False, True],
        "Corresponding Owner Household ID": [2, 0, 2], "Corresponding Inhabitant Household ID": [np.nan, np.nan, 2.0],
        "Rent": [48.0, 11.0, 0.0],
    })
    pop = SimpleNamespace(household_data=hh)
    match_renters_to_properties(pop, houses, rental_income_taxes=0.0)
    inhabitant = houses["Corresponding Inhabitant Household ID"].values
    owner = houses["Corresponding Owner Household ID"].values
    rented = ~houses["Is Owner-Occupied"].values
    assert not np.any(rented & (inhabitant == owner))
    assert houses.loc[1, "Corresponding Inhabitant Household ID"] == 1


def test_initial_household_loan_terms_reproduce_observed_principal_payments():
    from macro_data.configuration.can_2022_constants import (
        CAN_2022_CONSUMER_LOAN_MATURITY_Q, CAN_2022_MORTGAGE_MATURITY_Q)
    # StatCan 11-10-0065-01, 2022 mean SAAR ($M/yr) vs 36-10-0580 stocks ($M); installment = stock / maturity
    assert 729_932 / CAN_2022_CONSUMER_LOAN_MATURITY_Q * 4 == pytest.approx(60_172, rel=0.02)
    assert 2_126_996 / CAN_2022_MORTGAGE_MATURITY_Q * 4 == pytest.approx(58_695, rel=0.02)


def test_cad_native_build_rebases_model_exchange_rate():
    import pandas as pd
    from macro_data.data_wrapper import rebase_cad_native_exchange_rate
    df = pd.DataFrame({"2021": [1.25, 1.0], "2022": [1.30, 1.0]}, index=["CAN", "USA"])
    out = rebase_cad_native_exchange_rate(df, io_rate=1.0, year=2022)
    assert out.loc["CAN", "2022"] == pytest.approx(1.0)
    assert out.loc["CAN", "2021"] == pytest.approx(1.25 / 1.30)
    assert out.loc["USA", "2022"] == 1.0 and df.loc["CAN", "2022"] == 1.30  # input untouched
    assert rebase_cad_native_exchange_rate(df, io_rate=1.30, year=2022) is df  # non-CAD-native build: no-op


def test_firm_deposits_allocated_by_output_without_firm_data():
    import numpy as np
    import pandas as pd
    from macro_data.processing.synthetic_firms.firm_tools import function_parameters_dependent_initialisation
    fd = pd.DataFrame({"Industry": [0, 1], "Production": [10.0, 30.0], "Price": [1.0, 1.0]})
    A = np.full((2, 2), 4.0); K = np.full((2, 2), 2.0); D = np.full((2, 2), 0.05)
    function_parameters_dependent_initialisation(
        fd, A, D, K, total_firm_deposits=8.0, total_firm_debt=0.0, assume_zero_initial_debt=True,
        assume_zero_initial_deposits=False, capital_inputs_utilisation_rate=1.0,
        initial_inventory_to_input_fraction=0.0, intermediate_inputs_utilisation_rate=1.0)
    np.testing.assert_allclose(fd["Deposits"].values, [2.0, 6.0])
