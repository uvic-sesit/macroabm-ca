"""Run isolated MacroABM-CA historical-fit experiments with detailed diagnostics.

The baseline spec reproduces the saved candidate_prov validation configuration.
All outputs remain under experiments/ar1_beating_baseline/ in this clone.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
NUMBA_CACHE = Path(tempfile.gettempdir()) / "macroabm_forecast_numba_cache"
NUMBA_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(NUMBA_CACHE))
sys.path.insert(0, str(REPO / "dev" / "validation"))
sys.path.insert(0, str(REPO))

from macro_data import DataWrapper
from macromodel.agents.individuals.individual_properties import ActivityStatus
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.simulation import Simulation

PKL = REPO / "dev" / "pkl_files" / "io2022_13prov_2022_canadianized.pkl"
LFS_INDEX = REPO / "scripts" / "data" / "labour_force_index_2014_2024.json"
DEFAULT_SPEC = Path(__file__).parent / "baseline_spec.json"
DEFAULT_OUT = Path(__file__).parent / "outputs"
N_PERIODS = 13
PROV10 = {
    "CAN_NL": "Newfoundland and Labrador",
    "CAN_PE": "Prince Edward Island",
    "CAN_NS": "Nova Scotia",
    "CAN_NB": "New Brunswick",
    "CAN_QC": "Quebec",
    "CAN_ON": "Ontario",
    "CAN_MB": "Manitoba",
    "CAN_SK": "Saskatchewan",
    "CAN_AB": "Alberta",
    "CAN_BC": "British Columbia",
}

HHC_COLS = ["Real Household Consumption (Value)", "Household Consumption (Value)"]
HHI_COLS = ["Real Household Investment (Value)", "Household Investment (Value)"]
GOV_COLS = ["Real Government Consumption (Value)", "Government Consumption (Value)"]


def labour_index_2022(quarters: int, convention: str) -> dict[str, list[float]]:
    """Construct the quarterly labour-force index from the existing annual LFS data."""
    source = json.loads(LFS_INDEX.read_text(encoding="utf-8"))
    n = quarters + 1
    provincial = {}
    for province, series in source.items():
        annual = {int(year): value for year, value in series.items()}
        base = annual[2022]
        ratios = [1.0, annual[2023] / base, annual[2024] / base]
        if convention == "observed_annual_interpolated":
            values = np.interp(np.arange(n), [0, 4, 8], ratios)
        elif convention == "observed_annual_blocks":
            values = np.ones(n)
            values[4 : min(8, n)] = ratios[1]
            values[8:] = ratios[2]
        else:
            raise ValueError(f"Unsupported labour-force convention: {convention}")
        provincial[province] = values
    fallback = np.mean(np.vstack(list(provincial.values())), axis=0)
    for territory in ("CAN_YT", "CAN_NT", "CAN_NU"):
        provincial[territory] = fallback
    return {province: values.astype(float).tolist() for province, values in provincial.items()}


def build_config(data: DataWrapper, seed: int, quarters: int) -> tuple[list, SimulationConfiguration]:
    provinces = [country for country in data.all_country_names if str(country).startswith("CAN_")]
    config = SimulationConfiguration(
        seed=seed,
        country_configurations={
            country: CountryConfiguration.n_industry_default(n_industries=data.n_industries)
            for country in provinces
        },
        t_max=quarters,
    )
    return provinces, config


def provincial_demand_growth() -> dict[str, dict[str, tuple[float, float]]]:
    data = pd.read_csv(REPO / "dev" / "statcan" / "36100222.csv", low_memory=False)
    data = data.loc[data["Prices"].eq("Chained (2017) dollars")]
    estimates = {
        "HHC": "Household final consumption expenditure",
        "GOV": "General governments final consumption expenditure",
        "HHI": "Residential structures",
    }
    output = {province: {} for province in PROV10}
    for key, estimate in estimates.items():
        pivot = data.loc[data["Estimates"].eq(estimate)].pivot_table(
            index="GEO", columns="REF_DATE", values="VALUE", aggfunc="first"
        )
        for province, geography in PROV10.items():
            v22, v23, v24 = pivot.loc[geography, 2022], pivot.loc[geography, 2023], pivot.loc[geography, 2024]
            output[province][key] = (v23 / v22 - 1.0, v24 / v22 - 1.0)
    return output


def annual_block_factor(nrows: int, growth_2023: float, growth_2024: float) -> np.ndarray:
    factor = np.ones(nrows)
    factor[4 : min(8, nrows)] = 1.0 + growth_2023
    factor[8:nrows] = 1.0 + growth_2024
    return factor


def configure(config: SimulationConfiguration, provinces: list, spec: dict, quarters: int) -> None:
    config.labour_force_update_before_markets = spec.get("labour_force_update_before_markets", False)
    labour_convention = spec["labour_force_path"]
    labour_paths = (
        labour_index_2022(quarters, labour_convention)
        if labour_convention in {"observed_annual_interpolated", "observed_annual_blocks"}
        else None
    )
    for province in provinces:
        country = config.country_configurations[province]
        country.assume_zero_noise = spec.get("assume_zero_noise", False)
        country.firms.functions.demand_estimator.parameters.update(
            {
                "firm_growth_adjustment_speed": spec["firm_growth_adjustment_speed"],
                "sectoral_growth_adjustment_speed": spec["sectoral_growth_adjustment_speed"],
                "demand_smoothing": spec["demand_smoothing"],
            }
        )
        country.firms.functions.demand_for_goods.parameters.update(
            {"unmet_demand_weight": spec["unmet_demand_weight"]}
        )
        country.firms.functions.excess_demand.parameters.update(
            {"consider_capital_inputs": spec["excess_demand_consider_capital_inputs"]}
        )
        country.firms.functions.target_capital_inputs.parameters.update(
            {
                "rolling_reference": spec["rolling_reference"],
                "target_capital_inputs_fraction": spec["target_capital_inputs_fraction"],
                "credit_gap_fraction": spec["credit_gap_fraction"],
            }
        )
        country.firms.functions.target_production.parameters.update(spec.get("target_production", {}))
        if labour_paths is not None:
            country.individuals.functions.demography.name = "ExogenousLabourForcePath"
            country.individuals.functions.demography.parameters = {"labour_force_index": labour_paths[str(province)]}
        country.government_entities.functions.consumption.name = "ExogenousGovernmentConsumptionSetter"
        country.households.functions.consumption.name = "ExogenousHouseholdConsumption"
        country.households.functions.investment.name = "ExogenousHouseholdInvestment"

        labour_parameters = spec.get("labour_market", {})
        country.labour_market.functions.clearing.parameters.update(labour_parameters)
        desired_labour = spec.get("desired_labour", {})
        country.firms.functions.desired_labour.parameters.update(desired_labour)
        tfp = spec.get("tfp_growth")
        if tfp:
            country.firms.functions.productivity_growth.name = "SimpleTFPGrowth"
            country.firms.functions.productivity_growth.parameters = {
                "investment_effectiveness": tfp.get("investment_effectiveness", 0.0)
            }
            country.firms.parameters.tfp_base_growth_rate = tfp["base_growth_rate"]


def install_final_demand_path(model: Simulation, provinces: list, spec: dict, quarters: int) -> None:
    if spec["final_demand_path"] != "observed_provincial_annual_blocks":
        raise ValueError(f"Unsupported final_demand_path: {spec['final_demand_path']}")
    growth = provincial_demand_growth()
    for province in provinces:
        exogenous = model.countries[province].exogenous
        frame = exogenous.national_accounts_during.copy()
        if len(frame) < quarters + 1:
            last = frame.index[-1]
            extension = pd.DataFrame(
                [frame.iloc[-1].copy() for _ in range(quarters + 1 - len(frame))],
                index=[last + pd.DateOffset(months=3 * (k + 1)) for k in range(quarters + 1 - len(frame))],
            )
            frame = pd.concat([frame, extension], axis=0)
        if str(province) in growth:
            values = growth[str(province)]
            groups = [
                (HHC_COLS, annual_block_factor(len(frame), *values["HHC"])),
                (GOV_COLS, annual_block_factor(len(frame), *values["GOV"])),
                (HHI_COLS, annual_block_factor(len(frame), *values["HHI"])),
            ]
            for columns, factor in groups:
                for column in columns:
                    if column in frame:
                        frame[column] = frame[column].to_numpy() * factor
        exogenous.national_accounts_during = frame


def value_sum(values: np.ndarray, prices: np.ndarray) -> float:
    array = np.asarray(values, dtype=float).reshape(-1)
    if np.all(np.isnan(array)):
        return float("nan")
    return float(np.nansum(array * prices)) / 1e9


def scalar_current(ts, name: str) -> float:
    try:
        value = np.asarray(ts.current(name), dtype=float).reshape(-1)
    except (AttributeError, KeyError):
        return float("nan")
    return float(value[0]) if value.size else float("nan")


def collect(model: Simulation, provinces: list, base_prices: dict) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    regional = {}
    for province in provinces:
        country = model.countries[province]
        firms = country.firms
        prices = base_prices[province]
        production = np.asarray(firms.ts.current("production"), dtype=float)
        used_intermediate = np.asarray(firms.ts.current("used_intermediate_inputs"), dtype=float)
        output_value = float(np.nansum(production * prices)) / 1e9
        intermediate_value = float(np.nansum(used_intermediate * prices[None, :])) / 1e9
        activity = country.individuals.states["Activity Status"]
        employed_agents = int(np.sum(activity == ActivityStatus.EMPLOYED))
        unemployed_agents = int(np.sum(activity == ActivityStatus.UNEMPLOYED))
        labour_force_agents = employed_agents + unemployed_agents
        scale = float(country.scale)
        labour_market = country.labour_market.ts
        target = np.asarray(firms.ts.current("target_production"), dtype=float)
        labour_limit = np.asarray(firms.ts.current("labour_inputs"), dtype=float)
        intermediate_limit = np.asarray(firms.ts.current("limiting_intermediate_inputs"), dtype=float)
        capital_limit = np.asarray(firms.ts.current("limiting_capital_inputs"), dtype=float)
        binding = np.argmin(np.vstack([target, labour_limit, intermediate_limit, capital_limit]), axis=0)

        row = {
            "real_gva": output_value - intermediate_value,
            "real_output": output_value,
            "target_production": value_sum(firms.ts.current("target_production"), prices),
            "estimated_demand": value_sum(firms.ts.current("estimated_demand"), prices),
            "realized_demand": value_sum(firms.ts.current("demand"), prices),
            "inventory": value_sum(firms.ts.current("inventory"), prices),
            "capital_limited_capacity": value_sum(firms.ts.current("limiting_capital_inputs"), prices),
            "intermediate_limited_capacity": value_sum(firms.ts.current("limiting_intermediate_inputs"), prices),
            "labour_capacity": value_sum(firms.ts.current("labour_inputs"), prices),
            "desired_labour_inputs": float(np.nansum(firms.ts.current("desired_labour_inputs"))),
            "realized_labour_inputs": float(np.nansum(firms.ts.current("labour_inputs"))),
            "employed_agents": employed_agents,
            "unemployed_agents": unemployed_agents,
            "labour_force_agents": labour_force_agents,
            "employed_persons": employed_agents * scale,
            "unemployed_persons": unemployed_agents * scale,
            "labour_force_persons": labour_force_agents * scale,
            "new_hires_agents": scalar_current(labour_market, "num_individuals_newly_joining"),
            "new_fires_agents": scalar_current(labour_market, "num_individuals_newly_fired"),
            "new_random_fires_agents": scalar_current(labour_market, "num_individuals_newly_randomly_fired"),
            "target_binding_cells": int(np.sum(binding == 0)),
            "labour_binding_cells": int(np.sum(binding == 1)),
            "intermediate_binding_cells": int(np.sum(binding == 2)),
            "capital_binding_cells": int(np.sum(binding == 3)),
            "household_consumption": scalar_current(country.economy.ts, "total_household_fce") / 1e9,
            "household_investment": scalar_current(country.economy.ts, "total_household_gross_fixed_capital_formation") / 1e9,
            "total_investment": scalar_current(country.economy.ts, "total_gross_fixed_capital_formation") / 1e9,
            "government_consumption": scalar_current(country.economy.ts, "total_government_consumption") / 1e9,
            "imports": scalar_current(country.economy.ts, "total_imports") / 1e9,
            "exports": scalar_current(country.economy.ts, "total_exports") / 1e9,
            "estimated_growth": scalar_current(country.economy.ts, "estimated_growth"),
            "realized_growth": scalar_current(country.economy.ts, "total_growth"),
        }
        row["unemployment_rate"] = 100.0 * unemployed_agents / labour_force_agents
        regional[str(province)] = row

    keys = next(iter(regional.values())).keys()
    national = {key: float(np.nansum([region[key] for region in regional.values()])) for key in keys}
    weights = np.asarray([region["real_gva"] for region in regional.values()], dtype=float)
    for key in ["estimated_growth", "realized_growth"]:
        values = np.asarray([region[key] for region in regional.values()], dtype=float)
        valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
        national[key] = float(np.average(values[valid], weights=weights[valid])) if valid.any() else float("nan")
    national["unemployment_rate"] = 100.0 * national["unemployed_agents"] / national["labour_force_agents"]
    for key in ["new_hires_agents", "new_fires_agents", "new_random_fires_agents"]:
        if all(np.isnan(region[key]) for region in regional.values()):
            national[key] = float("nan")
    return national, regional


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--periods", type=int, default=N_PERIODS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    data = DataWrapper.init_from_pickle(PKL)
    provinces, config = build_config(data, args.seed, args.periods)
    configure(config, provinces, spec, args.periods)
    model = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=config)
    install_final_demand_path(model, provinces, spec, args.periods)
    base_prices = {
        province: np.asarray(model.countries[province].economy.ts.current("good_prices"), dtype=float).reshape(-1)
        for province in provinces
    }

    quarters = pd.period_range("2022Q1", periods=args.periods, freq="Q").astype(str)
    national_rows = []
    regional_rows = []
    for period_index, quarter in enumerate(quarters):
        # Frozen C0 convention: 2022Q1 is the first post-iteration state, not initialization.
        model.iterate(period_index)
        national, regional = collect(model, provinces, base_prices)
        national_rows.append({"quarter": quarter, **national})
        for province, values in regional.items():
            regional_rows.append({"quarter": quarter, "province": province, **values})

    run_dir = args.output_dir / args.experiment_id / f"seed{args.seed:03d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(national_rows).to_csv(run_dir / "national_quarterly.csv", index=False)
    pd.DataFrame(regional_rows).to_csv(run_dir / "regional_quarterly.csv", index=False)
    (run_dir / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
