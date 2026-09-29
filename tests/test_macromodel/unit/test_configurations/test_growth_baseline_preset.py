"""Unit tests for the real-growth baseline preset and the bundled observed
labour-force index loader / on-off switch."""
import numpy as np
import pytest

from macromodel.configurations import CountryConfiguration
from macromodel.configurations.growth_baseline_preset import (
    apply_candidate_growth_baseline,
    observed_labour_force_index,
)


class TestObservedLabourForceIndex:
    def test_index_starts_at_one_and_has_requested_length(self):
        idx = observed_labour_force_index(n_quarters=53, province="CAN_ON")
        assert len(idx) == 53
        assert abs(idx[0] - 1.0) < 1e-9

    def test_bundled_terminal_growth_matches_lfs(self):
        # Bundled data pins the known 2014->2024 provincial labour-force growth.
        on = observed_labour_force_index(n_quarters=54, province="CAN_ON")
        nl = observed_labour_force_index(n_quarters=54, province="CAN_NL")
        assert on[-1] > 1.15         # Ontario ~ +18.8%
        assert nl[-1] < 1.0          # Newfoundland shrinks (~ -0.7%)

    def test_all_provinces_returned_as_dict(self):
        d = observed_labour_force_index(n_quarters=40)
        assert "CAN_ON" in d and "CAN_NL" in d
        assert all(len(v) == 40 and abs(v[0] - 1.0) < 1e-9 for v in d.values())

    def test_base_year_anchors_quarter_zero_at_simulation_start(self):
        # Production starts in 2022: the index must be 1.0 there and carry only the
        # post-2022 movement.
        legacy = np.array(observed_labour_force_index(n_quarters=20, province="CAN_ON"))
        rebased = np.array(observed_labour_force_index(n_quarters=20, province="CAN_ON",
                                                       base_year=2022))
        assert abs(rebased[0] - 1.0) < 1e-12
        assert not np.allclose(legacy, rebased)

    def test_per_province_tail_rates(self):
        n = 120
        d = observed_labour_force_index(
            n, post_sample_growth={"CAN_ON": 0.01, "CAN_NL": -0.005}, base_year=2022)
        flat = observed_labour_force_index(n, base_year=2022)
        assert d["CAN_ON"][-1] > flat["CAN_ON"][-1]
        assert d["CAN_NL"][-1] < flat["CAN_NL"][-1]
        # A province absent from the mapping keeps the flat tail.
        np.testing.assert_allclose(d["CAN_AB"], flat["CAN_AB"], rtol=1e-12)

    def test_unknown_province_in_tail_mapping_raises(self):
        with pytest.raises(ValueError):
            observed_labour_force_index(40, post_sample_growth={"CAN_XX": 0.01})


class TestApplyPreset:
    def test_default_preserves_legacy_demography(self):
        c = apply_candidate_growth_baseline(CountryConfiguration.n_industry_default(n_industries=43))
        assert c.individuals.functions.demography.name == "NoAging"
        assert c.firms.functions.demand_for_goods.parameters["unmet_demand_weight"] == 0.25
        assert c.firms.functions.target_capital_inputs.parameters["rolling_reference"] is True
        assert c.firms.functions.target_capital_inputs.parameters["target_capital_inputs_fraction"] == 0.1

    def test_capital_target_fraction_override(self):
        c = apply_candidate_growth_baseline(
            CountryConfiguration.n_industry_default(n_industries=43),
            capital_target_fraction=0.15)
        assert c.firms.functions.target_capital_inputs.parameters["target_capital_inputs_fraction"] == 0.15

    def test_flag_loads_bundled_labour_path(self):
        c = apply_candidate_growth_baseline(
            CountryConfiguration.n_industry_default(n_industries=43),
            use_observed_labour_path=True, province="CAN_AB", n_quarters=53)
        assert c.individuals.functions.demography.name == "ExogenousLabourForcePath"
        idx = c.individuals.functions.demography.parameters["labour_force_index"]
        assert len(idx) == 53 and abs(idx[0] - 1.0) < 1e-9

    def test_flag_with_production_style_arguments(self):
        c = apply_candidate_growth_baseline(
            CountryConfiguration.n_industry_default(n_industries=43),
            use_observed_labour_path=True, province="CAN_AB", n_quarters=117,
            labour_force_growth={"CAN_AB": 0.012}, labour_index_base_year=2022)
        idx = c.individuals.functions.demography.parameters["labour_force_index"]
        assert len(idx) == 117 and abs(idx[0] - 1.0) < 1e-9
        assert idx[-1] > idx[len(idx) // 2]

    def test_flag_requires_province_and_quarters(self):
        with pytest.raises(ValueError):
            apply_candidate_growth_baseline(
                CountryConfiguration.n_industry_default(n_industries=43),
                use_observed_labour_path=True)

    def test_explicit_index_overrides_flag(self):
        c = apply_candidate_growth_baseline(
            CountryConfiguration.n_industry_default(n_industries=43),
            labour_force_index=[1.0, 1.01, 1.02])
        assert c.individuals.functions.demography.parameters["labour_force_index"] == [1.0, 1.01, 1.02]
