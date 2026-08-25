"""Editable CIMS <-> macroABM sector and region mapping.

The CIMS--macroABM linkage needs to translate between two different sector
classifications and two different regional classifications:

* CIMS uses ~23 named sectors (``Coal Mining``, ``Light Industrial`` ...),
  named fuels (``Coal``, ``Natural Gas`` ...) and 7 regions where the four
  Atlantic provinces are lumped into a single ``AT`` region.
* macroABM uses the ~50 sub-code ISIC industries of the disaggregated Canadian
  IO table (``A01``, ``B05a``, ``D01a`` ...) and the 10 individual provinces
  (``CAN_AB`` ... ``CAN_PE``).

Historically these correspondences were hard-coded inside the CIMS model
(``industry_dict`` / ``goods_dict`` / ``elec_tech_dict``) which meant changing
the classification required editing CIMS source code, and a malformed entry
crashed the whole run.  This module instead loads the mapping from two plain
CSV files that an analyst can edit freely:

* ``data/cims_macro_sector_map.csv``  (macro_code -> CIMS sector / fuels / flags)
* ``data/cims_macro_region_map.csv``  (macro province -> CIMS region)

All lookups degrade gracefully: an unmapped or misspelled entry is skipped with
a warning rather than raising, so editing the CSV can never crash a model run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_SECTOR_MAP_PATH = _DATA_DIR / "cims_macro_sector_map.csv"
DEFAULT_REGION_MAP_PATH = _DATA_DIR / "cims_macro_region_map.csv"

# Columns the sector-map CSV must contain.
_REQUIRED_SECTOR_COLUMNS = {
    "macro_code",
    "cims_sector",
    "cims_fuel_names",
    "is_energy_bundle",
    "is_cims_comparable",
    "feedback_enabled",
}
_REQUIRED_REGION_COLUMNS = {"macro_region", "cims_region"}

# Separator used inside the ``cims_fuel_names`` cell to list several CIMS fuels
# that should all map onto a single macroABM good (e.g. refined products).
_FUEL_SEPARATOR = ";"


def _to_bool(value: object) -> bool:
    """Parse a spreadsheet-style boolean cell without raising."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "t"}


def _clean(value: object) -> str:
    """Return a stripped string, treating NaN/empty as ''."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


@dataclass
class SectorMap:
    """Resolved CIMS <-> macroABM sector and region correspondences.

    Build with :meth:`load`.  All attributes are derived from the editable CSV
    files; this object performs no file I/O after construction.
    """

    # macro_code -> CIMS sector name (only rows with feedback_enabled=True).
    macro_to_cims_sector: dict[str, str] = field(default_factory=dict)
    # CIMS sector name -> representative macro_code (for extracting result rows).
    cims_sector_to_macro: dict[str, str] = field(default_factory=dict)
    # CIMS fuel leaf name -> representative macro_code (for extracting result columns).
    cims_fuel_to_macro: dict[str, str] = field(default_factory=dict)
    # Ordered macro_codes flagged as energy-bundle goods.
    energy_bundle_codes: list[str] = field(default_factory=list)
    # Ordered macro_codes flagged as CIMS-comparable producing industries.
    comparable_codes: list[str] = field(default_factory=list)
    # macro province code -> CIMS region code (Atlantic provinces -> 'AT').
    macro_region_to_cims: dict[str, str] = field(default_factory=dict)
    # CIMS region code -> list of macro province codes that aggregate into it.
    cims_region_to_macro: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        sector_map_path: str | Path | None = None,
        region_map_path: str | Path | None = None,
    ) -> "SectorMap":
        """Load and validate the mapping CSVs.

        Args:
            sector_map_path: Override for the sector-map CSV (defaults to the
                packaged ``cims_macro_sector_map.csv``).
            region_map_path: Override for the region-map CSV (defaults to the
                packaged ``cims_macro_region_map.csv``).
        """
        sector_path = Path(sector_map_path) if sector_map_path else DEFAULT_SECTOR_MAP_PATH
        region_path = Path(region_map_path) if region_map_path else DEFAULT_REGION_MAP_PATH

        sectors = cls._load_sector_csv(sector_path)
        regions = cls._load_region_csv(region_path)
        return cls(**sectors, **regions)

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_sector_csv(path: Path) -> dict:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        missing = _REQUIRED_SECTOR_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Sector map {path} is missing required column(s): {sorted(missing)}"
            )

        macro_to_cims_sector: dict[str, str] = {}
        cims_sector_to_macro: dict[str, str] = {}
        cims_fuel_to_macro: dict[str, str] = {}
        energy_bundle_codes: list[str] = []
        comparable_codes: list[str] = []

        for _, row in df.iterrows():
            macro_code = _clean(row["macro_code"])
            if not macro_code:
                continue

            cims_sector = _clean(row["cims_sector"])
            if _to_bool(row["is_energy_bundle"]):
                energy_bundle_codes.append(macro_code)
            if _to_bool(row["is_cims_comparable"]):
                comparable_codes.append(macro_code)

            if cims_sector:
                # First macro_code seen for a CIMS sector becomes the
                # representative row used when extracting CIMS results.
                cims_sector_to_macro.setdefault(cims_sector, macro_code)
                if _to_bool(row["feedback_enabled"]):
                    macro_to_cims_sector[macro_code] = cims_sector

            for fuel in _clean(row["cims_fuel_names"]).split(_FUEL_SEPARATOR):
                fuel = fuel.strip()
                if fuel:
                    cims_fuel_to_macro.setdefault(fuel, macro_code)

        return {
            "macro_to_cims_sector": macro_to_cims_sector,
            "cims_sector_to_macro": cims_sector_to_macro,
            "cims_fuel_to_macro": cims_fuel_to_macro,
            "energy_bundle_codes": energy_bundle_codes,
            "comparable_codes": comparable_codes,
        }

    @staticmethod
    def _load_region_csv(path: Path) -> dict:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        missing = _REQUIRED_REGION_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Region map {path} is missing required column(s): {sorted(missing)}"
            )

        macro_region_to_cims: dict[str, str] = {}
        cims_region_to_macro: dict[str, list[str]] = {}
        for _, row in df.iterrows():
            macro_region = _clean(row["macro_region"])
            cims_region = _clean(row["cims_region"])
            if not macro_region or not cims_region:
                continue
            macro_region_to_cims[macro_region] = cims_region
            cims_region_to_macro.setdefault(cims_region, []).append(macro_region)

        return {
            "macro_region_to_cims": macro_region_to_cims,
            "cims_region_to_macro": cims_region_to_macro,
        }

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def energy_bundle_for(self, industries: list[str]) -> list[str]:
        """Energy-bundle macro codes present in *industries*, in model order."""
        flagged = set(self.energy_bundle_codes)
        return [code for code in industries if code in flagged]

    def comparable_for(self, industries: list[str]) -> list[str]:
        """CIMS-comparable macro codes present in *industries*, in model order."""
        flagged = set(self.comparable_codes)
        return [code for code in industries if code in flagged]

    def cims_region(self, macro_region: str) -> str | None:
        """CIMS region for a macro province code, or None (with a warning)."""
        cims = self.macro_region_to_cims.get(macro_region)
        if cims is None:
            logger.warning("No CIMS region mapping for macro region %r", macro_region)
        return cims
