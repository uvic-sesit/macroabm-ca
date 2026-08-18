"""Build the 2022 provincial DataWrapper (13 regions x OECD-50) from the validated inputs.

Mirrors dev/validation/build_baseline_2026_07.py but for the 2022 base year:
  * year = 2022, OECD-50 industries, 13 regions incl. territories (YT/NT/NU);
  * provincial IO = <raw-data root>/icio/icio_2022_can_provinces.csv (macroabm-io2022 compat table);
  * capital stock / capital compensation / labour compensation injected from
    <root>/can_2022/ by the reader (see default_readers.inject_can_provincial_socioeconomic_2022);
  * raw-data root is configurable (see _paths.raw_data_root: $MACROABM_RAW_DATA / <repo>/raw_data /
    legacy <repo>/dev/raw_data);
  * behavioural equations untouched.

use_disagg_can_2014_reader is intentionally OFF (that branch is 2014-only); the provincial
reader is triggered by aggregation_structure instead. WIOD/HFCS remain as fallbacks.

Usage:
    uv run python dev/io2022/build_2022_datawrapper.py --scale 1000 [--build-only] [--pickle PATH]
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from macro_data import DataWrapper, configuration_utils
from macro_data.configuration.countries import Country as CountryCode
from macro_data.configuration.region import Region

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "household_prototype"))
from _paths import raw_data_root  # configurable raw-data root (env / root raw_data/ / legacy dev/raw_data)

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = raw_data_root(REPO_ROOT)  # <root>/{hfcs, can_2022, icio}; override via $MACROABM_RAW_DATA
PKL_PATH = REPO_ROOT / "dev" / "pkl_files" / "io2022_13prov_2022.pkl"
# Validated national Canadian household file (MVP integration). When --canadianized is set, every provincial
# SyntheticCountry samples this CAD-native distribution instead of the French HFCS proxy (schema-adapted).
CANADIANIZED_HH_CSV = REPO_ROOT / "dev" / "io2022" / "household_prototype" / "prototype_household_consumption.csv"

# 13 regions (10 provinces + 3 territories), matching the 2022 provincial IO table.
REGIONS = [
    Region.from_code("CAN_NL", "Newfoundland and Labrador"),
    Region.from_code("CAN_PE", "Prince Edward Island"),
    Region.from_code("CAN_NS", "Nova Scotia"),
    Region.from_code("CAN_NB", "New Brunswick"),
    Region.from_code("CAN_QC", "Quebec"),
    Region.from_code("CAN_ON", "Ontario"),
    Region.from_code("CAN_MB", "Manitoba"),
    Region.from_code("CAN_SK", "Saskatchewan"),
    Region.from_code("CAN_AB", "Alberta"),
    Region.from_code("CAN_BC", "British Columbia"),
    Region.from_code("CAN_YT", "Yukon"),
    Region.from_code("CAN_NT", "Northwest Territories"),
    Region.from_code("CAN_NU", "Nunavut"),
]

# Territories have tiny populations -> use a much smaller agent scale so every OECD sector is
# staffed by at least one synthetic worker.
TERRITORIES = {"CAN_YT", "CAN_NT", "CAN_NU"}
TERRITORY_SCALE = 10


def build_data_config(scale: int = 1000, canadianized_households: bool = False):
    data_config = configuration_utils.default_data_configuration(
        countries=["CAN"],
        aggregate_industries=False,
        proxy_country_dict={"CAN": "FRA"},
        use_disagg_can_2014_reader=False,  # 2014-only branch; provincial reader triggered by aggregation_structure
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

    # The territories (YT/NT/NU) have tiny populations; at scale=1000 they generate too few
    # synthetic individuals to staff all 50 OECD sectors with >=1 worker (the synthetic-population
    # builder raises otherwise). Give them a much smaller scale (more agents per person) so every
    # sector is populated. Each region gets its own config copy so the scales are independent.
    for region in REGIONS:
        region_config = base_config.model_copy(deep=True)
        region_config.eu_proxy_country = CountryCode("FRA")
        region_config.scale = TERRITORY_SCALE if str(region) in TERRITORIES else scale
        data_config.country_configs[region] = region_config

    data_config.aggregation_structure = {CountryCode("CAN"): REGIONS}
    if canadianized_households:
        data_config.canadianized_can_households_csv = CANADIANIZED_HH_CSV
    return data_config


def build_pickle(pkl_path: Path = PKL_PATH, scale: int = 1000, force: bool = False,
                 canadianized_households: bool = False):
    if pkl_path.exists() and not force:
        print(f"Pickle already exists at {pkl_path} - skipping (use --force to rebuild).")
        return
    pkl_path.parent.mkdir(parents=True, exist_ok=True)
    data_config = build_data_config(scale=scale, canadianized_households=canadianized_households)
    t0 = time.time()
    creator = DataWrapper.from_config(
        configuration=data_config,
        raw_data_path=INPUT_PATH,
        single_hfcs_survey=True,
    )
    creator.save(pkl_path)
    print(f"Pickle saved to {pkl_path} ({(time.time() - t0) / 60:.1f} min)")
    return creator


def inspect(pkl_path: Path = PKL_PATH):
    data = DataWrapper.init_from_pickle(pkl_path)
    provinces = [c for c in data.all_country_names if str(c).startswith("CAN_")]
    print(f"\n=== 2022 DataWrapper init inspection ===")
    print(f"n_industries: {data.n_industries}")
    print(f"industries: {list(data.industries)}")
    print(f"n regions: {len(provinces)} -> {[str(p) for p in provinces]}")
    print(f"all_country_names: {[str(c) for c in data.all_country_names]}")
    for p in provinces:
        sc = data.synthetic_countries[p]
        print(f"  {str(p):8s} n_sellers_by_industry sum={np.sum(sc.n_sellers_by_industry)} "
              f"n_buyers={sc.n_buyers}")


def inspect_households(pkl_path: Path = PKL_PATH, provinces_to_check=("CAN_ON", "CAN_PE", "CAN_NL")):
    """Cheap household-side acceptance check per province (tenure/income/wealth/APC/NaN)."""
    data = DataWrapper.init_from_pickle(pkl_path)
    names = {str(c): c for c in data.all_country_names}
    for pname in provinces_to_check:
        if pname not in names:
            print(f"  {pname}: not built")
            continue
        hh = data.synthetic_countries[names[pname]].population.household_data
        n = len(hh)
        own = (hh["Tenure Status of the Main Residence"] == 1).mean() if "Tenure Status of the Main Residence" in hh else float("nan")
        inc = np.nanmean(hh["Income"].values.astype(float)) if "Income" in hh else float("nan")
        wealth = np.nanmean(hh["Wealth"].values.astype(float)) if "Wealth" in hh else float("nan")
        apc = np.nanmedian(hh["Consumption of Consumer Goods/Services as a Share of Income"].values.astype(float)) if "Consumption of Consumer Goods/Services as a Share of Income" in hh else float("nan")
        moncols = [c for c in ["Income", "Wealth", "Value of the Main Residence", "Amount spent on Consumption of Goods and Services"] if c in hh]
        nbad = int(sum(np.sum(~np.isfinite(hh[c].values.astype(float))) for c in moncols))
        print(f"  {pname:8s} n_hh={n:6d} owner={own:5.3f} mean_income={inc:11.0f} mean_wealth={wealth:12.0f} "
              f"median_APC={apc:5.3f} nonfinite_money={nbad}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=1000)
    ap.add_argument("--pickle", type=Path, default=PKL_PATH)
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--force", action="store_true", help="rebuild pickle even if it exists")
    ap.add_argument("--canadianized", action="store_true", help="use the validated Canadian household file")
    ap.add_argument("--check-households", action="store_true", help="print per-province household diagnostics")
    args = ap.parse_args()

    build_pickle(pkl_path=args.pickle, scale=args.scale, force=args.force,
                 canadianized_households=args.canadianized)
    if not args.build_only:
        inspect(args.pickle)
    if args.check_households:
        inspect_households(args.pickle)
