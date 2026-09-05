"""Monetary-policy diagnostics on top of the endogenous-closure checkpoint.

This script is intentionally diagnostic only. It toggles the existing central-bank
policy-rate setter between ConstantPolicyRate and PolednaPolicyRate, while keeping
the preferred endogenous closure and the UC pre-stock ITC mechanism unchanged.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
NUMBA_CACHE = Path(tempfile.gettempdir()) / "macroabm_ca_numba_cache"
NUMBA_CACHE.mkdir(exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(NUMBA_CACHE))

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments" / "itc_endogenous_closure"))
sys.path.insert(0, str(REPO / "dev" / "validation"))

import closure_feedback_exp as C
import provincial_validation_2022 as P
import run_uc_closure_comparison as UC
from macromodel.agents.central_bank.func.policy_rate import (
    ConstantPolicyRate,
    PolednaPolicyRate,
    quarterly_to_annual_effective,
)


Q = 55
SEED = 0
PRICE_DP = 0.05
OUT = REPO / "experiments" / "itc_monetary_diagnostic" / "results"


def apply_policy_rule(model, provs, rule_name: str) -> None:
    if rule_name == "constant":
        rule = ConstantPolicyRate
    elif rule_name == "poledna":
        rule = PolednaPolicyRate
    else:
        raise ValueError(f"Unknown policy rule: {rule_name}")
    for c in provs:
        model.countries[c].central_bank.functions["policy_rate"] = rule()


def build_model(rule_name: str, q: int, treatment: bool = False):
    if treatment:
        model, provs = UC.build_model(q=q, price_dp=PRICE_DP, treatment=True)
    else:
        model, provs = C.build_closure_model(q=q, seed=SEED, price_dp=PRICE_DP, itc_rate=0.0)
        if rule_name in {"constant", "poledna"}:
            UC.set_uc_params(model, provs, treatment=False)
    apply_policy_rule(model, provs, rule_name)
    return model, provs


def base_prices(model, provs) -> dict[str, np.ndarray]:
    return {c: np.asarray(model.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}


def collect_monetary(model, provs, base_price_map) -> dict[str, float | bool]:
    out: dict[str, float | bool] = UC.collect(model, provs, base_price_map)
    additions: dict[str, float] = {
        "policy_rate": 0.0,
        "policy_rate_annual_equiv": 0.0,
        "firm_lending_rate": 0.0,
        "firm_lending_rate_annual_equiv": 0.0,
        "household_lending_rate": 0.0,
        "firm_deposit_rate": 0.0,
        "household_deposit_rate": 0.0,
        "government_interest_expense": 0.0,
        "firm_credit_new": 0.0,
        "firm_credit_outstanding": 0.0,
        "household_credit_new": 0.0,
        "household_credit_outstanding": 0.0,
        "firm_interest_paid": 0.0,
        "household_interest_paid": 0.0,
    }
    n = 0
    for c in provs:
        if str(c) not in P.PROV10:
            continue
        country = model.countries[c]
        banks = country.banks.ts
        credit = country.credit_market.ts
        policy_rate = float(country.central_bank.ts.current("policy_rate")[0])
        firm_lending_rate = 0.5 * (
            float(banks.current("average_interest_rates_on_short_term_firm_loans")[0])
            + float(banks.current("average_interest_rates_on_long_term_firm_loans")[0])
        )
        additions["policy_rate"] += policy_rate
        additions["policy_rate_annual_equiv"] += float(quarterly_to_annual_effective(policy_rate))
        additions["firm_lending_rate"] += firm_lending_rate
        additions["firm_lending_rate_annual_equiv"] += float(quarterly_to_annual_effective(firm_lending_rate))
        additions["household_lending_rate"] += float(banks.current("average_interest_rates_on_household_consumption_loans")[0])
        additions["firm_deposit_rate"] += float(banks.current("average_interest_rate_on_firm_deposits")[0])
        additions["household_deposit_rate"] += float(banks.current("average_interest_rate_on_household_deposits")[0])
        additions["firm_credit_new"] += (
            float(np.nan_to_num(credit.current("total_newly_loans_granted_firms_short_term")[0], nan=0.0))
            + float(np.nan_to_num(credit.current("total_newly_loans_granted_firms_long_term")[0], nan=0.0))
        ) / 1e9
        additions["firm_credit_outstanding"] += (
            float(credit.current("total_outstanding_loans_granted_firms_short_term")[0])
            + float(credit.current("total_outstanding_loans_granted_firms_long_term")[0])
        ) / 1e9
        additions["household_credit_new"] += (
            float(np.nan_to_num(credit.current("total_newly_loans_granted_households_consumption")[0], nan=0.0))
            + float(np.nan_to_num(credit.current("total_newly_loans_granted_mortgages")[0], nan=0.0))
        ) / 1e9
        additions["household_credit_outstanding"] += (
            float(credit.current("total_outstanding_loans_granted_households_consumption")[0])
            + float(credit.current("total_outstanding_loans_granted_mortgages")[0])
        ) / 1e9
        additions["firm_interest_paid"] += float(np.asarray(country.firms.ts.current("interest_paid"), float).sum()) / 1e9
        additions["household_interest_paid"] += float(np.asarray(country.households.ts.current("interest_paid"), float).sum()) / 1e9
        unemployment_benefits = (
            sum(a.name == "UNEMPLOYED" for a in country.individuals.states["Activity Status"])
            * country.central_government.ts.current("unemployment_benefits_by_individual")[0]
        )
        household_transfers = float(country.households.ts.current("income_social_transfers").sum())
        local_benefits = float(unemployment_benefits) + household_transfers
        additions["government_interest_expense"] += (
            float(country.central_government.ts.current("deficit")[0])
            + float(country.central_government.ts.current("revenue")[0])
            - float(country.government_entities.ts.current("nominal_amount_spent_in_lcu").sum())
            - local_benefits
            - float(country.central_government.ts.current("itc_refunds")[0])
        ) / 1e9
        n += 1
    if n:
        for key in [
            "policy_rate",
            "policy_rate_annual_equiv",
            "firm_lending_rate",
            "firm_lending_rate_annual_equiv",
            "household_lending_rate",
            "firm_deposit_rate",
            "household_deposit_rate",
        ]:
            additions[key] /= n
    out.update(additions)
    out["finite"] = bool(out["finite"]) and all(np.isfinite(v) for v in additions.values())
    return out


def run_case(rule_name: str, q: int, treatment: bool = False) -> pd.DataFrame:
    model, provs = build_model(rule_name=rule_name, q=q, treatment=treatment)
    prices0 = base_prices(model, provs)
    rows = []
    for t in range(q + 1):
        rows.append(
            {
                "rule": rule_name,
                "case": "treatment" if treatment else "control",
                "t": t,
                "year_float": 2022.0 + t / 4.0,
                "policy_active": UC.ACT0 <= t <= UC.ACT1,
                **collect_monetary(model, provs, prices0),
            }
        )
        if t < q:
            if treatment:
                UC.set_policy_active(model, provs, treatment=True, active=UC.ACT0 <= t <= UC.ACT1)
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
        "firm_credit_new",
        "household_credit_new",
        "firm_interest_paid",
        "household_interest_paid",
        "government_interest_expense",
    ]
    stocks = [
        "capital_stock",
        "employment_agents",
        "debt",
        "firm_credit_outstanding",
        "household_credit_outstanding",
    ]
    rates = [
        "unemployment_rate",
        "cpi_inflation",
        "policy_rate",
        "policy_rate_annual_equiv",
        "firm_lending_rate",
        "firm_lending_rate_annual_equiv",
        "household_lending_rate",
        "firm_deposit_rate",
        "household_deposit_rate",
    ]
    out = []
    for (rule, case), group in df.groupby(["rule", "case"], sort=False):
        annual = group.groupby("year")[flows].sum()
        annual[stocks] = group.groupby("year")[stocks].last()
        annual[rates] = group.groupby("year")[rates].mean()
        annual["finite"] = group.groupby("year")["finite"].all()
        annual["rule"] = rule
        annual["case"] = case
        out.append(annual.reset_index())
    return pd.concat(out, ignore_index=True)


def add_growth(annual: pd.DataFrame) -> pd.DataFrame:
    annual = annual.sort_values(["rule", "case", "year"]).copy()
    annual["gva_growth"] = annual.groupby(["rule", "case"])["gva"].pct_change() * 100.0
    return annual


def run_baselines(q: int) -> pd.DataFrame:
    frames = []
    for rule in ["constant", "poledna"]:
        print(f"RUNNING no-ITC baseline: {rule}", flush=True)
        frame = run_case(rule_name=rule, q=q, treatment=False)
        frame.to_csv(OUT / f"monetary_baseline_{rule}_quarterly.csv", index=False)
        frames.append(frame)
        print(f"DONE no-ITC baseline: {rule}", flush=True)
    quarterly = pd.concat(frames, ignore_index=True)
    quarterly.to_csv(OUT / "monetary_baseline_quarterly.csv", index=False)
    annual = add_growth(annualize(quarterly))
    annual.to_csv(OUT / "monetary_baseline_annual.csv", index=False)
    return annual


def run_uc_comparison(q: int) -> pd.DataFrame:
    frames = []
    for rule in ["constant", "poledna"]:
        for treatment in [False, True]:
            print(f"RUNNING UC {rule} {'treatment' if treatment else 'control'}", flush=True)
            frame = run_case(rule_name=rule, q=q, treatment=treatment)
            frame.to_csv(OUT / f"monetary_uc_{rule}_{'treatment' if treatment else 'control'}_quarterly.csv", index=False)
            frames.append(frame)
            print(f"DONE UC {rule} {'treatment' if treatment else 'control'}", flush=True)
    quarterly = pd.concat(frames, ignore_index=True)
    quarterly.to_csv(OUT / "monetary_uc_quarterly.csv", index=False)
    annual = add_growth(annualize(quarterly))
    annual.to_csv(OUT / "monetary_uc_annual.csv", index=False)
    return annual


def summarize_uc(annual: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rule in ["constant", "poledna"]:
        sub = annual[annual.rule == rule]
        for start, end in [(2026, 2030), (2026, 2035)]:
            row = {"rule": rule, "window": f"{start}-{end}", **UC.summarize_delta(sub, start, end)}
            c = sub[(sub.case == "control") & (sub.year >= start) & (sub.year <= end)]
            t = sub[(sub.case == "treatment") & (sub.year >= start) & (sub.year <= end)]
            row["d_firm_credit_new"] = float(t["firm_credit_new"].sum() - c["firm_credit_new"].sum())
            row["d_firm_credit_outstanding_last"] = float(
                t["firm_credit_outstanding"].iloc[-1] - c["firm_credit_outstanding"].iloc[-1]
            )
            row["avg_gva_growth_gap_pp"] = float(t["gva_growth"].mean() - c["gva_growth"].mean())
            row["avg_cpi_inflation_gap_pp"] = float(100.0 * (t["cpi_inflation"].mean() - c["cpi_inflation"].mean()))
            row["avg_policy_rate_gap_pp"] = float(100.0 * (t["policy_rate"].mean() - c["policy_rate"].mean()))
            rows.append(row)
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "monetary_uc_summary.csv", index=False)
    return summary


def print_baseline_tables(annual: pd.DataFrame) -> None:
    cols = [
        "rule",
        "year",
        "cpi_inflation",
        "policy_rate",
        "policy_rate_annual_equiv",
        "firm_lending_rate",
        "firm_lending_rate_annual_equiv",
        "household_deposit_rate",
        "government_interest_expense",
        "gva_growth",
        "unemployment_rate",
        "household_consumption",
        "realized_investment",
        "firm_credit_new",
        "firm_credit_outstanding",
    ]
    table = annual[annual.case == "control"][cols].copy()
    for col in ["cpi_inflation", "policy_rate", "firm_lending_rate", "household_deposit_rate", "unemployment_rate"]:
        table[col] *= 100.0
    print("NO_ITC_BASELINE_ANNUAL")
    print(table.to_csv(index=False, float_format="%.6f"))


def print_uc_tables(annual: pd.DataFrame, summary: pd.DataFrame) -> None:
    rows = []
    for rule in ["constant", "poledna"]:
        sub = annual[annual.rule == rule]
        c = sub[sub.case == "control"].set_index("year")
        t = sub[sub.case == "treatment"].set_index("year")
        for year in range(2026, 2036):
            rows.append(
                {
                    "rule": rule,
                    "year": year,
                    "gva_growth_gap_pp": t.loc[year, "gva_growth"] - c.loc[year, "gva_growth"],
                    "cpi_inflation_gap_pp": 100.0 * (t.loc[year, "cpi_inflation"] - c.loc[year, "cpi_inflation"]),
                    "policy_rate_gap_pp": 100.0 * (t.loc[year, "policy_rate"] - c.loc[year, "policy_rate"]),
                }
            )
    print("UC_ANNUAL_GAPS")
    print(pd.DataFrame(rows).to_csv(index=False, float_format="%.6f"))
    keep = [
        "rule",
        "window",
        "d_realized_investment",
        "d_gva",
        "d_household_consumption",
        "d_employment_agents_2030",
        "d_employment_agents_2035",
        "d_unemployment_rate_pp_2030",
        "d_unemployment_rate_pp_2035",
        "d_imports",
        "gross_itc_refunds",
        "d_tax_revenue",
        "d_deficit",
        "d_debt_2030",
        "d_debt_2035",
        "avg_gva_growth_gap_pp",
        "avg_cpi_inflation_gap_pp",
        "avg_policy_rate_gap_pp",
        "stable",
    ]
    keep = [c for c in keep if c in summary.columns]
    print("UC_SUMMARY")
    print(summary[keep].to_csv(index=False, float_format="%.6f"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "uc", "all", "summarize"], default="all")
    parser.add_argument("--q", type=int, default=Q)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode in {"baseline", "all"}:
        baseline = run_baselines(args.q)
        print_baseline_tables(baseline)
    if args.mode in {"uc", "all"}:
        uc = run_uc_comparison(args.q)
        summary = summarize_uc(uc)
        print_uc_tables(uc, summary)
    if args.mode == "summarize":
        baseline_path = OUT / "monetary_baseline_quarterly.csv"
        uc_path = OUT / "monetary_uc_quarterly.csv"
        if baseline_path.exists():
            baseline = add_growth(annualize(pd.read_csv(baseline_path)))
            baseline.to_csv(OUT / "monetary_baseline_annual.csv", index=False)
            print_baseline_tables(baseline)
        if uc_path.exists():
            uc = add_growth(annualize(pd.read_csv(uc_path)))
            uc.to_csv(OUT / "monetary_uc_annual.csv", index=False)
            summary = summarize_uc(uc)
            print_uc_tables(uc, summary)


if __name__ == "__main__":
    main()
