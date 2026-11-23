"""Run MacroABM-CA on its own (no CIMS, COPPER or LabourABM): the helpers behind
``MacroABM-CA_quickstart.ipynb``.

    from scenarios.macro_only import load_data, build, run, results, run_scenario

    data = load_data("dev/pkl_files/io2022_10prov_2022_v2_pumf_built-2026-08-18.pkl")
    sim = build(data, end_year=2030)                 # the baseline settings below
    run(sim)
    df = results(sim)                                # one row per province and quarter
    a = run_scenario(data, household_demand_growth=0.02)   # results only, frees memory

A scenario is the baseline plus changes. Change a setting by passing it to ``build``
(``build(data, household_demand_growth=0.02)``); change the economy during the run with a
*hook*, a function ``hook(sim, year, month)`` the model calls at the start of every
quarter (``run(sim, hooks=[my_hook])``). ``extra_government_purchases`` is an example.

``BASELINE`` copies the macro settings of the linkage's EPM baseline
(M3-linkages ``scenarios/baseline/config.toml``, ``[Models.MacroABM.Config]``, branch
``epm``, 2026-11-18). Everything in that file's ``[...Config.Linkage]`` section (energy
use and prices from CIMS, electricity supply from COPPER, ITCs, PMD, carbon pricing)
needs the linkage inputs and is not applied here, so a run here is the macro model's
own baseline, not the linkage baseline.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

# Rents are counted once, inside real estate (the linkage baseline's
# housing_services_in_household_io = true). Reporting only: no behaviour reads GDP.
os.environ.setdefault("HOUSING_SERVICES_IN_HOUSEHOLD_IO", "1")

from macro_data import DataWrapper  # noqa: E402
from macromodel.simulation import Simulation  # noqa: E402

try:
    from scenarios.run_cims_linkage import build_simulation  # noqa: E402
except ImportError:  # pragma: no cover - imported from inside scenarios/
    from run_cims_linkage import build_simulation  # type: ignore # noqa: E402

# The linkage runner logs every step at INFO; keep the notebook quiet.
logging.getLogger().setLevel(logging.WARNING)

START_YEAR = 2022  # the 2022 pickle starts in 2022Q1
STEPS_PER_YEAR = 4

BASELINE: dict = dict(
    seed=4,
    use_candidate_baseline=True,
    # labour force: observed to 2024, then these annual growth rates
    labour_force_growth={
        "CAN_AB": 0.01334, "CAN_BC": 0.00418, "CAN_MB": 0.00672, "CAN_NB": 0.00756,
        "CAN_NL": -0.00298, "CAN_NS": 0.00443, "CAN_ON": 0.00502, "CAN_PE": 0.00956,
        "CAN_QC": -0.00244, "CAN_SK": 0.00882,
    },
    # household and government demand grow with the labour force (+1%/yr for households)
    household_demand_from_labour_force=True,
    household_demand_growth=0.01,
    government_demand_from_labour_force=True,
    # productivity
    tfp_base_growth_rate=0.001,
    tfp_investment_effectiveness=0.01,
    # prices and wages
    price_setting_noise_std=0.01,
    price_setting_speed_gf=0.5,
    price_setting_speed_cp=0.5,
    price_setting_speed_dp=0.0,
    price_setting_cost_push_basis="change",
    inflation_expectation_anchor=1.0,
    inflation_expectation_target=0.02,
    rent_inflation_indexation=1.0,
    rent_inflation_delay=1,
    wage_cpi_indexation=0.5,
    wage_cpi_lag=4,
    # trade between provinces
    firm_price_advantage_change_growth=1.0,
    firm_price_advantage_window=4,
    firm_price_advantage_symmetric=True,
    firm_price_advantage_smoothing=0.25,
)
# Applied after the build: all provinces share one inflation expectation.
NATIONAL_INFLATION_EXPECTATION = True
# Quarters of per-agent transaction history kept (the linkage's trim_agent_history).
HISTORY_LIMIT = 4


@contextmanager
def _errors_only():
    """Hide log warnings for a while. Loading and building repeat a known, harmless unit
    note per province (CH4 emission factors rescaled to annual)."""
    root = logging.getLogger()
    level = root.level
    root.setLevel(logging.ERROR)
    try:
        yield
    finally:
        root.setLevel(level)


def load_data(pkl_path: str | Path) -> DataWrapper:
    """Load the model's starting data (the 2022 provincial pickle)."""
    pkl_path = Path(pkl_path)
    if not pkl_path.exists():
        raise FileNotFoundError(
            f"Pickle not found: {pkl_path}\n"
            "Copy io2022_10prov_2022_v2_pumf_built-2026-08-18.pkl from the SESIT SharePoint "
            "folder 'Projects - Shared/SESIT - MacroABM data' into dev/pkl_files/.")
    with _errors_only():
        return DataWrapper.init_from_pickle(pkl_path)


def build(data: DataWrapper, *, end_year: int = 2030, **changes) -> Simulation:
    """Build a simulation from 2022Q1 to the end of ``end_year``.

    ``changes`` override ``BASELINE`` (any keyword of
    ``scenarios.run_cims_linkage.build_simulation``).
    """
    settings = {**BASELINE, **changes}
    timesteps = (end_year - START_YEAR + 1) * STEPS_PER_YEAR
    with _errors_only():
        sim = build_simulation(data, timesteps=timesteps, **settings)
    sim.national_inflation_expectation = NATIONAL_INFLATION_EXPECTATION
    # Keep only the last few quarters of each agent's goods-market transactions (nothing
    # reads older ones; they are most of a run's memory). Results are unaffected.
    sim.set_agent_history_limit(HISTORY_LIMIT)
    return sim


def run_scenario(data: DataWrapper, *, end_year: int = 2030, hooks: Iterable[Callable] = (),
                 **changes) -> pd.DataFrame:
    """Build, run and return ``results`` in one call, without keeping the simulation.

    A run holds a few GB of memory until it is deleted; use this when only the results
    table is needed (comparing scenarios), and ``build`` + ``run`` to inspect the model.
    """
    sim = build(data, end_year=end_year, **changes)
    run(sim, hooks)
    return results(sim)


def run(sim: Simulation, hooks: Iterable[Callable] = (), *, quiet: bool = False) -> Simulation:
    """Run the simulation to its end, printing one line per year."""
    sim.prehooks.extend(hooks)
    t0 = time.time()
    while sim.steps_completed < sim.t_max:
        sim.run_steps(1)
        if not quiet and sim.steps_completed % STEPS_PER_YEAR == 0:
            year = START_YEAR + sim.steps_completed // STEPS_PER_YEAR - 1
            print(f"  {year} done  ({time.time() - t0:.0f} s)")
    return sim


def results(sim: Simulation) -> pd.DataFrame:
    """Quarterly results, one row per province and quarter.

    Money is in nominal CAD per quarter. ``Real GDP`` is GDP deflated by the province's
    CPI (2022Q1 = 1). The model's starting state (before the first quarter) is dropped.
    """
    frames = []
    for name, country in sim.countries.items():
        df = country.shallow_output().iloc[1:].reset_index(drop=True)
        df.insert(0, "quarter", pd.period_range(f"{START_YEAR}Q1", periods=len(df), freq="Q"))
        df.insert(0, "province", name.removeprefix("CAN_"))
        df["Real GDP"] = df["GDP Output"] / (df["CPI"] / df["CPI"].iloc[0])
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# Columns averaged (not summed) over a year.
_AVERAGED = ("Rate", "CPI", "PPI", "CFPI", "Debt")


def annual(df: pd.DataFrame, columns: list[str] | None = None, *, national: bool = False) -> pd.DataFrame:
    """Annual table from ``results``: per province, or for Canada if ``national``.

    Flows are summed over the year. Rates, prices and indices are averaged; for Canada
    they are weighted by each province's nominal GDP (for the unemployment rate this is
    an approximation of a labour-force weight).
    """
    columns = columns or [c for c in df.columns if c not in ("province", "quarter")]
    averaged = [c for c in columns if any(a in c for a in _AVERAGED)]
    d = df.assign(year=df["quarter"].dt.year)
    if not national:
        how = {c: ("mean" if c in averaged else "sum") for c in columns}
        return d.groupby(["province", "year"]).agg(how)
    weight = d["GDP Output"].copy()
    d[averaged] = d[averaged].mul(weight, axis=0)
    out = d.groupby("year")[columns].sum()
    out[averaged] = out[averaged].div(weight.groupby(d["year"]).sum(), axis=0)
    return out


def government_purchases(sim: Simulation, province: str) -> pd.DataFrame:
    """What the province's government actually bought, by industry (nominal CAD per
    quarter; rows = quarters). Use it to check a purchase hook took hold."""
    ge = sim.countries[f"CAN_{province}"].government_entities
    history = ge.ts.historic("consumption_in_lcu")[-sim.steps_completed:]
    rows = [np.asarray(q, dtype=float).reshape(-1, len(sim.countries[f"CAN_{province}"].firms.industries)).sum(0)
            for q in history]
    return pd.DataFrame(rows, columns=list(sim.countries[f"CAN_{province}"].firms.industries),
                        index=pd.period_range(f"{START_YEAR}Q1", periods=len(rows), freq="Q"))


def industry_output(sim: Simulation) -> pd.DataFrame:
    """Real production by industry, summed over provinces (rows = quarters)."""
    total = None
    for country in sim.countries.values():
        prod = country.firms.industry_timeseries_dataframes()["production"]
        total = prod if total is None else total.add(prod, fill_value=0.0)
    total = total.iloc[1:].reset_index(drop=True)
    total.index = pd.period_range(f"{START_YEAR}Q1", periods=len(total), freq="Q")
    return total


def save(sim: Simulation, folder: str | Path, name: str = "simulation_shallow.h5") -> Path:
    """Save the summary results (the same file the linkage writes) to ``folder``."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    if path.exists():
        path.unlink()
    sim.shallow_hdf_save(folder, name)
    return path


def extra_government_purchases(province: str, industry: str, cad_per_year: float,
                               start_year: int, end_year: int | None = None) -> Callable:
    """Hook: the government buys ``cad_per_year`` (nominal CAD) more from ``industry`` in
    ``province`` (e.g. "BC", "P" for education) from ``start_year`` to ``end_year``.

    The purchase is debt-financed and goes through the goods market like any other
    government spending, so part of it is imported and the rest reaches suppliers
    through the input-output links.
    """
    key = f"CAN_{province}"

    def hook(sim: Simulation, year: int, month: int) -> None:
        country = sim.countries[key]
        on = year >= start_year and (end_year is None or year <= end_year)
        if not on:
            country.government_entities.set_exogenous_orders(None)
            return
        industries = list(country.firms.industries)
        orders = np.zeros(len(industries))
        orders[industries.index(industry)] = cad_per_year / STEPS_PER_YEAR
        country.government_entities.set_exogenous_orders(orders)

    hook.__name__ = f"extra_government_purchases_{province}_{industry}"
    return hook
