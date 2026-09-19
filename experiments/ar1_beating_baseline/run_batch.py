"""Run several seeds for one isolated historical experiment in one process."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import run_historical_experiment as runner


def run_seed(data, spec: dict, experiment_id: str, seed: int, periods: int, output_dir: Path) -> None:
    provinces, config = runner.build_config(data, seed, periods)
    runner.configure(config, provinces, spec, periods)
    model = runner.Simulation.from_datawrapper(datawrapper=data, simulation_configuration=config)
    runner.install_final_demand_path(model, provinces, spec, periods)
    base_prices = {
        province: np.asarray(model.countries[province].economy.ts.current("good_prices"), dtype=float).reshape(-1)
        for province in provinces
    }
    national_rows = []
    regional_rows = []
    quarters = pd.period_range("2022Q1", periods=periods, freq="Q").astype(str)
    for period_index, quarter in enumerate(quarters):
        model.iterate(period_index)
        national, regional = runner.collect(model, provinces, base_prices)
        national_rows.append({"quarter": quarter, **national})
        for province, values in regional.items():
            regional_rows.append({"quarter": quarter, "province": province, **values})
    run_dir = output_dir / experiment_id / f"seed{seed:03d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(national_rows).to_csv(run_dir / "national_quarterly.csv", index=False)
    pd.DataFrame(regional_rows).to_csv(run_dir / "regional_quarterly.csv", index=False)
    (run_dir / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(run_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--periods", type=int, default=runner.N_PERIODS)
    parser.add_argument("--output-dir", type=Path, default=runner.DEFAULT_OUT)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    data = runner.DataWrapper.init_from_pickle(runner.PKL)
    for seed in args.seeds:
        run_seed(data, spec, args.experiment_id, seed, args.periods, args.output_dir)


if __name__ == "__main__":
    main()
