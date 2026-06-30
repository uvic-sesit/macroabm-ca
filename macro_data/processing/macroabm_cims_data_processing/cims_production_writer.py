"""Write macroABM production back into CIMS service-request inputs.

The MacroABM -> CIMS half of the linkage.  After a macroABM run, each province
produces an annual production trajectory by industry.  CIMS, in turn, is driven
by Region-level ``Service requested`` rows (one per sector, per region) that
express activity in *physical* units (``$ million GDP``, ``tonne``,
``1000 m3`` ...).

Rather than convert macroABM's abstract production into those physical units
(which would require fragile per-sector unit conversions and a national->
provincial split), this writer uses a **growth-ratio** method:

    new_request[year] = cims_original[anchor_year] * macro[year] / macro[anchor_year]

i.e. it keeps CIMS' own base-year level and unit, and only re-shapes the
*growth path* of each sector according to macroABM's implied growth.  Years
before the anchor (historical/calibration years) are left untouched.

The output is written as a standard CIMS **policy overlay** -- one folder named
after ``policy_name`` containing ``{policy_name}_{REGION}.csv`` files in exactly
the same 24-column schema as the model/policy CSVs in ``cims-models-fork/csv``.
Adding the policy name to a scenario's ``policies`` list is all CIMS needs; no
CIMS code changes are required.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .sector_map import SectorMap

logger = logging.getLogger(__name__)

# The 24 columns of a CIMS model/policy CSV, in order.
_HEADER = [
    "Branch", "Type", "Region", "Sector", "Service", "Technology", "Parameter",
    "Context", "Sub_Context", "Target", "Source", "Unit",
    "2000", "2005", "2010", "2015", "2020", "2025", "2030", "2035", "2040", "2045", "2050",
    "Comments",
]
_YEAR_COLUMNS = [c for c in _HEADER if c.isdigit()]
_SOURCE_TAG = "macroABM_linkage"


def _sector_folder(cims_sector: str) -> str:
    """CIMS model folder name for a sector (e.g. 'Light Industrial' -> 'sector_light industrial')."""
    return f"sector_{cims_sector.lower()}"


class CIMSProductionWriter:
    """Writes scaled CIMS service-request policy CSVs from macroABM production.

    Args:
        cims_model_dir: Path to ``cims-models-fork/csv/model`` (source of the
            original Region-level service-request trajectories and units).
        output_dir: Directory to write the policy overlay into.
        sector_map: Resolved :class:`SectorMap` (defaults to the packaged map).
        policy_name: Name of the generated CIMS policy (folder + file prefix).
        anchor_year: Year at which CIMS' own level is preserved and macroABM
            growth is anchored (default 2020, the first forecast milestone).
    """

    def __init__(
        self,
        cims_model_dir: str | Path,
        output_dir: str | Path,
        sector_map: SectorMap | None = None,
        policy_name: str = "macroabm_production",
        anchor_year: int = 2020,
    ) -> None:
        self.cims_model_dir = Path(cims_model_dir)
        self.output_dir = Path(output_dir)
        self.sector_map = sector_map or SectorMap.load()
        self.policy_name = policy_name
        self.anchor_year = anchor_year

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def write(self, production_by_region: dict[str, pd.DataFrame], itr: str | None = None) -> list[Path]:
        """Write one policy CSV per CIMS region.

        Args:
            production_by_region: Maps macroABM province code (``CAN_AB`` ...)
                to a DataFrame of annual production indexed by milestone year
                with macro industry codes as columns.
            itr: Optional iteration label (used only in log messages).

        Returns:
            List of written file paths.
        """
        cims_region_production = self._aggregate_to_cims_regions(production_by_region)

        written: list[Path] = []
        policy_dir = self.output_dir / self.policy_name
        policy_dir.mkdir(parents=True, exist_ok=True)

        for cims_region, sector_growth in cims_region_production.items():
            rows = []
            for cims_sector, growth in sector_growth.items():
                row = self._build_row(cims_region, cims_sector, growth)
                if row is not None:
                    rows.append(row)
            if not rows:
                logger.warning("[itr=%s] no service-request rows generated for region %s", itr, cims_region)
                continue
            out_path = policy_dir / f"{self.policy_name}_{cims_region}.csv"
            self._write_csv(out_path, rows)
            written.append(out_path)
            logger.info("[itr=%s] wrote %d sector rows -> %s", itr, len(rows), out_path)

        return written

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate_to_cims_regions(
        self, production_by_region: dict[str, pd.DataFrame]
    ) -> dict[str, dict[str, pd.Series]]:
        """Aggregate macro-province production into CIMS-region, CIMS-sector growth.

        Returns ``{cims_region: {cims_sector: Series(indexed by year)}}`` where
        each Series is the summed macroABM production for the macro codes that
        map onto that CIMS sector.
        """
        # Sum macro provinces that share a CIMS region (Atlantic -> AT).
        region_frames: dict[str, list[pd.DataFrame]] = {}
        for macro_region, df in production_by_region.items():
            cims_region = self.sector_map.macro_region_to_cims.get(macro_region)
            if cims_region is None:
                logger.warning("Skipping unmapped macro province %r", macro_region)
                continue
            region_frames.setdefault(cims_region, []).append(df)

        result: dict[str, dict[str, pd.Series]] = {}
        for cims_region, frames in region_frames.items():
            combined = frames[0].copy()
            for extra in frames[1:]:
                combined = combined.add(extra, fill_value=0.0)

            sector_series: dict[str, pd.Series] = {}
            for macro_code in combined.columns:
                cims_sector = self.sector_map.macro_to_cims_sector.get(macro_code)
                if cims_sector is None:
                    continue
                series = combined[macro_code].astype(float)
                if cims_sector in sector_series:
                    sector_series[cims_sector] = sector_series[cims_sector].add(series, fill_value=0.0)
                else:
                    sector_series[cims_sector] = series.copy()
            result[cims_region] = sector_series
        return result

    # ------------------------------------------------------------------
    # Row construction
    # ------------------------------------------------------------------

    def _read_original_service_row(self, cims_region: str, cims_sector: str) -> pd.Series | None:
        """Return the original Region-level 'Service requested' row, if present."""
        folder = _sector_folder(cims_sector)
        path = self.cims_model_dir / folder / f"{folder}_{cims_region}.csv"
        if not path.exists():
            logger.debug("No CIMS source file for %s/%s (%s)", cims_sector, cims_region, path)
            return None
        df = pd.read_csv(path, skiprows=1, dtype=str, keep_default_na=False)
        mask = (df["Type"] == "Region") & (df["Parameter"] == "Service requested")
        matches = df[mask]
        if matches.empty:
            logger.debug("No Region 'Service requested' row in %s", path)
            return None
        return matches.iloc[0]

    def _build_row(self, cims_region: str, cims_sector: str, macro_growth: pd.Series) -> dict | None:
        """Build one scaled service-request row dict, or None if unavailable."""
        original = self._read_original_service_row(cims_region, cims_sector)
        if original is None:
            return None

        anchor_macro = macro_growth.get(self.anchor_year)
        if anchor_macro is None or anchor_macro <= 0:
            logger.warning(
                "No positive macroABM anchor (%s) production for %s/%s; leaving original trajectory.",
                self.anchor_year, cims_sector, cims_region,
            )
            scale_ratio = {}
        else:
            scale_ratio = {
                int(year): float(value) / float(anchor_macro)
                for year, value in macro_growth.items()
                if int(year) >= self.anchor_year
            }

        try:
            anchor_original = float(original[str(self.anchor_year)])
        except (KeyError, ValueError):
            anchor_original = np.nan

        row = {col: original.get(col, "") for col in _HEADER}
        row["Source"] = _SOURCE_TAG
        row["Comments"] = f"Scaled by macroABM linkage (anchor {self.anchor_year})"

        for year_col in _YEAR_COLUMNS:
            year = int(year_col)
            ratio = scale_ratio.get(year)
            if ratio is not None and not np.isnan(anchor_original):
                row[year_col] = repr(anchor_original * ratio)
            # else: keep the original value already copied in.
        return row

    @staticmethod
    def _write_csv(path: Path, rows: list[dict]) -> None:
        breadcrumb = ["" for _ in _HEADER]
        breadcrumb[0] = f"{rows[0]['Branch']}"
        breadcrumb[1] = "<-- generated by macroABM linkage"

        df = pd.DataFrame(rows, columns=_HEADER)
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(",".join(breadcrumb) + "\n")
            df.to_csv(f, index=False)
