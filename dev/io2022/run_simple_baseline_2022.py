"""Run the 2022 simple/default baseline and report the headline stability metrics.

This is the validated integration-acceptance run: the shipped-defaults (no candidate growth overlays)
13-region x OECD-50 model over N quarters. It reports real GVA start->end, unemployment start->end,
per-province GVA, any NaN/inf, and any catastrophic small-region collapse.

Build the pickle first (pickles are git-ignored -- regenerate locally):
    uv run python dev/io2022/build_2022_datawrapper.py --pickle dev/pkl_files/io2022_13prov_2022.pkl --force --build-only

Then:
    uv run python dev/io2022/run_simple_baseline_2022.py --quarters 13
    # or point at an alternate pickle:
    IO2022_PKL=dev/pkl_files/io2022_13prov_2022_tradefix.pkl uv run python dev/io2022/run_simple_baseline_2022.py
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np

from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.simulation import Simulation

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PKL = REPO / "dev" / "pkl_files" / "io2022_13prov_2022.pkl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", type=int, default=13)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pickle", type=Path, default=Path(os.environ.get("IO2022_PKL", str(DEFAULT_PKL))))
    args = ap.parse_args()

    d = DataWrapper.init_from_pickle(args.pickle)
    provs = [c for c in d.all_country_names if str(c).startswith("CAN_")]
    cfg = SimulationConfiguration(
        seed=args.seed,
        country_configurations={
            c: CountryConfiguration.n_industry_default(n_industries=d.n_industries) for c in provs
        },
        t_max=args.quarters,
    )
    m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)

    # base-year good prices to double-deflate real GVA
    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}

    def real_gva(country: str) -> float:
        f = m.countries[country].firms
        q = np.array(f.ts.current("production"), float)
        u = np.array(f.ts.current("used_intermediate_inputs"), float)
        gross = float((q * p0[country]).sum())
        inter = float((u * p0[country][None, :]).sum()) if u.ndim == 2 else 0.0
        return (gross - inter) / 1e9

    def unemployment() -> float:
        return float(
            np.mean(
                [np.array(m.countries[c].economy.ts.current("unemployment_rate"), float).reshape(-1)[0] for c in provs]
            )
        ) * 100.0

    g_start = sum(real_gva(c) for c in provs)
    u_start = unemployment()
    prov_start = {c: real_gva(c) for c in provs}

    non_finite = 0
    for t in range(args.quarters):
        m.iterate(t)
        for c in provs:
            for field in ("production", "used_intermediate_inputs", "labour_inputs"):
                arr = np.asarray(m.countries[c].firms.ts.current(field), float)
                non_finite += int(np.sum(~np.isfinite(arr)))

    g_end = sum(real_gva(c) for c in provs)
    u_end = unemployment()
    prov_end = {c: real_gva(c) for c in provs}
    collapsed = [str(c) for c in provs if prov_end[c] < 0.05 * max(prov_start[c], 1e-9)]

    print(f"\n=== 2022 SIMPLE/DEFAULT baseline | {len(provs)} regions | seed {args.seed} | {args.quarters}q ===")
    print(f"  real GVA (double-deflated): {g_start:.1f}B -> {g_end:.1f}B  ({(g_end / g_start - 1) * 100:+.1f}%)")
    print(f"  unemployment: {u_start:.1f}% -> {u_end:.1f}%")
    print(f"  NaN/inf over run: {non_finite}")
    print(f"  catastrophic small-region collapse (end<5% of start): {collapsed if collapsed else 'none'}")
    for c in provs:
        print(f"    {str(c):8s} {prov_start[c]:7.2f}B -> {prov_end[c]:7.2f}B")


if __name__ == "__main__":
    main()
