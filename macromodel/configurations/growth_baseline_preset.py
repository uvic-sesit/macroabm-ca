"""Candidate (provisional) real-growth baseline preset.

This module carries the machine-readable parameter set for the *provisional*
internally-transmitted real-growth configuration, and a helper that applies it to a
`CountryConfiguration`. Every field is an opt-in override; the shipped model defaults
are unchanged, so a configuration that does not call `apply_candidate_growth_baseline`
reproduces legacy behaviour exactly.

STATUS: provisional. This baseline is robust across five seeds and suitable for model
development and controlled comparative scenario testing, but is NOT yet fully validated
for quantitative inference. No decision has been made about merging to MacroABM-CA
`main` or upstreaming general changes to INET.

DATA DEPENDENCY (not committed here): the baseline additionally requires
  (1) a provincial DataWrapper pickle (e.g. dev/pkl_files/disagg_sectorprovs_*.pkl), and
  (2) an observed provincial labour-force index path (derived from StatCan LFS 14-10-0327).
Neither is bundled in this branch. `CANDIDATE_GROWTH_BASELINE["labour_force_index"]` is
left None; a runner must supply a per-province quarterly index (base 1.0 at t0). Absent a
path, demography falls back to the shipped `NoAging` default (fixed labour force).
"""
from __future__ import annotations

from typing import Any, Optional

# Machine-readable parameter set (opt-in overrides on n_industry_default).
CANDIDATE_GROWTH_BASELINE: dict[str, Any] = {
    "demand_estimator": {
        # reconnect the endogenous growth forecast (shipped default is 0.0 = discarded)
        "sectoral_growth_adjustment_speed": 1.0,
        "firm_growth_adjustment_speed": 1.0,
        # adaptive-expectations smoothing alpha (shipped default 1.0 = no smoothing)
        "demand_smoothing": 0.3,
    },
    "demand_for_goods": {
        # weight rho on recorded unmet demand (shipped default 1.0)
        "unmet_demand_weight": 0.25,
    },
    "excess_demand": {
        # record demand-side unmet orders rather than seller spare capacity
        # (shipped default 1.0 = capacity-capped)
        "consider_capital_inputs": 0.0,
    },
    "target_production": {
        "capital_inputs_target_considers_capital_inputs": 1.0,  # w (shipped default)
    },
    "target_capital_inputs": {
        "target_capital_inputs_fraction": 0.1,  # lambda (shipped default 0.0)
        "rolling_reference": True,               # shipped default False
    },
    "government_consumption_setter": "ExogenousGovernmentConsumptionSetter",
    "household_consumption_setter": "ExogenousHouseholdConsumption",
    "household_investment_setter": "ExogenousHouseholdInvestment",
    "demography": "ExogenousLabourForcePath",   # shipped default "NoAging"
    # supplied per-province by the runner; None -> falls back to NoAging (see module docstring)
    "labour_force_index": None,
}


def apply_candidate_growth_baseline(
    country_config,
    labour_force_index: Optional[list[float]] = None,
    demography_seed: int = 0,
):
    """Apply the candidate growth baseline (opt-in overrides) to one CountryConfiguration.

    Args:
        country_config: a CountryConfiguration (e.g. CountryConfiguration.n_industry_default(...)).
        labour_force_index: per-province quarterly labour-force index (base 1.0 at t0).
            If None, demography stays at the shipped NoAging default (fixed labour force).
        demography_seed: reproducible-selection seed for the labour-force reclassification.

    Returns:
        The mutated country_config (also mutated in place).
    """
    p = CANDIDATE_GROWTH_BASELINE
    fc = country_config.firms.functions
    fc.demand_estimator.parameters.update(p["demand_estimator"])
    fc.demand_for_goods.parameters.update(p["demand_for_goods"])
    fc.excess_demand.parameters.update(p["excess_demand"])
    fc.target_production.parameters.update(p["target_production"])
    fc.target_capital_inputs.parameters.update(p["target_capital_inputs"])

    country_config.government_entities.functions.consumption.name = p["government_consumption_setter"]
    country_config.households.functions.consumption.name = p["household_consumption_setter"]
    country_config.households.functions.investment.name = p["household_investment_setter"]

    if labour_force_index is not None:
        country_config.individuals.functions.demography.name = p["demography"]
        country_config.individuals.functions.demography.parameters = {
            "labour_force_index": list(labour_force_index),
            "seed": int(demography_seed),
        }
    return country_config
