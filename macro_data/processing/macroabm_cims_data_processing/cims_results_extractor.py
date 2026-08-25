"""Extract macroABM linkage inputs from standard CIMS result files.

This module replaces the bespoke ``extract_*`` methods that used to live inside
the CIMS model (``CIMS/model.py`` in the old ``CIMS_v1_fork``).  Instead of
reaching into CIMS' in-memory graph, it reads the *standard* CSV files that any
unmodified CIMS run already produces:

* ``{scenario}_results_general.csv`` -- long-format results containing, among
  other parameters, ``quantity_requested`` or ``requested_quantities`` (energy/
  intermediate demand by producing sector and fuel/good target; label varies by
  CIMS version).
* ``results_tech.csv`` -- technology-level results containing ``capital cost``
  and ``output`` and -- once the logging template is extended -- ``new_stock``
  and ``total_stock``.

From these it reconstructs, per CIMS region and milestone year:

* ``requested_quantities`` -- a (macro_code x macro_code) matrix of demand by
  producing industry (rows) for each input good (columns).
* ``investment`` -- a (macro_code x macro_code) matrix built by computing each
  producing sector's total investment
  ``sum(new_stock * capital_cost / max(output, output_floor))`` and allocating
  it across goods in proportion to that sector's requested quantities.  The
  output floor is the configured percentile (default 1st) of positive
  technology-level outputs for that milestone year (all regions), which stops
  near-zero ``output`` rows from producing pathological investment spikes.

Because the mapping between CIMS and macroABM classifications is loaded from an
editable CSV (see :mod:`.sector_map`), any sector/fuel that cannot be mapped is
skipped with a warning rather than raising -- editing the mapping can never
crash a run.

NOTE FOR CIMS MAINTAINERS:
    ``new_stock`` and ``total_stock`` are *not* in CIMS' default logging
    templates.  The linkage adds them to ``results/results_tech.txt`` (a data
    file, not code).  If a future CIMS version is pulled without that template
    change, investment/stock extraction will be empty -- this is intentionally
    degraded (warned), not fatal.  See the linkage documentation.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .sector_map import SectorMap

logger = logging.getLogger(__name__)

# Parameter names as they appear in the standard CIMS result CSVs.
_PARAM_QUANTITY_NAMES = ("quantity_requested", "requested_quantities")
_PARAM_CAPITAL_COST = "capital cost"
_PARAM_OUTPUT = "output"
_PARAM_NEW_STOCK = "new_stock"
_PARAM_TOTAL_STOCK = "total_stock"
_PARAM_SERVICE_REQUESTED = "service requested"

# Energy intensity normalises requested quantities by the sector's activity
# level: the CIMS *Region-level* ``service requested`` driver -- rows with an
# empty sector/technology whose ``target`` is ``CIMS.CAN.<region>.<sector>``.
# This is the sector's real final-service demand in its own unit (tonne, PJ,
# m3, ...), the same quantity the MacroABM->CIMS writer anchors on, so both
# linkage directions share one activity basis.  The *deeper*
# ``Type=Sector``/``Type=Service`` nodes are internal service ratios normalised
# to 1.0 and are deliberately ignored.  (A naive sum of technology-level
# ``output`` is NOT used: it mixes units -- e.g. GJ of compression + tonne of
# ore -- across nested tree levels and double-counts competing technologies at
# each node.)  Because only anchor-relative *ratios* are used downstream, the
# sector-specific unit cancels.

# Columns we rely on in the long-format result files.
_RESULT_COLUMNS = {"region", "sector", "year", "technology", "parameter", "target", "value"}

# Default lower bound for the investment denominator: 1st percentile of positive
# technology-level outputs in the milestone year (all CIMS regions).
_DEFAULT_OUTPUT_FLOOR_PERCENTILE = 1.0


def _fuel_leaf(target: str) -> str:
    """Return the leaf name of a CIMS target branch (last dot-separated token)."""
    return str(target).split(".")[-1].strip()


class CIMSResultsExtractor:
    """Builds macroABM linkage matrices from standard CIMS result files.

    Args:
        results_dir: Directory holding a CIMS run's result CSVs (the folder
            ``scenario_runner.py`` writes to, e.g. ``cims/outputs/Reference``).
        sector_map: Resolved :class:`SectorMap`.  Defaults to the packaged map.
        steps_per_year: macroABM timesteps per calendar year; annual CIMS values
            are divided by this to obtain per-step quantities (default 4).
        output_floor_percentile: Percentile (0–100) of positive technology-level
            ``output`` values used as the investment denominator floor.  Default
            ``1.0`` (1st percentile).  Set to ``0`` to disable flooring aside from
            the legacy zero→NaN behaviour.
    """

    def __init__(
        self,
        results_dir: str | Path,
        sector_map: SectorMap | None = None,
        steps_per_year: int = 4,
        output_floor_percentile: float = _DEFAULT_OUTPUT_FLOOR_PERCENTILE,
    ) -> None:
        if not 0.0 <= output_floor_percentile <= 100.0:
            raise ValueError(
                f"output_floor_percentile must be in [0, 100], got {output_floor_percentile}"
            )
        self.results_dir = Path(results_dir)
        self.sector_map = sector_map or SectorMap.load()
        self.steps_per_year = steps_per_year
        self.output_floor_percentile = float(output_floor_percentile)
        self._general: pd.DataFrame | None = None
        self._tech: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def _find_general_results(self) -> Path | None:
        matches = sorted(self.results_dir.glob("*_results_general.csv"))
        if not matches:
            logger.warning("No *_results_general.csv found in %s", self.results_dir)
            return None
        return matches[0]

    @staticmethod
    def _read_results(path: Path) -> pd.DataFrame:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        missing = _RESULT_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"CIMS results {path} missing column(s): {sorted(missing)}")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        return df

    @property
    def general(self) -> pd.DataFrame:
        if self._general is None:
            path = self._find_general_results()
            self._general = self._read_results(path) if path else pd.DataFrame()
        return self._general

    @property
    def tech(self) -> pd.DataFrame:
        if self._tech is None:
            path = self.results_dir / "results_tech.csv"
            self._tech = self._read_results(path) if path.exists() else pd.DataFrame()
            if self._tech.empty:
                logger.warning("No results_tech.csv in %s; investment will be empty.", self.results_dir)
        return self._tech

    # ------------------------------------------------------------------
    # Matrix construction
    # ------------------------------------------------------------------

    def requested_quantities(self, region: str, year: int, industries: list[str]) -> pd.DataFrame:
        """Build the requested-quantities matrix for one CIMS region and year.

        Rows are producing industries (macro codes), columns are input goods
        (macro codes); both are reindexed to *industries* with zeros elsewhere.
        Values are divided by ``steps_per_year``.
        """
        matrix = pd.DataFrame(0.0, index=industries, columns=industries)
        df = self.general
        if df.empty:
            return matrix

        mask = (
            (df["parameter"].isin(_PARAM_QUANTITY_NAMES))
            & (df["region"] == region)
            & (df["year"] == year)
            & (df["technology"] == "")
            & (df["target"] != "")
            & (df["context"] != "Total" if "context" in df.columns else True)
        )
        subset = df[mask]

        unmapped_sectors: set[str] = set()
        unmapped_fuels: set[str] = set()
        for _, row in subset.iterrows():
            macro_row = self.sector_map.cims_sector_to_macro.get(row["sector"])
            macro_col = self.sector_map.cims_fuel_to_macro.get(_fuel_leaf(row["target"]))
            if macro_row is None:
                unmapped_sectors.add(row["sector"])
                continue
            if macro_col is None:
                unmapped_fuels.add(_fuel_leaf(row["target"]))
                continue
            if macro_row in matrix.index and macro_col in matrix.columns:
                value = row["value"]
                if pd.notna(value):
                    matrix.loc[macro_row, macro_col] += float(value)

        if unmapped_sectors:
            logger.debug("[%s %s] unmapped producing sectors: %s", region, year, sorted(unmapped_sectors))
        if unmapped_fuels:
            logger.debug("[%s %s] unmapped fuels/goods: %s", region, year, sorted(unmapped_fuels))

        return matrix / float(self.steps_per_year)

    def _output_floor(self, year: int) -> float | None:
        """Return the investment output floor for *year*, or None if disabled/unavailable.

        Uses the configured percentile of strictly positive technology-level
        ``output`` values across **all regions** for that milestone year so a
        cluster of near-zero outputs in one province cannot set the floor.
        """
        if self.output_floor_percentile <= 0.0:
            return None

        df = self.tech
        if df.empty:
            return None

        outputs = df[
            (df["year"] == year)
            & (df["technology"] != "")
            & (df["parameter"] == _PARAM_OUTPUT)
        ]["value"]
        positive = pd.to_numeric(outputs, errors="coerce")
        positive = positive[np.isfinite(positive) & (positive > 0.0)]
        if positive.empty:
            return None

        floor = float(np.percentile(positive.to_numpy(), self.output_floor_percentile))
        if not np.isfinite(floor) or floor <= 0.0:
            return None
        return floor

    def _sector_investment_totals(self, region: str, year: int) -> dict[str, float]:
        """Total investment per CIMS sector: sum(new_stock * capital_cost / output).

        Near-zero (or zero) technology ``output`` values are replaced by an
        output floor before division so ``new_stock * capital_cost / output``
        cannot explode.  See :meth:`_output_floor`.
        """
        df = self.tech
        if df.empty:
            return {}

        base = df[(df["region"] == region) & (df["year"] == year) & (df["technology"] != "")]
        if base.empty:
            return {}

        pivot = (
            base[base["parameter"].isin([_PARAM_CAPITAL_COST, _PARAM_OUTPUT, _PARAM_NEW_STOCK])]
            .pivot_table(
                index=["sector", "node", "technology"],
                columns="parameter",
                values="value",
                aggfunc="sum",
            )
        )
        for col in (_PARAM_CAPITAL_COST, _PARAM_OUTPUT, _PARAM_NEW_STOCK):
            if col not in pivot.columns:
                pivot[col] = np.nan

        raw_output = pd.to_numeric(pivot[_PARAM_OUTPUT], errors="coerce")
        floor = self._output_floor(year)
        if floor is None:
            denom = raw_output.replace(0.0, np.nan)
        else:
            # Non-positive / missing output → floor; positive-but-tiny → clip up.
            floored = raw_output.isna() | (raw_output <= 0.0) | (raw_output < floor)
            n_floored = int(floored.sum())
            if n_floored:
                logger.warning(
                    "[%s %s] applying output floor %.6g (p%s of year-positive outputs) "
                    "to %d/%d technologies in investment denominator",
                    region,
                    year,
                    floor,
                    self.output_floor_percentile,
                    n_floored,
                    len(raw_output),
                )
            denom = raw_output.where(~floored, floor)

        tech_investment = pivot[_PARAM_NEW_STOCK] * pivot[_PARAM_CAPITAL_COST] / denom
        tech_investment = tech_investment.fillna(0.0)

        totals = tech_investment.groupby(level="sector").sum()
        return {str(sector): float(val) for sector, val in totals.items()}

    def investment(
        self,
        region: str,
        year: int,
        industries: list[str],
        requested_quantities: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Build the investment matrix for one CIMS region and year.

        Each producing sector's total investment is allocated across input
        goods in proportion to its requested quantities, mirroring the old
        per-technology allocation aggregated to the sector level.
        """
        matrix = pd.DataFrame(0.0, index=industries, columns=industries)
        totals = self._sector_investment_totals(region, year)
        if not totals:
            return matrix

        if requested_quantities is None:
            requested_quantities = self.requested_quantities(region, year, industries)

        for cims_sector, total in totals.items():
            macro_row = self.sector_map.cims_sector_to_macro.get(cims_sector)
            if macro_row is None or macro_row not in matrix.index or total == 0.0:
                continue
            row_shares = requested_quantities.loc[macro_row]
            row_sum = row_shares.sum()
            if row_sum <= 0:
                continue
            matrix.loc[macro_row] += (row_shares / row_sum) * (total / float(self.steps_per_year))

        return matrix

    def _sector_capital_stock_totals(self, region: str, year: int) -> dict[str, float]:
        """Total capital *stock* value per CIMS sector: sum(total_stock * capital_cost).

        Unlike :meth:`_sector_investment_totals` -- which uses the lumpy annual
        ``new_stock`` *flow* and therefore needs an output floor to keep it finite
        -- this uses the durable ``total_stock``.  The capital stock changes only
        gradually year-on-year (assets are long-lived), so its ratio to the anchor
        year is smooth, which is the correct basis for a capital-*stock*
        productivity target.  No per-technology output division and no output
        floor are applied.
        """
        df = self.tech
        if df.empty:
            return {}
        base = df[(df["region"] == region) & (df["year"] == year) & (df["technology"] != "")]
        if base.empty:
            return {}
        pivot = (
            base[base["parameter"].isin([_PARAM_CAPITAL_COST, _PARAM_TOTAL_STOCK])]
            .pivot_table(
                index=["sector", "node", "technology"],
                columns="parameter",
                values="value",
                aggfunc="sum",
            )
        )
        for col in (_PARAM_CAPITAL_COST, _PARAM_TOTAL_STOCK):
            if col not in pivot.columns:
                pivot[col] = np.nan
        tech_capital = (pivot[_PARAM_TOTAL_STOCK] * pivot[_PARAM_CAPITAL_COST]).fillna(0.0)
        if tech_capital.empty:
            return {}
        totals = tech_capital.groupby(level="sector").sum()
        return {str(sector): float(val) for sector, val in totals.items()}

    def capital_stock(
        self,
        region: str,
        year: int,
        industries: list[str],
        requested_quantities: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Build the capital-stock matrix (durable capital stock value by sector and good).

        Each producing sector's total capital stock value
        (``sum(total_stock * capital_cost)``) is allocated across input goods in
        proportion to its requested quantities -- mirroring :meth:`investment` but
        on the durable stock rather than the annual flow (so no per-step division
        and no output floor).
        """
        matrix = pd.DataFrame(0.0, index=industries, columns=industries)
        totals = self._sector_capital_stock_totals(region, year)
        if not totals:
            return matrix

        if requested_quantities is None:
            requested_quantities = self.requested_quantities(region, year, industries)

        for cims_sector, total in totals.items():
            macro_row = self.sector_map.cims_sector_to_macro.get(cims_sector)
            if macro_row is None or macro_row not in matrix.index or total == 0.0:
                continue
            row_shares = requested_quantities.loc[macro_row]
            row_sum = row_shares.sum()
            if row_sum <= 0:
                continue
            matrix.loc[macro_row] += (row_shares / row_sum) * total

        return matrix

    # ------------------------------------------------------------------
    # Energy intensity (energy per unit sector activity)
    # ------------------------------------------------------------------

    def _sector_activity(self, region: str, year: int) -> dict[str, float]:
        """Return each CIMS sector's activity level for *region*/*year*.

        The activity level is the denominator of energy intensity, keyed by CIMS
        sector name.  It is the Region-level ``service requested`` driver (an
        empty sector/technology row whose ``target`` is
        ``CIMS.CAN.<region>.<sector>``); deeper normalised service nodes and
        higher aggregates are skipped.
        """
        df = self.general
        if df.empty:
            return {}
        mask = (
            (df["parameter"] == _PARAM_SERVICE_REQUESTED)
            & (df["region"] == region)
            & (df["year"] == year)
            & (df["technology"] == "")
            & (df["sector"] == "")
            & (df["target"] != "")
        )
        subset = df[mask]
        totals: dict[str, float] = {}
        for _, row in subset.iterrows():
            # Region-level rows have target ``CIMS.CAN.<region>.<sector>`` (four
            # dot-separated tokens); the leaf is the CIMS sector name.  Higher
            # aggregates (province/national) and deeper normalised service nodes
            # have a different token count and are skipped.
            parts = str(row["target"]).split(".")
            if len(parts) != 4:
                continue
            cims_sector = parts[-1].strip()
            value = row["value"]
            if cims_sector and pd.notna(value):
                totals[cims_sector] = totals.get(cims_sector, 0.0) + float(value)
        return totals

    def energy_intensity(
        self,
        region: str,
        year: int,
        industries: list[str],
        requested_quantities: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Build the energy-intensity matrix (energy per unit output) for a region/year.

        Rows are producing industries (macro codes), columns are input goods
        (macro codes).  Each producing sector's requested quantities are divided
        by that sector's activity level (see :meth:`_sector_activity`), giving a
        physical energy-per-unit-output measure.  Sectors with a missing or
        non-positive activity level are left as zeros (no intensity signal), and
        the downstream linkage skips zero entries rather than dividing by them.
        """
        if requested_quantities is None:
            requested_quantities = self.requested_quantities(region, year, industries)

        matrix = pd.DataFrame(0.0, index=industries, columns=industries)
        activity = self._sector_activity(region, year)
        if not activity:
            logger.warning(
                "[%s %s] no Region-level service-requested activity found; energy intensity will be empty.",
                region, year,
            )
            return matrix

        for cims_sector, level in activity.items():
            macro_row = self.sector_map.cims_sector_to_macro.get(cims_sector)
            if macro_row is None or macro_row not in matrix.index:
                continue
            if not np.isfinite(level) or level <= 0.0:
                continue
            matrix.loc[macro_row] = requested_quantities.loc[macro_row] / level
        return matrix

    def capital_intensity(
        self,
        region: str,
        year: int,
        industries: list[str],
        capital_stock: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Build the capital-intensity matrix (capital *stock* per unit activity).

        Same layout and activity denominator as :meth:`energy_intensity`, but the
        numerator is the durable capital *stock* value (see :meth:`capital_stock`),
        not the annual investment *flow*.  Because the stock changes only
        gradually, its year-on-year ratio is smooth, so the intensity-target
        linkage sets a gently-changing capital-stock target rather than imposing a
        lumpy one-year investment as an immediate cost (which previously produced
        large spurious cost/price shocks in extraction sectors).  The MacroABM's
        own depreciation dynamics then spread that stock's cost over the asset
        life.
        """
        if capital_stock is None:
            capital_stock = self.capital_stock(region, year, industries)

        matrix = pd.DataFrame(0.0, index=industries, columns=industries)
        activity = self._sector_activity(region, year)
        if not activity:
            return matrix

        for cims_sector, level in activity.items():
            macro_row = self.sector_map.cims_sector_to_macro.get(cims_sector)
            if macro_row is None or macro_row not in matrix.index:
                continue
            if not np.isfinite(level) or level <= 0.0:
                continue
            matrix.loc[macro_row] = capital_stock.loc[macro_row] / level
        return matrix

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def process(
        self,
        region: str,
        years: list[int],
        industries: list[str],
        export_dir: str | Path,
        itr: str,
    ) -> None:
        """Extract and write processed matrices for every milestone year.

        Writes ``requested_quantities_{itr}_{year}_{region}.csv``,
        ``investment_{itr}_{year}_{region}.csv`` and
        ``energy_intensity_{itr}_{year}_{region}.csv`` to *export_dir*.
        """
        export_path = Path(export_dir)
        export_path.mkdir(parents=True, exist_ok=True)
        for year in years:
            rq = self.requested_quantities(region, year, industries)
            inv = self.investment(region, year, industries, requested_quantities=rq)
            intensity = self.energy_intensity(region, year, industries, requested_quantities=rq)
            cap_stock = self.capital_stock(region, year, industries, requested_quantities=rq)
            cap_intensity = self.capital_intensity(region, year, industries, capital_stock=cap_stock)
            rq.to_csv(export_path / f"requested_quantities_{itr}_{year}_{region}.csv")
            inv.to_csv(export_path / f"investment_{itr}_{year}_{region}.csv")
            intensity.to_csv(export_path / f"energy_intensity_{itr}_{year}_{region}.csv")
            cap_intensity.to_csv(export_path / f"capital_intensity_{itr}_{year}_{region}.csv")
            logger.info(
                "[%s %s itr=%s] wrote requested_quantities + investment + energy/capital intensity",
                region, year, itr,
            )
