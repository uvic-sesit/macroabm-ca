#!/usr/bin/env python3
"""Run one macroABM iteration of the CIMS--macroABM linkage (provincial mode).

This is the macroABM-side entry point invoked by the M3-linkages orchestrator
(``scripts/macroabm_runner.py``).  A single invocation performs one outer-loop
iteration of the linkage:

1. Extract the linkage inputs (requested quantities + investment by sector and
   fuel) from a completed CIMS run's *standard* result CSVs, per CIMS region and
   milestone year (:class:`CIMSResultsExtractor`).
2. Build and run the provincial Canadian macroABM (2014 -> end year), calling
   ``firms.link()`` for every province at each CIMS milestone year via a
   simulation pre-hook.
3. Collect each province's annual production and write it back into CIMS as a
   ``macroabm_production`` policy overlay using the growth-ratio method
   (:class:`CIMSProductionWriter`).
4. Write per-period provincial GDP growth to ``gdp_growth_by_period.json`` for
   the orchestrator's convergence check (and start-to-end totals to
   ``gdp_growth.json`` for backward compatibility).

When ``--warm-start`` is enabled the simulation can restart from a milestone
checkpoint instead of rerunning from ``sim_start_year`` every iteration.
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from macro_data import DataWrapper
from macro_data.processing.macroabm_cims_data_processing import (
    CIMSProductionWriter,
    CIMSResultsExtractor,
    SectorMap,
)
from macro_data.readers.cims_data import CIMSDataReader
from macromodel.configurations.growth_baseline_preset import apply_candidate_growth_baseline
from macromodel.simulation import Simulation

# Candidate-baseline household-demand overlay (matches scripts/run_candidate_baseline.py).
_HH_DEMAND_COLS = [
    "Real Household Consumption (Value)",
    "Household Consumption (Value)",
    "Real Household Investment (Value)",
    "Household Investment (Value)",
]
_HOUSEHOLD_DEMAND_GROWTH = 0.02

# Reuse the proven provincial configuration helpers.  Support running both as a
# module (``python -m scenarios.run_cims_linkage``) and as a file
# (``python scenarios/run_cims_linkage.py``).
try:
    from scenarios.run_canada_provincial import (  # type: ignore
        CANADIAN_PROVINCES,
        build_simulation_configuration,
        create_data_pickle,
    )
except ImportError:  # pragma: no cover - depends on invocation style
    from run_canada_provincial import (  # type: ignore
        CANADIAN_PROVINCES,
        build_simulation_configuration,
        create_data_pickle,
    )

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("cims_linkage")


@dataclass
class SimulationCheckpoint:
    simulation: Simulation
    steps_completed: int
    milestone_year: int


def _province_code(country_name: object) -> str:
    """Return the macro province code (e.g. 'CAN_AB') from a country key."""
    code = getattr(country_name, "code", None)
    return str(code) if code is not None else str(country_name)


def milestone_years(base_year: int, end_year: int, year_step: int) -> list[int]:
    """CIMS milestone years strictly after *base_year* up to *end_year*."""
    return list(range(base_year + year_step, end_year + 1, year_step))


def period_key(start_year: int, end_year: int) -> str:
    return f"{start_year}-{end_year}"


def linkage_periods(base_year: int, end_year: int, year_step: int) -> list[tuple[int, int]]:
    ends = milestone_years(base_year, end_year, year_step)
    starts = [base_year] + ends[:-1]
    return list(zip(starts, ends))


def year_end_timestep_index(year: int, sim_start_year: int, steps_per_year: int) -> int:
    """Index into per-timestep GDP history after completing calendar *year*."""
    return (year - sim_start_year + 1) * steps_per_year


def checkpoint_years(base_year: int, end_year: int, year_step: int) -> list[int]:
    """Milestone calendar years at whose completion we persist checkpoints."""
    return [base_year] + milestone_years(base_year, end_year, year_step)


def _prune_rolling_checkpoints(checkpoint_dir: Path, *, keep: Path) -> None:
    """Delete superseded milestone checkpoints, retaining only *keep*."""
    keep = keep.resolve()
    for path in checkpoint_dir.glob("checkpoint_*.pkl"):
        if path.resolve() == keep:
            continue
        logger.info("Rolling retention: deleting superseded checkpoint %s", path)
        path.unlink(missing_ok=True)


def milestone_checkpoint_years(
    base_year: int,
    end_year: int,
    year_step: int,
    history_boundary: int,
) -> set[int]:
    """Milestone years for per-milestone checkpoint files (not the history file)."""
    years = set(checkpoint_years(base_year, end_year, year_step))
    years.discard(history_boundary)
    if base_year < history_boundary:
        years.discard(base_year)
    return years


def load_sim_at_milestone(
    *,
    target_milestone: int,
    checkpoint_dir: Path,
    history_boundary: int,
    history_checkpoint: Path | None,
    sim_start_year: int,
    steps_per_year: int,
    total_steps: int,
    link_prehook,
    checkpoint_retention: str,
) -> Simulation:
    """Load simulation state at *target_milestone*, replaying from history if needed."""
    cp_path = checkpoint_dir / f"checkpoint_{target_milestone}.pkl"

    if target_milestone == history_boundary:
        if history_checkpoint is None or not history_checkpoint.exists():
            raise FileNotFoundError(
                f"Warm restart requested from history boundary {history_boundary} "
                f"but history checkpoint not found at {history_checkpoint}"
            )
        logger.info("Warm restart: loading history checkpoint %s", history_checkpoint)
        return load_sim_checkpoint(history_checkpoint).simulation

    if cp_path.exists():
        logger.info("Warm restart: loading checkpoint %s", cp_path)
        return load_sim_checkpoint(cp_path).simulation

    if checkpoint_retention != "rolling":
        raise FileNotFoundError(
            f"Warm restart requested from milestone {target_milestone} "
            f"but checkpoint not found at {cp_path}"
        )

    if history_checkpoint is None or not history_checkpoint.exists():
        raise FileNotFoundError(
            f"Rolling retention: no checkpoint at {cp_path} and no history checkpoint "
            f"to replay from at {history_checkpoint}"
        )

    logger.info(
        "Rolling retention: replaying from history checkpoint %s to milestone %s",
        history_checkpoint,
        target_milestone,
    )
    sim = load_sim_checkpoint(history_checkpoint).simulation
    sim.configuration.t_max = total_steps
    sim.prehooks = [link_prehook]
    replay_steps = year_end_timestep_index(target_milestone, sim_start_year, steps_per_year)
    run_with_checkpoints(
        sim,
        total_steps=replay_steps,
        checkpoint_dir=checkpoint_dir,
        save_years=set(),
        checkpoint_retention="all",
    )
    return sim


def save_sim_checkpoint(sim: Simulation, path: Path, milestone_year: int) -> None:
    """Persist simulation state at a milestone year.

    Pre-hooks are omitted from the pickle (they are rebuilt on load from the
    current CIMS inputs) because nested callables such as ``link_prehook`` are
    not picklable.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    saved_prehooks = sim.prehooks
    sim.prehooks = []
    try:
        payload = SimulationCheckpoint(
            simulation=sim,
            steps_completed=sim.steps_completed,
            milestone_year=milestone_year,
        )
        with open(path, "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    finally:
        sim.prehooks = saved_prehooks
    logger.info("Saved macroABM checkpoint at milestone %s (%s)", milestone_year, path)


def load_sim_checkpoint(path: Path) -> SimulationCheckpoint:
    try:
        with open(path, "rb") as f:
            payload = pickle.load(f)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load macroABM checkpoint at {path}. "
            "The file may be corrupt or from an incompatible run; delete it and retry. "
            f"Original error: {exc}"
        ) from exc
    if not isinstance(payload, SimulationCheckpoint):
        raise TypeError(f"Unexpected checkpoint payload in {path}")
    return payload


def _completed_milestone_year(sim: Simulation) -> int | None:
    """Return the calendar year just completed, or None if not at a year boundary."""
    if sim.timestep.month != 1:
        return None
    return sim.timestep.year - 1


def run_with_checkpoints(
    sim: Simulation,
    *,
    total_steps: int,
    checkpoint_dir: Path,
    save_years: set[int],
    checkpoint_retention: str = "all",
) -> None:
    """Run until *total_steps*, saving checkpoints after selected milestone years."""
    while sim.steps_completed < total_steps:
        sim.iterate(sim.steps_completed)
        completed = _completed_milestone_year(sim)
        if completed is not None and completed in save_years:
            path = checkpoint_dir / f"checkpoint_{completed}.pkl"
            save_sim_checkpoint(sim, path, completed)
            if checkpoint_retention == "rolling":
                _prune_rolling_checkpoints(checkpoint_dir, keep=path)


def extract_cims_inputs(
    cims_results_dir: Path,
    export_dir: Path,
    industries: list[str],
    cims_regions: list[str],
    years: list[int],
    sector_map: SectorMap,
    itr: str,
    steps_per_year: int,
) -> None:
    """Extract processed requested-quantity/investment/intensity matrices for every region."""
    extractor = CIMSResultsExtractor(
        cims_results_dir,
        sector_map=sector_map,
        steps_per_year=steps_per_year,
    )
    for region in cims_regions:
        extractor.process(region, years, industries, export_dir, itr)


def build_link_prehook(
    reader: CIMSDataReader,
    sector_map: SectorMap,
    industries: list[str],
    years: list[int],
    itr: str,
    *,
    method: str = "nudge",
    anchor_year: int | None = None,
    reset_multipliers: bool = True,
    intermediate_factor: float = 0.1,
    capital_factor: float = 0.1,
    capital_investment_boost: float = 0.1,
    activity_consistent: bool = False,
):
    """Create a simulation pre-hook that calls firms.link() at milestone years.

    With ``method="intensity_target"`` the hook also loads the anchor-year and
    current-year energy/capital intensity matrices and passes them to
    ``firms.link()`` so it can set energy-per-output directly (index-anchored to
    ``anchor_year``) instead of nudging.
    """
    energy_codes = sector_map.energy_bundle_for(industries)
    comparable_codes = sector_map.comparable_for(industries)
    milestone = set(years)
    method = (method or "nudge").lower()
    if anchor_year is None and years:
        anchor_year = min(years)

    def link_prehook(sim: Simulation, year: int, month: int) -> None:
        if month != 1 or year not in milestone:
            return
        for country in sim.countries.values():
            province = _province_code(country.country_name)
            cims_region = sector_map.macro_region_to_cims.get(province)
            if cims_region is None or not reader.available(itr, year, cims_region):
                continue
            rq = reader.get_requested_quantities(itr, year, cims_region)
            inv = reader.get_investment(itr, year, cims_region)

            if method == "intensity_target":
                if not reader.intensity_available(itr, year, cims_region) or not reader.intensity_available(
                    itr, anchor_year, cims_region
                ):
                    logger.warning(
                        "intensity_target: intensity matrices missing for region=%s year=%s (or anchor %s); "
                        "skipping link this milestone.",
                        cims_region, year, anchor_year,
                    )
                    continue
                country.firms.link(
                    requested_quantities=rq,
                    investment=inv,
                    comparable_codes=comparable_codes,
                    energy_bundle_codes=energy_codes,
                    method="intensity_target",
                    energy_intensity=reader.get_energy_intensity(itr, year, cims_region),
                    anchor_energy_intensity=reader.get_energy_intensity(itr, anchor_year, cims_region),
                    capital_intensity=reader.get_capital_intensity(itr, year, cims_region),
                    anchor_capital_intensity=reader.get_capital_intensity(itr, anchor_year, cims_region),
                    is_anchor=(year == anchor_year),
                    reset_multipliers=reset_multipliers,
                    activity_consistent=activity_consistent,
                )
            else:
                country.firms.link(
                    requested_quantities=rq,
                    investment=inv,
                    comparable_codes=comparable_codes,
                    energy_bundle_codes=energy_codes,
                    intermediate_factor=intermediate_factor,
                    capital_factor=capital_factor,
                    capital_investment_boost=capital_investment_boost,
                )
            logger.info(
                "link() applied (%s): province=%s cims_region=%s year=%s", method, province, cims_region, year
            )

    return link_prehook


def _gdp_value_at_year(country, year: int, sim_start_year: int, steps_per_year: int) -> float | None:
    history = country.economy.ts.historic("gdp_output")
    idx = year_end_timestep_index(year, sim_start_year, steps_per_year)
    if idx >= len(history):
        return None
    return float(np.asarray(history[idx]).ravel()[0])


def compute_gdp_growth_by_period(
    sim: Simulation,
    periods: list[tuple[int, int]],
    sim_start_year: int,
    steps_per_year: int,
) -> dict[str, dict[str, float]]:
    """Return ``{province: {period_key: growth}}`` for each completed period."""
    growth_by_province: dict[str, dict[str, float]] = {}
    for country in sim.countries.values():
        province = _province_code(country.country_name)
        period_growth: dict[str, float] = {}
        for start_year, end_year in periods:
            start_gdp = _gdp_value_at_year(country, start_year, sim_start_year, steps_per_year)
            end_gdp = _gdp_value_at_year(country, end_year, sim_start_year, steps_per_year)
            if start_gdp is None or end_gdp is None or abs(start_gdp) <= 1e-12:
                continue
            period_growth[period_key(start_year, end_year)] = end_gdp / start_gdp - 1.0
        if period_growth:
            growth_by_province[province] = period_growth
    return growth_by_province


def compute_gdp_growth(sim: Simulation) -> dict[str, float]:
    """Start-to-end nominal GDP growth (end/start - 1) per province."""
    growth: dict[str, float] = {}
    for country in sim.countries.values():
        province = _province_code(country.country_name)
        history = country.economy.ts.historic("gdp_output")
        if not history:
            continue
        start = float(np.asarray(history[0]).ravel()[0])
        end = float(np.asarray(history[-1]).ravel()[0])
        if abs(start) > 1e-12:
            growth[province] = end / start - 1.0
    return growth


def energy_bundle_indices(sector_map: SectorMap, industries: list[str]) -> list[int]:
    """Industry indices of the CIMS energy carriers, for a substitution bundle.

    Groups the energy-bundle macro codes present in *industries* (coal, natural
    gas, crude oil, refined petroleum, electricity) so the macroABM treats them
    as mutually substitutable inputs.
    """
    energy_codes = sector_map.energy_bundle_for(industries)
    return [industries.index(code) for code in energy_codes]


def apply_growth_limits(
    sim: Simulation,
    industry_indices: list[int],
    max_growth_per_year: float | None,
    max_decline_per_year: float | None,
    steps_per_year: int,
) -> None:
    """Set the per-sector production growth clamp on every province's firms.

    Applied after the simulation is built or restored (and on every iteration),
    so it also configures sims restored from checkpoints written before the clamp
    existed.  A no-op when no sectors are given.
    """
    if not industry_indices or (max_growth_per_year is None and max_decline_per_year is None):
        return
    for country in sim.countries.values():
        country.firms.set_growth_limits(
            industry_indices, max_growth_per_year, max_decline_per_year, steps_per_year
        )


def apply_import_limits(sim: Simulation, industry_indices: list[int]) -> None:
    """Cap ROW exports (= domestic imports) of the given industries at their base-year share.

    Applied after the simulation is built or restored (and on every iteration), so it
    also configures sims restored from checkpoints written before the cap existed.
    A no-op when no sectors are given.  See
    :meth:`RestOfTheWorld.set_import_limits` for the semantics.
    """
    if not industry_indices:
        return
    sim.rest_of_the_world.set_import_limits(industry_indices)
    # Clamping ROW's desired exports is not sufficient on its own: the goods market has
    # an unmet-demand backstop that adds to ROW's realised sales without reference to
    # the quantity it offered, so a capped sector was simply refilled there (measured at
    # up to 32x offered supply for sector D after the 2030 milestone).  Suppress the
    # backstop for the same industries.
    clearer = sim.goods_market.functions.get("clearing")
    if clearer is not None and hasattr(clearer, "set_import_limited_industries"):
        clearer.set_import_limited_industries(industry_indices)
    else:
        logger.warning(
            "Goods-market clearer does not support import limits; ROW's additional-exports "
            "backstop will refill capped sectors and the cap will not bind."
        )


def apply_capacity_unconstrained(sim: Simulation, industry_indices: list[int]) -> None:
    """Lift the capital ceiling on the given industries in every province (diagnostic).

    Phase 0 of the supply-side linkage: sector D's production was measured pinned to its
    capital ceiling (within 0.1% of ``limiting_capital_inputs`` every year from 2026), so
    this asks how far it would get with capacity free.  A no-op when no sectors are given.
    """
    if not industry_indices:
        return
    for country in sim.countries.values():
        country.firms.set_capacity_unconstrained_industries(industry_indices)


def industry_indices_for(codes: str | None, industries: list[str]) -> list[int]:
    """Resolve a comma-separated list of macro sector codes to industry indices.

    Unknown codes are skipped with a warning rather than failing the run, matching how
    the growth-limit sector list is handled.
    """
    wanted = [c.strip() for c in str(codes or "").split(",") if c.strip()]
    indices: list[int] = []
    for code in wanted:
        if code in industries:
            indices.append(industries.index(code))
        else:
            logger.warning("Import/growth limit sector %r not in model industries; ignoring.", code)
    return indices


def _extend_exogenous_national_accounts(model: Simulation, required_length: int) -> None:
    """Hold the last observed exogenous national-accounts quarter flat past the data tail."""
    for country in model.countries.values():
        frame = country.exogenous.national_accounts_during.copy()
        if len(frame) >= required_length:
            continue
        last_index = frame.index[-1]
        rows, index = [], []
        for step in range(required_length - len(frame)):
            rows.append(frame.iloc[-1].copy())
            index.append(last_index + pd.DateOffset(months=3 * (step + 1)))
        country.exogenous.national_accounts_during = pd.concat(
            [frame, pd.DataFrame(rows, index=index)], axis=0
        )


def _apply_household_demand_overlay(
    model: Simulation,
    growth_rate: float = _HOUSEHOLD_DEMAND_GROWTH,
) -> None:
    """Apply the candidate-baseline exogenous household demand growth overlay."""
    for country in model.countries.values():
        frame = country.exogenous.national_accounts_during
        fac = (1.0 + growth_rate) ** (np.arange(len(frame)) / 4.0)
        for col in _HH_DEMAND_COLS:
            if col in frame.columns:
                frame[col] = frame[col].values * fac


def build_simulation(
    data: DataWrapper,
    *,
    timesteps: int,
    seed: int,
    firms_bundles: list[list[int]] | None = None,
    use_candidate_baseline: bool = False,
    labour_force_growth: float | None = None,
    capital_target_fraction: float | None = None,
    capital_rolling_reference: bool | None = None,
    household_demand_growth: float | None = None,
    wage_tightness_markup_scale: float | None = None,
    max_work_effort: float | None = None,
    link_wages_to_tfp: bool | None = None,
    tfp_base_growth_rate: float | None = None,
    tfp_investment_effectiveness: float | None = None,
) -> Simulation:
    """Build a provincial Simulation, optionally with the candidate growth baseline.

    ``labour_force_growth`` continues the observed labour-force index past its 2024 data
    tail at a constant annual rate instead of freezing it, so labour supply can expand
    over the projection (see ``observed_labour_force_index``).

    When ``use_candidate_baseline`` is True, applies the provisional real-growth
    preset from ``growth_baseline_preset`` (observed labour paths, exogenous
    government/household setters, demand/capital mechanisms) plus the turnkey
    post-build overlays (flat NA extension past the data tail and +2%/yr HH demand).
    """
    config = build_simulation_configuration(
        len(data.industries), timesteps=timesteps, seed=seed, firms_bundles=firms_bundles
    )
    if use_candidate_baseline:
        logger.info("Applying candidate growth baseline (observed labour path + HH overlay)")
        for i, province in enumerate(CANADIAN_PROVINCES):
            apply_candidate_growth_baseline(
                config.country_configurations[province],
                use_observed_labour_path=True,
                province=_province_code(province),
                n_quarters=timesteps + 1,
                demography_seed=1000 + i + 100 * seed,
                labour_force_growth=labour_force_growth,
                capital_target_fraction=capital_target_fraction,
                capital_rolling_reference=capital_rolling_reference,
            )
    if wage_tightness_markup_scale is not None:
        # Diagnostic clamp on the wage spiral.  Firms mark offered wages up by recent
        # hiring shortfalls, scaled by this factor (shipped default 0.5); measured wage
        # rates rise ~47% over two years against 8% CPI once the labour market is tight.
        # 0.0 removes the tightness channel entirely -- a test of whether the spiral is
        # what destabilises the run, NOT a proposed behavioural change.
        for province in CANADIAN_PROVINCES:
            cc = config.country_configurations[province]
            cc.firms.functions.offered_wage_setter.parameters[
                "labour_market_tightness_markup_scale"
            ] = float(wage_tightness_markup_scale)
        logger.info(
            "Wage tightness markup scale overridden to %s (shipped default 0.5)",
            wage_tightness_markup_scale,
        )
    if max_work_effort is not None:
        # Incumbent wages are indexed to the work-effort productivity factor:
        # set_employee_income multiplies each stayer's wage by
        # current_labour_productivity_factor / prev_labour_productivity_factor every
        # quarter.  That factor is min(max_increase_in_work_effort, target /
        # (labour x industry_productivity)), so when firms are input-constrained it
        # climbs toward its ceiling and drags wages up with it -- compounding, and
        # independent of labour-market tightness.  Lowering the ceiling toward 1.0
        # pins the ratio at 1 and freezes that channel.  DIAGNOSTIC: it also removes
        # firms' ability to raise output via work effort, so it is not a pure wage clamp.
        for province in CANADIAN_PROVINCES:
            cc = config.country_configurations[province]
            cc.firms.functions.labour_productivity.parameters[
                "max_increase_in_work_effort"
            ] = float(max_work_effort)
        logger.info(
            "Max increase in work effort overridden to %s (shipped default 1.5)",
            max_work_effort,
        )
    if link_wages_to_tfp is not None:
        # The live wage formula is a LEVEL formula:
        #   real_wage = (1 + markup) * tfp_multiplier * labour_productivity_factor
        #               * initial_wage_per_capita / tax
        # The markup ships inert (scale 0.0) and the productivity factor was measured
        # FALLING 13.5% over 2024-2026 while real wages rose 30.1%, so the TFP multiplier
        # is the only term left that can account for the rise (implied ~2.04 -> 3.07,
        # i.e. ~52x the configured 0.1%/quarter base rate).  Setting this False pins the
        # TFP term in wage setting only; TFP's effect on production is untouched.
        for province in CANADIAN_PROVINCES:
            cc = config.country_configurations[province]
            cc.firms.functions.wage_setter.parameters["link_wages_to_tfp"] = bool(link_wages_to_tfp)
        logger.info(
            "Wage-TFP link set to %s (shipped behaviour: True)",
            bool(link_wages_to_tfp),
        )
    if tfp_base_growth_rate is not None or tfp_investment_effectiveness is not None:
        # TFP calibration.  run_canada_provincial hard-codes base 0.001/quarter with
        # SimpleTFPGrowth investment_effectiveness 0.3; the resulting multiplier was
        # measured compounding at ~5.24%/quarter (~52x base), and since wages are
        # multiplied by it that is the source of the wage spiral.
        for province in CANADIAN_PROVINCES:
            firms = config.country_configurations[province].firms
            if tfp_base_growth_rate is not None:
                firms.parameters.tfp_base_growth_rate = float(tfp_base_growth_rate)
            if tfp_investment_effectiveness is not None:
                firms.functions.productivity_growth.parameters["investment_effectiveness"] = float(
                    tfp_investment_effectiveness
                )
        logger.info(
            "TFP calibration overridden: base_growth=%s investment_effectiveness=%s",
            tfp_base_growth_rate,
            tfp_investment_effectiveness,
        )

    sim = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=config)
    if use_candidate_baseline:
        _extend_exogenous_national_accounts(sim, required_length=timesteps + 1)
        # The overlay's default (+2%/yr) outruns labour-supply growth (~0.72%/yr), so firms
        # bid wages up against a hard supply limit and the labour share climbs without
        # bound.  Overridable so the two can be tested at compatible rates.
        _apply_household_demand_overlay(
            sim,
            growth_rate=(
                _HOUSEHOLD_DEMAND_GROWTH if household_demand_growth is None
                else float(household_demand_growth)
            ),
        )
    return sim


EXPORT_CHECKPOINT_NAME = "simulation_export.pkl"
DEFAULT_H5_FILENAME = "simulation_results.h5"
DEFAULT_SHALLOW_H5_FILENAME = "simulation_shallow.h5"


def export_simulation_h5(sim: Simulation, h5_path: Path) -> None:
    """Write the full macroABM simulation state to an HDF5 file."""
    h5_path = h5_path.resolve()
    h5_path.parent.mkdir(parents=True, exist_ok=True)
    sim.save(h5_path.parent, h5_path.name)
    logger.info("Saved full macroABM results to %s", h5_path)


def export_shallow_h5(sim: Simulation, h5_path: Path) -> None:
    """Write per-province summary time series (GDP, unemployment, etc.) to HDF5."""
    h5_path = h5_path.resolve()
    if h5_path.exists():
        h5_path.unlink()
    sim.shallow_hdf_save(h5_path.parent, h5_path.name)
    logger.info("Saved shallow macroABM summary to %s", h5_path)


def export_h5_from_checkpoint(checkpoint_path: Path, h5_path: Path) -> None:
    """Load a saved simulation checkpoint and write it to HDF5."""
    payload = load_sim_checkpoint(checkpoint_path.resolve())
    export_simulation_h5(payload.simulation, h5_path)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run one macroABM iteration of the CIMS--macroABM linkage.")
    p.add_argument("--export-h5-only", action="store_true",
                   help="Export HDF5 from a checkpoint and exit (no simulation run).")
    p.add_argument("--export-h5", type=Path, default=None,
                   help="HDF5 output path (used with --export-h5-only).")
    p.add_argument("--export-from-checkpoint", type=Path, default=None,
                   help="Simulation checkpoint pickle to export (used with --export-h5-only).")
    p.add_argument("--save-shallow-h5", action=argparse.BooleanOptionalAction, default=True,
                   help="Save per-province summary HDF5 (GDP, unemployment, etc.) every run.")
    p.add_argument("--shallow-h5-filename", type=str, default=DEFAULT_SHALLOW_H5_FILENAME,
                   help="Shallow HDF5 filename written under --output-dir.")
    p.add_argument("--save-export-checkpoint", action="store_true",
                   help="Save a simulation pickle for deferred HDF5 export when warm-start is off.")
    p.add_argument("--cims-results-dir", type=Path, default=None,
                   help="Directory with the completed CIMS run's result CSVs.")
    p.add_argument("--cims-model-dir", type=Path, default=None,
                   help="Path to cims-models-fork/csv/model (source of service-request trajectories).")
    p.add_argument("--raw-data-path", type=Path, default=None,
                   help="macroABM raw_data/ directory (IO tables, etc.).")
    p.add_argument("--output-dir", type=Path, default=None,
                   help="Directory for processed data, feedback policy, and gdp_growth.json.")
    p.add_argument("--feedback-dir", type=Path, default=None,
                   help="Directory to write the macroabm_production policy overlay into.")
    p.add_argument("--pkl-path", type=Path, default=None,
                   help="Provincial data pickle path (default: <output-dir>/data_provincial_model.pkl).")
    p.add_argument("--iteration", type=str, default="00", help="Iteration label (zero-padded).")
    p.add_argument("--sim-start-year", type=int, default=2014)
    p.add_argument("--sim-end-year", type=int, default=2050)
    p.add_argument("--steps-per-year", type=int, default=4)
    p.add_argument("--cims-base-year", type=int, default=2015)
    p.add_argument("--cims-year-step", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--intermediate-factor",
        type=float,
        default=0.1,
        help="Damping step for intermediate-input productivity in firms.link() (default 0.1).",
    )
    p.add_argument(
        "--capital-factor",
        type=float,
        default=0.1,
        help="Damping step for capital-input productivity in firms.link() (default 0.1).",
    )
    p.add_argument(
        "--capital-investment-boost",
        type=float,
        default=0.1,
        help="Extra multiplier on negative capital productivity adjustments (default 0.1).",
    )
    p.add_argument(
        "--linkage-method",
        choices=["nudge", "intensity_target"],
        default="nudge",
        help="How firms.link() applies CIMS results: legacy 'nudge' or 'intensity_target' "
             "(directly set energy-per-output, index-anchored to the anchor year).",
    )
    p.add_argument(
        "--intensity-anchor-year",
        type=int,
        default=None,
        help="Anchor year for the intensity-target index (default: first CIMS milestone / "
             "history boundary). At the anchor year the index is 1 (no shock).",
    )
    p.add_argument(
        "--no-reset-multipliers",
        dest="reset_multipliers",
        action="store_false",
        help="Do not reset firm tech multipliers at milestones (keep intra-period drift on top of the target).",
    )
    p.set_defaults(reset_multipliers=True)
    p.add_argument(
        "--energy-substitution",
        action="store_true",
        help="Group the CIMS energy carriers into one substitution bundle (BundledLeontief + bundle "
             "arbitrage) so firms can substitute between energy types on relative price across the "
             "years between CIMS milestones.",
    )
    p.add_argument(
        "--growth-limit-sectors",
        type=str,
        default="",
        help="Comma-separated macro industry codes whose annual production growth is clamped in the "
             "macroABM (e.g. 'B05a,B05b,B05c,C19'). Empty disables the clamp.",
    )
    p.add_argument(
        "--growth-limit-up",
        type=float,
        default=None,
        help="Max annual production growth for the clamped sectors (e.g. 0.05 = +5%%/yr). Omit for unbounded upside.",
    )
    p.add_argument(
        "--growth-limit-down",
        type=float,
        default=None,
        help="Max annual production decline for the clamped sectors (e.g. 0.05 = -5%%/yr). Omit for unbounded downside.",
    )
    p.add_argument(
        "--feedback-relaxation",
        type=float,
        default=1.0,
        help="Under-relaxation weight alpha in [0,1] for the macroABM->CIMS feedback: "
             "written = alpha*new + (1-alpha)*previous. 1.0 = full overwrite (default); "
             "smaller damps the loop (e.g. 0.3).",
    )
    p.add_argument(
        "--previous-feedback-dir",
        type=Path,
        default=None,
        help="Previous iteration's feedback output dir (new_cims_inputs), read to blend the "
             "feedback under --feedback-relaxation. Omit on iteration 1.",
    )
    p.add_argument("--sector-map", type=Path, default=None, help="Override sector-map CSV.")
    p.add_argument("--region-map", type=Path, default=None, help="Override region-map CSV.")
    p.add_argument("--force-rebuild-pickle", action="store_true")
    p.add_argument(
        "--use-candidate-baseline",
        action="store_true",
        help="Apply the provisional real-growth candidate baseline (observed labour path + HH overlay).",
    )
    p.add_argument("--warm-start", action="store_true",
                   help="Enable milestone checkpointing and partial reruns.")
    p.add_argument("--history-boundary", type=int, default=2020,
                   help="Last milestone year treated as fixed history when warm-starting.")
    p.add_argument("--checkpoint-dir", type=Path, default=None,
                   help="Directory for per-milestone macroABM checkpoints.")
    p.add_argument("--history-checkpoint", type=Path, default=None,
                   help="Shared history checkpoint saved after the cold history run.")
    p.add_argument("--rerun-from-milestone", type=int, default=None,
                   help="Restart the simulation from this milestone checkpoint year.")
    p.add_argument(
        "--checkpoint-retention",
        choices=["all", "rolling"],
        default="all",
        help=(
            "'all' keeps every milestone checkpoint (large disk use). "
            "'rolling' keeps only the latest milestone file and replays from "
            "the shared history checkpoint when an intermediate milestone is needed."
        ),
    )
    return p.parse_args()


def _require_normal_run_args(args: argparse.Namespace) -> None:
    required = {
        "cims_results_dir": "--cims-results-dir",
        "cims_model_dir": "--cims-model-dir",
        "raw_data_path": "--raw-data-path",
        "output_dir": "--output-dir",
        "feedback_dir": "--feedback-dir",
    }
    missing = [flag for attr, flag in required.items() if getattr(args, attr) is None]
    if missing:
        raise SystemExit(f"Missing required arguments for a linkage run: {', '.join(missing)}")


def main() -> None:
    args = parse_args()
    if args.export_h5_only:
        if args.export_h5 is None or args.export_from_checkpoint is None:
            raise SystemExit("--export-h5-only requires --export-h5 and --export-from-checkpoint.")
        export_h5_from_checkpoint(args.export_from_checkpoint, args.export_h5)
        return

    _require_normal_run_args(args)
    output_dir: Path = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pkl_path: Path = (args.pkl_path or output_dir / "data_provincial_model.pkl").resolve()
    processed_dir = output_dir / "cims_data"

    sector_map = SectorMap.load(sector_map_path=args.sector_map, region_map_path=args.region_map)

    years = milestone_years(args.cims_base_year, args.sim_end_year, args.cims_year_step)
    cims_regions = sorted(set(sector_map.macro_region_to_cims.values()))
    periods = linkage_periods(args.cims_base_year, args.sim_end_year, args.cims_year_step)
    cp_years = milestone_checkpoint_years(
        args.cims_base_year,
        args.sim_end_year,
        args.cims_year_step,
        args.history_boundary,
    )
    checkpoint_retention = args.checkpoint_retention

    create_data_pickle(args.raw_data_path.resolve(), pkl_path, force=args.force_rebuild_pickle)
    data = DataWrapper.init_from_pickle(pkl_path)
    industries = list(data.industries)
    logger.info("Loaded provincial data: %d industries, %d provinces", len(industries), len(CANADIAN_PROVINCES))

    firms_bundles: list[list[int]] | None = None
    if args.energy_substitution:
        indices = energy_bundle_indices(sector_map, industries)
        if len(indices) >= 2:
            firms_bundles = [indices]
            logger.info(
                "Energy substitution enabled: bundling %d energy carriers %s (BundledLeontief + arbitrage).",
                len(indices), sector_map.energy_bundle_for(industries),
            )
        else:
            logger.warning(
                "Energy substitution requested but only %d energy carrier(s) present; "
                "substitution needs >= 2, leaving PureLeontief.",
                len(indices),
            )

    # Resolve the production growth-limit sectors (macro codes) to industry indices.
    gl_codes = [c.strip() for c in str(args.growth_limit_sectors).split(",") if c.strip()]
    gl_indices = [industries.index(c) for c in gl_codes if c in industries]
    gl_missing = [c for c in gl_codes if c not in industries]
    if gl_missing:
        logger.warning("Growth-limit sectors not found in the model industries (ignored): %s", gl_missing)
    if gl_indices and (args.growth_limit_up is not None or args.growth_limit_down is not None):
        logger.info(
            "Production growth clamp enabled for %s: up=%s/yr down=%s/yr.",
            [industries[i] for i in gl_indices], args.growth_limit_up, args.growth_limit_down,
        )

    logger.info("Extracting CIMS results from %s", args.cims_results_dir)
    extract_cims_inputs(
        cims_results_dir=args.cims_results_dir.resolve(),
        export_dir=processed_dir,
        industries=industries,
        cims_regions=cims_regions,
        years=years,
        sector_map=sector_map,
        itr=args.iteration,
        steps_per_year=args.steps_per_year,
    )

    total_steps = (args.sim_end_year - args.sim_start_year + 1) * args.steps_per_year
    history_steps = year_end_timestep_index(args.history_boundary, args.sim_start_year, args.steps_per_year)
    checkpoint_dir = (args.checkpoint_dir or output_dir / "checkpoints").resolve()
    history_checkpoint = args.history_checkpoint

    reader = CIMSDataReader(processed_dir)
    intensity_anchor_year = (
        args.intensity_anchor_year if args.intensity_anchor_year is not None else args.history_boundary
    )
    if args.linkage_method == "intensity_target" and intensity_anchor_year not in years:
        # The anchor must be a CIMS milestone so its intensity matrix exists;
        # fall back to the first milestone otherwise.
        logger.warning(
            "intensity anchor year %s is not a CIMS milestone %s; using the first milestone %s instead.",
            intensity_anchor_year, years, years[0] if years else None,
        )
        intensity_anchor_year = years[0] if years else intensity_anchor_year
    link_prehook = build_link_prehook(
        reader,
        sector_map,
        industries,
        years,
        args.iteration,
        method=args.linkage_method,
        anchor_year=intensity_anchor_year,
        reset_multipliers=args.reset_multipliers,
        intermediate_factor=args.intermediate_factor,
        capital_factor=args.capital_factor,
        capital_investment_boost=args.capital_investment_boost,
    )

    sim: Simulation | None = None
    if args.warm_start and args.rerun_from_milestone is not None:
        sim = load_sim_at_milestone(
            target_milestone=args.rerun_from_milestone,
            checkpoint_dir=checkpoint_dir,
            history_boundary=args.history_boundary,
            history_checkpoint=history_checkpoint.resolve() if history_checkpoint else None,
            sim_start_year=args.sim_start_year,
            steps_per_year=args.steps_per_year,
            total_steps=total_steps,
            link_prehook=link_prehook,
            checkpoint_retention=checkpoint_retention,
        )
        sim.configuration.t_max = total_steps
        sim.prehooks = [link_prehook]
        apply_growth_limits(sim, gl_indices, args.growth_limit_up, args.growth_limit_down, args.steps_per_year)
        logger.info(
            "Warm restart: continuing from milestone %s (%d/%d steps completed)",
            args.rerun_from_milestone,
            sim.steps_completed,
            total_steps,
        )
        run_with_checkpoints(
            sim,
            total_steps=total_steps,
            checkpoint_dir=checkpoint_dir,
            save_years=cp_years,
            checkpoint_retention=checkpoint_retention,
        )
    elif args.warm_start and history_checkpoint is not None and history_checkpoint.exists():
        try:
            logger.info("Warm restart: loading shared history checkpoint %s", history_checkpoint)
            sim = load_sim_checkpoint(history_checkpoint).simulation
        except (RuntimeError, RecursionError, EOFError, pickle.UnpicklingError, TypeError) as exc:
            logger.warning(
                "Could not load history checkpoint at %s (%s). "
                "Deleting it and rerunning the cold history path.",
                history_checkpoint,
                exc,
            )
            history_checkpoint.unlink(missing_ok=True)
            sim = None
        if sim is not None:
            sim.configuration.t_max = total_steps
            sim.prehooks = [link_prehook]
            apply_growth_limits(sim, gl_indices, args.growth_limit_up, args.growth_limit_down, args.steps_per_year)
            run_with_checkpoints(
                sim,
                total_steps=total_steps,
                checkpoint_dir=checkpoint_dir,
                save_years=cp_years,
                checkpoint_retention=checkpoint_retention,
            )

    if sim is None and args.warm_start:
        logger.info(
            "Warm-start cold path: simulating history through %s (%d steps)",
            args.history_boundary,
            history_steps,
        )
        sim = build_simulation(
            data,
            timesteps=total_steps,
            seed=args.seed,
            firms_bundles=firms_bundles,
            use_candidate_baseline=args.use_candidate_baseline,
        )
        sim.prehooks.append(link_prehook)
        apply_growth_limits(sim, gl_indices, args.growth_limit_up, args.growth_limit_down, args.steps_per_year)
        run_with_checkpoints(
            sim,
            total_steps=history_steps,
            checkpoint_dir=checkpoint_dir,
            save_years=set(),
            checkpoint_retention=checkpoint_retention,
        )
        if history_checkpoint is not None:
            save_sim_checkpoint(sim, history_checkpoint.resolve(), args.history_boundary)
        logger.info("Warm-start cold path: simulating future years through %s", args.sim_end_year)
        run_with_checkpoints(
            sim,
            total_steps=total_steps,
            checkpoint_dir=checkpoint_dir,
            save_years=cp_years,
            checkpoint_retention=checkpoint_retention,
        )
    elif sim is None:
        sim = build_simulation(
            data,
            timesteps=total_steps,
            seed=args.seed,
            firms_bundles=firms_bundles,
            use_candidate_baseline=args.use_candidate_baseline,
        )
        sim.prehooks.append(link_prehook)
        apply_growth_limits(sim, gl_indices, args.growth_limit_up, args.growth_limit_down, args.steps_per_year)
        logger.info("Running provincial macroABM for %d timesteps", total_steps)
        sim.run()

    assert sim is not None

    production_by_region = collect_production(
        sim, args.sim_end_year, args.sim_start_year, args.steps_per_year,
        args.cims_base_year, args.cims_year_step,
    )
    writer = CIMSProductionWriter(
        cims_model_dir=args.cims_model_dir.resolve(),
        output_dir=args.feedback_dir.resolve(),
        sector_map=sector_map,
        anchor_year=args.cims_base_year + args.cims_year_step,
        relaxation=args.feedback_relaxation,
        previous_output_dir=(
            args.previous_feedback_dir.resolve() if args.previous_feedback_dir is not None else None
        ),
    )
    if args.feedback_relaxation < 1.0 and args.previous_feedback_dir is not None:
        logger.info(
            "Under-relaxing macroABM->CIMS feedback: alpha=%s, blending with %s",
            args.feedback_relaxation, args.previous_feedback_dir,
        )
    written = writer.write(production_by_region, itr=args.iteration)
    logger.info("Wrote %d CIMS feedback policy files", len(written))

    for province, df in production_by_region.items():
        df.to_csv(output_dir / f"production_annual_{args.iteration}_{province}.csv")

    growth_by_period = compute_gdp_growth_by_period(
        sim, periods, args.sim_start_year, args.steps_per_year,
    )
    with open(output_dir / "gdp_growth_by_period.json", "w", encoding="utf-8") as f:
        json.dump(growth_by_period, f, indent=2)
    logger.info("Saved per-period provincial GDP growth for %d provinces", len(growth_by_period))

    growth = compute_gdp_growth(sim)
    with open(output_dir / "gdp_growth.json", "w", encoding="utf-8") as f:
        json.dump(growth, f, indent=2)
    logger.info("Saved provincial GDP growth for %d provinces", len(growth))

    if args.save_shallow_h5:
        export_shallow_h5(sim, output_dir / args.shallow_h5_filename)

    if args.save_export_checkpoint:
        export_checkpoint = output_dir / EXPORT_CHECKPOINT_NAME
        save_sim_checkpoint(sim, export_checkpoint, args.sim_end_year)
        logger.info("Saved export checkpoint for deferred HDF5 write: %s", export_checkpoint)


def collect_production(sim: Simulation, end_year: int, sim_start_year: int, steps_per_year: int,
                       base_year: int, year_step: int) -> dict:
    """Return ``{province_code: production_DataFrame}`` from each province's firms."""
    production_by_region = {}
    for country in sim.countries.values():
        province = _province_code(country.country_name)
        df = country.firms.get_production_annual(
            current_year=end_year,
            sim_start_year=sim_start_year,
            steps_per_year=steps_per_year,
            base_year=base_year,
            year_step=year_step,
        )
        if not df.empty:
            production_by_region[province] = df
    return production_by_region


if __name__ == "__main__":
    main()
