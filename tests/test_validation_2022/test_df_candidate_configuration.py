import pytest

from macromodel.configurations.household_closure_configuration import HouseholdClosureConfiguration


@pytest.mark.parametrize('distress', [False, True])
def test_both_cashflow_candidate_arms_include_narrow_d1(distress):
    cfg = HouseholdClosureConfiguration.cashflow_candidate(distress)
    assert cfg.rent_offset_enabled
    assert cfg.overdraft_limit_enabled
    assert cfg.credit_enabled and cfg.income_enabled and cfg.recalibrate_saving_with_d2
    assert cfg.distress_enabled is distress
    assert cfg.distress_periods == 3
    assert not cfg.deposit_only_saving
    assert not HouseholdClosureConfiguration().rent_offset_enabled
