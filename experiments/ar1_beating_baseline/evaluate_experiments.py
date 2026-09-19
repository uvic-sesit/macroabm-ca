"""Score isolated historical experiments against the frozen official/AR(1) benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OFFICIAL = HERE.parents[1] / "dev/working_paper/ar1_benchmark/outputs/quarterly_forecasts_and_realizations.csv"
OUTPUTS = HERE / "outputs"


def metrics(actual: pd.Series, forecast: pd.Series) -> tuple[float, float]:
    valid = actual.notna() & forecast.notna()
    errors = forecast[valid] - actual[valid]
    return float(np.sqrt(np.mean(errors**2))), float(np.mean(np.abs(errors)))


def load_experiment(experiment_id: str) -> tuple[pd.DataFrame, int]:
    paths = sorted((OUTPUTS / experiment_id).glob("seed*/national_quarterly.csv"))
    if not paths:
        raise FileNotFoundError(f"No runs found for {experiment_id}")
    frames = []
    for path in paths:
        frame = pd.read_csv(path)
        frame["seed"] = int(path.parent.name.removeprefix("seed"))
        frame["model_gva_growth"] = 100.0 * np.log(frame["real_gva"]).diff()
        frames.append(frame)
    pooled = pd.concat(frames, ignore_index=True)
    ensemble = pooled.groupby("quarter", as_index=False).mean(numeric_only=True)
    return ensemble, len(paths)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_ids", nargs="+")
    parser.add_argument("--output-dir", type=Path, default=OUTPUTS / "comparison")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    official = pd.read_csv(OFFICIAL)
    all_paths = []
    rows = []
    for experiment_id in args.experiment_ids:
        model, n_seeds = load_experiment(experiment_id)
        merged = official.merge(model, on="quarter", how="left")
        gva = merged.iloc[1:]
        gva_rmse, gva_mae = metrics(gva["real_gva_growth_realized"], gva["model_gva_growth"])
        u_rmse, u_mae = metrics(merged["unemployment_rate_realized"], merged["unemployment_rate"])
        rows.extend(
            [
                {
                    "experiment": experiment_id,
                    "seeds": n_seeds,
                    "target": "real_gva_growth",
                    "rmse": gva_rmse,
                    "mae": gva_mae,
                    "ar1_rmse": 0.3542,
                    "ar1_mae": 0.2941,
                },
                {
                    "experiment": experiment_id,
                    "seeds": n_seeds,
                    "target": "unemployment_rate",
                    "rmse": u_rmse,
                    "mae": u_mae,
                    "ar1_rmse": 1.3392,
                    "ar1_mae": 1.2781,
                },
            ]
        )
        all_paths.append(merged.assign(experiment=experiment_id))

    summary = pd.DataFrame(rows)
    summary["relative_rmse"] = summary["rmse"] / summary["ar1_rmse"]
    summary["relative_mae"] = summary["mae"] / summary["ar1_mae"]
    summary["beats_ar1_rmse"] = summary["relative_rmse"] < 1.0
    summary["beats_ar1_mae"] = summary["relative_mae"] < 1.0
    summary.to_csv(args.output_dir / "metrics.csv", index=False)
    paths = pd.concat(all_paths, ignore_index=True)
    paths.to_csv(args.output_dir / "quarterly_paths.csv", index=False)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)
    first = all_paths[0]
    x = np.arange(len(first))
    axes[0].plot(x[1:], first["real_gva_growth_realized"].iloc[1:], color="black", marker="o", label="Observed")
    axes[0].plot(x[1:], first["real_gva_growth_ar1"].iloc[1:], color="#777777", linestyle="--", label="AR(1)")
    axes[1].plot(x, first["unemployment_rate_realized"], color="black", marker="o", label="Observed")
    axes[1].plot(x, first["unemployment_rate_ar1"], color="#777777", linestyle="--", label="AR(1)")
    colors = plt.cm.tab10(np.linspace(0, 1, len(all_paths)))
    for color, frame in zip(colors, all_paths, strict=True):
        label = frame["experiment"].iloc[0]
        axes[0].plot(x[1:], frame["model_gva_growth"].iloc[1:], color=color, marker=".", label=label)
        axes[1].plot(x, frame["unemployment_rate"], color=color, marker=".", label=label)
    axes[0].set_ylabel("Real GVA growth, % q/q")
    axes[1].set_ylabel("Unemployment rate, %")
    axes[1].set_xticks(x, first["quarter"], rotation=45, ha="right")
    for axis in axes:
        axis.grid(axis="y", color="#dddddd")
        axis.legend(frameon=False, fontsize=8, ncol=3)
    fig.tight_layout()
    fig.savefig(args.output_dir / "comparison.png", dpi=180)
    plt.close(fig)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
