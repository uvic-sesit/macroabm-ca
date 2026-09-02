"""Closure-only diagnostics for the validated CAN-2022 baseline.

This branch intentionally does not include either ITC behavioral mechanism.
It only prepares reusable macro-closure infrastructure:

- endogenous household consumption via DisposableIncomeHouseholdConsumption;
- household investment remains exogenous;
- fiscal ITC refunds are dormant unless explicitly activated;
- demand-pull pricing is configurable, cost-push pricing is kept off;
- central bank and credit settings are left unchanged.

The government-purchase protection option is diagnostic: after goods-market
clearing, it overwrites government-entity realized purchases with their
exogenous nominal demand basket so government purchases are not reduced by
market rationing/crowding-out in the deficit accounting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments" / "itc_endogenous_closure"))
sys.path.insert(0, str(REPO / "dev" / "io2022"))
sys.path.insert(0, str(REPO / "dev" / "validation"))

import provincial_validation_2022 as P
from macro_data import DataWrapper
from macromodel.agents.households.func.consumption import DisposableIncomeHouseholdConsumption
from macromodel.agents.households.func.investment import DefaultHouseholdInvestment, ExogenousHouseholdInvestment
from macromodel.agents.government_entities.func.consumption import (
    AutoregressiveGovernmentConsumptionSetter,
    ExogenousGovernmentConsumptionSetter,
)
from macromodel.simulation import Simulation
from save_baseline_2022 import build_config


PKL = P.PKL
DATA_REPO = REPO
if not PKL.exists() or not (REPO / "dev" / "statcan" / "36100222.csv").exists():
    shared_repo = REPO.parent / "macroabm-ca"
    shared_pkl = shared_repo / "dev" / "pkl_files" / PKL.name
    if shared_pkl.exists():
        DATA_REPO = shared_repo
        PKL = shared_pkl
        P.REPO = shared_repo
        P.PKL = shared_pkl
PROV10 = P.PROV10
SECTOR_CODES = P.SECTOR_CODES
ELIGIBLE_CODES = ("C27", "C28")
ELIGIBLE_INDICES = [SECTOR_CODES.index(code) for code in ELIGIBLE_CODES]


def build_closure_model(
    q: int,
    seed: int = 0,
    price_dp: float = 0.0,
    itc_rate: float = 0.0,
    eligible_indices: Iterable[int] = ELIGIBLE_INDICES,
    protect_government_purchases: bool = False,
    household_investment: str = "exogenous",
    government_consumption: str = "exogenous",
):
    """Build the closure test model from the validated CAN-2022 candidate baseline."""
    P.Q = q
    try:
        data = DataWrapper.init_from_pickle(PKL)
        provs, cfg = build_config(data, seed, q)
        P.configure(cfg, provs, candidate=True)
        model = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=cfg)
        P.post_build(model, provs, "candidate_prov")
        P.install_external_demand(model, provs)
    finally:
        P.Q = 13

    for c in provs:
        country = model.countries[c]
        _activate_disposable_income_consumption(country)
        _configure_household_investment(country, household_investment)
        _configure_government_consumption(country, government_consumption)
        _configure_prices(country, price_dp=price_dp)
        _configure_fiscal_itc(country, itc_rate=itc_rate, eligible_indices=eligible_indices)
        if protect_government_purchases:
            _wrap_government_purchase_protection(country)
    return model, provs


def _activate_disposable_income_consumption(country) -> None:
    old = country.households.functions["consumption"]
    country.households.functions["consumption"] = DisposableIncomeHouseholdConsumption(
        consumption_smoothing_fraction=old.consumption_smoothing_fraction,
        consumption_smoothing_window=old.consumption_smoothing_window,
        minimum_consumption_fraction=old.minimum_consumption_fraction,
        elasticity_of_substitution=getattr(old, "elasticity_of_substitution", 1.0),
    )


def _configure_household_investment(country, mode: str) -> None:
    if mode == "exogenous":
        old = country.households.functions["investment"]
        if not isinstance(old, ExogenousHouseholdInvestment):
            country.households.functions["investment"] = ExogenousHouseholdInvestment()
    elif mode == "default":
        country.households.functions["investment"] = DefaultHouseholdInvestment()
    else:
        raise ValueError(f"Unknown household_investment mode: {mode}")


def _configure_government_consumption(country, mode: str) -> None:
    old = country.government_entities.functions["consumption"]
    if mode == "exogenous":
        if not isinstance(old, ExogenousGovernmentConsumptionSetter):
            country.government_entities.functions["consumption"] = ExogenousGovernmentConsumptionSetter(
                consistency=getattr(old, "consistency", 1.0),
                default_growth=getattr(old, "default_growth", None),
            )
    elif mode == "autoregressive":
        country.government_entities.functions["consumption"] = AutoregressiveGovernmentConsumptionSetter(
            consistency=getattr(old, "consistency", 1.0),
            default_growth=getattr(old, "default_growth", None),
        )
    else:
        raise ValueError(f"Unknown government_consumption mode: {mode}")


def _configure_prices(country, price_dp: float) -> None:
    prices = country.firms.functions["prices"]
    prices.price_setting_speed_dp = float(price_dp)
    prices.price_setting_speed_cp = 0.0


def _configure_fiscal_itc(country, itc_rate: float, eligible_indices: Iterable[int]) -> None:
    country.central_government.states["ITC Refund Rate"] = float(itc_rate)
    country.central_government.states["ITC Eligible Capital Indices"] = list(eligible_indices)


def _wrap_government_purchase_protection(country) -> None:
    original_update = country.update_realised_metrics

    def wrapped_update_realised_metrics() -> None:
        _protect_current_government_purchases(country)
        original_update()

    country.update_realised_metrics = wrapped_update_realised_metrics


def _protect_current_government_purchases(country) -> None:
    gov = country.government_entities
    desired_lcu = np.asarray(gov.ts.current("desired_consumption_in_lcu"), float).reshape(-1)
    n_entities = int(gov.ts.current("n_government_entities"))
    desired_lcu_by_entity = np.tile(desired_lcu / n_entities, (n_entities, 1))
    desired_usd_by_entity = desired_lcu_by_entity / country.exchange_rate_usd_to_lcu

    prices = np.asarray(country.economy.ts.current("good_prices"), float).reshape(-1)
    desired_real = np.divide(
        desired_usd_by_entity,
        prices[None, :],
        out=np.zeros_like(desired_usd_by_entity),
        where=prices[None, :] > 0.0,
    )

    gov.ts.dicts["nominal_amount_spent_in_lcu"][-1] = desired_lcu_by_entity
    gov.ts.dicts["nominal_amount_spent_in_usd"][-1] = desired_usd_by_entity
    gov.ts.dicts["real_amount_bought"][-1] = desired_real
    for country_name in gov.all_country_names:
        key_lcu = "nominal_amount_spent_in_lcu_to_" + country_name
        key_usd = "nominal_amount_spent_in_usd_to_" + country_name
        key_real = "real_amount_bought_from_" + country_name
        if country_name == country.country_name:
            gov.ts.dicts[key_lcu][-1] = desired_lcu_by_entity
            gov.ts.dicts[key_usd][-1] = desired_usd_by_entity
            gov.ts.dicts[key_real][-1] = desired_real
        else:
            gov.ts.dicts[key_lcu][-1] = np.zeros_like(desired_lcu_by_entity)
            gov.ts.dicts[key_usd][-1] = np.zeros_like(desired_usd_by_entity)
            gov.ts.dicts[key_real][-1] = np.zeros_like(desired_real)


def collect_diagnostics(model, provs) -> dict[str, float]:
    out = {
        "household_consumption": 0.0,
        "cpi": 0.0,
        "cpi_inflation": 0.0,
        "government_desired_purchases": 0.0,
        "government_realized_purchases": 0.0,
        "government_unrealized_purchases": 0.0,
        "government_revenue": 0.0,
        "taxes_production": 0.0,
        "taxes_vat": 0.0,
        "taxes_cf": 0.0,
        "taxes_corporate_income": 0.0,
        "taxes_income": 0.0,
        "taxes_employee_si": 0.0,
        "taxes_employer_si": 0.0,
        "benefits_transfers": 0.0,
        "itc_refunds": 0.0,
        "deficit": 0.0,
        "debt": 0.0,
    }
    n = 0
    for c in provs:
        if str(c) not in PROV10:
            continue
        country = model.countries[c]
        gov = country.central_government
        entities = country.government_entities
        econ = country.economy
        out["household_consumption"] += float(country.households.ts.current("total_consumption")[0]) / 1e9
        out["cpi"] += float(econ.ts.current("cpi")[0])
        out["cpi_inflation"] += float(econ.ts.current("cpi_inflation")[0])
        desired = float(np.asarray(entities.ts.current("desired_consumption_in_lcu"), float).sum()) / 1e9
        realized = float(np.asarray(entities.ts.current("nominal_amount_spent_in_lcu"), float).sum()) / 1e9
        out["government_desired_purchases"] += desired
        out["government_realized_purchases"] += realized
        out["government_unrealized_purchases"] += desired - realized
        out["government_revenue"] += float(gov.ts.current("revenue")[0]) / 1e9
        for key in [
            "taxes_production",
            "taxes_vat",
            "taxes_cf",
            "taxes_corporate_income",
            "taxes_income",
            "taxes_employee_si",
            "taxes_employer_si",
        ]:
            out[key] += float(gov.ts.current(key)[0]) / 1e9
        unemployment_benefits = (
            sum(a.name == "UNEMPLOYED" for a in country.individuals.states["Activity Status"])
            * gov.ts.current("unemployment_benefits_by_individual")[0]
        )
        household_transfers = float(country.households.ts.current("income_social_transfers").sum())
        out["benefits_transfers"] += (float(unemployment_benefits) + household_transfers) / 1e9
        out["itc_refunds"] += float(gov.ts.current("itc_refunds")[0]) / 1e9
        out["deficit"] += float(gov.ts.current("deficit")[0]) / 1e9
        out["debt"] += float(gov.ts.current("debt")[0]) / 1e9
        n += 1
    if n:
        out["cpi"] /= n
        out["cpi_inflation"] /= n
    return out


def run_smoke(q: int, seed: int, price_dp: float, itc_rate: float, protect_government_purchases: bool):
    model, provs = build_closure_model(
        q=q,
        seed=seed,
        price_dp=price_dp,
        itc_rate=itc_rate,
        protect_government_purchases=protect_government_purchases,
    )
    rows = []
    for t in range(q + 1):
        rows.append({"t": t, "year": 2022.0 + t / 4.0, **collect_diagnostics(model, provs)})
        if t < q:
            model.iterate(t)
    return rows


def print_last(rows: list[dict[str, float]]) -> None:
    keys = [k for k in rows[-1] if k not in {"t", "year"}]
    print(f"{'t':>3s} {'year':>8s} " + " ".join(f"{k:>28s}" for k in keys))
    row = rows[-1]
    print(f"{row['t']:3.0f} {row['year']:8.2f} " + " ".join(f"{row[k]:28.6f}" for k in keys))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["smoke"], nargs="?", default="smoke")
    parser.add_argument("--q", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--price-dp", type=float, default=0.0)
    parser.add_argument("--itc-rate", type=float, default=0.0)
    parser.add_argument("--protect-government-purchases", action="store_true")
    args = parser.parse_args()

    rows = run_smoke(
        q=args.q,
        seed=args.seed,
        price_dp=args.price_dp,
        itc_rate=args.itc_rate,
        protect_government_purchases=args.protect_government_purchases,
    )
    print_last(rows)
    print(
        f"q={args.q}, seed={args.seed}, price_dp={args.price_dp:.4f}, "
        f"itc_rate={args.itc_rate:.4f}, "
        f"protect_government_purchases={args.protect_government_purchases}"
    )


if __name__ == "__main__":
    main()
