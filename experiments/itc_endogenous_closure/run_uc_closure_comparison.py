"""UC design_b_pre_stock treatment-control under closure variants."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NUMBA_CACHE = Path(tempfile.gettempdir()) / "macroabm_ca_numba_cache"
NUMBA_CACHE.mkdir(exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(NUMBA_CACHE))

import numpy as np
import pandas as pd

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments" / "itc_endogenous_closure"))
sys.path.insert(0, str(REPO / "dev" / "io2022"))
sys.path.insert(0, str(REPO / "dev" / "validation"))

import closure_feedback_exp as C
import provincial_validation_2022 as P


Q = 55
SEED = 0
TAU = 0.30
ETA = 0.50
ACT0 = 16
ACT1 = 35
DESIGN_MODE = "lagged_share_pre_stock_adjustment"
OUT = REPO / "experiments" / "itc_endogenous_closure" / "results"

OLD_CLOSURE_PRE_STOCK = {
    "cum_2026_30_investment": 52.9993,
    "cum_2026_30_gva": 53.2202,
    "cum_2026_30_target_production": 81.2184,
    "cum_2026_30_realized_production": 112.9425,
    "cum_2026_30_imports": 34.3034,
    "gross_itc_refunds": 63.1340,
    "eligible_purchase_additionality": 0.0163,
}


def set_uc_params(model, provs, treatment: bool) -> None:
    for c in provs:
        setter = model.countries[c].firms.functions["target_capital_inputs"]
        setter.itc_user_cost_rate = 0.0
        if treatment:
            setter.itc_user_cost_eta = ETA
            setter.itc_user_cost_eligible_indices = C.ELIGIBLE_INDICES
            setter.itc_user_cost_mode = DESIGN_MODE


def set_policy_active(model, provs, treatment: bool, active: bool) -> None:
    rate = TAU if treatment and active else 0.0
    for c in provs:
        country = model.countries[c]
        country.firms.functions["target_capital_inputs"].itc_user_cost_rate = rate
        country.central_government.states["ITC Refund Rate"] = rate
        country.central_government.states["ITC Eligible Capital Indices"] = C.ELIGIBLE_INDICES


def build_model(q: int, price_dp: float, treatment: bool, protect_government_purchases: bool = False):
    model, provs = C.build_closure_model(
        q=q,
        seed=SEED,
        price_dp=price_dp,
        itc_rate=0.0,
        eligible_indices=C.ELIGIBLE_INDICES,
        protect_government_purchases=protect_government_purchases,
    )
    set_uc_params(model, provs, treatment=treatment)
    return model, provs


def collect(model, provs, base_prices) -> dict[str, float | bool]:
    out: dict[str, float | bool] = {
        "desired_investment": 0.0,
        "realized_investment": 0.0,
        "eligible_purchases": 0.0,
        "capital_stock": 0.0,
        "target_production": 0.0,
        "realized_production": 0.0,
        "gva": 0.0,
        "employment_agents": 0.0,
        "unemployment_rate": 0.0,
        "household_consumption": 0.0,
        "imports": 0.0,
        "unmet_demand": 0.0,
        "cpi_inflation": 0.0,
        "itc_refunds": 0.0,
        "tax_revenue": 0.0,
        "taxes_production": 0.0,
        "taxes_vat": 0.0,
        "taxes_cf": 0.0,
        "taxes_corporate_income": 0.0,
        "taxes_exports": 0.0,
        "taxes_income": 0.0,
        "taxes_employee_si": 0.0,
        "taxes_employer_si": 0.0,
        "rent_received": 0.0,
        "base_production_tax": 0.0,
        "base_vat": 0.0,
        "base_cf": 0.0,
        "base_corporate_tax": 0.0,
        "base_income_tax": 0.0,
        "base_employee_si": 0.0,
        "base_employer_si": 0.0,
        "benefits_transfers": 0.0,
        "government_desired_purchases": 0.0,
        "government_realized_purchases": 0.0,
        "government_unrealized_purchases": 0.0,
        "deficit": 0.0,
        "debt": 0.0,
        "dp_signal_mean": 0.0,
        "dp_trigger_fraction": 0.0,
        "dp_price_contribution_mean": 0.0,
        "finite": True,
    }
    n = 0
    dp_firms = 0
    for c in provs:
        if str(c) not in P.PROV10:
            continue
        country = model.countries[c]
        firms = country.firms
        gov = country.central_government
        econ = country.economy
        prices = np.asarray(econ.ts.current("good_prices"), float).reshape(-1)
        prices0 = base_prices[c]

        desired_capital = np.asarray(firms.ts.current("unconstrained_target_capital_inputs"), float)
        realized_capital = np.asarray(firms.ts.current("real_amount_bought_as_capital_goods"), float)
        capital_stock = np.asarray(firms.ts.current("capital_inputs_stock"), float)
        production = np.asarray(firms.ts.current("production"), float).reshape(-1)
        target = np.asarray(firms.ts.current("target_production"), float).reshape(-1)
        used_intermediate = np.asarray(firms.ts.current("used_intermediate_inputs"), float)
        firm_prices0 = prices0[firms.states["Industry"]]

        out["desired_investment"] = float(out["desired_investment"]) + float((desired_capital * prices[None, :]).sum()) / 1e9
        out["realized_investment"] = float(out["realized_investment"]) + float((realized_capital * prices[None, :]).sum()) / 1e9
        out["eligible_purchases"] = (
            float(out["eligible_purchases"])
            + float((realized_capital[:, C.ELIGIBLE_INDICES] * prices[C.ELIGIBLE_INDICES][None, :]).sum()) / 1e9
        )
        out["capital_stock"] = float(out["capital_stock"]) + float((capital_stock * prices[None, :]).sum()) / 1e9
        out["target_production"] = float(out["target_production"]) + float((target * firm_prices0).sum()) / 1e9
        out["realized_production"] = (
            float(out["realized_production"]) + float((production * firm_prices0).sum()) / 1e9
        )
        gva = float((production * firm_prices0).sum())
        if used_intermediate.ndim == 2:
            gva -= float((used_intermediate * prices0[None, :]).sum())
        out["gva"] = float(out["gva"]) + gva / 1e9

        status = np.asarray([a.name for a in country.individuals.states["Activity Status"]])
        out["employment_agents"] = float(out["employment_agents"]) + float((status == "EMPLOYED").sum())
        out["unemployment_rate"] = float(out["unemployment_rate"]) + float(econ.ts.current("unemployment_rate")[0])
        out["household_consumption"] = (
            float(out["household_consumption"]) + float(country.households.ts.current("total_consumption")[0]) / 1e9
        )
        row_purchases = np.nan_to_num(np.asarray(firms.ts.current("real_amount_bought_from_ROW"), float), nan=0.0)
        out["imports"] = float(out["imports"]) + float((row_purchases * prices[None, :]).sum()) / 1e9
        excess = np.nan_to_num(np.asarray(firms.ts.current("real_excess_demand"), float), nan=0.0)
        out["unmet_demand"] = float(out["unmet_demand"]) + float(excess.sum()) / 1e9
        out["cpi_inflation"] = float(out["cpi_inflation"]) + float(econ.ts.current("cpi_inflation")[0])
        out["itc_refunds"] = float(out["itc_refunds"]) + float(gov.ts.current("itc_refunds")[0]) / 1e9
        out["tax_revenue"] = float(out["tax_revenue"]) + float(gov.ts.current("revenue")[0]) / 1e9
        for tax_key in [
            "taxes_production",
            "taxes_vat",
            "taxes_cf",
            "taxes_corporate_income",
            "taxes_exports",
            "taxes_income",
            "taxes_employee_si",
            "taxes_employer_si",
        ]:
            out[tax_key] = float(out[tax_key]) + float(gov.ts.current(tax_key)[0]) / 1e9
        out["rent_received"] = float(out["rent_received"]) + float(gov.ts.current("total_rent_received")[0]) / 1e9

        out["base_production_tax"] = (
            float(out["base_production_tax"]) + float((production * np.asarray(firms.ts.current("price"), float)).sum()) / 1e9
        )
        out["base_vat"] = (
            float(out["base_vat"]) + float(np.asarray(country.households.ts.current("consumption"), float).sum()) / 1e9
        )
        out["base_cf"] = (
            float(out["base_cf"])
            + float(np.maximum(0.0, np.asarray(country.households.ts.current("investment"), float)).sum()) / 1e9
        )
        out["base_corporate_tax"] = (
            float(out["base_corporate_tax"])
            + (
                float(np.maximum(np.asarray(firms.ts.current("profits"), float), 0.0).sum())
                + float(np.maximum(np.asarray(country.banks.ts.current("profits"), float), 0.0).sum())
            )
            / 1e9
        )
        employed = np.asarray([a.name for a in country.individuals.states["Activity Status"]]) == "EMPLOYED"
        employee_income = np.asarray(country.individuals.ts.current("employee_income"), float)
        wage_base = float(employee_income[employed].sum())
        rent_base = float(
            country.households.ts.current("rent")[
                country.households.states["Tenure Status of the Main Residence"] == 3
            ].sum()
        )
        financial_income_base = float(np.asarray(country.households.ts.current("income_financial_assets"), float).sum())
        out["base_income_tax"] = (
            float(out["base_income_tax"])
            + (
                (1.0 - gov.states["Employee Social Insurance Tax"]) * wage_base
                + rent_base
                + financial_income_base
            )
            / 1e9
        )
        out["base_employee_si"] = float(out["base_employee_si"]) + wage_base / 1e9
        out["base_employer_si"] = float(out["base_employer_si"]) + wage_base / 1e9

        unemployment_benefits = (
            sum(a.name == "UNEMPLOYED" for a in country.individuals.states["Activity Status"])
            * gov.ts.current("unemployment_benefits_by_individual")[0]
        )
        household_transfers = float(country.households.ts.current("income_social_transfers").sum())
        out["benefits_transfers"] = (
            float(out["benefits_transfers"]) + (float(unemployment_benefits) + household_transfers) / 1e9
        )

        entities = country.government_entities
        desired_g = float(np.asarray(entities.ts.current("desired_consumption_in_lcu"), float).sum()) / 1e9
        realized_g = float(np.asarray(entities.ts.current("nominal_amount_spent_in_lcu"), float).sum()) / 1e9
        out["government_desired_purchases"] = float(out["government_desired_purchases"]) + desired_g
        out["government_realized_purchases"] = float(out["government_realized_purchases"]) + realized_g
        out["government_unrealized_purchases"] = float(out["government_unrealized_purchases"]) + desired_g - realized_g
        out["deficit"] = float(out["deficit"]) + float(gov.ts.current("deficit")[0]) / 1e9
        out["debt"] = float(out["debt"]) + float(gov.ts.current("debt")[0]) / 1e9

        if len(firms.ts.historic("price")) == 1:
            prev_supply = (
                np.asarray(firms.ts.current("production"), float).reshape(-1)
                + np.asarray(firms.ts.current("inventory"), float).reshape(-1)
            )
        else:
            prev_supply = (
                np.asarray(firms.ts.prev("production"), float).reshape(-1)
                + np.asarray(firms.ts.current("inventory"), float).reshape(-1)
            )
        prev_demand = np.asarray(firms.ts.current("demand"), float).reshape(-1)
        prev_prices = np.asarray(firms.ts.current("price"), float).reshape(-1)
        prev_avg_prices = np.asarray(econ.ts.prev("good_prices"), float).reshape(-1)
        avg_price_by_firm = prev_avg_prices[firms.states["Industry"]]
        trigger = np.logical_or(
            np.logical_and(prev_supply <= prev_demand, prev_prices < avg_price_by_firm),
            np.logical_and(prev_supply > prev_demand, prev_prices >= avg_price_by_firm),
        )
        raw_dp = np.divide(prev_demand, prev_supply, out=np.ones_like(prev_demand), where=prev_supply != 0.0) - 1.0
        dp_signal = np.clip(raw_dp, -0.1, 0.1)
        active_dp = np.where(trigger, dp_signal, 0.0)
        positive_dp = active_dp > 0.0
        price_dp = float(firms.functions["prices"].price_setting_speed_dp)
        out["dp_signal_mean"] = float(out["dp_signal_mean"]) + float(active_dp.mean()) * active_dp.size
        out["dp_trigger_fraction"] = float(out["dp_trigger_fraction"]) + float(positive_dp.sum())
        out["dp_price_contribution_mean"] = (
            float(out["dp_price_contribution_mean"]) + float((price_dp * active_dp).mean()) * active_dp.size
        )
        dp_firms += active_dp.size
        n += 1

    if n:
        out["unemployment_rate"] = float(out["unemployment_rate"]) / n
        out["cpi_inflation"] = float(out["cpi_inflation"]) / n
    if dp_firms:
        out["dp_signal_mean"] = float(out["dp_signal_mean"]) / dp_firms
        out["dp_trigger_fraction"] = float(out["dp_trigger_fraction"]) / dp_firms
        out["dp_price_contribution_mean"] = float(out["dp_price_contribution_mean"]) / dp_firms
    out["finite"] = all(np.isfinite(v) for v in out.values() if isinstance(v, float))
    return out


def run_case(q: int, price_dp: float, treatment: bool, protect_government_purchases: bool = False) -> pd.DataFrame:
    model, provs = build_model(
        q=q,
        price_dp=price_dp,
        treatment=treatment,
        protect_government_purchases=protect_government_purchases,
    )
    base_prices = {
        c: np.asarray(model.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs
    }
    rows = []
    for t in range(q + 1):
        rows.append(
            {
                "case": "treatment" if treatment else "control",
                "t": t,
                "year_float": 2022.0 + t / 4.0,
                "policy_active": ACT0 <= t <= ACT1,
                **collect(model, provs, base_prices),
            }
        )
        if t < q:
            set_policy_active(model, provs, treatment=treatment, active=ACT0 <= t <= ACT1)
            model.iterate(t)
    return pd.DataFrame(rows)


def annualize(quarterly: pd.DataFrame) -> pd.DataFrame:
    df = quarterly.copy()
    df["year"] = np.floor(df.year_float).astype(int)
    df = df[(df.year >= 2026) & (df.year <= 2035)]
    flows = [
        "desired_investment",
        "realized_investment",
        "eligible_purchases",
        "target_production",
        "realized_production",
        "gva",
        "household_consumption",
        "imports",
        "unmet_demand",
        "itc_refunds",
        "tax_revenue",
        "taxes_production",
        "taxes_vat",
        "taxes_cf",
        "taxes_corporate_income",
        "taxes_exports",
        "taxes_income",
        "taxes_employee_si",
        "taxes_employer_si",
        "rent_received",
        "base_production_tax",
        "base_vat",
        "base_cf",
        "base_corporate_tax",
        "base_income_tax",
        "base_employee_si",
        "base_employer_si",
        "benefits_transfers",
        "government_desired_purchases",
        "government_realized_purchases",
        "government_unrealized_purchases",
        "deficit",
        "dp_signal_mean",
        "dp_trigger_fraction",
        "dp_price_contribution_mean",
    ]
    stocks = ["capital_stock", "employment_agents", "debt"]
    rates = ["unemployment_rate", "cpi_inflation"]
    out = []
    for case, group in df.groupby("case", sort=False):
        annual = group.groupby("year")[flows].sum()
        annual[stocks] = group.groupby("year")[stocks].last()
        annual[rates] = group.groupby("year")[rates].mean()
        annual["finite"] = group.groupby("year")["finite"].all()
        annual["case"] = case
        out.append(annual.reset_index())
    return pd.concat(out, ignore_index=True)


def summarize_delta(annual: pd.DataFrame, start: int, end: int) -> dict[str, float]:
    c = annual[(annual.case == "control") & (annual.year >= start) & (annual.year <= end)]
    t = annual[(annual.case == "treatment") & (annual.year >= start) & (annual.year <= end)]
    flows = [
        "desired_investment",
        "realized_investment",
        "target_production",
        "realized_production",
        "gva",
        "household_consumption",
        "imports",
        "unmet_demand",
        "tax_revenue",
        "benefits_transfers",
        "government_realized_purchases",
        "deficit",
    ]
    row = {f"d_{k}": float(t[k].sum() - c[k].sum()) for k in flows}
    row["gross_itc_refunds"] = float(t["itc_refunds"].sum())
    row["control_eligible_purchases"] = float(c["eligible_purchases"].sum())
    row["treatment_eligible_purchases"] = float(t["eligible_purchases"].sum())
    incr_eligible = row["treatment_eligible_purchases"] - row["control_eligible_purchases"]
    row["incremental_eligible_purchases"] = incr_eligible
    row["eligible_additionality"] = incr_eligible / row["treatment_eligible_purchases"]
    last_year = end
    tc_last = t[t.year == last_year].iloc[-1]
    cc_last = c[c.year == last_year].iloc[-1]
    for key in ["capital_stock", "employment_agents", "debt", "unemployment_rate", "cpi_inflation"]:
        row[f"d_{key}_{last_year}"] = float(tc_last[key] - cc_last[key])
    row[f"d_unemployment_rate_pp_{last_year}"] = 100.0 * row[f"d_unemployment_rate_{last_year}"]
    row[f"d_cpi_inflation_pp_{last_year}"] = 100.0 * row[f"d_cpi_inflation_{last_year}"]
    row["stable"] = bool(c["finite"].all() and t["finite"].all())
    return row


def run_variant(
    label: str, price_dp: float, protect_government_purchases: bool = False, case: str = "both"
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    treatment_flags = [False, True] if case == "both" else [case == "treatment"]
    for treatment in treatment_flags:
        print(f"RUNNING {label} {'treatment' if treatment else 'control'}", flush=True)
        frame = run_case(
            Q,
            price_dp=price_dp,
            treatment=treatment,
            protect_government_purchases=protect_government_purchases,
        )
        frame.to_csv(OUT / f"uc_pre_stock_eta050_{label}_{frame.case.iloc[0]}_quarterly.csv", index=False)
        frames.append(frame)
        print(f"DONE {label} {'treatment' if treatment else 'control'}", flush=True)
    if case != "both":
        other_case = "control" if case == "treatment" else "treatment"
        other_path = OUT / f"uc_pre_stock_eta050_{label}_{other_case}_quarterly.csv"
        if other_path.exists():
            frames.append(pd.read_csv(other_path))
    quarterly = pd.concat(frames, ignore_index=True)
    if set(quarterly.case.unique()) != {"control", "treatment"}:
        return quarterly, pd.DataFrame(), pd.DataFrame()
    annual = annualize(quarterly)
    annual.to_csv(OUT / f"uc_pre_stock_eta050_{label}_annual.csv", index=False)
    summaries = []
    for start, end in [(2026, 2030), (2026, 2035), (2031, 2035)]:
        row = {"variant": label, "window": f"{start}-{end}", **summarize_delta(annual, start, end)}
        summaries.append(row)
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / f"uc_pre_stock_eta050_{label}_summary.csv", index=False)
    return quarterly, annual, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--variant",
        choices=["all", "hh_only", "hh_dp005", "hh_dp010", "hh_dp025", "hh_dp050", "hh_dp005_protected_g"],
        default="all",
    )
    parser.add_argument("--case", choices=["both", "control", "treatment"], default="both")
    args = parser.parse_args()
    specs = [
        ("hh_only", 0.0, False),
        ("hh_dp005", 0.05, False),
        ("hh_dp010", 0.10, False),
        ("hh_dp025", 0.25, False),
        ("hh_dp050", 0.50, False),
        ("hh_dp005_protected_g", 0.05, True),
    ]
    if args.variant != "all":
        specs = [spec for spec in specs if spec[0] == args.variant]
    summaries = []
    for label, price_dp, protect_government_purchases in specs:
        _, _, summary = run_variant(label, price_dp, protect_government_purchases, case=args.case)
        summaries.append(summary)
    all_summary = pd.concat(summaries, ignore_index=True)
    print("SUMMARY")
    cols = [
        "variant",
        "window",
        "d_desired_investment",
        "d_realized_investment",
        "d_capital_stock_2030",
        "d_capital_stock_2035",
        "d_target_production",
        "d_realized_production",
        "d_gva",
        "d_employment_agents_2030",
        "d_employment_agents_2035",
        "d_unemployment_rate_pp_2030",
        "d_unemployment_rate_pp_2035",
        "d_household_consumption",
        "d_imports",
        "d_unmet_demand",
        "d_cpi_inflation_pp_2030",
        "d_cpi_inflation_pp_2035",
        "gross_itc_refunds",
        "d_tax_revenue",
        "d_benefits_transfers",
        "d_government_realized_purchases",
        "d_deficit",
        "d_debt_2030",
        "d_debt_2035",
        "eligible_additionality",
        "stable",
    ]
    available_cols = [c for c in cols if c in all_summary.columns]
    print(all_summary[available_cols].to_csv(index=False, float_format="%.6f"))
    print("OLD_CLOSURE_PRE_STOCK_2026_30")
    print(pd.DataFrame([OLD_CLOSURE_PRE_STOCK]).to_csv(index=False, float_format="%.6f"))


if __name__ == "__main__":
    main()
