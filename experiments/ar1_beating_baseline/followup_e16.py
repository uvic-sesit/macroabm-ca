"""Focused E16 ablation and one-seed ITC propagation diagnostic."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "outputs" / "e16_followup"
NUMBA_CACHE = Path(tempfile.gettempdir()) / "macroabm_forecast_numba_cache"
NUMBA_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(NUMBA_CACHE))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "experiments" / "itc_endogenous_closure"))
sys.path.insert(0, str(REPO / "dev" / "validation"))

import evaluate_experiments as evaluate
import run_batch
import run_historical_experiment as historical
import closure_feedback_exp as closure
import provincial_validation_2022 as provincial
import run_uc_closure_comparison as uc


SEEDS = (0, 1, 2)
Q_HIST = 13
Q_ITC = 55

# The isolated clone contains the frozen model pickle and validation inputs but
# not the full raw OECD/World Bank bundle loaded by the richer fiscal closure.
# Read those inputs from the original repository without importing or modifying
# any of its code or outputs.
READ_ONLY_DATA_REPO = REPO.parent / "macroabm-ca"
closure.DATA_REPO = READ_ONLY_DATA_REPO


def base_spec() -> dict:
    return {
        "description": "Frozen candidate baseline",
        "demand_smoothing": 0.3,
        "firm_growth_adjustment_speed": 1.0,
        "sectoral_growth_adjustment_speed": 1.0,
        "unmet_demand_weight": 0.25,
        "excess_demand_consider_capital_inputs": 0.0,
        "rolling_reference": True,
        "target_capital_inputs_fraction": 0.1,
        "credit_gap_fraction": 0.0,
        "labour_force_path": "observed_annual_interpolated",
        "final_demand_path": "observed_provincial_annual_blocks",
    }


def ablation_specs() -> list[tuple[str, str, dict]]:
    baseline = base_spec()
    smooth = {**baseline, "description": "E16 smoothing backbone", "demand_smoothing": 1.0}
    change1 = {
        **smooth,
        "description": "Change 1: annual labour-force levels in calendar-year blocks",
        "labour_force_path": "observed_annual_blocks",
    }
    change12 = {
        **change1,
        "description": "Changes 1+2: establish labour force before matching",
        "labour_force_update_before_markets": True,
    }
    change123 = {
        **change12,
        "description": "Changes 1+2+3: remove capital pre-clamp from labour plans",
        "desired_labour": {"consider_capital_inputs": 0.0},
    }
    full = {
        **change123,
        "description": "Full E16: also remove capital pre-clamp from intermediate plans",
        "target_production": {"intermediate_inputs_target_considers_capital_inputs": 0.0},
    }
    return [
        ("ABL00_baseline", "Baseline", baseline),
        ("ABL0_smoothing", "Smoothing 1.0 only", smooth),
        ("ABL1_change1", "Change 1 only", change1),
        ("ABL2_change12", "Changes 1+2", change12),
        ("ABL3_change123", "Changes 1+2+3", change123),
        ("ABL4_full_e16", "Full E16", full),
    ]


def run_ablation() -> None:
    data = historical.DataWrapper.init_from_pickle(historical.PKL)
    for experiment_id, _, spec in ablation_specs():
        for seed in SEEDS:
            path = historical.DEFAULT_OUT / experiment_id / f"seed{seed:03d}" / "national_quarterly.csv"
            if not path.exists():
                print(f"RUN {experiment_id} seed={seed}", flush=True)
                run_batch.run_seed(data, spec, experiment_id, seed, Q_HIST, historical.DEFAULT_OUT)
    official = pd.read_csv(evaluate.OFFICIAL)
    rows = []
    for experiment_id, label, _ in ablation_specs():
        model, n_seeds = evaluate.load_experiment(experiment_id)
        merged = official.merge(model, on="quarter", how="left")
        gva_rmse, _ = evaluate.metrics(
            merged.iloc[1:]["real_gva_growth_realized"], merged.iloc[1:]["model_gva_growth"]
        )
        unemployment_rmse, _ = evaluate.metrics(
            merged["unemployment_rate_realized"], merged["unemployment_rate"]
        )
        rows.append(
            {
                "specification": label,
                "experiment_id": experiment_id,
                "seeds": n_seeds,
                "gva_rmse": gva_rmse,
                "unemployment_rmse": unemployment_rmse,
            }
        )
    OUT.mkdir(parents=True, exist_ok=True)
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "e16_ablation_metrics.csv", index=False)
    print(result.to_string(index=False))


def apply_e16(model, provs) -> None:
    """Apply E16 planning/timing changes without changing the closure or UC rule."""
    model.configuration.labour_force_update_before_markets = True
    paths = historical.labour_index_2022(Q_ITC, "observed_annual_blocks")
    for c in provs:
        country = model.countries[c]
        country.individuals.functions["demography"].labour_force_index = paths[str(c)]
        country.firms.functions["demand_estimator"].demand_smoothing = 1.0
        country.firms.functions["desired_labour"].consider_capital_inputs = 0.0
        country.firms.functions[
            "target_production"
        ].intermediate_inputs_target_considers_capital_inputs = 0.0


def build_e16(treatment: bool):
    model, provs = closure.build_closure_model(
        q=Q_ITC,
        seed=0,
        price_dp=0.05,
        itc_rate=0.0,
        eligible_indices=closure.ELIGIBLE_INDICES,
        household_investment="exogenous",
        government_consumption="exogenous",
    )
    apply_e16(model, provs)
    uc.set_uc_params(model, provs, treatment=treatment)
    return model, provs


def install_recorder(model, provs):
    cache = {str(c): [] for c in provs}
    for c in provs:
        firms = model.countries[c].firms
        original = firms.compute_estimated_demand
        key = str(c)

        def record(current_estimated_growth, _firms=firms, _original=original, _key=key):
            cache[_key].append(np.array(_firms.ts.current("demand"), float))
            return _original(current_estimated_growth=current_estimated_growth)

        firms.compute_estimated_demand = record
    return cache


def install_no_b(model, provs, cache) -> None:
    """Replay control own-demand memory only inside firm expectation formation."""
    counters = {str(c): [0] for c in provs}
    for c in provs:
        firms = model.countries[c].firms
        key = str(c)

        def growth_by_firm(
            previous_average_good_prices,
            min_growth=-0.2,
            max_growth=0.2,
            _firms=firms,
            _key=key,
        ):
            if len(_firms.ts.historic("inventory")) == 1:
                previous_supply = _firms.ts.current("production") + _firms.ts.current("inventory")
            else:
                previous_supply = _firms.ts.current("production") + _firms.ts.prev("inventory")
            k = counters[_key][0]
            growth = _firms.functions["growth_estimator"].compute_growth(
                prev_average_good_prices=previous_average_good_prices,
                prev_firm_prices=_firms.ts.current("price"),
                prev_supply=previous_supply,
                prev_demand=cache[_key][k],
                current_firm_sectors=_firms.states["Industry"],
            )
            return np.maximum(min_growth, np.minimum(max_growth, growth))

        def estimated_demand(current_estimated_growth, _firms=firms, _key=key):
            k = counters[_key][0]
            result = _firms.functions["demand_estimator"].compute_estimated_demand(
                previous_demand=cache[_key][k],
                current_estimated_growth=current_estimated_growth,
                estimated_growth_by_firm=_firms.ts.current("estimated_growth_by_firm"),
            )
            counters[_key][0] += 1
            return result

        firms.compute_estimated_growth_by_firm = growth_by_firm
        firms.compute_estimated_demand = estimated_demand


def run_e16_case(case: str, cache=None):
    treatment = case != "control"
    model, provs = build_e16(treatment=treatment)
    recorded = install_recorder(model, provs) if case == "control" else None
    if case == "no_b":
        install_no_b(model, provs, cache)
    base_prices = {
        c: np.asarray(model.countries[c].economy.ts.current("good_prices"), float).reshape(-1)
        for c in provs
    }
    rows = []
    for t in range(Q_ITC + 1):
        rows.append(
            {
                "case": case,
                "t": t,
                "year_float": 2022.0 + t / 4.0,
                "policy_active": treatment and uc.ACT0 <= t <= uc.ACT1,
                **uc.collect(model, provs, base_prices),
            }
        )
        if t < Q_ITC:
            if treatment:
                uc.set_policy_active(model, provs, treatment=True, active=uc.ACT0 <= t <= uc.ACT1)
            model.iterate(t)
    return pd.DataFrame(rows), recorded


def window_delta(treatment: pd.DataFrame, control: pd.DataFrame, start: int, end: int) -> dict:
    treatment = treatment.assign(year=np.floor(treatment.year_float).astype(int))
    control = control.assign(year=np.floor(control.year_float).astype(int))
    t = treatment[(treatment.year >= start) & (treatment.year <= end)]
    c = control[(control.year >= start) & (control.year <= end)]
    flows = [
        "desired_investment",
        "realized_investment",
        "realized_production",
        "gva",
        "household_consumption",
        "imports",
        "itc_refunds",
    ]
    result = {f"d_{name}": float(t[name].sum() - c[name].sum()) for name in flows}
    last_t = t[t.year == end].iloc[-1]
    last_c = c[c.year == end].iloc[-1]
    result["d_employment_agents_end"] = float(last_t.employment_agents - last_c.employment_agents)
    result["d_capital_stock_end"] = float(last_t.capital_stock - last_c.capital_stock)
    result["d_unemployment_rate_pp_end"] = float(
        100.0 * (last_t.unemployment_rate - last_c.unemployment_rate)
    )
    return result


def original_summary() -> pd.DataFrame:
    path = (
        REPO.parent
        / "macroabm-ca-itc-monetary-diagnostic"
        / "experiments/itc_monetary_diagnostic/results/final_richer_uc_constant_summary.csv"
    )
    source = pd.read_csv(path)
    rows = []
    for window in ("2026-2030", "2026-2035"):
        row = source[source.window == window].iloc[0]
        rows.append(
            {
                "baseline": "Original policy baseline",
                "case": "full",
                "window": window,
                "d_desired_investment": row.d_desired_investment,
                "d_realized_investment": row.d_realized_investment,
                "d_realized_production": row.d_realized_production,
                "d_gva": row.d_gva,
                "d_household_consumption": row.d_household_consumption,
                "d_imports": row.d_imports,
                "d_itc_refunds": row.gross_itc_refunds,
                "d_capital_stock_end": row.d_capital_stock_end,
                "d_employment_agents_end": row.d_employment_agents_end,
                "d_unemployment_rate_pp_end": row.d_unemployment_pp_end,
            }
        )
    return pd.DataFrame(rows)


def run_itc() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = {}
    cache = None
    for case in ("control", "full", "no_b"):
        print(f"RUN E16 ITC {case}", flush=True)
        frame, recorded = run_e16_case(case, cache=cache)
        frame.to_csv(OUT / f"e16_itc_{case}_quarterly.csv", index=False)
        frames[case] = frame
        if recorded is not None:
            cache = recorded
        print(f"DONE E16 ITC {case}", flush=True)
    rows = []
    for start, end in ((2026, 2030), (2026, 2035), (2031, 2035)):
        for case in ("full", "no_b"):
            rows.append(
                {
                    "baseline": "E16",
                    "case": case,
                    "window": f"{start}-{end}",
                    **window_delta(frames[case], frames["control"], start, end),
                }
            )
    summary = pd.concat([original_summary(), pd.DataFrame(rows)], ignore_index=True)
    summary.to_csv(OUT / "e16_itc_comparison.csv", index=False)
    print(summary.to_string(index=False))


def summarize_existing_itc() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = {
        case: pd.read_csv(OUT / f"e16_itc_{case}_quarterly.csv")
        for case in ("control", "full", "no_b")
    }
    rows = []
    for start, end in ((2026, 2030), (2026, 2035), (2031, 2035)):
        for case in ("full", "no_b"):
            rows.append(
                {
                    "baseline": "E16",
                    "case": case,
                    "window": f"{start}-{end}",
                    **window_delta(frames[case], frames["control"], start, end),
                }
            )
    summary = pd.concat([original_summary(), pd.DataFrame(rows)], ignore_index=True)
    summary.to_csv(OUT / "e16_itc_comparison.csv", index=False)

    original_control_path = (
        REPO.parent
        / "macroabm-ca-itc-monetary-diagnostic"
        / "experiments/itc_monetary_diagnostic/results/final_richer_uc_constant_control_quarterly.csv"
    )
    original_control = pd.read_csv(original_control_path)
    e16_control = frames["control"]
    level_rows = []
    for label, frame in (("Original policy baseline", original_control), ("E16", e16_control)):
        frame = frame.assign(year=np.floor(frame.year_float).astype(int))
        active = frame[(frame.year >= 2026) & (frame.year <= 2030)]
        last = active[active.year == 2030].iloc[-1]
        level_rows.append(
            {
                "baseline": label,
                "realized_investment_2026_30": active.realized_investment.sum(),
                "production_2026_30": active.realized_production.sum(),
                "gva_2026_30": active.gva.sum(),
                "household_consumption_2026_30": active.household_consumption.sum(),
                "imports_2026_30": active.imports.sum(),
                "capital_stock_2030": last.capital_stock,
                "employment_agents_2030": last.employment_agents,
                "unemployment_rate_2030": last.unemployment_rate,
            }
        )
    levels = pd.DataFrame(level_rows)
    levels.to_csv(OUT / "baseline_level_comparison.csv", index=False)
    print(summary.to_string(index=False))
    print("\nBASELINE LEVELS")
    print(levels.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["ablation", "itc", "summarize_itc", "all"])
    args = parser.parse_args()
    if args.mode in {"ablation", "all"}:
        run_ablation()
    if args.mode in {"itc", "all"}:
        run_itc()
    if args.mode == "summarize_itc":
        summarize_existing_itc()


if __name__ == "__main__":
    main()
