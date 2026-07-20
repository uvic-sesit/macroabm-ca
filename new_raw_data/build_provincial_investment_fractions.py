#!/usr/bin/env python3
"""Build the province-level GFCF institutional-split file used by ProvincialInvestmentReader.

Downloads StatsCan table 36-10-0222 (expenditure-based provincial GDP), and for each province
computes the Firm / Household / Government split of gross fixed capital formation, mapping the
Canadian expenditure-account components onto the model's institutional-sector definition:

    Government = General governments GFCF
    Household  = Residential structures + NPISH GFCF
    Firm       = Business GFCF - Residential structures  (non-res structures + M&E + IP)

Output: new_raw_data/statcan_provincial/provincial_investment_fractions.csv
        columns: region, year, firm, household, government   (fractions sum to 1)

See docs/canada/provincial_raw_data.md (section 3b) for provenance and assumptions.
"""
from __future__ import annotations

import argparse
import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

PID = "36100222"
BULK_URL = f"https://www150.statcan.gc.ca/n1/tbl/csv/{PID}-eng.zip"
YEAR = "2014"
PRICES = "Current prices"

PROVINCES = {
    "Alberta": "CAN_AB", "British Columbia": "CAN_BC", "Manitoba": "CAN_MB",
    "New Brunswick": "CAN_NB", "Newfoundland and Labrador": "CAN_NL", "Nova Scotia": "CAN_NS",
    "Ontario": "CAN_ON", "Prince Edward Island": "CAN_PE", "Quebec": "CAN_QC", "Saskatchewan": "CAN_SK",
}

BUSINESS = "Business gross fixed capital formation"
RESIDENTIAL = "Residential structures"
NPISH = "Non-profit institutions serving households' gross fixed capital formation"
GOVERNMENT = "General governments gross fixed capital formation"


def download(cache: Path) -> Path:
    dest = cache / f"{PID}.csv"
    if dest.exists():
        return dest
    cache.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {BULK_URL}")
    with urllib.request.urlopen(BULK_URL, timeout=300) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        member = next(n for n in zf.namelist() if n.endswith(f"{PID}.csv"))
        dest.write_bytes(zf.read(member))
    return dest


def build(cache: Path, out: Path, do_download: bool = True) -> Path:
    csv = download(cache) if do_download else cache / f"{PID}.csv"
    df = pd.read_csv(csv, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
    df = df[(df["Prices"] == PRICES) & (df["REF_DATE"] == YEAR) & (df["GEO"].isin(PROVINCES))].copy()
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")

    def val(geo: str, estimate: str) -> float:
        v = df[(df["GEO"] == geo) & (df["Estimates"] == estimate)]["VALUE"]
        return float(v.values[0]) if len(v) else float("nan")

    rows = []
    for geo, code in PROVINCES.items():
        business = val(geo, BUSINESS)
        residential = val(geo, RESIDENTIAL)
        npish = val(geo, NPISH)
        government = val(geo, GOVERNMENT)
        firm = business - residential
        household = residential + (npish if npish == npish else 0.0)  # NaN-safe
        total = firm + household + government
        rows.append((code, int(YEAR), round(firm / total, 6), round(household / total, 6),
                     round(government / total, 6)))

    panel = pd.DataFrame(rows, columns=["region", "year", "firm", "household", "government"])
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "provincial_investment_fractions.csv"
    panel.to_csv(dest, index=False)
    print(f"wrote {dest}\n{panel.to_string(index=False)}")
    return dest


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=here / "_statcan_cache")
    ap.add_argument("--out", type=Path, default=here / "statcan_provincial")
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    build(a.cache, a.out, do_download=not a.no_download)


if __name__ == "__main__":
    main()
