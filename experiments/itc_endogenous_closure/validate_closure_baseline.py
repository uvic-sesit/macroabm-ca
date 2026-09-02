"""No-ITC baseline validation for the endogenous-closure layer."""

from __future__ import annotations

import sys
import os
import tempfile
import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NUMBA_CACHE = Path(tempfile.gettempdir()) / "macroabm_ca_numba_cache"
NUMBA_CACHE.mkdir(exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(NUMBA_CACHE))

import numpy as np
import pandas as pd

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dev" / "io2022"))
sys.path.insert(0, str(REPO / "dev" / "validation"))
sys.path.insert(0, str(REPO / "experiments" / "itc_endogenous_closure"))

import closure_feedback_exp as C
import provincial_validation_2022 as P
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from save_baseline_2022 import build_config


Q = 55
SEED = 0
OUT = REPO / "experiments" / "itc_endogenous_closure" / "results"


def build_original_model(q: int, seed: int = 0):
    P.Q = q
    try:
        data = DataWrapper.init_from_pickle(P.PKL)
        provs, cfg = build_config(data, seed, q)
        P.configure(cfg, provs, candidate=True)
        model = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=cfg)
        P.post_build(model, provs, "candidate_prov")
        P.install_external_demand(model, provs)
    finally:
        P.Q = 13
    return model, provs


def collect(model, provs, base_prices) -> dict[str, float | bool]:
    out: dict[str, float | bool] = {
        "real_gva": 0.0,
        "household_consumption": 0.0,
        "household_investment": 0.0,
        "unemployment": 0.0,
        "cpi_inflation": 0.0,
        "unmet_demand": 0.0,
        "government_desired": 0.0,
        "government_realized": 0.0,
        "government_unrealized": 0.0,
        "tax_revenue": 0.0,
        "benefits_transfers": 0.0,
        "deficit": 0.0,
        "debt": 0.0,
        "finite": True,
    }
    n = 0
    for c in provs:
        if str(c) not in P.PROV10:
            continue
        country = model.countries[c]
        firms = country.firms
        gov = country.central_government
        entities = country.government_entities
        prices0 = base_prices[c]

        production = np.asarray(firms.ts.current("production"), float).reshape(-1)
        used_intermediate = np.asarray(firms.ts.current("used_intermediate_inputs"), float)
        firm_prices0 = prices0[firms.states["Industry"]]
        gva = float((production * firm_prices0).sum())
        if used_intermediate.ndim == 2:
            gva -= float((used_intermediate * prices0[None, :]).sum())
        out["real_gva"] = float(out["real_gva"]) + gva / 1e9

        hh_cons = float(country.households.ts.current("total_consumption")[0]) / 1e9
        out["household_consumption"] = float(out["household_consumption"]) + hh_cons
        hh_inv = float(country.households.ts.current("total_investment")[0]) / 1e9
        out["household_investment"] = float(out["household_investment"]) + hh_inv
        out["unemployment"] = float(out["unemployment"]) + float(country.economy.ts.current("unemployment_rate")[0])
        out["cpi_inflation"] = float(out["cpi_inflation"]) + float(country.economy.ts.current("cpi_inflation")[0])
        excess = np.nan_to_num(np.asarray(firms.ts.current("real_excess_demand"), float), nan=0.0)
        out["unmet_demand"] = float(out["unmet_demand"]) + float(excess.sum()) / 1e9

        desired_g = float(np.asarray(entities.ts.current("desired_consumption_in_lcu"), float).sum()) / 1e9
        realized_g = float(np.asarray(entities.ts.current("nominal_amount_spent_in_lcu"), float).sum()) / 1e9
        out["government_desired"] = float(out["government_desired"]) + desired_g
        out["government_realized"] = float(out["government_realized"]) + realized_g
        out["government_unrealized"] = float(out["government_unrealized"]) + desired_g - realized_g

        out["tax_revenue"] = float(out["tax_revenue"]) + float(gov.ts.current("revenue")[0]) / 1e9
        unemployment_benefits = (
            sum(a.name == "UNEMPLOYED" for a in country.individuals.states["Activity Status"])
            * gov.ts.current("unemployment_benefits_by_individual")[0]
        )
        household_transfers = float(country.households.ts.current("income_social_transfers").sum())
        out["benefits_transfers"] = (
            float(out["benefits_transfers"]) + (float(unemployment_benefits) + household_transfers) / 1e9
        )
        out["deficit"] = float(out["deficit"]) + float(gov.ts.current("deficit")[0]) / 1e9
        out["debt"] = float(out["debt"]) + float(gov.ts.current("debt")[0]) / 1e9
        n += 1

        for value in out.values():
            if isinstance(value, float) and not np.isfinite(value):
                out["finite"] = False

    if n:
        out["unemployment"] = float(out["unemployment"]) / n
        out["cpi_inflation"] = float(out["cpi_inflation"]) / n
    return out


def run_case(
    label: str,
    variant: str,
    price_dp: float = 0.0,
    household_investment: str = "exogenous",
    government_consumption: str = "exogenous",
) -> pd.DataFrame:
    if variant == "original":
        model, provs = build_original_model(Q, SEED)
    elif variant == "closure":
        model, provs = C.build_closure_model(
            q=Q,
            seed=SEED,
            price_dp=price_dp,
            itc_rate=0.0,
            household_investment=household_investment,
            government_consumption=government_consumption,
        )
    else:
        raise ValueError(variant)
    base_prices = {c: np.asarray(model.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}
    rows = []
    for t in range(Q + 1):
        rows.append({"case": label, "t": t, "year_float": 2022.0 + t / 4.0, **collect(model, provs, base_prices)})
        if t < Q:
            model.iterate(t)
    return pd.DataFrame(rows)


def annualize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["year"] = np.floor(df["year_float"]).astype(int)
    df = df[(df["year"] >= 2022) & (df["year"] <= 2035)]
    flows = [
        "real_gva",
        "household_consumption",
        "household_investment",
        "unmet_demand",
        "government_desired",
        "government_realized",
        "government_unrealized",
        "tax_revenue",
        "benefits_transfers",
        "deficit",
    ]
    stocks = ["debt"]
    rates = ["unemployment", "cpi_inflation"]
    parts = []
    for case, group in df.groupby("case", sort=False):
        annual = group.groupby("year", sort=True)[flows].sum()
        annual[stocks] = group.groupby("year", sort=True)[stocks].last()
        annual[rates] = group.groupby("year", sort=True)[rates].mean()
        annual["stable"] = group.groupby("year", sort=True)["finite"].all()
        annual["case"] = case
        annual["real_gva_growth_pct"] = annual["real_gva"].pct_change() * 100.0
        annual["hh_consumption_growth_pct"] = annual["household_consumption"].pct_change() * 100.0
        annual["cpi_inflation_pct"] = annual["cpi_inflation"] * 100.0
        annual["unemployment_pct"] = annual["unemployment"] * 100.0
        parts.append(annual.reset_index())
    return pd.concat(parts, ignore_index=True)


def compact_summary(annual: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for case, group in annual.groupby("case", sort=False):
        rows.append(
            {
                "case": case,
                "avg_real_gva_growth_pct_2027_35": group.loc[group.year >= 2027, "real_gva_growth_pct"].mean(),
                "hh_cons_2026": group.loc[group.year == 2026, "household_consumption"].iloc[0],
                "hh_cons_2035": group.loc[group.year == 2035, "household_consumption"].iloc[0],
                "hh_inv_2026": group.loc[group.year == 2026, "household_investment"].iloc[0],
                "hh_inv_2035": group.loc[group.year == 2035, "household_investment"].iloc[0],
                "hh_cons_growth_2026_35_pct": (
                    group.loc[group.year == 2035, "household_consumption"].iloc[0]
                    / group.loc[group.year == 2026, "household_consumption"].iloc[0]
                    - 1.0
                )
                * 100.0,
                "avg_unemployment_pct": group["unemployment_pct"].mean(),
                "avg_cpi_inflation_pct": group["cpi_inflation_pct"].mean(),
                "cum_unmet_demand": group["unmet_demand"].sum(),
                "cum_gov_desired": group["government_desired"].sum(),
                "cum_gov_realized": group["government_realized"].sum(),
                "cum_gov_unrealized": group["government_unrealized"].sum(),
                "cum_tax_revenue": group["tax_revenue"].sum(),
                "cum_benefits_transfers": group["benefits_transfers"].sum(),
                "cum_deficit": group["deficit"].sum(),
                "debt_2035": group.loc[group.year == 2035, "debt"].iloc[0],
                "stable": bool(group["stable"].all()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        choices=[
            "all",
            "A_original_c0",
            "B_hh_endog",
            "C_dp_005",
            "C_dp_010",
            "D_dp005_hhinv_default",
            "E_dp005_hhinv_default_govar",
        ],
        default="all",
    )
    args = parser.parse_args()
    specs = [
        ("A_original_c0", "original", 0.0, "exogenous", "exogenous"),
        ("B_hh_endog", "closure", 0.0, "exogenous", "exogenous"),
        ("C_dp_005", "closure", 0.05, "exogenous", "exogenous"),
        ("C_dp_010", "closure", 0.10, "exogenous", "exogenous"),
        ("D_dp005_hhinv_default", "closure", 0.05, "default", "exogenous"),
        ("E_dp005_hhinv_default_govar", "closure", 0.05, "default", "autoregressive"),
    ]
    if args.case != "all":
        specs = [spec for spec in specs if spec[0] == args.case]

    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for label, variant, price_dp, household_investment, government_consumption in specs:
        print(f"RUNNING {label}", flush=True)
        frame = run_case(label, variant, price_dp, household_investment, government_consumption)
        frame.to_csv(OUT / f"{label}_quarterly.csv", index=False)
        frames.append(frame)
        print(f"DONE {label}", flush=True)
    quarterly = pd.concat(frames, ignore_index=True)
    annual = annualize(quarterly)
    summary = compact_summary(annual)
    cols = [
        "case",
        "avg_real_gva_growth_pct_2027_35",
        "hh_cons_2026",
        "hh_cons_2035",
        "hh_cons_growth_2026_35_pct",
        "avg_unemployment_pct",
        "avg_cpi_inflation_pct",
        "cum_unmet_demand",
        "cum_gov_desired",
        "cum_gov_realized",
        "cum_gov_unrealized",
        "cum_tax_revenue",
        "cum_benefits_transfers",
        "cum_deficit",
        "debt_2035",
        "stable",
    ]
    print("SUMMARY_2026_2035")
    print(summary[cols].to_csv(index=False, float_format="%.6f"))
    print("ANNUAL_CORE")
    print(
        annual[
            [
                "case",
                "year",
                "real_gva_growth_pct",
                "household_consumption",
                "household_investment",
                "hh_consumption_growth_pct",
                "unemployment_pct",
                "cpi_inflation_pct",
                "unmet_demand",
                "government_desired",
                "government_realized",
                "government_unrealized",
                "tax_revenue",
                "benefits_transfers",
                "deficit",
                "debt",
                "stable",
            ]
        ].to_csv(index=False, float_format="%.6f")
    )


if __name__ == "__main__":
    main()
