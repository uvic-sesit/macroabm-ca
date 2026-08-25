"""CIMS--macroABM linkage data processing.

Public API for the preprocessing (CIMS results -> macroABM inputs) and
postprocessing (macroABM production -> CIMS service requests) steps of the
CIMS--macroABM linkage.  None of this logic lives in the CIMS model itself;
CIMS only ever reads/writes standard files.
"""

from .cims_production_writer import CIMSProductionWriter
from .cims_results_extractor import CIMSResultsExtractor
from .linkage_state import LinkageState, gdp_growth_converged
from .sector_map import SectorMap

__all__ = [
    "CIMSResultsExtractor",
    "CIMSProductionWriter",
    "LinkageState",
    "gdp_growth_converged",
    "SectorMap",
]
