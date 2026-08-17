"""Prepare the observed 2022 compensation-of-employees input for the DataWrapper wage bill.

Extracts PRM500000 (wages_salaries) and PRM600000 (employers_social_contributions) per
province x OECD-50 sector from the macroabm-io2022 canonical VA breakdown, and writes them to the
can_2022 input directory the reader loads (see default_readers._load_can_2022_compensation_of_employees).

The reader sums the two columns into total compensation of employees (the model's labour_compensation ==
firm Total Wages Paid == firm labour cost) and derives the per-province employer/wages ratio to override
tau_sif so the wage vs employer split matches PRM500000/PRM600000. CAD millions; not committed (regenerable).

Usage:
    uv run python dev/io2022/prepare_compensation_input.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SRC = REPO.parent / "macroabm-io2022" / "canonical" / "VA_tax_output_basic.csv"
DST = REPO / "dev" / "raw_data" / "can_2022" / "compensation_of_employees_oecd50_by_province_CADmillions.csv"


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(f"Canonical VA breakdown not found at {SRC} (needs the macroabm-io2022 repo).")
    va = pd.read_csv(SRC, index_col=0)
    idx = va.index.to_series().str.split("|", n=1, expand=True)
    out = pd.DataFrame(
        {
            "region": idx[0].str.replace("CAN_", "", regex=False).values,
            "oecd": idx[1].values,
            "wages_salaries": va["wages_salaries"].values,
            "employers_social_contributions": va["employers_social_contributions"].values,
        }
    )
    DST.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(DST, index=False)
    coe = out["wages_salaries"].sum() + out["employers_social_contributions"].sum()
    print(f"Wrote {DST} ({len(out)} rows, {out.region.nunique()} regions).")
    print(f"National CoE = {coe / 1e3:.1f} CAD bn; employer/wages = "
          f"{out['employers_social_contributions'].sum() / out['wages_salaries'].sum():.3f}")


if __name__ == "__main__":
    main()
