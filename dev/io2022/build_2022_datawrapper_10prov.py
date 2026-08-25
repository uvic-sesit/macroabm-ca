"""Build the 10-PROVINCE 2022 DataWrapper (production-workflow variant).

Same as build_2022_datawrapper.py (the colleague's validated 13-region build) except:
  * territories YT/NT/NU are folded into ROW at the IO-table level
    (fold_territories_2022.py) instead of being simulated -- the production
    CER-MacroABM workflow is a 10-province structure end to end, and the CER linkage
    drops the territories from every channel by design;
  * INPUT_PATH is dev/raw_data_10prov (a local overlay whose icio/ holds the folded
    table under the standard 2022 filename);
  * no territory scale hack needed.

Usage:
    uv run python dev/io2022/build_2022_datawrapper_10prov.py --force \
        [--pickle dev/pkl_files/<name>.pkl]
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from macro_data import DataWrapper, configuration_utils
from macro_data.configuration.countries import Country as CountryCode
from macro_data.configuration.region import Region

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = REPO_ROOT / "dev" / "raw_data_10prov"
PKL_PATH = REPO_ROOT / "dev" / "pkl_files" / "io2022_10prov_2022.pkl"
# Validated national Canadian household file (SFS-2023 donor transplant + CIS-2022 income
# + SHS-2023 consumption). With --canadianized-households every province samples this
# CAD-native distribution instead of the French HFCS proxy. Generate it with:
#   uv run python dev/io2022/household_prototype/prepare_household_canadianization.py --real
#   uv run python dev/io2022/household_prototype/prepare_household_consumption.py
CANADIANIZED_HH_CSV = REPO_ROOT / "dev" / "io2022" / "household_prototype" / "prototype_household_consumption.csv"

# The production 10 provinces, in the same (alphabetical-by-code) order as the legacy
# 2014 provincial build, so the goods market's participant order matches the sorted
# trade-proportion DataFrames exactly as before (the explicit reindex in simulation.py
# makes this a belt-and-braces choice rather than a correctness requirement).
REGIONS = [
    Region.from_code("CAN_AB", "Alberta"),
    Region.from_code("CAN_BC", "British Columbia"),
    Region.from_code("CAN_MB", "Manitoba"),
    Region.from_code("CAN_NB", "New Brunswick"),
    Region.from_code("CAN_NL", "Newfoundland and Labrador"),
    Region.from_code("CAN_NS", "Nova Scotia"),
    Region.from_code("CAN_ON", "Ontario"),
    Region.from_code("CAN_PE", "Prince Edward Island"),
    Region.from_code("CAN_QC", "Quebec"),
    Region.from_code("CAN_SK", "Saskatchewan"),
]


def build_data_config(scale: int = 1000, canadianized_households: bool = False):
    data_config = configuration_utils.default_data_configuration(
        countries=["CAN"],
        aggregate_industries=False,
        proxy_country_dict={"CAN": "FRA"},
        use_disagg_can_2014_reader=False,
        year=2022,
    )

    data_config.year = 2022
    data_config.time_unit = 3
    data_config.can_disaggregation = False
    data_config.aggregate_industries = False
    data_config.prune_date = None
    data_config.seed = 0

    base_config = data_config.country_configs[CountryCode("CAN")]
    base_config.single_firm_per_industry = True
    base_config.single_bank = True
    base_config.single_government_entity = True
    base_config.firms_configuration.constructor = "Default"
    base_config.scale = scale

    for region in REGIONS:
        region_config = base_config.model_copy(deep=True)
        region_config.eu_proxy_country = CountryCode("FRA")
        region_config.scale = scale
        data_config.country_configs[region] = region_config

    data_config.aggregation_structure = {CountryCode("CAN"): REGIONS}
    if canadianized_households:
        if not CANADIANIZED_HH_CSV.exists():
            raise FileNotFoundError(
                f"{CANADIANIZED_HH_CSV} missing -- run the two household_prototype prep "
                "scripts first (see the note beside CANADIANIZED_HH_CSV)."
            )
        data_config.canadianized_can_households_csv = CANADIANIZED_HH_CSV
    return data_config


def build_pickle(pkl_path: Path = PKL_PATH, scale: int = 1000, force: bool = False,
                 lfs_unemployment: bool = False, canadianized_households: bool = False):
    if pkl_path.exists() and not force:
        print(f"Pickle already exists at {pkl_path} - skipping (use --force to rebuild).")
        return
    folded = INPUT_PATH / "icio" / "icio_2022_can_provinces.csv"
    if not folded.exists():
        raise FileNotFoundError(
            f"{folded} missing - run dev/io2022/fold_territories_2022.py first and place the "
            "folded table under that name in the raw_data_10prov overlay."
        )
    pkl_path.parent.mkdir(parents=True, exist_ok=True)
    data_config = build_data_config(scale=scale, canadianized_households=canadianized_households)
    t0 = time.time()
    creator = DataWrapper.from_config(
        configuration=data_config,
        raw_data_path=INPUT_PATH,
        single_hfcs_survey=True,
    )
    if lfs_unemployment:
        # Opt-in "option 2" calibration: reclassify surplus unemployed to inactive so
        # each province's t0 unemployment matches LFS 2022 (see lfs_unemployment_2022).
        from lfs_unemployment_2022 import apply_lfs_unemployment
        apply_lfs_unemployment(creator, INPUT_PATH, seed=data_config.seed)
    creator.save(pkl_path)
    print(f"Pickle saved to {pkl_path} ({(time.time() - t0) / 60:.1f} min)")
    return creator


def inspect(pkl_path: Path = PKL_PATH):
    data = DataWrapper.init_from_pickle(pkl_path)
    provinces = [c for c in data.all_country_names if str(c).startswith("CAN_")]
    print(f"\n=== 2022 10-province DataWrapper init inspection ===")
    print(f"base year: {data.configuration.year}")
    print(f"n_industries: {data.n_industries}")
    print(f"industries: {list(data.industries)}")
    print(f"n regions: {len(provinces)} -> {[str(p) for p in provinces]}")
    print(f"all_country_names: {[str(c) for c in data.all_country_names]}")
    for p in provinces:
        sc = data.synthetic_countries[p]
        print(f"  {str(p):8s} n_sellers_by_industry sum={np.sum(sc.n_sellers_by_industry)} "
              f"n_buyers={sc.n_buyers}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=1000)
    ap.add_argument("--pickle", type=Path, default=PKL_PATH)
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--force", action="store_true", help="rebuild pickle even if it exists")
    ap.add_argument("--canadianized-households", action="store_true",
                    help="sample the validated Canadian household distribution "
                         "(SFS-2023 + CIS-2022 + SHS-2023) instead of the French HFCS proxy")
    ap.add_argument("--lfs-unemployment", action="store_true",
                    help="calibrate t0 unemployment to LFS 2022 per province (option 2: "
                         "surplus unemployed -> inactive; employment untouched)")
    args = ap.parse_args()

    build_pickle(pkl_path=args.pickle, scale=args.scale, force=args.force,
                 lfs_unemployment=args.lfs_unemployment,
                 canadianized_households=args.canadianized_households)
    if not args.build_only:
        inspect(args.pickle)
