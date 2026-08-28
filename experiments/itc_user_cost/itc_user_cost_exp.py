"""User-cost ITC experiment for the frozen 2022 Canadian baseline.

Alternative to the working-paper desired-scale bridge. This keeps target
production unchanged and activates a reduced-form user-cost response in
FinancialTargetCapitalInputsSetter:

    K*_ijt = K*_base,ijt * (1 - tau * s_i,t-1) ** (-eta_K)

where s_i,t-1 is the value share of C27/C28 in the previous planned capital
bundle. The wedge is active only over 2026-2030. Fiscal cost is reported as an
implied claim on realized eligible capital purchases; it is not transferred
through government accounts in this harness.

Usage:
    uv run python experiments/itc_user_cost/itc_user_cost_exp.py smoke
    uv run python experiments/itc_user_cost/itc_user_cost_exp.py long
    uv run python experiments/itc_user_cost/itc_user_cost_exp.py design_a_long
    uv run python experiments/itc_user_cost/itc_user_cost_exp.py design_b_long 0.50
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "dev" / "io2022"))
sys.path.insert(0, str(REPO / "dev" / "validation"))

import provincial_validation_2022 as P
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from save_baseline_2022 import build_config


OUT = REPO / "dev" / "validation" / "prov_2022"
Q_SMOKE = 20
Q_LONG = 55
PROJ_START = 16
ACT0, ACT1 = 16, 35
TAU = 0.30
ETA_K = 1.0
E_K = [P.SECTOR_CODES.index("C27"), P.SECTOR_CODES.index("C28")]
GC = GG = GI = 0.02
GL = 0.01
GX = 0.02
DESIGNS = {
    "design_b": {
        "mode": "lagged_share_all",
        "equation": "K*_ijt = K*_base,ijt * (1 - tau * s_i,t-1)^(-eta_K)",
        "description": "whole-bundle scaling by lagged value-based eligible share",
    },
    "design_a": {
        "mode": "eligible_goods_only",
        "equation": "K*_ijt = K*_base,ijt * (1 - tau)^(-eta_K) for j in {C27,C28}; unchanged otherwise",
        "description": "eligible-goods-only desired capital response",
    },
}


def _qf(n: int, g: float) -> np.ndarray:
    f = np.ones(n)
    for t in range(PROJ_START, n):
        f[t] = (1.0 + g) ** ((t - (PROJ_START - 1)) / 4.0)
    return f


def build_model(q: int, treatment: bool, design: str = "design_b", eta_k: float = ETA_K):
    P.Q = q
    orig_e_matrix = P._E_matrix
    P._E_matrix = lambda ok: orig_e_matrix(ok) * _qf(orig_e_matrix(ok).shape[0], GX)[:, None, None]
    try:
        data = DataWrapper.init_from_pickle(P.PKL)
        provs, cfg = build_config(data, 0, q)
        P.configure(cfg, provs, True)
        if treatment:
            for c in provs:
                params = cfg.country_configurations[c].firms.functions.target_capital_inputs.parameters
                params.update(
                    {
                        "itc_user_cost_eta": eta_k,
                        "itc_user_cost_eligible_indices": E_K,
                        "itc_user_cost_mode": DESIGNS[design]["mode"],
                    }
                )
        model = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=cfg)
        P.post_build(model, provs, "candidate_prov")
        for c in provs:
            frame = model.countries[c].exogenous.national_accounts_during
            n = len(frame)
            for col, g in (
                [(x, GC) for x in P.HHC_COLS]
                + [(x, GI) for x in P.HHI_COLS]
                + [(x, GG) for x in P.GOV_COLS]
            ):
                if col in frame.columns:
                    frame[col] = frame[col].values * _qf(n, g)
            model.countries[c].exogenous.national_accounts_during = frame
            dem = model.countries[c].individuals.functions["demography"]
            labour_force = np.asarray(dem.labour_force_index, float)
            dem.labour_force_index = list(labour_force * _qf(len(labour_force), GL))
        P.install_external_demand(model, provs)
    finally:
        P._E_matrix = orig_e_matrix
        P.Q = 13
    return model, provs


def set_policy_rate(model, provs, active: bool) -> None:
    rate = TAU if active else 0.0
    for c in provs:
        model.countries[c].firms.functions["target_capital_inputs"].itc_user_cost_rate = rate


def collect(model, provs, p0, policy_active: bool, eta_k: float = ETA_K):
    totals = {
        "eligible_purchases": 0.0,
        "fiscal_cost": 0.0,
        "desired_eligible_capital": 0.0,
        "desired_noneligible_capital": 0.0,
        "realized_eligible_investment": 0.0,
        "realized_noneligible_investment": 0.0,
        "desired_capital": 0.0,
        "realized_investment": 0.0,
        "capital_limited_capacity": 0.0,
        "capital_stock": 0.0,
        "target_production": 0.0,
        "production": 0.0,
        "gva": 0.0,
        "employment": 0.0,
        "imports": 0.0,
        "investment_multiplier_median": 1.0,
        "investment_multiplier_mean": 1.0,
        "investment_multiplier_p90": 1.0,
    }
    multipliers = []
    for c in provs:
        if str(c) not in P.PROV10:
            continue
        country = model.countries[c]
        fg = country.firms
        econ = country.economy.ts
        prices = np.asarray(econ.current("good_prices"), float).reshape(-1)
        base_prices = p0[c]
        desired_capital = np.asarray(fg.ts.current("unconstrained_target_capital_inputs"), float).reshape(-1, 50)
        realized_capital = np.asarray(fg.ts.current("real_amount_bought_as_capital_goods"), float).reshape(-1, 50)
        capital_stock = np.asarray(fg.ts.current("capital_inputs_stock"), float).reshape(-1, 50)
        target_production = np.asarray(fg.ts.current("target_production"), float).reshape(-1)
        production = np.asarray(fg.ts.current("production"), float).reshape(-1)
        used_intermediate = np.asarray(fg.ts.current("used_intermediate_inputs"), float)
        firm_sector_prices = base_prices[fg.states["Industry"]]
        eligible_purchases = float((realized_capital[:, E_K] * prices[E_K][None, :]).sum()) / 1e9
        desired_eligible = float((desired_capital[:, E_K] * prices[E_K][None, :]).sum()) / 1e9
        desired_total = float((desired_capital * prices[None, :]).sum()) / 1e9
        realized_total = float((realized_capital * prices[None, :]).sum()) / 1e9
        totals["eligible_purchases"] += eligible_purchases
        totals["desired_eligible_capital"] += desired_eligible
        totals["desired_noneligible_capital"] += desired_total - desired_eligible
        totals["realized_eligible_investment"] += eligible_purchases
        totals["realized_noneligible_investment"] += realized_total - eligible_purchases
        if policy_active:
            totals["fiscal_cost"] += TAU * eligible_purchases
        totals["desired_capital"] += desired_total
        totals["realized_investment"] += realized_total
        totals["capital_stock"] += float((capital_stock * prices[None, :]).sum()) / 1e9
        limiting_capital = np.asarray(fg.ts.current("limiting_capital_inputs"), float).reshape(-1)
        finite_limiting_capital = np.where(np.isfinite(limiting_capital), limiting_capital, 0.0)
        totals["capital_limited_capacity"] += float((finite_limiting_capital * firm_sector_prices).sum()) / 1e9
        totals["target_production"] += float((target_production * firm_sector_prices).sum()) / 1e9
        totals["production"] += float((production * firm_sector_prices).sum()) / 1e9
        totals["gva"] += (
            float((production * firm_sector_prices).sum())
            - (float((used_intermediate * base_prices[None, :]).sum()) if used_intermediate.ndim == 2 else 0.0)
        ) / 1e9
        status = np.asarray([a.name for a in country.individuals.states["Activity Status"]])
        totals["employment"] += float((status == "EMPLOYED").sum())
        row_purchases = np.asarray(fg.ts.current("real_amount_bought_from_ROW"), float).reshape(-1, 50)
        totals["imports"] += float((row_purchases * prices[None, :]).sum()) / 1e9
        lagged_planned = np.asarray(fg.ts.current("unconstrained_target_capital_inputs"), float).reshape(-1, 50)
        lagged_values = lagged_planned * prices[None, :]
        lagged_total = lagged_values.sum(axis=1)
        lagged_eligible = lagged_values[:, E_K].sum(axis=1)
        eligible_share = np.divide(
            lagged_eligible,
            lagged_total,
            out=np.zeros_like(lagged_total),
            where=lagged_total > 0.0,
        )
        rate = TAU if policy_active else 0.0
        multipliers.extend((1.0 - rate * eligible_share) ** (-eta_k))
    multipliers = np.asarray(multipliers, float)
    if multipliers.size:
        totals["investment_multiplier_median"] = float(np.median(multipliers))
        totals["investment_multiplier_mean"] = float(np.mean(multipliers))
        totals["investment_multiplier_p90"] = float(np.percentile(multipliers, 90))
    return totals


def run_case(q: int, treatment: bool, design: str = "design_b", eta_k: float = ETA_K):
    model, provs = build_model(q, treatment, design=design, eta_k=eta_k)
    p0 = {c: np.asarray(model.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}
    rows = []
    for t in range(q + 1):
        policy_active = treatment and ACT0 <= t <= ACT1
        rows.append(collect(model, provs, p0, policy_active=policy_active, eta_k=eta_k))
        if t < q:
            set_policy_rate(model, provs, treatment and ACT0 <= t <= ACT1)
            model.iterate(t)
    return {k: np.asarray([r[k] for r in rows], float) for k in rows[0]}


def _quarter_to_year(t: int) -> float:
    return 2022.0 + t / 4.0


def save_audit(
    control: dict[str, np.ndarray], treatment: dict[str, np.ndarray], q: int, design: str, eta_k: float
) -> tuple[Path, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    annual_records = []
    for t in range(q + 1):
        for case_name, data in [("control", control), ("treatment", treatment)]:
            row = {"t": t, "year": _quarter_to_year(t), "case": case_name}
            row.update({k: float(v[t]) for k, v in data.items()})
            records.append(row)
    quarterly = pd.DataFrame.from_records(records)
    suffix = f"{design}_eta{int(round(eta_k * 100)):03d}"
    quarterly_path = OUT / f"itc_user_cost_{suffix}_quarterly_audit.csv"
    quarterly.to_csv(quarterly_path, index=False)
    for year in range(2022, int(_quarter_to_year(q)) + 1):
        year_rows = quarterly[(quarterly["year"] >= year) & (quarterly["year"] < year + 1)]
        if year_rows.empty:
            continue
        for case_name in ["control", "treatment"]:
            subset = year_rows[year_rows["case"] == case_name]
            row = {"year": year, "case": case_name}
            for key in control:
                if key in {"capital_stock", "capital_limited_capacity", "employment"}:
                    row[key] = float(subset[key].iloc[-1])
                else:
                    row[key] = float(subset[key].sum())
            annual_records.append(row)
    annual = pd.DataFrame.from_records(annual_records)
    annual_path = OUT / f"itc_user_cost_{suffix}_annual_audit.csv"
    annual.to_csv(annual_path, index=False)
    np.savez(
        OUT / f"itc_user_cost_{suffix}_audit_arrays.npz",
        **{f"control_{k}": v for k, v in control.items()},
        **{f"treatment_{k}": v for k, v in treatment.items()},
    )
    return quarterly_path, annual_path


def report(q: int, design: str = "design_b", eta_k: float = ETA_K):
    print(
        f"Running {design} matched control/treatment, q={q}, tau={TAU:.2f}, eta_K={eta_k:.2f}"
    )
    control = run_case(q, False, design=design, eta_k=eta_k)
    treatment = run_case(q, True, design=design, eta_k=eta_k)
    quarterly_path, annual_path = save_audit(control, treatment, q, design=design, eta_k=eta_k)
    years = [2026, 2030, 2035] if q >= 55 else [2026]
    idx = {2026: 16, 2030: 32, 2035: 52}
    print(f"\nEquation: {DESIGNS[design]['equation']}")
    print(DESIGNS[design]["description"])
    print("\nDirect investment multiplier diagnostics, treatment:")
    for year in [2026, 2030]:
        if idx[year] <= q:
            print(
                f"  {year}: median={treatment['investment_multiplier_median'][idx[year]]:.4f} "
                f"mean={treatment['investment_multiplier_mean'][idx[year]]:.4f} "
                f"p90={treatment['investment_multiplier_p90'][idx[year]]:.4f}"
            )
    print("\nTreatment - control deltas ($B except employment in model agents):")
    for year in years:
        if idx[year] > q:
            continue
        print(f"\n{year}")
        for key in [
            "eligible_purchases",
            "fiscal_cost",
            "desired_capital",
            "realized_investment",
            "capital_limited_capacity",
            "capital_stock",
            "target_production",
            "production",
            "gva",
            "employment",
            "imports",
        ]:
            delta = treatment[key][idx[year]] - control[key][idx[year]]
            label = key.replace("_", " ")
            print(f"  {label:22s} {delta:+12.4f}")
    active_slice = slice(ACT0, min(ACT1 + 1, q + 1))
    treat_eligible = treatment["eligible_purchases"][active_slice].sum()
    control_eligible = control["eligible_purchases"][active_slice].sum()
    incremental_eligible = treat_eligible - control_eligible
    treatment_fiscal = treatment["fiscal_cost"][active_slice].sum()
    additionality = incremental_eligible / treat_eligible if treat_eligible > 0 else np.nan
    print("\nActive-window eligible purchases and fiscal cost, 2026-2030 ($B):")
    print(f"  treatment eligible purchases {treat_eligible:+12.4f}")
    print(f"  control eligible purchases   {control_eligible:+12.4f}")
    print(f"  incremental eligible purch.  {incremental_eligible:+12.4f}")
    print(f"  treatment fiscal cost        {treatment_fiscal:+12.4f}")
    print(f"  additionality ratio          {additionality:+12.4f}")
    print("\nCumulative active-window treatment-control deltas:")
    for key in [
        "desired_capital",
        "realized_investment",
        "target_production",
        "production",
        "gva",
        "imports",
    ]:
        delta = treatment[key][active_slice].sum() - control[key][active_slice].sum()
        print(f"  {key.replace('_', ' '):22s} {delta:+12.4f}")
    print("\nAdditional investment decomposition, 2026-2030 ($B):")
    for key in [
        "desired_eligible_capital",
        "desired_noneligible_capital",
        "realized_eligible_investment",
        "realized_noneligible_investment",
    ]:
        delta = treatment[key][active_slice].sum() - control[key][active_slice].sum()
        print(f"  {key.replace('_', ' '):30s} {delta:+12.4f}")
    print(f"\nSaved audit files:\n  {quarterly_path}\n  {annual_path}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    eta_k = float(sys.argv[2]) if len(sys.argv) > 2 else ETA_K
    if mode == "smoke":
        report(Q_SMOKE, "design_b", eta_k=eta_k)
    elif mode == "long":
        report(Q_LONG, "design_b", eta_k=eta_k)
    elif mode == "design_a_smoke":
        report(Q_SMOKE, "design_a", eta_k=eta_k)
    elif mode == "design_a_long":
        report(Q_LONG, "design_a", eta_k=eta_k)
    elif mode == "design_b_long":
        report(Q_LONG, "design_b", eta_k=eta_k)
    else:
        raise SystemExit("Use: smoke, long, design_a_smoke, design_a_long, or design_b_long")


if __name__ == "__main__":
    main()
