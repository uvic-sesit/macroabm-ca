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
4. Write the start-to-end GDP growth of every province to ``gdp_growth.json`` so
   the orchestrator's convergence check can compare iterations.

The macroABM and CIMS classifications/regions are translated through the
editable mapping CSVs in
``macro_data/processing/macroabm_cims_data_processing/data/`` -- see
:mod:`macro_data.processing.macroabm_cims_data_processing.sector_map`.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from macro_data import DataWrapper
from macro_data.processing.macroabm_cims_data_processing import (
    CIMSProductionWriter,
    CIMSResultsExtractor,
    SectorMap,
)
from macro_data.readers.cims_data import CIMSDataReader
from macromodel.simulation import Simulation

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


def _province_code(country_name: object) -> str:
    """Return the macro province code (e.g. 'CAN_AB') from a country key."""
    code = getattr(country_name, "code", None)
    return str(code) if code is not None else str(country_name)


def milestone_years(base_year: int, end_year: int, year_step: int) -> list[int]:
    """CIMS milestone years strictly after *base_year* up to *end_year*."""
    return list(range(base_year + year_step, end_year + 1, year_step))


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
    """Extract processed requested-quantity/investment matrices for every region."""
    extractor = CIMSResultsExtractor(cims_results_dir, sector_map=sector_map, steps_per_year=steps_per_year)
    for region in cims_regions:
        extractor.process(region, years, industries, export_dir, itr)


def build_link_prehook(
    reader: CIMSDataReader,
    sector_map: SectorMap,
    industries: list[str],
    years: list[int],
    itr: str,
):
    """Create a simulation pre-hook that calls firms.link() at milestone years.

    The hook is invoked with ``(simulation, year, month)`` at the start of every
    timestep; it acts only at the first quarter of each CIMS milestone year.
    """
    energy_codes = sector_map.energy_bundle_for(industries)
    comparable_codes = sector_map.comparable_for(industries)
    milestone = set(years)

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
            country.firms.link(
                requested_quantities=rq,
                investment=inv,
                comparable_codes=comparable_codes,
                energy_bundle_codes=energy_codes,
            )
            logger.info("link() applied: province=%s cims_region=%s year=%s", province, cims_region, year)

    return link_prehook


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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run one macroABM iteration of the CIMS--macroABM linkage.")
    p.add_argument("--cims-results-dir", type=Path, required=True,
                   help="Directory with the completed CIMS run's result CSVs.")
    p.add_argument("--cims-model-dir", type=Path, required=True,
                   help="Path to cims-models-fork/csv/model (source of service-request trajectories).")
    p.add_argument("--raw-data-path", type=Path, required=True,
                   help="macroABM raw_data/ directory (IO tables, etc.).")
    p.add_argument("--output-dir", type=Path, required=True,
                   help="Directory for processed data, feedback policy, and gdp_growth.json.")
    p.add_argument("--feedback-dir", type=Path, required=True,
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
    p.add_argument("--sector-map", type=Path, default=None, help="Override sector-map CSV.")
    p.add_argument("--region-map", type=Path, default=None, help="Override region-map CSV.")
    p.add_argument("--force-rebuild-pickle", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pkl_path: Path = (args.pkl_path or output_dir / "data_provincial_model.pkl").resolve()
    processed_dir = output_dir / "cims_data"

    sector_map = SectorMap.load(sector_map_path=args.sector_map, region_map_path=args.region_map)

    years = milestone_years(args.cims_base_year, args.sim_end_year, args.cims_year_step)
    cims_regions = sorted(set(sector_map.macro_region_to_cims.values()))

    # 1. Build/load the provincial data pickle.
    create_data_pickle(args.raw_data_path.resolve(), pkl_path, force=args.force_rebuild_pickle)
    data = DataWrapper.init_from_pickle(pkl_path)
    industries = list(data.industries)
    logger.info("Loaded provincial data: %d industries, %d provinces", len(industries), len(CANADIAN_PROVINCES))

    # 2. Extract CIMS linkage inputs from the standard result files.
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

    # 3. Build the provincial simulation and register the link pre-hook.
    # +1 so the run covers sim_end_year *inclusively* (year Y quarter 1 falls on
    # timestep (Y - sim_start_year) * steps_per_year, so the final milestone year
    # is both simulated in full and reached by the link() pre-hook).
    timesteps = (args.sim_end_year - args.sim_start_year + 1) * args.steps_per_year
    config = build_simulation_configuration(len(industries), timesteps=timesteps, seed=args.seed)
    sim = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=config)

    reader = CIMSDataReader(processed_dir)
    sim.prehooks.append(
        build_link_prehook(reader, sector_map, industries, years, args.iteration)
    )

    logger.info("Running provincial macroABM for %d timesteps", timesteps)
    sim.run()

    # 4. Collect production and write the feedback policy for the next CIMS run.
    production_by_region = collect_production(
        sim, args.sim_end_year, args.sim_start_year, args.steps_per_year,
        args.cims_base_year, args.cims_year_step,
    )
    writer = CIMSProductionWriter(
        cims_model_dir=args.cims_model_dir.resolve(),
        output_dir=args.feedback_dir.resolve(),
        sector_map=sector_map,
        anchor_year=args.cims_base_year + args.cims_year_step,
    )
    written = writer.write(production_by_region, itr=args.iteration)
    logger.info("Wrote %d CIMS feedback policy files", len(written))

    # Save a reference copy of production per province.
    for province, df in production_by_region.items():
        df.to_csv(output_dir / f"production_annual_{args.iteration}_{province}.csv")

    # 5. Provincial GDP growth for the convergence check.
    growth = compute_gdp_growth(sim)
    with open(output_dir / "gdp_growth.json", "w", encoding="utf-8") as f:
        json.dump(growth, f, indent=2)
    logger.info("Saved provincial GDP growth for %d provinces", len(growth))


if __name__ == "__main__":
    main()
