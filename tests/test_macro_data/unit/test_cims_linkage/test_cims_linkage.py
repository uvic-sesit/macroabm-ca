"""Unit tests for the CIMS--macroABM linkage processing modules.

These exercise the editable sector map, the CIMS-results extractor, the
processed-data reader, the production writer (including byte-format checks
against the CIMS service-request CSV schema), and the convergence helper.  None
require running the macroABM or CIMS models.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_data.processing.macroabm_cims_data_processing import (
    CIMSProductionWriter,
    CIMSResultsExtractor,
    LinkageState,
    SectorMap,
    gdp_growth_converged,
)
from macro_data.readers.cims_data import CIMSDataReader

# A small but representative industry list spanning energy + non-energy codes.
INDUSTRIES = ["A01", "B05a", "B05b", "C19", "D01a", "G", "K"]


# ---------------------------------------------------------------------------
# SectorMap
# ---------------------------------------------------------------------------

def test_sector_map_loads_defaults():
    sm = SectorMap.load()
    # Energy bundle should include the canonical energy goods.
    for code in ["B05a", "B05b", "B05c", "C19", "D01a", "D01b", "D01c", "D01d", "D01e"]:
        assert code in sm.energy_bundle_codes
    # Comparable codes cover A-H aggregates but not service codes K/L/...
    assert "A01" in sm.comparable_codes
    assert "K" not in sm.comparable_codes
    # Producing-sector and fuel inversion.
    assert sm.cims_sector_to_macro["Coal Mining"] == "B05a"
    assert sm.cims_fuel_to_macro["Natural Gas"] == "B05b"
    # Feedback mapping (macro -> CIMS sector).
    assert sm.macro_to_cims_sector["B05a"] == "Coal Mining"


def test_region_map_atlantic_lumped():
    sm = SectorMap.load()
    assert sm.macro_region_to_cims["CAN_AB"] == "AB"
    for prov in ["CAN_NB", "CAN_NL", "CAN_NS", "CAN_PE"]:
        assert sm.macro_region_to_cims[prov] == "AT"
    assert set(sm.cims_region_to_macro["AT"]) == {"CAN_NB", "CAN_NL", "CAN_NS", "CAN_PE"}


def test_sector_map_helpers_filter_to_model_industries():
    sm = SectorMap.load()
    bundle = sm.energy_bundle_for(INDUSTRIES)
    assert bundle == ["B05a", "B05b", "C19", "D01a"]  # preserves model order
    assert "A01" in sm.comparable_for(INDUSTRIES)


def test_sector_map_missing_column_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("macro_code,cims_sector\nA01,Agriculture\n")
    with pytest.raises(ValueError):
        SectorMap.load(sector_map_path=bad)


# ---------------------------------------------------------------------------
# CIMSResultsExtractor
# ---------------------------------------------------------------------------

def _write_general_results(path, *, quantity_parameter: str = "quantity_requested"):
    """Minimal results_general.csv with quantity rows for AB / 2025."""
    rows = [
        # Coal Mining requests Coal and Natural Gas.
        ("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "", quantity_parameter, "", "", "CIMS.Generic Fuels.Coal", "GJ", 400.0),
        ("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "", quantity_parameter, "", "", "CIMS.Generic Fuels.Natural Gas", "GJ", 100.0),
        # A 'Total' aggregate row that must be ignored.
        ("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "", quantity_parameter, "Total", "", "", "GJ", 500.0),
        # Light Industrial requests refined product (Diesel -> C19).
        ("CIMS.CAN.AB.Light Industrial", "AB", "Light Industrial", 2025, "", quantity_parameter, "", "", "CIMS.Generic Fuels.Diesel", "GJ", 80.0),
        # A tech-level row that must be ignored at the requested-quantities step.
        ("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "SomeTech", quantity_parameter, "", "", "CIMS.Generic Fuels.Coal", "GJ", 999.0),
    ]
    cols = ["node", "region", "sector", "year", "technology", "parameter", "context", "sub_context", "target", "unit", "value"]
    pd.DataFrame(rows, columns=cols).to_csv(path / "Reference_results_general.csv", index=False)


def _write_tech_results(path, rows=None):
    """Minimal results_tech.csv with new_stock / capital cost / output for AB / 2025."""
    if rows is None:
        rows = [
            ("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "T1", "new_stock", "", "", "", "", 10.0),
            ("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "T1", "capital cost", "", "", "", "", 2.0),
            ("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "T1", "output", "", "", "", "", 1.0),
        ]
    cols = ["node", "region", "sector", "year", "technology", "parameter", "context", "sub_context", "target", "unit", "value"]
    pd.DataFrame(rows, columns=cols).to_csv(path / "results_tech.csv", index=False)


def _tech_row(node, region, sector, year, tech, parameter, value):
    return (node, region, sector, year, tech, parameter, "", "", "", "", value)


def test_extractor_requested_quantities(tmp_path):
    _write_general_results(tmp_path)
    extractor = CIMSResultsExtractor(tmp_path, steps_per_year=4)
    rq = extractor.requested_quantities("AB", 2025, INDUSTRIES)

    # Coal -> B05a column, Natural Gas -> B05b column, on the Coal Mining row (B05a).
    assert rq.loc["B05a", "B05a"] == pytest.approx(400.0 / 4)
    assert rq.loc["B05a", "B05b"] == pytest.approx(100.0 / 4)
    # Diesel -> C19 column on Light Industrial row (mapped to C10T12... not in INDUSTRIES) -> skipped.
    # Total row and tech-level row must not leak in.
    assert rq.loc["B05a"].sum() == pytest.approx(500.0 / 4)


def test_extractor_requested_quantities_accepts_requested_quantities_label(tmp_path):
    _write_general_results(tmp_path, quantity_parameter="requested_quantities")
    extractor = CIMSResultsExtractor(tmp_path, steps_per_year=4)
    rq = extractor.requested_quantities("AB", 2025, INDUSTRIES)

    assert rq.loc["B05a", "B05a"] == pytest.approx(400.0 / 4)
    assert rq.loc["B05a", "B05b"] == pytest.approx(100.0 / 4)
    assert rq.loc["B05a"].sum() == pytest.approx(500.0 / 4)


def test_extractor_investment_allocates_by_requested_shares(tmp_path):
    _write_general_results(tmp_path)
    _write_tech_results(tmp_path)
    extractor = CIMSResultsExtractor(tmp_path, steps_per_year=4)
    rq = extractor.requested_quantities("AB", 2025, INDUSTRIES)
    inv = extractor.investment("AB", 2025, INDUSTRIES, requested_quantities=rq)

    # Total investment = new_stock * capital_cost / output = 10 * 2 / 1 = 20, /4 = 5.
    # Allocated across goods by requested shares (Coal 0.8, NG 0.2).
    assert inv.loc["B05a", "B05a"] == pytest.approx(5.0 * 0.8)
    assert inv.loc["B05a", "B05b"] == pytest.approx(5.0 * 0.2)


def test_extractor_investment_applies_output_floor_to_near_zero_output(tmp_path):
    """Near-zero output must not explode investment when a year-wide floor exists."""
    _write_general_results(tmp_path)

    # Many healthy techs (output=100) across regions set a ~100 floor at p1; one
    # AB tech has tiny output but non-zero new_stock (Ontario-style singularity).
    rows = []
    for i in range(200):
        region = "ON" if i % 2 == 0 else "AB"
        node = f"CIMS.CAN.{region}.Other"
        tech = f"Healthy{i}"
        rows.extend(
            [
                _tech_row(node, region, "Commercial", 2025, tech, "new_stock", 0.0),
                _tech_row(node, region, "Commercial", 2025, tech, "capital cost", 1.0),
                _tech_row(node, region, "Commercial", 2025, tech, "output", 100.0),
            ]
        )
    rows.extend(
        [
            _tech_row("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "Tiny", "new_stock", 10.0),
            _tech_row("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "Tiny", "capital cost", 2.0),
            _tech_row("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "Tiny", "output", 1e-12),
        ]
    )
    _write_tech_results(tmp_path, rows=rows)

    extractor = CIMSResultsExtractor(tmp_path, steps_per_year=4, output_floor_percentile=1.0)
    floor = extractor._output_floor(2025)
    assert floor == pytest.approx(100.0)

    rq = extractor.requested_quantities("AB", 2025, INDUSTRIES)
    inv = extractor.investment("AB", 2025, INDUSTRIES, requested_quantities=rq)

    # Floored investment = 10 * 2 / 100 = 0.2, / steps_per_year = 0.05.
    assert inv.loc["B05a"].sum() == pytest.approx(0.05)
    # Without a floor this would be ~2e13 per step; keep a generous sanity bound.
    assert inv.to_numpy().sum() < 1.0


def test_extractor_output_floor_can_be_disabled(tmp_path):
    _write_general_results(tmp_path)
    _write_tech_results(
        tmp_path,
        rows=[
            _tech_row("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "T1", "new_stock", 10.0),
            _tech_row("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "T1", "capital cost", 2.0),
            _tech_row("CIMS.CAN.AB.Coal Mining", "AB", "Coal Mining", 2025, "T1", "output", 0.0),
        ],
    )
    extractor = CIMSResultsExtractor(tmp_path, steps_per_year=4, output_floor_percentile=0.0)
    assert extractor._output_floor(2025) is None
    inv = extractor.investment("AB", 2025, INDUSTRIES)
    # Legacy behaviour: exact-zero output → NaN denominator → filled to 0.
    assert inv.to_numpy().sum() == pytest.approx(0.0)


def test_extractor_missing_tech_file_yields_zero_investment(tmp_path):
    _write_general_results(tmp_path)  # no results_tech.csv
    extractor = CIMSResultsExtractor(tmp_path, steps_per_year=4)
    inv = extractor.investment("AB", 2025, INDUSTRIES)
    assert inv.to_numpy().sum() == pytest.approx(0.0)


def test_extractor_process_writes_files_and_reader_roundtrip(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _write_general_results(results_dir)
    _write_tech_results(results_dir)
    export_dir = tmp_path / "cims_data"

    extractor = CIMSResultsExtractor(results_dir, steps_per_year=4)
    extractor.process("AB", [2025], INDUSTRIES, export_dir, itr="00")

    reader = CIMSDataReader(export_dir)
    assert reader.available("00", 2025, "AB")
    rq = reader.get_requested_quantities("00", 2025, "AB")
    assert list(rq.index) == INDUSTRIES
    assert rq.loc["B05a", "B05a"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# CIMSProductionWriter
# ---------------------------------------------------------------------------

_HEADER_LINE = (
    "Branch,Type,Region,Sector,Service,Technology,Parameter,Context,Sub_Context,"
    "Target,Source,Unit,2000,2005,2010,2015,2020,2025,2030,2035,2040,2045,2050,Comments"
)


def _make_cims_model_dir(tmp_path):
    """Create a CIMS csv/model dir with one Coal Mining AB sector file."""
    model_dir = tmp_path / "model"
    folder = model_dir / "sector_coal mining"
    folder.mkdir(parents=True)
    breadcrumb = "CIMS.CAN.AB.Coal Mining," + "<-- nav" + "," * 22
    region_row = (
        "CIMS.CAN.AB,Region,AB,Coal Mining,,,Service requested,,,CIMS.CAN.AB.Coal Mining,,kt,"
        "100,110,120,130,140,150,160,170,180,190,200,"
    )
    (folder / "sector_coal mining_AB.csv").write_text(
        "\n".join([breadcrumb, _HEADER_LINE, region_row]) + "\n"
    )
    return model_dir


def test_production_writer_growth_ratio_and_format(tmp_path):
    model_dir = _make_cims_model_dir(tmp_path)
    out_dir = tmp_path / "out"

    # MacroABM production for Alberta: B05a (Coal Mining) doubles from 2020 to 2050.
    production = pd.DataFrame(
        {"B05a": {2020: 50.0, 2025: 60.0, 2050: 100.0}},
    )
    writer = CIMSProductionWriter(model_dir, out_dir, anchor_year=2020)
    written = writer.write({"CAN_AB": production}, itr="00")

    assert len(written) == 1
    out_file = written[0]
    lines = out_file.read_text().splitlines()
    # Row 1 breadcrumb, row 2 exact header, row 3 data.
    assert lines[1] == _HEADER_LINE
    data = pd.read_csv(out_file, skiprows=1)
    row = data.iloc[0]
    assert row["Parameter"] == "Service requested"
    assert row["Unit"] == "kt"
    assert row["Source"] == "macroABM_linkage"
    # Anchor (2020) preserves CIMS level 140; 2050 scaled by 100/50 = 2x -> 280.
    assert float(row["2020"]) == pytest.approx(140.0)
    assert float(row["2050"]) == pytest.approx(280.0)
    # Historical years (< anchor) untouched.
    assert float(row["2000"]) == pytest.approx(100.0)


def test_production_writer_atlantic_aggregation(tmp_path):
    model_dir = _make_cims_model_dir(tmp_path)
    # Add an AT file so the aggregated Atlantic provinces have a target.
    folder = model_dir / "sector_coal mining"
    breadcrumb = "CIMS.CAN.AT.Coal Mining," + "<-- nav" + "," * 22
    region_row = (
        "CIMS.CAN.AT,Region,AT,Coal Mining,,,Service requested,,,CIMS.CAN.AT.Coal Mining,,kt,"
        "10,11,12,13,14,15,16,17,18,19,20,"
    )
    (folder / "sector_coal mining_AT.csv").write_text(
        "\n".join([breadcrumb, _HEADER_LINE, region_row]) + "\n"
    )
    out_dir = tmp_path / "out"

    prod_nb = pd.DataFrame({"B05a": {2020: 5.0, 2050: 5.0}})
    prod_ns = pd.DataFrame({"B05a": {2020: 5.0, 2050: 15.0}})
    writer = CIMSProductionWriter(model_dir, out_dir, anchor_year=2020)
    written = writer.write({"CAN_NB": prod_nb, "CAN_NS": prod_ns}, itr="00")

    at_files = [p for p in written if p.name.endswith("_AT.csv")]
    assert len(at_files) == 1
    data = pd.read_csv(at_files[0], skiprows=1)
    row = data.iloc[0]
    # Aggregated Atlantic production: 2020 -> 10, 2050 -> 20, ratio 2x; anchor level 14 -> 28.
    assert float(row["2050"]) == pytest.approx(28.0)


# ---------------------------------------------------------------------------
# LinkageState / convergence
# ---------------------------------------------------------------------------

def test_linkage_state_counter():
    state = LinkageState(max_iterations=2)
    assert state.current == "00"
    assert not state.reached_max
    assert state.increment() == "01"
    state.increment()
    assert state.reached_max
    state.reset()
    assert state.current == "00"


def test_gdp_growth_convergence():
    prev = {"CAN_AB": 0.20, "CAN_BC": 0.15}
    # Within 10% relative change -> converged.
    close = {"CAN_AB": 0.21, "CAN_BC": 0.16}
    assert gdp_growth_converged(prev, close, tolerance=0.10)
    # Large move in one province -> not converged.
    far = {"CAN_AB": 0.30, "CAN_BC": 0.16}
    assert not gdp_growth_converged(prev, far, tolerance=0.10)
    # No previous iteration -> not converged.
    assert not gdp_growth_converged({}, close)
