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
# Government demand overlay (2026-10-29): real government consumption follows the same
# per-province labour-force index as household demand (population only, no autonomous term).
_GOV_DEMAND_COLS = [
    "Real Government Consumption (Value)",
    "Government Consumption (Value)",
]

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

# Energy producers whose purchases of their own output are fuel use in the per-unit target.
_SELF_FUEL_CODES = {"B05", "B06", "C19"}
# (buyer, good) purchases that are feedstock, not fuel: refineries' crude oil from B06.
_FEEDSTOCK_PAIRS = {("C19", "B06")}
# Minimum anchor-year share of generation for a fuel's COPPER ratio to be applied.
_GENMIX_MIN_SHARE = 0.05


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
    household_energy_anchor_basis: str = "realised",
    household_energy_order_margin: float = 0.1,
    household_quantity_conserve_budget: bool = False,
    firm_energy_quantities: bool = False,
    firm_energy_multiplier_cap: float | None = None,
    firm_energy_target_mode: str = "quantity",
    firm_energy_fuel_prices: dict | None = None,
    firm_energy_generation_mix: dict | None = None,
    quantity_anchor_floor: float = 0.0,
    quantity_anchor_conserve_total: bool = False,
    row_electricity_split: dict | None = None,
    row_electricity_split_strict: bool = False,
    row_electricity_split_signal: float = 0.0,
    capacity_ceiling_margin: float = 0.0,
    capacity_gate_margin: float = 0.0,
    capacity_gate_provinces: set[str] | None = None,
    d_production_floor_margin: float = 0.0,
    d_production_floor_provinces: set[str] | None = None,
    transition_capital: bool = False,
    export_demand_pinning: bool = False,
    exogenous_fossil_production: bool = False,
    investment_tax_credit: bool = False,
    steps_per_year: int = 4,
    additive_intensity: bool = False,
    household_energy_shares: bool = False,
    extra_export_mode_industries: set[str] | None = None,
    feedstock_pairs: set[tuple[str, str]] | None = None,
    intensity_only_sectors: set[str] | None = None,
):
    """Create a simulation pre-hook that calls firms.link() at milestone years.

    ``intensity_only_sectors``: buyer industries EXEMPT from the firm quantity anchor
    (the LEVEL pin) while keeping the intensity target ``link()`` writes for every fuel
    (the per-unit LEVEL and MIX of the source).  Their energy purchases then scale
    with their own output at the source's intensity and mix: the source sets energy
    per unit of output, the model sets output.  Opt-in (WTC supply-side sensitivity,
    doc 5h).  The exempt rows are also left out of the source-side totals the anchor
    conserves (``quantity_anchor_conserve_total``), on both sides of the ratio, so
    the anchored total of the REMAINING rows still grows at the source's rate over
    those same rows.  Measured on the WTC ``_CP_TT_EX`` pair (2026-10-17): the
    conserve step holds Alberta's anchored electricity total to the source's index
    (model 1.150 vs CIMS 1.159 in 2040), but land transport's electricity base in
    the model is 4.5% of Alberta's industrial electricity against 0.5% for CIMS's
    freight, so CIMS's 7-15x freight electrification lands on a 9x oversized base
    and the rescale pushes every other anchored row to 0.78-0.80 of its baseline
    purchases in the arm -- chemicals' electricity at 0.72 of 2022 against CIMS's
    1.15.  Feedstock pairs are unaffected (still exempt from both channels).

    ``feedstock_pairs``: (buyer industry, energy good) pairs exempt from BOTH the
    intensity target and the firm quantity anchor.  A refinery's B06 column is
    crude feedstock, chemicals' B06 column is gas feedstock; neither is end-use
    energy, neither appears in the source's demand file, yet the anchor was
    scaling the whole coefficient by the source's industrial natural-gas path
    (2022 scheme: "Natural Gas" -> B06).  Measured on the 2026-08-25 CORE pair at
    2050: NB C19 crude input 6.0 -> 1.7 $bn at flat output under the Net-zero
    demand path (value added +$6.3bn), while AB/BC/SK refineries ran crude inputs
    ABOVE output (0.51 -> 1.14 of output in AB, GVA -$5.2bn).  Exempt pairs keep
    their IO coefficient and scale with output; the small genuine energy part of
    the purchase (refinery fuel gas) no longer follows the source.  Opt-in; None
    is bit-identical.

    The hook loads the anchor-year and current-year energy/capital intensity
    matrices and passes them to ``firms.link()`` so it can set energy-per-output
    directly (index-anchored to ``anchor_year``).

    ``extra_export_mode_industries`` extends ``_PRODUCTION_TARGET_EXCLUDED`` per
    run: codes whose export index is routed to export-mode (ROW demand pinning)
    rather than becoming a production target.  Opt-in from the caller so the
    shipped set stays untouched for every arm that does not ask (first user:
    the C10T12 flat export pin, arm IESP).
    """
    export_mode_excluded = _PRODUCTION_TARGET_EXCLUDED | set(extra_export_mode_industries or ())
    feedstock_pairs = set(feedstock_pairs or ())
    if feedstock_pairs:
        logger.info("feedstock pairs exempt from the linkage: %s", sorted(feedstock_pairs))
    intensity_only_sectors = {str(c).strip() for c in (intensity_only_sectors or ()) if str(c).strip()}
    if intensity_only_sectors:
        _unknown = sorted(c for c in intensity_only_sectors if c not in industries)
        if _unknown:
            raise ValueError(
                f"intensity_only_sectors names industries the model does not have: {_unknown}"
            )
        if not firm_energy_quantities:
            logger.warning(
                "intensity_only_sectors=%s set without firm_energy_quantities: nothing is "
                "anchored by level anyway, the key has NO effect.", sorted(intensity_only_sectors)
            )
        logger.info(
            "INTENSITY-ONLY sectors (exempt from the firm quantity anchor; CIMS intensity and "
            "mix per fuel kept, level follows their own output; excluded from the "
            "conserve-total set on both sides): %s", sorted(intensity_only_sectors)
        )
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

                # D PRODUCTION FLOOR: the gate's under-utilisation twin. A province
                # whose demand expectations lag a fast external build-out leaves its
                # capacity-floored capital idle (Alberta NZ: output 0.66 of CER's
                # generation path by 2050 while being the CHEAPEST seller -- sold out
                # at pool time, marginal MWh imported at 3x its price). Lift target
                # production to the CER generation path (same value/_invup/_cfup
                # recovery as the gate, margin usually 1.0); the market absorbs the
                # supply by displacing imports because the province is already
                # price-competitive. D only, selected provinces only, floor never
                # reduces an already-higher target, and the gate still wins above it.
                country.firms.set_production_floor(None, None)
                if (
                    d_production_floor_margin
                    and d_production_floor_margin > 0.0
                    and d_production_floor_provinces
                    and province_code in d_production_floor_provinces
                ):
                    _pfloored = {}
                    for idx, value in floored.items():
                        _code = industries[idx]
                        if _code != "D":
                            continue
                        _cfup, _invup = 1.0, 1.0
                        if "capacity_factor_uplift" in cap.columns and _code in cap.index:
                            _v = float(cap.loc[_code, "capacity_factor_uplift"])
                            if np.isfinite(_v) and _v > 0.0:
                                _cfup = _v
                        if "investment_uplift" in cap.columns and _code in cap.index:
                            _v = float(cap.loc[_code, "investment_uplift"])
                            if np.isfinite(_v) and _v > 0.0:
                                _invup = _v
                        _floor_val = (value / _invup / _cfup) * float(d_production_floor_margin)
                        country.firms.set_production_floor([idx], _floor_val)
                        _pfloored[_code] = round(_floor_val, 4)
                    if _pfloored:
                        logger.info(
                            "D production floor: region=%s year=%s generation path x %.2f -> %s",
                            floor_region, year, float(d_production_floor_margin), _pfloored,
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
                        basis=household_energy_anchor_basis,
                        order_margin=household_energy_order_margin,
                        conserve_budget=household_quantity_conserve_budget,
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
                excluded_pairs=feedstock_pairs or None,
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
                                if code in export_mode_excluded and aligned[i] > 0.0]
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
                             if code in export_mode_excluded}
                    # PROVINCIAL production path, when the extractor wrote one: this
                    # province's own file carries a `production_index` column (its own
                    # crude + gas path). Applied to THIS country only; the national
                    # `export_index` above keeps pinning ROW. Without the column the
                    # national index drives every province, as before.
                    _prod = None
                    if reader.export_demand_index_available(itr, year, demand_region):
                        _xp = reader.get_export_demand_index(itr, year, demand_region)
                        if "production_index" in _xp.columns:
                            _prod = (_xp["production_index"].reindex(industries)
                                     .fillna(0.0).to_numpy(dtype=float))
                    if _prod is not None:
                        country.firms.set_production_target(None, None)
                        for _k, _v in enumerate(_prod):
                            if _v > 0.0 and _k not in _skip:
                                country.firms.set_production_target([_k], float(_v))
                        logger.info(
                            "exogenous production path (province %s): %s (excluded from "
                            "production targets, export-pinned only: %s)", demand_region,
                            {industries[k]: round(float(v), 4)
                             for k, v in enumerate(_prod) if v > 0.0 and k not in _skip},
                            {industries[k] for k in _skip if aligned[k] > 0.0},
                        )
                    else:
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
                _qty_rows = [] if firm_energy_target_mode == "intensity" else list(rq.index)
                if firm_energy_target_mode == "intensity":
                    # Per-unit-of-output targets (Firms.anchor_energy_intensity): the
                    # source sets each row's FUEL MIX change, as value shares at the
                    # province's anchor-year $/GJ; energy per unit of output is the
                    # model's IO base times the source's energy-intensity index. No
                    # growth ratios, rescale or increments.
                    px = (firm_energy_fuel_prices or {}).get(province, {})
                    shifts: dict[tuple[int, int], float] = {}
                    for i_code in rq.index:
                        if (i_code == _HOUSEHOLD_PROXY_ROW or i_code not in industries
                                or i_code not in rq_anchor_f.index):
                            continue
                        # Energy producers' use of their OWN output is fuel too (oil & gas
                        # producers' own gas, refineries' own refined fuels, coal own use);
                        # electricity's self-input is transmission/own use, handled elsewhere.
                        fuels = [j for j in energy_codes if j in industries
                                 and (j != i_code or j in _SELF_FUEL_CODES)
                                 and (i_code, j) not in _FEEDSTOCK_PAIRS
                                 and j in rq.columns and j in rq_anchor_f.columns]
                        def _w(frame):
                            v = {j: max(0.0, float(np.nan_to_num(frame.loc[i_code, j])))
                                 * float(px.get(j, 1.0)) for j in fuels}
                            t = sum(v.values())
                            return {j: x / t for j, x in v.items()} if t > 0.0 else None
                        w_now, w_0 = _w(rq), _w(rq_anchor_f)
                        if w_now is None or w_0 is None:
                            continue
                        ii = industries.index(i_code)
                        for j in fuels:
                            shifts[(ii, industries.index(j))] = w_now[j] - w_0[j]
                    _eii = (reader.get_energy_intensity_index(itr, year, demand_region)
                            if hasattr(reader, "get_energy_intensity_index") else None)
                    e_index = ({industries.index(c): float(v) for c, v in _eii.items()
                                if c in industries and np.isfinite(v) and v > 0.0}
                               if _eii is not None else None)
                    # Electricity sector: coal and gas per unit of output follow COPPER's
                    # generation mix (fuel share of generation vs the anchor year), so the
                    # coal phase-out and the falling gas share reach the sector's purchases.
                    ratios: dict[tuple[int, int], float] = {}
                    gm = (firm_energy_generation_mix or {}).get(province, {})
                    if "D" in industries and gm:
                        g_now, g_0 = gm.get(int(year), {}), gm.get(int(anchor_year), {})
                        for j_code in ("B05", "B06"):
                            if j_code not in industries or not g_now:
                                continue
                            s0, s1 = float(g_0.get(j_code, 0.0)), float(g_now.get(j_code, 0.0))
                            if s0 >= _GENMIX_MIN_SHARE:
                                ratios[(industries.index("D"), industries.index(j_code))] = s1 / s0
                            elif s0 > 0.0:
                                # A ratio on a tiny base (QC/ON gas ~1% of 2022 generation) sent
                                # the sector's gas per unit of output to the cap and broke QC in
                                # the reference: left to the recipe.
                                continue
                            elif s1 <= 0.0:
                                # COPPER has none of this fuel at the anchor or now (e.g. AB coal,
                                # retired before 2022 in COPPER but in the IO-2022 recipe): zero.
                                ratios[(industries.index("D"), industries.index(j_code))] = 0.0
                    summary = country.firms.anchor_energy_intensity(
                        shifts, energy_indices, max_multiplier=firm_energy_multiplier_cap,
                        energy_index=e_index,
                        include_self={industries.index(c) for c in _SELF_FUEL_CODES if c in industries},
                        pair_ratio=ratios or None,
                        exclude_pairs={(industries.index(a), industries.index(b))
                                       for a, b in _FEEDSTOCK_PAIRS if a in industries and b in industries})
                    if ratios:
                        logger.info("firm intensity anchor: province=%s year=%s electricity fuel ratios "
                                    "(COPPER generation share vs anchor): %s", province, year,
                                    {industries[j]: round(v, 3) for (_i, j), v in ratios.items()})
                    if e_index:
                        _vals = [e_index[k] for k in {_i for (_i, _j) in shifts} if k in e_index]
                        if _vals:
                            logger.info("firm intensity anchor: province=%s year=%s CIMS energy-intensity "
                                        "index median=%.3f min=%.3f max=%.3f", province, year,
                                        float(np.median(_vals)), float(np.min(_vals)), float(np.max(_vals)))
                    d_idx = industries.index("D") if "D" in industries else None
                    d_shifts = [v for (_i, _j), v in shifts.items() if _j == d_idx]
                    logger.info(
                        "firm intensity anchor: province=%s year=%s rows=%d pairs written=%s "
                        "capped=%s | electricity share shift (value) median=%.3f max=%.3f",
                        province, year, len({_i for (_i, _j) in shifts}), summary.get("pairs"),
                        summary.get("capped"),
                        float(np.median(d_shifts)) if d_shifts else float("nan"),
                        float(np.max(d_shifts)) if d_shifts else float("nan"))
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
                exempt_pairs_seen = 0
                for i_code in _qty_rows:
                    if i_code == _HOUSEHOLD_PROXY_ROW or i_code not in industries:
                        continue
                    if i_code not in rq_anchor_f.index:
                        continue
                    if i_code in intensity_only_sectors:
                        # Intensity-only: link() has written the source's per-fuel
                        # intensity for this row; no level pin on top of it.
                        exempt_pairs_seen += sum(
                            1 for j_code in energy_codes
                            if j_code in industries and j_code != i_code
                            and (i_code, j_code) not in feedstock_pairs
                            and j_code in rq.columns and j_code in rq_anchor_f.columns
                        )
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
                        if (i_code, j_code) in feedstock_pairs:
                            continue  # feedstock, not fuel: see build_link_prehook
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
                # The SOURCE's own total index per fuel, over exactly the rows this
                # channel anchors (household proxy and self-input excluded, matching
                # the loop above).  Handed to the anchor so the model's anchored total
                # grows at the source's rate while the source still sets composition --
                # see `Firms.anchor_energy_quantities` for the Manitoba measurement
                # that made this necessary.
                conserve: dict[int, float] | None = None
                if quantity_anchor_conserve_total:
                    conserve = {}
                    for j_code in energy_codes:
                        if j_code not in industries:
                            continue
                        cur = base = 0.0
                        for i_code in rq.index:
                            if (i_code == _HOUSEHOLD_PROXY_ROW or i_code not in industries
                                    or i_code == j_code or i_code not in rq_anchor_f.index
                                    or (i_code, j_code) in feedstock_pairs
                                    or i_code in intensity_only_sectors):
                                # Intensity-only rows are not in the anchored set, so
                                # they must not be in the total it is conserved to.
                                continue
                            if j_code not in rq.columns or j_code not in rq_anchor_f.columns:
                                continue
                            cur += float(rq.loc[i_code, j_code])
                            base += float(rq_anchor_f.loc[i_code, j_code])
                        if base > 0.0 and cur > 0.0:
                            conserve[industries.index(j_code)] = cur / base
                if firm_targets or firm_increments:
                    country.firms.anchor_energy_quantities(
                        firm_targets,
                        increments=firm_increments or None,
                        energy_indices=energy_indices,
                        conserve_total=conserve,
                        max_multiplier=firm_energy_multiplier_cap,
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
                    if intensity_only_sectors:
                        # Open-loop check for the exempt rows: realised energy per unit
                        # of output last step against the coefficient link() wrote.
                        # A ratio near 1 for every fuel means the written intensity
                        # (and so the mix) is what the firms buy; a uniform shortfall
                        # across fuels is stock timing or rationing, not a mix drift.
                        _pairs = [
                            (i_code, j_code)
                            for i_code in sorted(intensity_only_sectors)
                            for j_code in energy_codes
                            if j_code in industries and j_code != i_code
                            and (i_code, j_code) not in feedstock_pairs
                        ]
                        _ratios = country.firms.realised_vs_written_intensity(
                            _pairs, industries
                        )
                        logger.info(
                            "intensity-only rows: region=%s year=%s exempt pairs=%d "
                            "(left out of the level anchor and the conserve set); "
                            "realised/written energy intensity last step by row and fuel=%s",
                            cims_region, year, exempt_pairs_seen,
                            {i: {j: round(v, 3) for j, v in d.items()}
                             for i, d in _ratios.items()},
                        )
                elif firm_energy_target_mode != "intensity":
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


# Energy goods never get the price-elastic export overlay: their prices are exogenous
# CIMS paths (regional by construction) and their quantities are CIMS-anchored.
EXPORT_PRICE_ELASTICITY_EXCLUDED = ("D", "C19", "B06")


def apply_export_price_elasticity(
    sim: Simulation, codes: str | None, epsilon: float | None, industries: list[str]
) -> list[int]:
    """Opt selected trade-exposed sectors into a price-elastic export demand (WTC, doc 5g).

    ROW's import budget for a listed sector is scaled each step by
    M_i = sum_p s_p,i (P_p,i / P_ref,i)^(-epsilon) and re-divided between provinces with
    the same per-province factor, where P_p,i is the province's production-weighted firm
    price and P_ref,i the national one, both relative to their first-step value (see
    ``Simulation._update_export_price_elasticity``).  Energy goods (D, C19, B06) are
    excluded; unknown codes are skipped with a warning.  A no-op when nothing is listed
    or epsilon is None.  Applied after build or restore, like the import limits.
    """
    wanted = [c.strip() for c in str(codes or "").split(",") if c.strip()]
    if not wanted or epsilon is None:
        return []
    excluded = [c for c in wanted if c in EXPORT_PRICE_ELASTICITY_EXCLUDED]
    unknown = [c for c in wanted if c not in industries and c not in excluded]
    kept = [c for c in wanted if c in industries and c not in excluded]
    if excluded:
        logger.warning("Export price elasticity: energy goods %s excluded by design.", excluded)
    if unknown:
        logger.warning("Export price elasticity: sectors %s not in model industries; ignoring.", unknown)
    indices = [industries.index(c) for c in kept]
    if not indices:
        logger.warning("Export price elasticity requested but no eligible sector remains; OFF.")
        return []
    clearer = sim.goods_market.functions.get("clearing")
    if clearer is None or not hasattr(clearer, "set_row_origin_multipliers"):
        raise RuntimeError(
            "export price elasticity needs a goods-market clearer with "
            "set_row_origin_multipliers; without it the national budget would be scaled "
            "but never re-divided between provinces."
        )
    sim.rest_of_the_world.set_export_price_elasticity(indices, float(epsilon))
    logger.info(
        "Export price elasticity overlay ON: epsilon=%.3f, sectors=%s (indices %s); "
        "excluded energy goods=%s; ROW budget x M_i and ROW origin shares x m_p,i "
        "(prices relative to first step; (P_p/P_ref)^-eps clipped to [0.2, 5]).",
        float(epsilon), kept, indices, excluded,
    )
    return indices


def parse_row_export_sigma(spec, codes: list[str]) -> dict[str, float]:
    """Per-sector sigma for the real-price-elastic export demand (doc 5m).

    ``spec`` is one number (the same sigma for every listed sector), a mapping
    ``{code: sigma}``, or a string ``"3"`` / ``"C20:3,C23:1.5"``.  Sectors listed without a
    sigma of their own take the single number if one was given; a sector with no sigma at
    all is an error, so a typo cannot silently leave a sector out.
    """
    default = None
    per: dict[str, float] = {}
    if spec is None:
        return {}
    if isinstance(spec, dict):
        per = {str(k).strip(): float(v) for k, v in spec.items()}
    elif isinstance(spec, (int, float)):
        default = float(spec)
    else:
        for part in str(spec).split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                k, v = part.split(":", 1)
                per[k.strip()] = float(v)
            else:
                default = float(part)
    out = {}
    for c in codes:
        if c in per:
            out[c] = per[c]
        elif default is not None:
            out[c] = default
        else:
            raise ValueError(f"row export elasticity: no sigma for sector {c!r} in {spec!r}")
    extra = sorted(set(per) - set(codes))
    if extra:
        logger.warning("row export elasticity: sigma given for sectors not listed (%s); ignored.", extra)
    return out


def apply_row_export_elasticity(
    sim: Simulation, codes: str | None, sigma, reference: str | None, cap: float | None,
    industries: list[str], reference_step: int = 0,
) -> dict[int, float]:
    """Opt selected trade-exposed sectors into a REAL-price-elastic export demand (WTC, doc 5m).

    The quantity ROW buys from province p of sector s becomes
    Q_s,p = Q_s,p_base x (P_s,p / P_world,s)^(-sigma_s), with P_world,s ROW's own offered price
    for s (``reference="row"``, default: the sector's price relative to the economy's, so the
    national purchase can grow) or the national production-weighted price (``"national"``,
    the 5g form).  Both are indexed to their first-step value (no change at equal prices by
    construction); the national ROW purchase of a sector is bounded to [1/cap, cap] of its
    base path.  See ``Simulation._update_row_export_elasticity`` and
    ``RestOfTheWorld.set_row_export_elasticity``.  Energy goods (D, C19, B06) are excluded;
    unknown codes are skipped with a warning.  A no-op when nothing is listed or sigma is
    None.  Applied after build or restore, like the 5g overlay.
    """
    wanted = [c.strip() for c in str(codes or "").split(",") if c.strip()]
    if not wanted or sigma is None:
        return {}
    excluded = [c for c in wanted if c in EXPORT_PRICE_ELASTICITY_EXCLUDED]
    unknown = [c for c in wanted if c not in industries and c not in excluded]
    kept = [c for c in wanted if c in industries and c not in excluded]
    if excluded:
        logger.warning("Row export elasticity: energy goods %s excluded by design.", excluded)
    if unknown:
        logger.warning("Row export elasticity: sectors %s not in model industries; ignoring.", unknown)
    if not kept:
        logger.warning("Row export elasticity requested but no eligible sector remains; OFF.")
        return {}
    sigma_by_code = parse_row_export_sigma(sigma, kept)
    clearer = sim.goods_market.functions.get("clearing")
    if clearer is None or not hasattr(clearer, "set_row_origin_multipliers"):
        raise RuntimeError(
            "row export elasticity needs a goods-market clearer with "
            "set_row_origin_multipliers; without it the national budget would be scaled "
            "but never re-divided between provinces."
        )
    ref = str(reference or "row").lower()
    cap_f = 1.5 if cap is None else float(cap)
    sigma_by_index = {industries.index(c): v for c, v in sigma_by_code.items()}
    step0 = int(reference_step or 0)
    sim.rest_of_the_world.set_row_export_elasticity(
        sigma_by_index, reference=ref, cap=cap_f, reference_step=step0)
    if getattr(sim.rest_of_the_world, "_export_price_elasticity", None) is not None:
        logger.warning(
            "Row export elasticity (5m) is ON together with the 5g export_price_elasticity "
            "overlay: the two compound on ROW's origin split (sigma + eps on the province "
            "relative price)."
        )
    logger.info(
        "REAL-price-elastic export demand ON (doc 5m): sigma by sector %s (indices %s), "
        "world price = %s, national purchase bounded to [%.3f, %.3f] x base path; "
        "excluded energy goods=%s; ROW budget x M_s and ROW origin shares x m_p,s "
        "(prices relative to step %d, inert before it; (P_p/P_world)^-sigma clipped to [0.2, 5] per province).",
        sigma_by_code, sigma_by_index, ref, 1.0 / cap_f, cap_f, excluded, step0,
    )
    return sigma_by_index


def apply_row_first_clearing(sim: Simulation, codes: str | None, industries: list[str], mode: str = "all") -> list[int]:
    """Serve ROW's directed orders for the listed sectors before domestic buyers (WTC, doc 5r).

    See ``WaterBucketGoodsMarketClearer.set_row_first_industries``: a pre-pass in which each
    province offers all its supply of the sector to ROW's orders directed at it, ahead of
    the province-to-province passes.  Unknown codes are skipped with a warning; a no-op
    when nothing is listed.  Raises if the clearer has no such hook.  Applied after build or
    restore, like the export overlays.
    """
    wanted = [c.strip() for c in str(codes or "").split(",") if c.strip()]
    if not wanted:
        return []
    unknown = [c for c in wanted if c not in industries]
    if unknown:
        logger.warning("ROW-first clearing: sectors %s not in model industries; ignoring.", unknown)
    idx = [industries.index(c) for c in wanted if c in industries]
    clearer = sim.goods_market.functions.get("clearing")
    if clearer is None or not hasattr(clearer, "set_row_first_industries"):
        raise RuntimeError("ROW-first clearing needs a goods-market clearer with set_row_first_industries.")
    clearer.set_row_first_industries(idx, mode=mode)
    logger.info(
        "ROW-first clearing ON (doc 5r, mode=%s): ROW's directed orders for %s (indices %s) are served "
        "before the province-to-province passes.", mode, [c for c in wanted if c in industries], idx)
    return idx


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


def _index_factor(path: list[float], n_quarters: int) -> np.ndarray:
    """A per-province index as a growth factor over *n_quarters*, normalised to 1 at the
    first quarter; the last value is held rather than truncating the tail to zero."""
    fac = np.asarray(path, dtype=float)
    if len(fac) < n_quarters:
        fac = np.concatenate([fac, np.full(n_quarters - len(fac), fac[-1])])
    fac = fac[:n_quarters]
    return fac / fac[0]


def _apply_government_demand_overlay(
    model: Simulation, index_by_province: dict[str, list[float]]
) -> None:
    """Grow real government consumption along each province's labour-force index.

    `_extend_exogenous_national_accounts` holds the exogenous accounts flat past the data
    tail, so under `ExogenousGovernmentConsumptionSetter` real government consumption --
    about a fifth of GDP -- stays at its last observed level for the whole projection
    while the labour force and household demand grow. Measured on the 2026-10-28 baseline
    (seed 4): real government consumption +0.3 %/yr against real GDP +1.0 %/yr, its share
    of GDP income falling from 22 % to 19 % by 2050, and `household_demand_growth` having
    to carry the public sector's missing growth (household consumption rising from 57 % to
    61 % of GDP income).

    This applies the SAME normalised index the household overlay uses -- population growth
    only, no autonomous per-head term -- so government consumption per labour-force member
    is held constant, as household demand is before its autonomous term.
    """
    for name, country in model.countries.items():
        frame = country.exogenous.national_accounts_during
        path = index_by_province.get(str(name))
        if path is None:
            logger.warning("government demand overlay: no index for %s; leaving it flat.", name)
            continue
        fac = _index_factor(path, len(frame))
        for col in _GOV_DEMAND_COLS:
            if col in frame.columns:
                frame[col] = frame[col].values * fac


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
            # The index is built for timesteps+1 quarters and the accounts frame need not
            # match; hold the last value rather than truncating the tail to zero.
            fac = _index_factor(path, len(frame))
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
    obps_charge_mode: str = "markup",
    household_bundles: list[list[int]] | None = None,
    household_elasticity: float | None = None,
    household_income_driven: bool = False,
    firm_price_advantage_symmetric: bool = False,
    firm_price_advantage_deadband: float | None = None,
    firm_price_advantage_smoothing: float | None = None,
    wage_cpi_indexation: float | None = None,
    wage_cpi_lag: int | None = None,
    inflation_expectation_anchor: float | None = None,
    inflation_expectation_target: float | None = None,
    rent_inflation_indexation: float | None = None,
    rent_inflation_delay: int | None = None,
    use_candidate_baseline: bool = False,
    labour_force_growth: float | None = None,
    labour_force_cap: dict[str, float] | None = None,
    capital_target_fraction: float | None = None,
    capital_rolling_reference: bool | None = None,
    unmet_demand_weight: float | None = None,
    demand_smoothing: float | None = None,
    household_demand_growth: float | None = None,
    household_demand_from_labour_force: bool = False,
    government_demand_from_labour_force: bool = False,
    exogenous_energy_prices: bool = False,
    tfp_base_growth_rate: float | None = None,
    tfp_investment_effectiveness: float | None = None,
    price_setting_noise_std: float | None = None,
    price_setting_speed_gf: float | None = None,
    price_setting_speed_cp: float | None = None,
    price_setting_speed_dp: float | None = None,
    price_setting_cost_push_basis: str | None = None,
    trade_temperature: float | None = None,
    firm_growth_ignore_price: bool = False,
    origin_shortfall_signal: float | None = None,
    domestic_only_industries: list[str] | None = None,
    firm_price_advantage_growth: float | None = None,
    origin_shortfall_relative: bool = False,
    firm_price_advantage_change_growth: float | None = None,
    firm_price_advantage_window: int | None = None,
    firm_unit_cost_change_growth: float | None = None,
    firm_unit_cost_window: int | None = None,
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
        use_obps_reg=use_obps_reg, obps_charge_mode=obps_charge_mode,
        household_bundles=household_bundles,
        household_elasticity=household_elasticity,
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
                unmet_demand_weight=unmet_demand_weight,
                demand_smoothing=demand_smoothing,
            )
    if household_income_driven:
        # Opt-in (2026-09-20, Atlantic intertie alternatives): households' consumption
        # follows their income instead of the candidate baseline's exogenous total path.
        # The exogenous total pins REAL consumption, so a price cut cannot raise real
        # spending by construction; this releases that pin (and with it the household
        # part of the growth calibration -- compare pairs on this setting, not levels).
        name = "CESHouseholdConsumption" if household_bundles else "DefaultHouseholdConsumption"
        for province in CANADIAN_PROVINCES:
            config.country_configurations[province].households.functions.consumption.name = name
        logger.info("Household consumption INCOME-DRIVEN (%s), exogenous total released.", name)
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

    if (price_setting_speed_cp is not None or price_setting_speed_dp is not None
            or price_setting_cost_push_basis is not None):
        # Cost-push and demand-pull terms of `DefaultPriceSetter`, both shipped at 0.0.
        # cost_push = unit_cost / sector_average_price - 1 (clipped +/-10% per step), so a
        # positive speed pulls every firm's price LEVEL toward its unit cost (wages +
        # intermediates + capital inputs + production taxes per unit): a cheaper input is
        # passed on instead of widening the margin, and a sector priced below cost reprices
        # upward. demand_pull = demand / supply - 1 on the CANVAS condition (below-average
        # price with excess demand, or above-average with excess supply). Sectors on an
        # exogenous price path (SectorExogenousPriceSetter, e.g. D under
        # --exogenous-energy-prices) are unaffected. Added for the WTC pass-through
        # sensitivity (2026-10-16).
        for province in CANADIAN_PROVINCES:
            prices_fn = config.country_configurations[province].firms.functions.prices
            if price_setting_speed_cp is not None:
                prices_fn.parameters["price_setting_speed_cp"] = float(price_setting_speed_cp)
            if price_setting_speed_dp is not None:
                prices_fn.parameters["price_setting_speed_dp"] = float(price_setting_speed_dp)
            if price_setting_cost_push_basis is not None:
                # "level" (shipped): price pulled toward unit cost, which excludes the operating
                # surplus -- at cp=0.5 the whole economy deflated and collapsed (2026-10-16).
                # "change": price follows the firm's own unit-cost change; margins are kept.
                prices_fn.parameters["cost_push_basis"] = str(price_setting_cost_push_basis)
        logger.info(
            "Price adjustment speeds overridden: price_setting_speed_cp=%s price_setting_speed_dp=%s "
            "cost_push_basis=%s (shipped 0.0 / 0.0 / level)",
            price_setting_speed_cp,
            price_setting_speed_dp,
            price_setting_cost_push_basis,
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

    if firm_growth_ignore_price:
        # Firm-specific growth for ANY sold-out firm (WTC 2026-10-17, doc 5i). The shipped
        # DefaultGrowthEstimator grants growth to a sold-out firm only when its price is at
        # or above the sector average, so a firm that is sold out because it is CHEAPER gets
        # no growth signal: the cost advantage reaches its price and its order book and is
        # discarded at the planning step. Measured 5c-5h: Alberta's electricity-intensive
        # sectors are sold out and 1-2% cheaper in the noREM arm and never expand.
        for province in config.country_configurations:
            ge = config.country_configurations[province].firms.functions.growth_estimator
            if ge.name != "DefaultGrowthEstimator":
                raise RuntimeError(
                    f"firm_growth_ignore_price needs DefaultGrowthEstimator, got {ge.name} in {province}")
            ge.parameters["ignore_price_when_sold_out"] = True
        logger.info(
            "Firm growth rule overridden: sold-out firms grow by demand/supply - 1 regardless "
            "of their price relative to the sector average (shipped: only if price >= average).")

    if firm_price_advantage_growth is not None and float(firm_price_advantage_growth) > 0.0:
        # RELATIVE form of the sold-out growth signal (WTC 2026-10-17, doc 5j). A sold-out
        # firm priced BELOW the sector average grows by k x (average / price - 1) x
        # (demand / supply): zero at the average price, so firms that are merely sold out
        # (the model's normal state, doc 5i) are untouched and only a firm that became
        # cheaper than its competitors expands, in proportion to its advantage.
        for province in config.country_configurations:
            ge = config.country_configurations[province].firms.functions.growth_estimator
            if ge.name != "DefaultGrowthEstimator":
                raise RuntimeError(
                    f"firm_price_advantage_growth needs DefaultGrowthEstimator, got {ge.name} in {province}")
            ge.parameters["price_advantage_growth"] = float(firm_price_advantage_growth)
        logger.info(
            "Firm growth rule (relative): a sold-out firm priced below the sector average grows "
            "by %.3f x (average / price - 1) x (demand / supply); shipped 0.0 (no growth for a "
            "cheap sold-out firm).", float(firm_price_advantage_growth))

    if firm_price_advantage_change_growth is not None and float(firm_price_advantage_change_growth) > 0.0:
        # CHANGE-keyed form of the sold-out growth signal (WTC 2026-10-17, doc 5k). Doc 5j
        # measured that the LEVEL of a firm's relative price is not a calibration state
        # (two-thirds of firms are cheaper than average AND sold out in the baseline, median
        # advantage 1.6-1.8%, the cost pass-through's own cross-province dispersion), so the
        # level form reproduces half of 5i's boom. This form keys on the CHANGE of the
        # firm's position over a window of L steps: growth = k x max(adv_t - adv_{t-L}, 0)
        # x (demand / supply) with adv = average / price - 1, for a sold-out firm priced
        # below the average. Zero in a stationary baseline by construction; an impulse of L
        # steps after a relative price fall in the arm.
        _window = int(firm_price_advantage_window) if firm_price_advantage_window is not None else 4
        if _window < 1:
            raise RuntimeError(f"firm_price_advantage_window must be >= 1, got {_window}")
        for province in config.country_configurations:
            ge = config.country_configurations[province].firms.functions.growth_estimator
            if ge.name != "DefaultGrowthEstimator":
                raise RuntimeError(
                    f"firm_price_advantage_change_growth needs DefaultGrowthEstimator, got {ge.name} in {province}")
            ge.parameters["price_advantage_change_growth"] = float(firm_price_advantage_change_growth)
            ge.parameters["price_advantage_window"] = _window
            # noise-robust options (2026-10-30): signed change, deadband, EMA-smoothed advantage
            if firm_price_advantage_symmetric:
                ge.parameters["price_advantage_symmetric"] = True
            if firm_price_advantage_deadband is not None:
                ge.parameters["price_advantage_deadband"] = float(firm_price_advantage_deadband)
            if firm_price_advantage_smoothing is not None:
                ge.parameters["price_advantage_smoothing"] = float(firm_price_advantage_smoothing)
        logger.info(
            "Firm growth rule (CHANGE-keyed, doc 5k): a sold-out firm priced below the sector "
            "average grows by %.3f x max(adv_t - adv_{t-%d}, 0) x (demand / supply), adv = "
            "average / price - 1; shipped 0.0 (no growth for a cheap sold-out firm).",
            float(firm_price_advantage_change_growth), _window)
        if firm_price_advantage_symmetric or firm_price_advantage_deadband or firm_price_advantage_smoothing:
            logger.info(
                "  noise-robust form: symmetric=%s (signed change), deadband=%s, EMA smoothing lambda=%s",
                bool(firm_price_advantage_symmetric), firm_price_advantage_deadband, firm_price_advantage_smoothing)
    elif firm_price_advantage_window is not None:
        raise RuntimeError("firm_price_advantage_window needs firm_price_advantage_change_growth > 0")

    if firm_unit_cost_change_growth is not None and float(firm_unit_cost_change_growth) > 0.0:
        # OWN-COST-keyed form of the sold-out growth signal (WTC 2026-10-17, doc 5o): a
        # sold-out firm grows by k x max(1 - c_t / mean(c_{t-L..t-1}), 0) x (demand / supply)
        # with c its REAL unit cost (unit cost over the province's production-weighted price
        # level).  Fires for exactly the firms whose real unit cost is falling; zero for a
        # flat or rising cost, so the baseline is touched only where its own costs fall.
        _ucw = int(firm_unit_cost_window) if firm_unit_cost_window is not None else 4
        if _ucw < 1:
            raise RuntimeError(f"firm_unit_cost_window must be >= 1, got {_ucw}")
        for province in config.country_configurations:
            ge = config.country_configurations[province].firms.functions.growth_estimator
            if ge.name != "DefaultGrowthEstimator":
                raise RuntimeError(
                    f"firm_unit_cost_change_growth needs DefaultGrowthEstimator, got {ge.name} in {province}")
            ge.parameters["unit_cost_change_growth"] = float(firm_unit_cost_change_growth)
            ge.parameters["unit_cost_window"] = _ucw
        logger.info(
            "Firm growth rule (OWN-COST-keyed, doc 5o): a sold-out firm grows by %.3f x "
            "max(1 - c_t / mean(c_{t-%d..t-1}), 0) x (demand / supply), c = real unit cost; "
            "shipped 0.0.", float(firm_unit_cost_change_growth), _ucw)
    elif firm_unit_cost_window is not None:
        raise RuntimeError("firm_unit_cost_window needs firm_unit_cost_change_growth > 0")

    if trade_temperature is not None:
        # Price sensitivity of the goods market's ORIGIN shares. `get_trade_proportions`
        # (lib_water_bucket.py) scales each origin's default share of a buyer's purchases
        # by exp(-trade_temperature x origin_price) and renormalises; the clearer divides
        # each origin's price by its own price at the first clearing (ROW's offered price
        # carries the data's exchange rate, ~1.3-1.5x the provinces' 1.0 index), so a
        # relative price change dp of one origin moves its share w by about
        # -T x dp x w(1-w). Shipped 0.0: origin shares frozen at the base-year IO split,
        # so no buyer switches supplier on price. One goods market for the whole
        # simulation (one parameter, not per province). Only meaningful with
        # price_setting_noise_std = 0: same-industry prices across provinces random-walk
        # 10-17% apart by 2040 on the shipped noise, several times any cost signal.
        # Added for the WTC origin-switching sensitivity (2026-10-17).
        config.goods_market_configuration.functions.clearing.parameters["trade_temperature"] = (
            float(trade_temperature)
        )
        logger.info(
            "Trade temperature overridden: trade_temperature=%s (shipped 0.0)", trade_temperature,
        )

    sim = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=config)
    if origin_shortfall_signal is not None and float(origin_shortfall_signal) > 0.0:
        # Orders DIRECTED at an origin that the origin could not fill are booked as that
        # origin's excess demand (damped by this fraction), instead of vanishing into the
        # pool that fills them from whichever province has slack (WTC 2026-10-17, doc 5i).
        # Without it a sold-out province never sees the orders the goods market tried to
        # place with it, so its demand estimate -- and its plan -- cannot grow.
        clearer = sim.goods_market.functions.get("clearing")
        if clearer is None or not hasattr(clearer, "set_origin_shortfall_signal"):
            raise RuntimeError("origin_shortfall_signal needs a clearer with set_origin_shortfall_signal")
        clearer.set_origin_shortfall_signal(float(origin_shortfall_signal), relative=bool(origin_shortfall_relative))
        if origin_shortfall_relative:
            if not getattr(clearer, "_origin_shortfall_relative", False):
                raise RuntimeError("origin_shortfall_relative did not reach the clearer")
            logger.info(
                "Origin shortfall signal ON (RELATIVE, doc 5j): %.2f x min(orders the price-adjusted "
                "origin shares moved toward the origin beyond its default share, unfilled directed "
                "orders) booked as its sellers' excess demand; zero where the shares sit at their "
                "calibrated defaults.", float(origin_shortfall_signal))
        else:
            logger.info(
                "Origin shortfall signal ON: %.2f of each origin's unfilled directed orders booked "
                "as its sellers' excess demand (shipped 0.0: pooled, no signal to the origin).",
                float(origin_shortfall_signal))
    elif origin_shortfall_relative:
        raise RuntimeError("origin_shortfall_relative needs origin_shortfall_signal > 0")
    if domestic_only_industries:
        # Non-tradable goods (WTC Atlantic PEI artefact, doc 5x): every participant buys them
        # only from itself, in the pair passes, the pool and the ROW backstop.
        clearer = sim.goods_market.functions.get("clearing")
        if clearer is None or not hasattr(clearer, "set_domestic_only_industries"):
            raise RuntimeError("domestic_only_industries needs a clearer with set_domestic_only_industries")
        missing = [c for c in domestic_only_industries if c not in data.industries]
        if missing:
            raise RuntimeError(f"domestic_only_industries: unknown industries {missing}")
        clearer.set_domestic_only_industries([data.industries.index(c) for c in domestic_only_industries])
        logger.info("Domestic-only (non-tradable) industries: %s", list(domestic_only_industries))
    if firm_growth_ignore_price:
        _ge = next(iter(sim.countries.values())).firms.functions.get("growth_estimator")
        if not getattr(_ge, "ignore_price_when_sold_out", False):
            raise RuntimeError("firm_growth_ignore_price did not reach the growth estimator")
        logger.info("Growth estimator %s built with ignore_price_when_sold_out=True", type(_ge).__name__)
    if firm_price_advantage_growth is not None and float(firm_price_advantage_growth) > 0.0:
        _ge = next(iter(sim.countries.values())).firms.functions.get("growth_estimator")
        _got = float(getattr(_ge, "price_advantage_growth", 0.0) or 0.0)
        if abs(_got - float(firm_price_advantage_growth)) > 1e-12:
            raise RuntimeError(
                f"firm_price_advantage_growth did not reach the growth estimator (got {_got})")
        logger.info("Growth estimator %s built with price_advantage_growth=%s", type(_ge).__name__, _got)
    if firm_price_advantage_change_growth is not None and float(firm_price_advantage_change_growth) > 0.0:
        _ge = next(iter(sim.countries.values())).firms.functions.get("growth_estimator")
        _got = float(getattr(_ge, "price_advantage_change_growth", 0.0) or 0.0)
        _got_w = int(getattr(_ge, "price_advantage_window", 0) or 0)
        _want_w = int(firm_price_advantage_window) if firm_price_advantage_window is not None else 4
        if abs(_got - float(firm_price_advantage_change_growth)) > 1e-12 or _got_w != _want_w:
            raise RuntimeError(
                "firm_price_advantage_change_growth / window did not reach the growth estimator "
                f"(got k={_got}, window={_got_w}; wanted k={firm_price_advantage_change_growth}, window={_want_w})")
        logger.info("Growth estimator %s built with price_advantage_change_growth=%s, price_advantage_window=%d",
                    type(_ge).__name__, _got, _got_w)
    if trade_temperature is not None:
        clearer = sim.goods_market.functions.get("clearing")
        got = getattr(clearer, "trade_temperature", None)
        logger.info(
            "Goods-market clearer %s built with trade_temperature=%s",
            type(clearer).__name__, got,
        )
        if got is None or abs(float(got) - float(trade_temperature)) > 1e-12:
            raise RuntimeError(
                f"trade_temperature={trade_temperature} did not reach the goods-market clearer (got {got})"
            )
        if exogenous_energy_prices and hasattr(clearer, "set_trade_temperature_neutral_industries"):
            # Sectors on an exogenous (CIMS) price path keep their default origin split:
            # their provincial price LEVELS differ by construction (regional fuel and
            # power prices), their quantities are anchored, and D's origin shares are
            # written from COPPER's interchange -- a price-driven re-sourcing of those
            # would double count the supply channel, not test buyer switching.
            pinned: set[str] = set()
            for name, country in data.synthetic_countries.items():
                exo = getattr(country, "firm_exo_prices", None)
                if exo is not None and getattr(exo, "prices", None) is not None:
                    pinned.update(str(c) for c in exo.prices.columns)
            idx = [data.industries.index(c) for c in sorted(pinned) if c in data.industries]
            clearer.set_trade_temperature_neutral_industries(idx)
            logger.info(
                "Trade temperature neutral (origin shares not price-adjusted) for exogenously "
                "priced industries: %s", sorted(pinned),
            )
    if use_candidate_baseline:
        _extend_exogenous_national_accounts(sim, required_length=timesteps + 1)
        # The overlay's default (+2%/yr) outruns labour-supply growth (~0.72%/yr), so firms
        # bid wages up against a hard supply limit and the labour share climbs without
        # bound.  Overridable so the two can be tested at compatible rates.
        _hh_index = None
        _lf_index = None
        if household_demand_from_labour_force or government_demand_from_labour_force:
            _lf_index = observed_labour_force_index(
                n_quarters=timesteps + 1, post_sample_growth=labour_force_growth,
                growth_cap=labour_force_cap,
                **({"base_year": labour_index_base_year}
                   if labour_index_base_year is not None else {}))
        if household_demand_from_labour_force:
            _hh_index = _lf_index
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
        if government_demand_from_labour_force:
            _apply_government_demand_overlay(sim, _lf_index)
            logger.info(
                "Real government consumption follows each province's OWN labour-force "
                "index (population only; otherwise flat past the data tail)")
    if wage_cpi_indexation is not None:
        # Partial / lagged CPI indexation of nominal wages (2026-10-30): wages paid at
        # a x CPI_t + (1 - a) x CPI_{t-L} instead of CPI_t (Country.wage_price_index).
        # Set on the country objects after build or restore, like the overlays above.
        _a = float(wage_cpi_indexation)
        _l = int(wage_cpi_lag) if wage_cpi_lag is not None else 4
        if not 0.0 <= _a <= 1.0 or _l < 1:
            raise RuntimeError(f"wage_cpi_indexation must be in [0, 1] and wage_cpi_lag >= 1 (got {_a}, {_l})")
        for _c in sim.countries.values():
            _c.wage_cpi_indexation = _a
            _c.wage_cpi_lag = _l
        logger.info("Nominal wages paid at %.2f x CPI_t + %.2f x CPI_{t-%d} (partial indexation ON)", _a, 1.0 - _a, _l)
    if inflation_expectation_anchor is not None:
        # Anchored inflation expectations (2026-10-30): expected = a x target + (1 - a) x AR
        # forecast, for the CPI and PPI expectations of every province
        # (Economy._anchor_expectation).  The target is given as an ANNUAL rate (0.02 = 2 %)
        # and converted to the model's quarterly rate here.  The central bank's own Taylor-rule
        # target (synthetic data, `targeted_inflation_rate`) is logged for comparison only:
        # the policy rate reaches interest paid, not prices, so it is not the anchor.
        _a = float(inflation_expectation_anchor)
        _t_annual = float(inflation_expectation_target) if inflation_expectation_target is not None else 0.02
        if not 0.0 <= _a <= 1.0:
            raise RuntimeError(f"inflation_expectation_anchor must be in [0, 1] (got {_a})")
        _t_q = (1.0 + _t_annual) ** 0.25 - 1.0
        for _c in sim.countries.values():
            _c.economy.inflation_expectation_anchor = _a
            _c.economy.inflation_expectation_target = _t_q
        try:
            _cb_t = float(next(iter(sim.countries.values())).central_bank.states["targeted_inflation_rate"])
        except Exception:  # noqa: BLE001
            _cb_t = float("nan")
        logger.info("Inflation expectations anchored: a=%.2f target=%.4f/yr (%.5f/quarter); central bank Taylor target stored as %.5f",
                    _a, _t_annual, _t_q, _cb_t)
    if rent_inflation_indexation is not None:
        # Rent indexation (2026-10-30): existing rents are raised each quarter by
        # a x CPI inflation of L quarters ago (households property function
        # `partial_rent_inflation_indexation` / `_delay`, shipped 0.0 / 1, i.e. rents are
        # nominally rigid until a property is re-let).  Under a 2 %/yr price path that
        # rigidity erodes real rents and house values by ~40 % by 2050 and moves the
        # housing block (L, F, G, K) and the rent share of GDP; a = 1 makes rents a
        # relative price like any other.
        _ri = float(rent_inflation_indexation)
        _rl = int(rent_inflation_delay) if rent_inflation_delay is not None else 1
        if not 0.0 <= _ri <= 1.0 or _rl < 1:
            raise RuntimeError(f"rent_inflation_indexation must be in [0, 1] and rent_inflation_delay >= 1 (got {_ri}, {_rl})")
        for _c in sim.countries.values():
            _pf = _c.households.functions["property"]
            _pf.partial_rent_inflation_indexation = _ri
            _pf.partial_rent_inflation_delay = _rl
        logger.info("Rents indexed to CPI inflation: a=%.2f, delay %d quarter(s) (shipped 0.0)", _ri, _rl)
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


def export_labour_force_index(sim: Simulation, csv_path: Path) -> bool:
    """Write the per-province quarterly labour-force index the run actually used.

    Reads the index back out of each country's demography configuration (the
    ExogenousLabourForcePath parameters), so the export is byte-for-byte the
    trajectory the demography followed -- no re-derivation from CLI flags that
    could drift.  Downstream, the LabourABM stage consumes this to grow its own
    labour force consistently with the macro run.

    CSV layout: one row per province (``region`` = "CAN_XX"), columns
    ``time_step_1..N`` holding the quarterly index (base 1.0 at the simulation
    start).  Returns False (writing nothing) when no province ran with an
    exogenous labour-force path, e.g. NoAging runs.
    """
    rows = {}
    for country_name, cc in sim.configuration.country_configurations.items():
        demography = cc.individuals.functions.demography
        if demography.name != "ExogenousLabourForcePath":
            continue
        index = (demography.parameters or {}).get("labour_force_index")
        if index:
            rows[_province_code(country_name)] = list(index)
    if not rows:
        logger.info("No ExogenousLabourForcePath in this run; labour-force index not exported.")
        return False
    n = max(len(v) for v in rows.values())
    frame = pd.DataFrame(
        {f"time_step_{i + 1}": {p: (v[i] if i < len(v) else v[-1]) for p, v in rows.items()}
         for i in range(n)}
    )
    frame.index.name = "region"
    csv_path = csv_path.resolve()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.sort_index().to_csv(csv_path)
    logger.info("Saved labour-force index for %d provinces to %s", len(rows), csv_path)
    return True


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

    export_labour_force_index(sim, output_dir / "labour_force_index.csv")

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
