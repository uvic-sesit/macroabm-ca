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
from macromodel.configurations.growth_baseline_preset import (
    apply_candidate_growth_baseline,
    observed_labour_force_index,
)
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


# Macro industry standing in for households in the CER sector map (residential proxy).
_HOUSEHOLD_PROXY_ROW = "L"
# Industries that may be EXPORT-pinned but must never receive a production target from the
# same index. Electricity qualifies because CER's international export path and its
# generation path move in opposite directions -- exports to 0.892x of the 2014 anchor by
# 2050, generation to 2.07x -- so reusing one matrix for both pins output to the wrong path.
# C19 (refined petroleum) joins for the opposite reason to electricity: its index is 1.0,
# meaning EXPORTS HELD FLAT at the base-year level while production follows domestic demand
# (which falls under Net-zero, as CER's own refined-product path does -- 0.895x by 2050).
# Under residual targeting a 1.0 index would instead hold PRODUCTION flat and let exports
# absorb the falling domestic demand, which is the artefact being removed: C19 exports to
# ROW ran 10.9 -> 37.6 $bn/yr and the exported share 13% -> 41% while unpinned.
# F/G/L/O/P/Q join for the same reason as C19: non-tradeable services whose ROW exports
# grew 956x-139,474x over 2025-2050 on the frozen base-year composition. Their index is
# 1.0 (exports flat at base year), and none of them ever receives a CER production path,
# so exclusion from production targeting is a no-op today; membership here is what routes
# their flat index to export-mode instead of a production pin.
_PRODUCTION_TARGET_EXCLUDED = {"D", "C19", "F", "G", "L", "O", "P", "Q"}


def _quantity_anchor_spec(base_q, now_q, base_total: float, floor: float):
    """Choose how one (row, fuel) pair is anchored: growth index, level increment, neither.

    THE GUARD.  Both quantity anchors -- firms' and households' -- turn CER's demand into
    a GROWTH INDEX ``now / base``, whose only protection is ``base > 0``.  Any positive
    base passes that however tiny, so a pair that is essentially zero in the anchor year
    and real by the target year (electric vehicles in Prince Edward Island, say) produces
    an enormous index.  Measured per province: up to 1800x, with PE and NL at a 95th
    percentile near 280.  Firms are then instructed to buy ~1800x their base-year
    electricity and the run collapses.

    Aggregation is what hides this today -- summing four Atlantic provinces gives every
    pair a non-trivial denominator -- so it is a latent fragility in the anchor rather
    than a property of per-province data.  De-aggregation merely exposes it, and this
    guard is what unblocks per-province linkage data generally.

    *floor* is deliberately SCALE-FREE: a pair is negligible when its anchor-year quantity
    is below that fraction of the row's TOTAL anchor-year energy demand, so the test means
    "this fuel is negligible for this industry" rather than "this number is small", which
    no defensible absolute threshold could say.  ``floor=0.0`` disables the guard exactly
    (nothing is below zero), leaving the index path bit-identical to before it existed.

    Negligible pairs are converted, not dropped: dropping them silently discards real CER
    demand.  The increment is CER's LEVEL change over the same denominator, which is
    well defined at a zero base -- the agents convert it back to model units against their
    own anchor-year energy (see ``Firms.anchor_energy_quantities``).

    Returns ``("index", v)``, ``("increment", v)``, or ``None`` when the pair carries
    nothing to anchor.
    """
    base_q = float(base_q)
    now_q = float(now_q)
    if not np.isfinite(now_q) or not np.isfinite(base_q):
        return None
    negligible = (
        floor > 0.0
        and base_total > 0.0
        and np.isfinite(base_total)
        and base_q < floor * base_total
    )
    if not negligible:
        if base_q > 0.0 and now_q > 0.0:
            return ("index", now_q / base_q)
        return None
    delta = (now_q - base_q) / base_total
    # Below this the pair is negligible at BOTH ends -- no level change to carry, and
    # the model's own dynamics are a better answer than a numerically empty target.
    if abs(delta) < 1e-9:
        return None
    return ("increment", delta)


def _row_energy_total(anchor_frame, row_code: str, energy_codes, industries) -> float:
    """Total anchor-year energy demand of one row, over the fuels the anchor can reach.

    The denominator of :func:`_quantity_anchor_spec`, and it has to cover the SAME fuel
    set the agent sums on its side, or the increment changes meaning between the two.  So
    this excludes the self-input for exactly the reason the anchor loops do.
    """
    total = 0.0
    for code in energy_codes:
        if code == row_code or code not in industries:
            continue
        if code not in anchor_frame.columns or row_code not in anchor_frame.index:
            continue
        v = float(anchor_frame.loc[row_code, code])
        if np.isfinite(v) and v > 0.0:
            total += v
    return total


def build_link_prehook(
    reader: CIMSDataReader,
    sector_map: SectorMap,
    industries: list[str],
    years: list[int],
    itr: str,
    *,
    anchor_year: int | None = None,
    reset_multipliers: bool = True,
    linkage_owns_coefficients: bool = False,
    capacity_floor: bool = False,
    capacity_floor_per_province: bool = False,
    linkage_data_per_province: bool = False,
    capacity_factor_from_cer: bool = False,
    electricity_own_use: bool = False,
    household_energy_quantities: bool = False,
    firm_energy_quantities: bool = False,
    quantity_anchor_floor: float = 0.0,
    row_electricity_split: dict | None = None,
    row_electricity_split_strict: bool = False,
    row_electricity_split_signal: float = 0.0,
    capacity_ceiling_margin: float = 0.0,
    capacity_gate_margin: float = 0.0,
    capacity_gate_provinces: set[str] | None = None,
    transition_capital: bool = False,
    export_demand_pinning: bool = False,
    exogenous_fossil_production: bool = False,
    investment_tax_credit: bool = False,
    steps_per_year: int = 4,
    additive_intensity: bool = False,
    household_energy_shares: bool = False,
):
    """Create a simulation pre-hook that calls firms.link() at milestone years.

    The hook loads the anchor-year and current-year energy/capital intensity
    matrices and passes them to ``firms.link()`` so it can set energy-per-output
    directly (index-anchored to ``anchor_year``).
    """
    energy_codes = sector_map.energy_bundle_for(industries)
    comparable_codes = sector_map.comparable_for(industries)
    energy_indices = [industries.index(code) for code in energy_codes if code in industries]
    quantity_anchor_floor = float(quantity_anchor_floor or 0.0)
    milestone = set(years)
    if anchor_year is None and years:
        anchor_year = min(years)

    def link_prehook(sim: Simulation, year: int, month: int) -> None:
        if month != 1 or year not in milestone:
            return

        # ROW electricity split: route ROW's D purchases to provinces by CER's own
        # (international exports + electrolysis) shares, refreshed per linkage year.
        # This is the SPLIT half of treating hydrogen exports as electricity leaving in
        # another form; the LEVEL half is the electrolysis-inclusive export index on the
        # ROW agent.  One goods market for the whole simulation, so set once per year,
        # outside the per-country loop.  `row_electricity_split` maps
        # year -> {province_code: share}; the shares vector is resolved against the same
        # sorted country axis the trade proportions use, with ROW's own slot at zero.
        if row_electricity_split and year in row_electricity_split:
            clearer = sim.goods_market.functions.get("clearing")
            d_index = industries.index("D") if "D" in industries else None
            if clearer is None or not hasattr(clearer, "set_row_split_override"):
                logger.warning(
                    "ROW electricity split: clearer does not support the override; skipping.")
            elif d_index is None:
                logger.warning("ROW electricity split: no 'D' industry; skipping.")
            else:
                axis = sorted(list(sim.countries.keys()) + ["ROW"])
                vec = np.zeros(len(axis))
                matched = {}
                for code, share in row_electricity_split[year].items():
                    for pos, name in enumerate(axis):
                        text = str(name)
                        if text != "ROW" and (text.endswith(f"_{code}") or text == code):
                            vec[pos] = float(share)
                            matched[code] = round(float(share), 4)
                            break
                if vec.sum() <= 0.0:
                    logger.warning(
                        "ROW electricity split: no province resolved for year %s; skipping.",
                        year)
                else:
                    clearer.set_row_split_override(
                        {d_index: vec},
                        strict=row_electricity_split_strict,
                        signal_shortfall=float(row_electricity_split_signal or 0.0),
                    )
                    logger.info(
                        "ROW electricity split: year=%s D origin shares set (strict=%s, "
                        "signal=%.2f): %s",
                        year, row_electricity_split_strict,
                        float(row_electricity_split_signal or 0.0), matched)
        for country in sim.countries.values():
            province = _province_code(country.country_name)
            cims_region = sector_map.macro_region_to_cims.get(province)
            if cims_region is None or not reader.available(itr, year, cims_region):
                continue
            province_code = province.rsplit("_", 1)[-1]

            # DEMAND-SIDE region. CER publishes every series per province -- there is no
            # "AT" in CER data -- so the CER-derived channels can read this province's own
            # file. Worth doing: energy intensity's household row at 2050 runs 0.1106 in PE
            # to 0.2388 in NL against an AT average of 0.1530.
            #
            # It also corrects a 4x OVER-CREDIT. `investment_tax_credit` is an ABSOLUTE
            # dollar amount and this loop applies it once per province, so NB/NS/PE/NL each
            # received the whole Atlantic credit: $2.207bn applied four times in 2050
            # Net-zero where $2.207bn is correct. Per province it is NB $233m, NS $974m,
            # PE $19m, NL $981m.
            #
            # `investment` and `capital_intensity` deliberately keep `cims_region`: both are
            # costed from CIMS, whose regions genuinely do aggregate the Atlantic four, and
            # the extractor writes no per-province file for them. Reading one would return
            # ZERO rather than raising and silently delete the signal.
            demand_region = cims_region
            if linkage_data_per_province and reader.demand_available(itr, year, province_code):
                demand_region = province_code
                if demand_region != cims_region:
                    # POSITIVE confirmation, not just absence of a warning: this flag only
                    # changes anything for the four provinces CIMS aggregates, so a run that
                    # silently kept reading "AT" would otherwise look identical to success.
                    logger.info(
                        "per-province CER data: province=%s year=%s (was CIMS region %s)",
                        province_code, year, cims_region,
                    )
            elif linkage_data_per_province:
                logger.warning(
                    "linkage_data_per_province is ENABLED but no per-province CER data for "
                    "%s (itr=%s year=%s) -- falling back to CIMS region %s.",
                    province_code, itr, year, cims_region,
                )

            rq = reader.get_requested_quantities(itr, year, demand_region)

            # Prefer this province's OWN capacity file when per-province floors are on and
            # one exists. CIMS aggregates NB/NS/PE/NL into "AT", and the floor inherited
            # that even though its path comes from CER, which publishes per province: all
            # four were floored at 5.6405 in 2050 Net-zero against own CER generation
            # ratios of 1.44 (NB) to 6.95 (NS), over-building New Brunswick and
            # under-building Nova Scotia. Falls back to the CIMS region when the
            # per-province file is absent, so an older processed directory still runs.
            # `_province_code` returns the MACRO region key ("CAN_NB"), while the processed
            # files are named by the bare province code ("NB") -- the same convention the
            # CIMS regions use, which is why the CIMS-costed lookups pass `cims_region`.
            pending_uplifts: dict[int, float] = {}
            floor_region = cims_region
            if capacity_floor_per_province and reader.capacity_available(itr, year, province_code):
                floor_region = province_code
            elif capacity_floor_per_province:
                logger.warning(
                    "capacity_floor_per_province is ENABLED but no per-province capacity "
                    "file for %s (itr=%s year=%s) -- falling back to CIMS region %s.",
                    province_code, itr, year, cims_region,
                )

            if capacity_floor and reader.capacity_available(itr, year, floor_region):
                # CER's installed-capacity path, applied as a floor on the power sector's
                # reference capital stock.  The end-use demand file cannot supply this --
                # end use is not supply -- so it comes from the separate capacity dataset.
                cap = reader.get_generation_capacity(itr, year, floor_region)
                col = cap.columns[0]
                floored = {
                    industries.index(code): float(cap.loc[code, col])
                    for code in cap.index
                    if code in industries and float(cap.loc[code, col]) > 0.0
                }
                # Capacity-factor uplift: raise the sector's capital REQUIREMENT by
                # cf(0)/cf(t), representing each MW delivering fewer MWh. Applied with a
                # capacity-indexed floor, the ceiling lands back on CER's generation path
                # while the capital stock tracks CER's MW build. See
                # Firms.set_capital_intensity_uplift for the measured effect.
                # COLLECTED HERE, APPLIED AFTER link(). `link()` rewrites
                # `base_capital_inputs_productivity_matrix` (both its own capital-factor
                # write and `_apply_transition_capital`), so an uplift written before it is
                # silently discarded -- the same trap `set_transmission_loss_rate` and the
                # firm quantity anchor are both sequenced around.
                _factors: dict[int, float] = {}
                for _col, _on in (("capacity_factor_uplift", capacity_factor_from_cer),):
                    if not _on or _col not in cap.columns:
                        continue
                    for code in cap.index:
                        if code not in industries:
                            continue
                        v = float(cap.loc[code, _col])
                        if np.isfinite(v) and v > 0.0:
                            k = industries.index(code)
                            _factors[k] = _factors.get(k, 1.0) * v
                pending_uplifts = {k: v for k, v in _factors.items() if abs(v - 1.0) > 1e-9}

                # Clear first: the floor now ACCUMULATES across calls, so without this a
                # sector dropped from one milestone's set would keep the previous value.
                country.firms.set_capacity_floor(None, None)
                for idx, value in floored.items():
                    country.firms.set_capacity_floor([idx], value)
                if floored:
                    logger.info(
                        "capacity floor: region=%s year=%s %s",
                        floor_region, year,
                        {industries[i]: round(v, 4) for i, v in sorted(floored.items())},
                    )
                # Capacity GATE: hard cap on target PRODUCTION at the CER generation
                # path x margin. The capital ceiling below bounds INVESTMENT, but the
                # limiting-capital computation uses effective (drifting) coefficients
                # and ignores utilisation, so output-per-capital escapes upward
                # (Manitoba ~1.5x of base under a binding ceiling). The gate closes
                # that valve on the production side, and cannot migrate the excess:
                # every gated province is capped at its own path. floored[] carries
                # the CAPACITY index when capacity_index_basis="capacity"; dividing by
                # the capacity_factor_uplift column (cf(0)/cf(t)) recovers the
                # GENERATION path. Off unless capacity_gate_margin > 0.
                country.firms.set_production_gate(None, None)
                # Optional province filter: gating every province at path x margin
                # (arm S9) squeezed the national total (1.88 vs CER 2.07) and re-rolled
                # BC's basin; gating ONLY the runaway province is the surgical form.
                _gate_this_province = (
                    not capacity_gate_provinces
                    or province_code in capacity_gate_provinces
                )
                if capacity_gate_margin and capacity_gate_margin > 0.0 and _gate_this_province:
                    _gated = {}
                    for idx, value in floored.items():
                        _code = industries[idx]
                        # D ONLY. The floored dict also carries the fossil supply
                        # floors (B05b/B05c), whose production is exogenously PINNED
                        # to CER's path -- a gate below the pin would clip the very
                        # path the pin exists to follow. Measured in arm S9 (gate on
                        # every floored industry): B05c's 2050 gate (1.03 x 1.1 = 1.13)
                        # sat far below its production pin (1.46).
                        if _code != "D":
                            continue
                        _cfup, _invup = 1.0, 1.0
                        if "capacity_factor_uplift" in cap.columns and _code in cap.index:
                            _v = float(cap.loc[_code, "capacity_factor_uplift"])
                            if np.isfinite(_v) and _v > 0.0:
                                _cfup = _v
                        # The capacity_index column is the multiplier-SCALED floor
                        # (index = scaled in generation_capacity); the raw CER path is
                        # value / investment_uplift. Arm S10 measured the consequence
                        # of skipping this: Manitoba's floor read 2.85 at 2050 against
                        # a CER path of ~1.27, so the gate armed at ~3.1x and never
                        # bound -- MB Net-zero growth stayed 2.13 vs CER 1.27.
                        if "investment_uplift" in cap.columns and _code in cap.index:
                            _v = float(cap.loc[_code, "investment_uplift"])
                            if np.isfinite(_v) and _v > 0.0:
                                _invup = _v
                        _gate_val = (value / _invup / _cfup) * float(capacity_gate_margin)
                        country.firms.set_production_gate([idx], _gate_val)
                        _gated[_code] = round(_gate_val, 4)
                    if _gated:
                        logger.info(
                            "capacity gate: region=%s year=%s generation path x %.2f -> %s",
                            floor_region, year, float(capacity_gate_margin), _gated,
                        )

                # Ceiling: the floor's twin, at floor x margin. One-sided guidance let
                # a slack province over-build without limit (Manitoba's D investment
                # 3.3x by 2050 against a CER generation path of 1.27x) and sell the
                # over-production to whoever the pool handed it -- including Alberta,
                # whose D intake went 11% -> 29% imported while its own buildout
                # under-ran. Off unless capacity_ceiling_margin > 0.
                country.firms.set_capacity_ceiling(None, None)
                if capacity_ceiling_margin and capacity_ceiling_margin > 0.0:
                    for idx, value in floored.items():
                        country.firms.set_capacity_ceiling(
                            [idx], value * float(capacity_ceiling_margin))
                    if floored:
                        logger.info(
                            "capacity ceiling: region=%s year=%s floor x %.2f",
                            floor_region, year, float(capacity_ceiling_margin),
                        )

                # Refund clean-electricity investment tax credits to the investing sector.
                # ITC region is resolved INDEPENDENTLY of linkage_data_per_province, because
                # reading it from an aggregate file is a bug rather than a modelling choice.
                # `credit_dollars` is an ABSOLUTE amount and this loop applies it once per
                # province, so NB/NS/PE/NL each received the WHOLE Atlantic credit: $2.207bn
                # applied four times in 2050 Net-zero where $2.207bn is correct (per province
                # NB $233m, NS $974m, PE $19m, NL $981m). Falls back to the CIMS region when
                # no per-province file exists, so an older processed directory still runs --
                # with the old, wrong behaviour, which the log line below makes visible.
                itc_region = demand_region
                if reader.investment_tax_credit_available(itr, year, province_code):
                    itc_region = province_code
                elif investment_tax_credit and itc_region != province_code:
                    logger.warning(
                        "investment_tax_credit for %s is being read from aggregate region "
                        "%s -- an absolute amount applied once per province, so every "
                        "province sharing that region receives the WHOLE credit. Re-extract "
                        "to get per-province files.",
                        province_code, itc_region,
                    )
                if investment_tax_credit and reader.investment_tax_credit_available(
                        itr, year, itc_region):
                    itc = reader.get_investment_tax_credit(itr, year, itc_region)
                    col = itc.columns[0]
                    credits = {industries.index(code): float(itc.loc[code, col])
                               for code in itc.index
                               if code in industries and float(itc.loc[code, col]) > 0.0}
                    country.apply_investment_tax_credit(credits, steps_per_year)
                elif investment_tax_credit:
                    logger.warning(
                        "investment_tax_credit is ENABLED but no table was found for "
                        "itr=%s year=%s region=%s -- the flag is having NO effect.",
                        itr, year, cims_region)

            if not reader.intensity_available(itr, year, demand_region) or not reader.intensity_available(
                itr, anchor_year, demand_region
            ):
                logger.warning(
                    "intensity_target: intensity matrices missing for region=%s year=%s (or anchor %s); "
                    "skipping link this milestone.",
                    cims_region, year, anchor_year,
                )
                continue
            if household_energy_shares:
                # Households allocate spending with a fixed weight vector, so the
                # linkage never reaches them.  Apply CER's residential fuel-share
                # changes to the household budget the same way additive_intensity
                # applies sector shares to firm coefficients.  The residential proxy
                # row of the energy-intensity matrix IS CER's residential fuel mix.
                ei_now = reader.get_energy_intensity(itr, year, demand_region)
                ei_anchor = reader.get_energy_intensity(itr, anchor_year, demand_region)
                # Transmission losses belong to the same weight write, not a second
                # pass over it.  Households buy in NOMINAL budget shares, so grossing
                # up the finished weight compounds against the real->nominal price
                # conversion below instead of composing with it: measured as real
                # household electricity +10.9% -> +35.9% off a 7.5% loss rate.  Passed
                # in here, the gross-up lands on the REAL share target, before pricing.
                hh_loss: dict[int, float] = {}
                if electricity_own_use and reader.own_use_available(itr, year, demand_region):
                    ou_hh = reader.get_electricity_own_use(itr, year, demand_region)
                    col_hh = ou_hh.columns[0]
                    for code in ou_hh.index:
                        if code in industries and float(ou_hh.loc[code, col_hh]) > 0.0:
                            hh_loss[industries.index(code)] = float(ou_hh.loc[code, col_hh])
                hh_row = _HOUSEHOLD_PROXY_ROW
                if hh_row in ei_now.index and hh_row in ei_anchor.index:
                    increments = {}
                    for j_code in energy_codes:
                        if j_code in ei_now.columns and j_code in ei_anchor.columns:
                            delta = float(ei_now.loc[hh_row, j_code]) - float(
                                ei_anchor.loc[hh_row, j_code]
                            )
                            if abs(delta) > 1e-12:
                                increments[industries.index(j_code)] = delta
                    if increments or hh_loss:
                        # Relative price of each fuel vs its anchor year, so CER's
                        # REAL (PJ) shares are converted to the nominal budget weights
                        # that deliver them.
                        prices_now = np.asarray(country.firms.ts.current("price")).ravel()
                        ind_of_firm = np.asarray(country.firms.states["Industry"])
                        if not hasattr(country.firms, "_hh_anchor_prices"):
                            country.firms._hh_anchor_prices = {}
                        rel = {}
                        for k in increments:
                            sel = ind_of_firm == k
                            if not sel.any():
                                continue
                            now = float(np.nanmean(prices_now[sel]))
                            base = country.firms._hh_anchor_prices.setdefault(k, now)
                            if base > 0 and np.isfinite(now):
                                rel[k] = now / base
                        country.households.apply_energy_share_increments(
                            increments, rel or None, loss_rates=hh_loss or None
                        )
                        logger.info(
                            "household energy shares: region=%s year=%s deltas=%s",
                            cims_region, year,
                            {industries[k]: round(v, 5) for k, v in increments.items()},
                        )

            if household_energy_quantities:
                # CER owns households' REAL electricity path, the model owns the rest.
                # rq[L, D] is households' electricity demand INCLUDING passenger
                # transport, since the passenger split routes personal-vehicle
                # electricity to the residential proxy -- so it, not CER's published
                # residential series, is the right target for this channel.
                rq_anchor = reader.get_requested_quantities(itr, anchor_year, demand_region)
                hh_targets: dict[int, float] = {}
                hh_increments: dict[int, float] = {}
                # Denominator for the negligible-pair guard: residential total energy
                # at the anchor year.  See `_quantity_anchor_spec`.
                hh_base_total = _row_energy_total(
                    rq_anchor, _HOUSEHOLD_PROXY_ROW, energy_codes, industries
                )
                for j_code in energy_codes:
                    if (
                        _HOUSEHOLD_PROXY_ROW in rq.index and j_code in rq.columns
                        and _HOUSEHOLD_PROXY_ROW in rq_anchor.index
                        and j_code in rq_anchor.columns
                        and j_code in industries
                    ):
                        spec = _quantity_anchor_spec(
                            rq_anchor.loc[_HOUSEHOLD_PROXY_ROW, j_code],
                            rq.loc[_HOUSEHOLD_PROXY_ROW, j_code],
                            hh_base_total,
                            quantity_anchor_floor,
                        )
                        if spec is None:
                            continue
                        kind, value = spec
                        if kind == "index":
                            hh_targets[industries.index(j_code)] = value
                        else:
                            hh_increments[industries.index(j_code)] = value
                if hh_targets or hh_increments:
                    prices_now = np.asarray(country.firms.ts.current("price")).ravel()
                    ind_of_firm = np.asarray(country.firms.states["Industry"])
                    px = {}
                    # Priced over the WHOLE energy set, not just the anchored fuels:
                    # the increment's denominator is total residential energy, and
                    # households need a price for every fuel in it to read that total
                    # off their nominal spending.
                    for k in energy_indices:
                        sel = ind_of_firm == k
                        if sel.any():
                            v = float(np.nanmean(prices_now[sel]))
                            if np.isfinite(v) and v > 0.0:
                                px[k] = v
                    country.households.anchor_energy_quantities(
                        hh_targets,
                        px,
                        increments=hh_increments or None,
                        energy_indices=energy_indices,
                    )
                    logger.info(
                        "household quantity anchor: region=%s year=%s targets=%s "
                        "increments (share of anchor-year residential energy)=%s",
                        cims_region, year,
                        {industries[k]: round(v, 4) for k, v in hh_targets.items()},
                        {industries[k]: round(v, 5) for k, v in hh_increments.items()},
                    )

            tc = None
            if transition_capital and reader.transition_capital_available(itr, year, cims_region):
                tc = reader.get_transition_capital(itr, year, cims_region)

            # THE firm-side linkage.  Everything else in this branch adjusts households,
            # exports or capacity; this is the only call that writes CER's engineering
            # result onto firms' input coefficients, and without it `intensity_target`
            # runs report success while applying nothing to industry.
            #
            # It was deleted by ff62756 ("Drive fossil production and export demand from
            # an external path"), which inserted the export block below where this call
            # used to sit and left `tc` assigned but unread.  Nothing failed: the
            # "link() applied" message at the end of the branch is unconditional, so
            # every run since 2026-08-06 logged a linkage it was not performing.
            # Instrumenting `firms.link` showed 0 calls against 30 such messages.
            # Keep this call and that log line together.
            country.firms.link(
                comparable_codes=comparable_codes,
                energy_bundle_codes=energy_codes,
                energy_intensity=reader.get_energy_intensity(itr, year, demand_region),
                anchor_energy_intensity=reader.get_energy_intensity(itr, anchor_year, demand_region),
                capital_intensity=reader.get_capital_intensity(itr, year, cims_region),
                anchor_capital_intensity=reader.get_capital_intensity(itr, anchor_year, cims_region),
                is_anchor=(year == anchor_year),
                reset_multipliers=reset_multipliers,
                linkage_owns_coefficients=linkage_owns_coefficients,
                additive_intensity=additive_intensity,
                transition_capital=tc,
            )

            # AFTER link(), which has just rewritten these same capital coefficients
            # (its own capital-intensity write and `_apply_transition_capital` both write
            # `base_capital_inputs_productivity_matrix`). Applied before, the uplift is
            # silently discarded -- the trap `set_transmission_loss_rate` and the firm
            # quantity anchor are both sequenced around.
            #
            # Raises D's capital REQUIREMENT by whatever part of its capacity floor is
            # the investment multiplier, so that part buys capital without also
            # licensing output. Otherwise floor and ceiling move together and the power
            # sector produces to a capacity-derived ceiling rather than CER's generation.
            if pending_uplifts:
                for _idx, _factor in pending_uplifts.items():
                    country.firms.set_capital_intensity_uplift([_idx], _factor)
                logger.info(
                    "capital-intensity uplift: region=%s year=%s %s",
                    floor_region, year,
                    {industries[i]: round(f, 4) for i, f in sorted(pending_uplifts.items())},
                )

            # Pin selected industries' EXPORT demand to a linkage-supplied path.
            # ROW splits its aggregate import forecast by frozen base-year shares, so
            # without this no sector's export path can diverge from any other's --
            # which makes oil and gas, both export-driven, unable to follow CER at all.
            # The index is NATIONAL and identical in every region file, because ROW is
            # a single global agent: a per-region index would be overwritten by
            # whichever region this loop processes last.
            if export_demand_pinning and not reader.export_demand_index_available(itr, year, cims_region):
                # A flag that is ON but finds no data is the single most common way a
                # linkage feature does nothing while the run reports success.
                logger.warning(
                    "export_demand_pinning is ENABLED but no export_demand_index was "
                    "found for itr=%s year=%s region=%s -- the flag is having NO effect.",
                    itr, year, cims_region,
                )
            if export_demand_pinning and reader.export_demand_index_available(itr, year, cims_region):
                xd = reader.get_export_demand_index(itr, year, cims_region)
                col = xd.columns[0]
                aligned = xd[col].reindex(industries).fillna(0.0).to_numpy(dtype=float)
                sim.rest_of_the_world.set_export_demand_index(aligned)
                # Electricity's index is an EXPORT path, not a production path: CER has
                # intl electricity exports falling to 0.892x of the 2014 anchor while
                # generation grows 2.07x. Same set that is held out of production
                # targets below -- one concept, applied on both sides.
                _export_mode = [i for i, code in enumerate(industries)
                                if code in _PRODUCTION_TARGET_EXCLUDED and aligned[i] > 0.0]
                sim.rest_of_the_world.set_export_target_industries(_export_mode)
                # Sector D's export index is a PHYSICAL (GW.h) ratio -- interchange
                # plus electrolysis -- so its budget must convert at D's own market
                # price or the model buys index x price-drift instead of the index
                # (measured: national D growth 2.35 vs CER 2.07, arm fix7). D ONLY:
                # the blanket conversion broke the fossil budgets (arm fix1b); see
                # RestOfTheWorld.set_real_terms_export_industries.
                _d_idx = industries.index("D") if "D" in industries else None
                if _d_idx is not None and _d_idx in _export_mode and hasattr(
                        sim.rest_of_the_world, "set_real_terms_export_industries"):
                    sim.rest_of_the_world.set_real_terms_export_industries([_d_idx])
                    logger.info(
                        "real-terms export conversion enabled for D (index %.4f)",
                        float(aligned[_d_idx]))
                if _export_mode:
                    logger.info(
                        "export-TARGETED industries (index multiplies base-year exports, "
                        "production left endogenous): %s",
                        {industries[i]: round(float(aligned[i]), 4) for i in _export_mode},
                    )
                # Drive the same industries' PRODUCTION to the same path. One matrix
                # serves both: it is CER production relative to the simulation start,
                # which is the anchor `ts.initial("production")` uses. The export
                # residual then takes whatever the home economy does not absorb, so
                # the extra output goes to EXPORTS rather than being forced into
                # domestic consumption.
                #
                # ELECTRICITY IS EXCLUDED, and the exclusion is essential. For oil and
                # gas the export path IS the production path -- both come from CER's
                # production series -- so one matrix legitimately serves both. For
                # electricity they point in OPPOSITE directions: CER has international
                # exports falling to 0.892x of the 2014 anchor by 2050 while generation
                # GROWS 2.07x. Feeding the export index into the production target put
                # every province's electricity output on a 0.892x path and collapsed the
                # run -- national D growth 0.11 against CER's 2.07, with D production
                # near zero in all ten provinces. Sector D's output is governed by the
                # capacity floor and demand, not by its export path.
                if exogenous_fossil_production:
                    _skip = {i for i, code in enumerate(industries)
                             if code in _PRODUCTION_TARGET_EXCLUDED}
                    for _c in sim.countries.values():
                        _c.firms.set_production_target(None, None)
                        for _k, _v in enumerate(aligned):
                            if _v > 0.0 and _k not in _skip:
                                _c.firms.set_production_target([_k], float(_v))
                    logger.info(
                        "exogenous production path: %s (excluded from production "
                        "targets, export-pinned only: %s)",
                        {industries[k]: round(float(v), 4)
                         for k, v in enumerate(aligned) if v > 0.0 and k not in _skip},
                        {industries[k] for k in _skip if aligned[k] > 0.0},
                    )
            if electricity_own_use and reader.own_use_available(itr, year, demand_region):
                # AFTER link(): the gross-up applies to the linkage-owned coefficients,
                # which link() has just written, and needs _linkage_owned_pairs populated.
                ou = reader.get_electricity_own_use(itr, year, demand_region)
                col = ou.columns[0]
                for code in ou.index:
                    if code in industries and float(ou.loc[code, col]) > 0.0:
                        country.firms.set_transmission_loss_rate(
                            industries.index(code), float(ou.loc[code, col])
                        )

            if firm_energy_quantities:
                # CER owns firms' REAL energy quantity path, the model owns the rest --
                # the firm-side counterpart of `household_energy_quantities`, and for
                # the same reason: writing a coefficient does not pin a quantity.
                #
                # LAST in this branch, deliberately.  It corrects the coefficient
                # `link()` wrote and `set_transmission_loss_rate` then grossed up, so
                # anything that rewrites those entries has to have run already.
                #
                # The residential proxy row is excluded: `rq[L, .]` is households'
                # demand routed through that row, and `household_energy_quantities`
                # already anchors it.  Anchoring firms in industry L to the same
                # target would count CER's residential demand a second time.
                #
                # A constant transmission-loss rate needs no adjustment here: the
                # target is an INDEX, and a rate that applies equally to the anchor
                # and the current milestone cancels out of the ratio.  A time-varying
                # rate would not, and would have to be carried into the target.
                rq_anchor_f = reader.get_requested_quantities(itr, anchor_year, demand_region)
                firm_targets: dict[tuple[int, int], float] = {}
                firm_increments: dict[tuple[int, int], float] = {}
                # EVERY row rq carries, not just `comparable_codes`.  That restriction
                # belongs to `link()`, whose intensity ratios are only defined for
                # CIMS-comparable sectors; this channel reads rq directly and needs no
                # such counterpart.  `_row_allocations` spreads each CER sector across
                # ~38 macro industries, so anchoring only the comparable rows covered
                # 10% of electricity demand (G 4.6%, H49 3.7%, C20 1.9% in AB 2050) and
                # left the other two thirds to grow with whatever the model did --
                # which is why the anchored pairs hit 96-98% of target while provincial
                # demand still ran -31% to +126% against CER.
                for i_code in rq.index:
                    if i_code == _HOUSEHOLD_PROXY_ROW or i_code not in industries:
                        continue
                    if i_code not in rq_anchor_f.index:
                        continue
                    # Denominator for the negligible-pair guard: this industry's TOTAL
                    # anchor-year energy demand.  See `_quantity_anchor_spec`.
                    base_total = _row_energy_total(
                        rq_anchor_f, i_code, energy_codes, industries
                    )
                    for j_code in energy_codes:
                        if j_code not in industries or j_code == i_code:
                            # Skip the self-input: an energy sector buying its own
                            # output cannot bootstrap in a sequential model (firms
                            # purchase before producing), the failure mode
                            # `set_transmission_loss_rate` documents.
                            continue
                        if j_code not in rq.columns or j_code not in rq_anchor_f.columns:
                            continue
                        spec = _quantity_anchor_spec(
                            rq_anchor_f.loc[i_code, j_code],
                            rq.loc[i_code, j_code],
                            base_total,
                            quantity_anchor_floor,
                        )
                        if spec is None:
                            continue
                        kind, value = spec
                        pair = (industries.index(i_code), industries.index(j_code))
                        if kind == "index":
                            firm_targets[pair] = value
                        else:
                            firm_increments[pair] = value
                if firm_targets or firm_increments:
                    country.firms.anchor_energy_quantities(
                        firm_targets,
                        increments=firm_increments or None,
                        energy_indices=energy_indices,
                    )
                    by_fuel: dict[str, list[float]] = {}
                    for (_i, _j), _v in firm_targets.items():
                        by_fuel.setdefault(industries[_j], []).append(_v)
                    inc_by_fuel: dict[str, list[float]] = {}
                    for (_i, _j), _v in firm_increments.items():
                        inc_by_fuel.setdefault(industries[_j], []).append(_v)
                    logger.info(
                        "firm quantity anchor: region=%s year=%s pairs=%d "
                        "median index by fuel=%s | increment pairs=%d "
                        "median increment by fuel (share of anchor-year energy)=%s",
                        cims_region, year, len(firm_targets),
                        {k: round(float(np.median(v)), 4)
                         for k, v in sorted(by_fuel.items())},
                        len(firm_increments),
                        {k: round(float(np.median(v)), 5)
                         for k, v in sorted(inc_by_fuel.items())},
                    )
                else:
                    logger.warning(
                        "firm_energy_quantities is ENABLED but no (industry, energy) "
                        "target could be built for itr=%s year=%s region=%s -- the "
                        "flag is having NO effect.", itr, year, cims_region,
                    )
            logger.info(
                "link() applied (intensity_target): province=%s cims_region=%s year=%s", province, cims_region, year
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


def apply_import_limits(
    sim: Simulation, industry_indices: list[int], *, mode: str = "share"
) -> None:
    """Cap ROW exports (= domestic imports) of the given industries at their base-year share.

    Applied after the simulation is built or restored (and on every iteration), so it
    also configures sims restored from checkpoints written before the cap existed.
    A no-op when no sectors are given.  See
    :meth:`RestOfTheWorld.set_import_limits` for the semantics.
    """
    if not industry_indices:
        return
    sim.rest_of_the_world.set_import_limits(industry_indices, mode=mode)
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


def industry_indices_for(codes: str | None, industries: list[str]) -> list[int]:
    """Resolve a comma-separated list of macro sector codes to industry indices.

    Unknown codes are skipped with a warning rather than failing the run, matching how
    a missing sector elsewhere in the runner is handled.
    """
    wanted = [c.strip() for c in str(codes or "").split(",") if c.strip()]
    indices: list[int] = []
    for code in wanted:
        if code in industries:
            indices.append(industries.index(code))
        else:
            logger.warning("Import limit sector %r not in model industries; ignoring.", code)
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
    index_by_province: dict[str, list[float]] | None = None,
) -> None:
    """Apply the candidate-baseline exogenous household demand growth overlay.

    With *index_by_province*, each province's demand follows ITS OWN path instead of one
    national rate, and `growth_rate` is ignored.

    WHY THAT IS THE RIGHT SHAPE.  `ExogenousLabourForcePath` does not create people: it
    reclassifies existing individuals NOT_ECONOMICALLY_ACTIVE -> UNEMPLOYED and leaves
    `n_individuals` alone, so the labour-force index adds JOB-SEEKERS WITHOUT ADDING
    CONSUMERS.  But the index is StatCan LFS data, and provincial labour-force growth over
    2015-2024 was mostly POPULATION growth -- BC 2.23%/yr, PE 2.34%/yr, largely
    immigration -- and those people brought their consumption with them.  Feeding a
    population-driven series into the supply side alone is the defect: provincial
    unemployment then drifts by (labour-force growth - employment growth), correlation
    +0.93 across the ten provinces, and BC reaches 17.7% unemployment by 2023 against
    about 5% in reality.

    Passing the SAME index to both sides fixes the asymmetry and fixes the magnitude with
    it -- there is no rate to tune.  It should also be self-limiting where a flat national
    rate was not: the previous +2%/yr default outran +0.72%/yr labour supply and drove the
    labour share up without bound, whereas demand and supply here grow together.
    """
    for name, country in model.countries.items():
        frame = country.exogenous.national_accounts_during
        if index_by_province is not None:
            path = index_by_province.get(str(name))
            if path is None:
                logger.warning("household demand overlay: no index for %s; leaving it flat.", name)
                continue
            fac = np.asarray(path, dtype=float)
            # The index is built for timesteps+1 quarters and the accounts frame need not
            # match; hold the last value rather than truncating the tail to zero.
            if len(fac) < len(frame):
                fac = np.concatenate([fac, np.full(len(frame) - len(fac), fac[-1])])
            fac = fac[:len(frame)]
            fac = fac / fac[0]
            # The provincial index carries POPULATION growth only. `growth_rate` is the
            # autonomous component on top of it -- demand per head rising over time -- and
            # it used to be discarded here, which made the parameter a silent no-op in every
            # run that passes an index (i.e. all of them). Compounding the two keeps the
            # supply/demand symmetry that fixes BC/PE while still giving the model an
            # autonomous demand driver, which is the only thing that moves real growth on a
            # demand-bound base. At growth_rate = 0.0 this multiplies by exactly 1.0, so
            # existing runs are bit-identical.
            fac = fac * (1.0 + growth_rate) ** (np.arange(len(frame)) / 4.0)
        else:
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
    use_obps_reg: bool = False,
    use_candidate_baseline: bool = False,
    labour_force_growth: float | None = None,
    labour_force_cap: dict[str, float] | None = None,
    capital_target_fraction: float | None = None,
    capital_rolling_reference: bool | None = None,
    household_demand_growth: float | None = None,
    household_demand_from_labour_force: bool = False,
    exogenous_energy_prices: bool = False,
    tfp_base_growth_rate: float | None = None,
    tfp_investment_effectiveness: float | None = None,
    price_setting_noise_std: float | None = None,
    price_setting_speed_gf: float | None = None,
    labour_index_base_year: int | None = None,
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
        len(data.industries), timesteps=timesteps, seed=seed, firms_bundles=firms_bundles,
        use_obps_reg=use_obps_reg,
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
                labour_force_cap=labour_force_cap,
                capital_target_fraction=capital_target_fraction,
                capital_rolling_reference=capital_rolling_reference,
                labour_index_base_year=labour_index_base_year,
            )
    if exogenous_energy_prices:
        # CER supplies price trajectories for the energy bundle; pin those industries'
        # prices to them so the endogenous price channel cannot feed back into demand.
        # SectorExogenousPriceSetter overrides only the industries present as columns in
        # the attached SectorExoPrices table -- everything else keeps DefaultPriceSetter.
        for province in CANADIAN_PROVINCES:
            config.country_configurations[province].firms.functions.prices.name = (
                "SectorExogenousPriceSetter"
            )
        logger.info("Exogenous energy prices enabled (SectorExogenousPriceSetter)")

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

    if price_setting_speed_gf is not None:
        # Pass-through of a province's OWN estimated PPI inflation into every firm's price.
        # The shipped 1.0 is FULL pass-through, and PPI is itself an index of those same
        # firm prices, so prices -> PPI -> expected inflation -> prices with no anchor in
        # between (demand-pull and cost-push are both zeroed). That is a unit root with
        # positive feedback: each province's price LEVEL self-reinforces in whatever
        # direction accumulated noise sends it.
        #
        # Measured on the 2050 runs: Ontario's price level reaches 2.3x Saskatchewan's
        # within a single scenario, and 91% of Ontario's 43 industries sit above 1.5x its
        # Current Measures level under Net-zero while 90% of Saskatchewan's sit below 0.8x
        # -- uniform across sectors, i.e. a province-wide level drift with no economic
        # driver. Because real GDP is nominal deflated by CPI, that drift is what produced
        # a spurious -15% national real GDP under Net-zero.
        #
        # Values below 1.0 damp the feedback; 0.0 removes the channel entirely and leaves
        # prices moving only on noise.
        for province in CANADIAN_PROVINCES:
            prices_fn = config.country_configurations[province].firms.functions.prices
            prices_fn.parameters["price_setting_speed_gf"] = float(price_setting_speed_gf)
        logger.info(
            "Price inflation pass-through overridden: price_setting_speed_gf=%s (shipped 1.0)",
            price_setting_speed_gf,
        )

    if price_setting_noise_std is not None:
        # Idiosyncratic price noise. `DefaultPriceSetter` multiplies each firm's PREVIOUS
        # price by (1 + N(0, std)) every step, and both economic terms that could pull a
        # firm back -- demand-pull and cost-push -- are multiplied by speeds of 0.0 in the
        # shipped configuration. So the executing rule is a geometric random walk with no
        # level anchor, and prices for the SAME industry in different provinces drift apart
        # without bound: measured median max/min across provinces of 1.48 (2015) rising to
        # 7.84 (2050), with log(dispersion)/sqrt(t) flat at ~0.17 (the random-walk
        # signature) and an implied per-step sd of 0.0549 against the configured 0.05.
        #
        # Dispersion scales as exp(3.08 * std * sqrt(t)) for 10 provinces, so this only
        # slows the divergence rather than bounding it -- 0.01 gives roughly 1.5x at 2050
        # instead of 7.8x. Bounding it properly needs a cross-province anchor, which is a
        # structural change and deliberately not made here.
        #
        # Applies ONLY to industries priced endogenously: the CER-pinned sectors
        # (SectorExogenousPriceSetter) are overridden before this rule is reached.
        for province in CANADIAN_PROVINCES:
            prices_fn = config.country_configurations[province].firms.functions.prices
            prices_fn.parameters["price_setting_noise_std"] = float(price_setting_noise_std)
        logger.info(
            "Price-setting noise overridden: price_setting_noise_std=%s (shipped 0.05)",
            price_setting_noise_std,
        )

    sim = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=config)
    if use_candidate_baseline:
        _extend_exogenous_national_accounts(sim, required_length=timesteps + 1)
        # The overlay's default (+2%/yr) outruns labour-supply growth (~0.72%/yr), so firms
        # bid wages up against a hard supply limit and the labour share climbs without
        # bound.  Overridable so the two can be tested at compatible rates.
        _hh_index = None
        if household_demand_from_labour_force:
            _hh_index = observed_labour_force_index(
                n_quarters=timesteps + 1, post_sample_growth=labour_force_growth,
                growth_cap=labour_force_cap,
                **({"base_year": labour_index_base_year}
                   if labour_index_base_year is not None else {}))
            logger.info(
                "Household demand follows each province's OWN labour-force index "
                "(2050 index: %s)",
                {k: round(v[-1], 3) for k, v in sorted(_hh_index.items())})
        _apply_household_demand_overlay(
            sim,
            growth_rate=(
                _HOUSEHOLD_DEMAND_GROWTH if household_demand_growth is None
                else float(household_demand_growth)
            ),
            index_by_province=_hh_index,
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
    p.add_argument(
        "--linkage-owns-coefficients",
        action="store_true",
        help="Hold endogenous technical-coefficient growth off the (industry, input) "
             "pairs the linkage writes, so the CIMS/CER intensity path is authoritative "
             "for those and drift applies only to unlinked coefficients.",
    )
    p.add_argument(
        "--household-energy-shares",
        action="store_true",
        help="Apply CER's residential fuel-share changes to the household consumption "
             "weight vector. Without it the linkage never reaches households: their fuel "
             "mix stays frozen at the base year while firms follow CER.",
    )
    p.add_argument(
        "--additive-intensity",
        action="store_true",
        help="Apply CER/CIMS fuel-mix changes as ADDITIVE share increments on the "
             "sector's own total-energy coefficient, instead of multiplying the model's "
             "baseline by the intensity ratio. Ratio targeting explodes wherever model "
             "and CER base-year fuel shares differ.",
    )
    p.add_argument(
        "--electricity-own-use",
        action="store_true",
        help="Give the power sector a transmission-loss coefficient on its own output, so "
             "generation exceeds delivered demand as it does in reality. Without it, model "
             "production tracks demand exactly and cannot reach CER's generation path.",
    )
    p.add_argument(
        "--investment-tax-credit",
        action="store_true",
        help="Refund clean-economy investment tax credits (Clean Technology, Clean "
             "Electricity, CCUS) to the investing sector via the production-tax channel. "
             "Rates are headline statutory rates: treat the fiscal cost as an upper bound.",
    )
    p.add_argument(
        "--exogenous-fossil-production",
        action="store_true",
        help="Drive the export-pinned industries' PRODUCTION to the linkage's path "
             "instead of leaving it demand-determined. Those sectors become exogenous "
             "INPUTS to the run rather than results; say so wherever the numbers are used. "
             "Requires --export-demand-pinning, which supplies the path and routes the "
             "extra output to exports.",
    )
    p.add_argument(
        "--export-demand-pinning",
        action="store_true",
        help="Pin selected industries' ROW export demand to a linkage-supplied index "
             "(export_demand_index_*.csv). Without it ROW splits its aggregate import "
             "forecast by FROZEN base-year shares, so no sector's export path can diverge "
             "from any other's -- which makes export-driven sectors like oil and gas "
             "unable to follow an external scenario at all.",
    )
    p.add_argument(
        "--transition-capital",
        action="store_true",
        help="Charge sectors the capital cost of switching fuel: raises their machinery, "
             "equipment and construction requirements, so how fast they can switch is "
             "paced by what they can finance rather than by the fuel price alone.",
    )
    p.add_argument(
        "--capacity-floor",
        action="store_true",
        help="Floor the power sector's reference capital stock at CER's installed-capacity "
             "path, so the capacity build shows up as investment and lifts the capital "
             "ceiling on generation.",
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
    if intensity_anchor_year not in years:
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
        anchor_year=intensity_anchor_year,
        reset_multipliers=args.reset_multipliers,
        linkage_owns_coefficients=args.linkage_owns_coefficients,
        capacity_floor=args.capacity_floor,
        electricity_own_use=args.electricity_own_use,
        transition_capital=args.transition_capital,
        export_demand_pinning=args.export_demand_pinning,
        exogenous_fossil_production=args.exogenous_fossil_production,
        investment_tax_credit=args.investment_tax_credit,
        steps_per_year=args.steps_per_year,
        additive_intensity=args.additive_intensity,
        household_energy_shares=args.household_energy_shares,
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
