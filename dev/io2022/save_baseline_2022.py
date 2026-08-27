"""Save-enabled twin of `run_simple_baseline_2022.py`.

Produces ONE canonical h5 artifact for the accepted 2022 shipped-default baseline, for
consumption by the (not-yet-adapted) validation battery / drift diagnostics.

The configuration is byte-for-byte identical to `run_simple_baseline_2022.py`:
  - same pickle (default `io2022_13prov_2022.pkl`, override with IO2022_PKL)
  - pure `CountryConfiguration.n_industry_default` (NO ExogenousGovernmentConsumptionSetter,
    NO growth overlays, NO ExogenousLabourForcePath, NO TFP / demand-growth / capital setters)
  - all `CAN_*` regions discovered from the pickle (13 regions)
  - seed 0, t_max = --quarters (default 13)
  - `model.run()` is exactly the same iterate loop the sibling script runs.

The ONLY additions over the sibling script are:
  1. `model.save(...)` after the run (existing built-in h5 infrastructure, not new serialization);
  2. a reopen/verify block: dims, NaN/inf, and saved-vs-in-memory headline agreement,
     read back through the battery's own `h5_extract` to prove compatibility.

No model behaviour is changed. Nothing is committed.

    uv run python dev/io2022/save_baseline_2022.py --quarters 13
    uv run python dev/io2022/save_baseline_2022.py --quarters 2   # smoke
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.simulation import Simulation

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PKL = REPO / "dev" / "pkl_files" / "io2022_13prov_2022.pkl"
DEFAULT_OUT = REPO / "dev" / "validation" / "baseline_2022"

# import the battery's own extractor to prove h5 compatibility (task F)
BATTERY_DIR = REPO / "dev" / "validation" / "battery"
sys.path.insert(0, str(BATTERY_DIR))
import h5_extract  # noqa: E402


def build_config(d: DataWrapper, seed: int, quarters: int):
    """EXACTLY the configuration built by run_simple_baseline_2022.py."""
    provs = [c for c in d.all_country_names if str(c).startswith("CAN_")]
    cfg = SimulationConfiguration(
        seed=seed,
        country_configurations={
            c: CountryConfiguration.n_industry_default(n_industries=d.n_industries) for c in provs
        },
        t_max=quarters,
    )
    return provs, cfg


def real_gva_current(m: Simulation, country: str, p0: np.ndarray) -> float:
    """Double-deflated real GVA (B$) from the CURRENT in-memory state, as in the sibling script."""
    f = m.countries[country].firms
    q = np.array(f.ts.current("production"), float)
    u = np.array(f.ts.current("used_intermediate_inputs"), float)
    gross = float((q * p0).sum())
    inter = float((u * p0[None, :]).sum()) if u.ndim == 2 else 0.0
    return (gross - inter) / 1e9


def unemployment_current(m: Simulation, provs) -> float:
    return float(
        np.mean(
            [np.array(m.countries[c].economy.ts.current("unemployment_rate"), float).reshape(-1)[0] for c in provs]
        )
    ) * 100.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", type=int, default=13)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pickle", type=Path, default=Path(os.environ.get("IO2022_PKL", str(DEFAULT_PKL))))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--h5-name", type=str, default=None)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    h5_name = args.h5_name or f"baseline_2022_simple_default_seed{args.seed}_{args.quarters}q.h5"
    h5_path = args.out / h5_name

    d = DataWrapper.init_from_pickle(args.pickle)
    provs, cfg = build_config(d, args.seed, args.quarters)
    m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)

    # base-year good prices for double deflation (captured at t0, as in the sibling script)
    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}

    g_start = sum(real_gva_current(m, c, p0[c]) for c in provs)
    u_start = unemployment_current(m, provs)
    prov_start = {c: real_gva_current(m, c, p0[c]) for c in provs}

    # same iterate loop + in-loop NaN scan as run_simple_baseline_2022.py
    non_finite = 0
    for t in range(args.quarters):
        m.iterate(t)
        for c in provs:
            for field in ("production", "used_intermediate_inputs", "labour_inputs"):
                arr = np.asarray(m.countries[c].firms.ts.current(field), float)
                non_finite += int(np.sum(~np.isfinite(arr)))

    g_end = sum(real_gva_current(m, c, p0[c]) for c in provs)
    u_end = unemployment_current(m, provs)
    prov_end = {c: real_gva_current(m, c, p0[c]) for c in provs}
    collapsed = [str(c) for c in provs if prov_end[c] < 0.05 * max(prov_start[c], 1e-9)]

    print(f"\n=== 2022 SIMPLE/DEFAULT baseline (SAVE) | {len(provs)} regions | seed {args.seed} | {args.quarters}q ===")
    print(f"  real GVA (double-deflated): {g_start:.1f}B -> {g_end:.1f}B  ({(g_end / g_start - 1) * 100:+.1f}%)")
    print(f"  unemployment: {u_start:.1f}% -> {u_end:.1f}%")
    print(f"  NaN/inf over run (in-memory scan): {non_finite}")
    print(f"  catastrophic small-region collapse (end<5% of start): {collapsed if collapsed else 'none'}")

    # --- SAVE (existing built-in infrastructure) ---
    m.save(save_dir=args.out, file_name=h5_name)
    size_gb = h5_path.stat().st_size / 1e9
    print(f"\n  saved -> {h5_path}  ({size_gb:.2f} GB)")

    # --- REOPEN + VERIFY (read back through the battery's own h5_extract) ---
    print("\n  --- verification (via battery/h5_extract) ---")
    problems = []
    with h5_extract.open_run(h5_path) as h5:
        region_keys = [str(c) for c in provs]
        # dimension + presence checks
        for c in region_keys:
            for grp in ("economy", "firms"):
                if f"{c}/{grp}" not in h5:
                    problems.append(f"missing group {c}/{grp}")
        # saved 3-way GDP identity components + real-GVA inputs must be present & finite
        needed_econ = ["gdp_output", "gdp_income", "gdp_expenditure", "initial_price", "good_prices"]
        needed_firms = ["production", "used_intermediate_inputs", "labour_inputs"]
        nan_saved = 0
        for c in region_keys:
            for name in needed_econ:
                key = f"{c}/economy/{name}"
                if key not in h5:
                    problems.append(f"missing {key}")
                    continue
                nan_saved += int(np.sum(~np.isfinite(np.asarray(h5[key][()], float))))
            for name in needed_firms:
                key = f"{c}/firms/{name}"
                if key not in h5:
                    problems.append(f"missing {key}")
                    continue
                nan_saved += int(np.sum(~np.isfinite(np.asarray(h5[key][()], float))))

        # saved headline: recompute real GVA + unemployment at the LAST saved step
        def saved_real_gva_last(c: str) -> float:
            q = h5_extract.load_matrix(h5, c, "firms/production")
            u = h5_extract.load_matrix(h5, c, "firms/used_intermediate_inputs")
            p0s = h5_extract.load_series(h5, c, "economy/initial_price")
            n = p0s.size
            ql = q[-1].reshape(-1)
            gross = float((ql * p0s).sum())
            ul = u[-1].reshape(n, n)
            inter = float((ul * p0s[None, :]).sum())
            return (gross - inter) / 1e9

        g_end_saved = sum(saved_real_gva_last(c) for c in region_keys)
        u_end_saved = float(
            np.mean([h5_extract.load_series(h5, c, "economy/unemployment_rate")[-1] for c in region_keys])
        ) * 100.0

        # dims: production should be (n_steps, n_industries); n_industries == d.n_industries
        prod_shape = h5[f"{region_keys[0]}/firms/production"].shape
        n_steps_saved = prod_shape[0]
        n_ind_saved = prod_shape[1] if len(prod_shape) > 1 else 1

    print(f"  regions saved: {len(region_keys)}  (expected 13)")
    print(f"  production dims: {prod_shape}  (n_steps={n_steps_saved}, n_industries={n_ind_saved}; "
          f"pickle n_industries={d.n_industries})")
    print(f"  NaN/inf in saved P1 series: {nan_saved}")
    print(f"  headline agreement (saved vs in-memory):")
    print(f"    real GVA end:  saved {g_end_saved:.1f}B  vs in-mem {g_end:.1f}B  "
          f"(|d|={abs(g_end_saved - g_end):.3f}B)")
    print(f"    unemployment end: saved {u_end_saved:.2f}%  vs in-mem {u_end:.2f}%  "
          f"(|d|={abs(u_end_saved - u_end):.3f}pp)")
    if problems:
        print("  PROBLEMS:")
        for p in problems:
            print(f"    - {p}")
    else:
        print("  no missing groups/series.")


if __name__ == "__main__":
    main()
