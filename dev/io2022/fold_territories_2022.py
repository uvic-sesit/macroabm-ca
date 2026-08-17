"""Fold the three territories (YT/NT/NU) of the 2022 provincial IO table into ROW.

The production CER-MacroABM workflow is a 10-province structure end to end (region maps,
labour-force index, per-province linkage artefacts, policy tables). Rather than threading
CAN_YT/CAN_NT/CAN_NU through every one of those, this script produces a 10-province
variant of the 13-region 2022 table by AGGREGATING the territory rows and columns into
ROW. Folding is a pure aggregation -- every accounting identity (row/column sums, VA,
Output) is preserved by construction; territory-province trade simply becomes external
trade, which mirrors how the CER linkage already treats the territories (dropped from
every linkage channel by design).

Input : dev/raw_data variant containing icio/icio_2022_can_provinces.csv (13 regions x OECD-50)
Output: icio_2022_can_provinces_10prov.csv next to the input (same layout, 10 CAN regions)

Usage:
    uv run python dev/io2022/fold_territories_2022.py [--input PATH] [--output PATH]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "dev" / "raw_data_10prov" / "icio" / "icio_2022_can_provinces.csv"
TERRITORIES = ["CAN_YT", "CAN_NT", "CAN_NU"]


def fold(input_path: Path, output_path: Path) -> None:
    df = pd.read_csv(input_path, header=[0, 1], index_col=[0, 1])

    # --- rows: add each territory's (region, industry) row onto ROW's matching row.
    for terr in TERRITORIES:
        block = df.loc[terr]
        for industry in block.index:
            df.loc[("ROW", industry)] += block.loc[industry].values
    df = df.drop(index=TERRITORIES, level=0)

    # --- columns: same, per (industry | final-demand category) label.
    cols = df.columns
    for terr in TERRITORIES:
        terr_cols = [c for c in cols if c[0] == terr]
        for _, label in terr_cols:
            df[("ROW", label)] += df[(terr, label)].values
    df = df.drop(columns=TERRITORIES, level=0)

    # Sanity: a pure fold moves values, it never creates or destroys them.
    check = pd.read_csv(input_path, header=[0, 1], index_col=[0, 1])
    if abs(check.sum().sum() - df.sum().sum()) > 1e-6 * abs(check.sum().sum()):
        raise AssertionError(
            f"fold changed the grand total: {check.sum().sum():.6e} -> {df.sum().sum():.6e}"
        )

    remaining = sorted({c for c, _ in df.columns if str(c).startswith("CAN_")})
    if len(remaining) != 10 or any(t in remaining for t in TERRITORIES):
        raise AssertionError(f"expected 10 CAN regions after fold, got {remaining}")

    df.to_csv(output_path)
    print(f"folded table written to {output_path}")
    print(f"regions: {remaining}")
    print(f"grand total preserved: {check.sum().sum():.6e} == {df.sum().sum():.6e}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    output = args.output or args.input.with_name("icio_2022_can_provinces_10prov.csv")
    fold(args.input, output)


if __name__ == "__main__":
    main()
