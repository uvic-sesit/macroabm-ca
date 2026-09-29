"""Real-growth baseline preset used for the Powering Canada's Growth analysis.

This module carries the machine-readable parameter set for the production
internally-transmitted real-growth configuration, and a helper that applies it to a
`CountryConfiguration`. Every field is an opt-in override; the shipped model defaults
are unchanged, so a configuration that does not call `apply_candidate_growth_baseline`
reproduces the default behaviour exactly.

What the preset sets:
  * the endogenous growth forecast is reconnected (sectoral / firm growth adjustment
    speeds 1.0) with adaptive-expectations smoothing;
  * unmet demand is recorded on the demand side and weighted at 0.25;
  * the capital-accumulation rule is activated (rolling reference, target fraction 0.1;
    the Net-zero run overrides the fraction to 0.15 through `capital_target_fraction`);
  * government and household consumption / investment follow the exogenous
    national-accounts setters;
  * demography follows `ExogenousLabourForcePath` when a labour-force index is supplied.

Labour supply: the observed provincial labour-force index (StatCan LFS 14-10-0327) is
bundled at `scripts/data/labour_force_index_2014_2024.json`, built by
`scripts/build_labour_force_index.py`. A runner supplies each province's post-sample
tail through `labour_force_growth` (per-province annual rates, e.g. StatCan population
projections). Without an index the demography stays at the shipped `NoAging` default.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

# Bundled observed provincial labour-force index (annual, base 1.0 at the first LFS
# year), built from StatCan LFS 14-10-0327 by scripts/build_labour_force_index.py. Small
# (~4 KB) so the baseline runs turnkey without the ~72 MB raw CSV.
_LABOUR_INDEX_JSON = Path(__file__).resolve().parents[2] / "scripts/data/labour_force_index_2014_2024.json"
# First year of the bundled index.  A runner passes the simulation start year as
# `base_year` (2022 in production) so quarter 0 is anchored at the simulation start.
_LABOUR_BASE_YEAR = 2014


def observed_labour_force_index(n_quarters: int, province: Optional[str] = None,
                                post_sample_growth: Optional[float | dict[str, float]] = None,
                                base_year: int = _LABOUR_BASE_YEAR,
                                ) -> dict[str, list[float]] | list[float]:
    """Quarterly observed labour-force index (base 1.0 at t0), interpolated to n_quarters.

    Reads the bundled annual index and linearly interpolates annual -> quarterly.  Past the
    last observed year the index is, by default, held **flat** (mirroring the exogenous
    national-accounts tail).  ``post_sample_growth`` continues the index at a constant
    annual rate instead, so labour supply keeps expanding over the projection; the
    production configuration passes StatCan's per-province working-age population
    projections here.

    Args:
        n_quarters: number of quarters required (e.g. t_max + 1).
        province: a country key (e.g. "CAN_ON"); if given, returns that province's list,
            else a dict of all provinces.
        post_sample_growth: annual labour-force growth applied after the last observed
            year, either one national rate or ``{province: rate}``.  ``None`` keeps the
            flat tail.
        base_year: the simulation start year; quarter 0 of the returned index is anchored
            there and the path is normalised to 1.0 at that point.

    Raises:
        FileNotFoundError: if the bundled JSON is missing (rebuild with
            scripts/build_labour_force_index.py).
    """
    if not _LABOUR_INDEX_JSON.exists():
        raise FileNotFoundError(
            f"{_LABOUR_INDEX_JSON} not found; rebuild with scripts/build_labour_force_index.py")
    raw = json.loads(_LABOUR_INDEX_JSON.read_text())
    years = sorted(int(y) for y in next(iter(raw.values())))
    # base_year anchors quarter 0 at the SIMULATION start, not the data's first year.
    # For a base year inside the observed window (the production 2022 start against the
    # bundled LFS index) the pre-start observations land at negative quarters, np.interp
    # holds the start-of-range value flat, and the idx/idx[0] rebase below normalises the
    # path to 1.0 at the simulation start -- exactly the semantics the demography expects.
    year_q = np.array([(y - base_year) * 4 + 1.5 for y in years])  # annual obs at mid-year
    grid = np.arange(n_quarters, dtype=float)

    def _interp(annual_by_year: dict[str, float],
                tail_growth: Optional[float] = None) -> list[float]:
        vals = np.array([annual_by_year[str(y)] for y in years], dtype=float)
        idx = np.interp(grid, year_q, vals)   # np.interp holds the endpoints flat outside the range
        if tail_growth:
            # Re-grow the flat tail at a constant annual rate, compounding quarterly from
            # the last in-sample observation rather than from the start of the flat region.
            last_obs_q = year_q[-1]
            tail = grid > last_obs_q
            if tail.any():
                quarters_past = grid[tail] - last_obs_q
                idx = idx.copy()
                idx[tail] = vals[-1] * (1.0 + tail_growth) ** (quarters_past / 4.0)
        return (idx / idx[0]).tolist()

    def _tail_growth_for(p: str) -> Optional[float]:
        g = post_sample_growth
        if isinstance(g, dict):
            # Per-province tails (e.g. StatCan 15-64 population projections). A province
            # absent from the mapping keeps the flat tail rather than inheriting someone
            # else's rate. Negative rates are legitimate and must survive the falsy check
            # below: QC and NL both have SHRINKING working-age populations to 2050.
            g = g.get(p)
        if g is None or g == 0:
            return g
        return float(g)

    if isinstance(post_sample_growth, dict):
        unknown = sorted(set(post_sample_growth) - set(raw))
        if unknown:
            raise ValueError(
                f"post_sample_growth names unknown provinces: {unknown}. A silently "
                "unmatched code would leave that province on a flat tail while the "
                "banner claimed a rate was applied.")

    result = {p: _interp(raw[p], _tail_growth_for(p)) for p in raw}

    if province is not None:
        return result[province]
    return result


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
        # lambda (shipped default 0.0).  The preset literal is 0.1; the Net-zero
        # production run overrides it to 0.15 through `capital_target_fraction`.
        "target_capital_inputs_fraction": 0.1,
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
    use_observed_labour_path: bool = False,
    province: Optional[str] = None,
    n_quarters: Optional[int] = None,
    labour_force_growth: Optional[float | dict[str, float]] = None,
    capital_target_fraction: Optional[float] = None,
    capital_rolling_reference: Optional[bool] = None,
    labour_index_base_year: Optional[int] = None,
):
    """Apply the real-growth baseline (opt-in overrides) to one CountryConfiguration.

    The labour-supply path is an on/off switch like the other mechanisms, with three ways
    to set it (in priority order):

    1. `labour_force_index=[...]`  -- pass an explicit per-province quarterly index.
    2. `use_observed_labour_path=True` (+ `province`, `n_quarters`) -- load the bundled
       observed provincial index (StatCan LFS 14-10-0327) for that province and horizon.
    3. neither -- demography stays at the shipped `NoAging` default (fixed labour force).

    Args:
        country_config: a CountryConfiguration (e.g. CountryConfiguration.n_industry_default(...)).
        labour_force_index: explicit quarterly index (base 1.0 at t0); overrides the flag.
        demography_seed: reproducible-selection seed for the labour-force reclassification.
        use_observed_labour_path: load the bundled observed index for `province`.
        province: country key (e.g. "CAN_ON"), required with use_observed_labour_path.
        n_quarters: horizon (t_max + 1), required with use_observed_labour_path.
        labour_force_growth: post-sample annual growth, one rate or ``{province: rate}``;
            see `observed_labour_force_index`.
        capital_target_fraction: override for the capital-accumulation target fraction
            (preset literal 0.1; the Net-zero production run passes 0.15).
        capital_rolling_reference: override for the rolling-reference switch.
        labour_index_base_year: the simulation start year the bundled index is anchored
            to (2022 in production).

    Returns:
        The mutated country_config (also mutated in place).
    """
    p = CANDIDATE_GROWTH_BASELINE
    fc = country_config.firms.functions
    fc.demand_estimator.parameters.update(p["demand_estimator"])
    fc.demand_for_goods.parameters.update(p["demand_for_goods"])
    fc.excess_demand.parameters.update(p["excess_demand"])
    fc.target_production.parameters.update(p["target_production"])
    # The preset activates the capital-accumulation rule (fraction 0.1, rolling reference),
    # which the shipped defaults leave inert (fraction 0.0).  Both are overridable: the
    # Net-zero production run raises the fraction to 0.15, and the capital channel can be
    # switched off without disturbing the rest of the baseline.
    capital_params = dict(p["target_capital_inputs"])
    if capital_target_fraction is not None:
        capital_params["target_capital_inputs_fraction"] = float(capital_target_fraction)
    if capital_rolling_reference is not None:
        capital_params["rolling_reference"] = bool(capital_rolling_reference)
    fc.target_capital_inputs.parameters.update(capital_params)

    country_config.government_entities.functions.consumption.name = p["government_consumption_setter"]
    country_config.households.functions.consumption.name = p["household_consumption_setter"]
    country_config.households.functions.investment.name = p["household_investment_setter"]

    if labour_force_index is None and use_observed_labour_path:
        if province is None or n_quarters is None:
            raise ValueError("use_observed_labour_path=True requires `province` and `n_quarters`.")
        labour_force_index = observed_labour_force_index(
            n_quarters=n_quarters, province=province,
            post_sample_growth=labour_force_growth,
            **({"base_year": labour_index_base_year}
               if labour_index_base_year is not None else {}))

    if labour_force_index is not None:
        country_config.individuals.functions.demography.name = p["demography"]
        country_config.individuals.functions.demography.parameters = {
            "labour_force_index": list(labour_force_index),
            "seed": int(demography_seed),
        }
    return country_config
