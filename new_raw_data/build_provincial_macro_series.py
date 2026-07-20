#!/usr/bin/env python3
"""Build the province-level macro panel consumed by ``ProvincialMacroReader``.

Downloads four Statistics Canada tables (bulk CSV), filters each to the ten provinces,
aggregates monthly data to calendar quarters, and writes a tidy panel:

    new_raw_data/statcan_provincial/provincial_macro_series.csv
      columns: region, date, cpi_inflation, unemployment_rate, hpi_nominal_growth, vacancy_rate

See docs/canada/provincial_raw_data.md for full provenance, filters, and assumptions.

Usage:
    python new_raw_data/build_provincial_macro_series.py [--cache DIR] [--out DIR]

Requires network access to www150.statcan.gc.ca (bulk CSV endpoint). If you already have
the raw table CSVs, drop them in <cache>/<pid>/<pid>.csv and pass --no-download.
"""
from __future__ import annotations

import argparse
import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

BULK_URL = "https://www150.statcan.gc.ca/n1/tbl/csv/{pid}-eng.zip"

# StatsCan province GEO label -> model region code
PROVINCES = {
    "Alberta": "CAN_AB",
    "British Columbia": "CAN_BC",
    "Manitoba": "CAN_MB",
    "New Brunswick": "CAN_NB",
    "Newfoundland and Labrador": "CAN_NL",
    "Nova Scotia": "CAN_NS",
    "Ontario": "CAN_ON",
    "Prince Edward Island": "CAN_PE",
    "Quebec": "CAN_QC",
    "Saskatchewan": "CAN_SK",
}

TABLES = {
    "cpi": "18100004",       # CPI, monthly, not seasonally adjusted
    "lfs": "14100287",       # Labour force characteristics by province, monthly, SA
    "nhpi": "18100205",      # New Housing Price Index, monthly
    "jvws": "14100325",      # Job vacancy rate by province, quarterly
}

_QMONTH = {1: 1, 2: 4, 3: 7, 4: 10}


def download(pid: str, cache: Path) -> None:
    dest = cache / pid / f"{pid}.csv"
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = BULK_URL.format(pid=pid)
    print(f"  downloading {url}")
    with urllib.request.urlopen(url, timeout=300) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        member = next(n for n in zf.namelist() if n.endswith(f"{pid}.csv"))
        dest.write_bytes(zf.read(member))


def load(pid: str, cache: Path, cols: list[str]) -> pd.DataFrame:
    return pd.read_csv(
        cache / pid / f"{pid}.csv",
        dtype=str,
        usecols=cols,
        encoding="utf-8-sig",       # strip BOM
        encoding_errors="replace",  # tolerate cp1252 accents in city names we don't use
    )


def to_quarter(ref_date: pd.Series) -> pd.PeriodIndex:
    """Monthly 'YYYY-MM' (or quarterly markers) -> Period[Q]."""
    return pd.PeriodIndex(ref_date, freq="M").asfreq("Q")


def quarter_mean(df: pd.DataFrame) -> pd.DataFrame:
    """df[region, REF_DATE, VALUE] -> quarterly mean per region/quarter."""
    df = df.copy()
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
    df["q"] = to_quarter(df["REF_DATE"])
    return df.dropna(subset=["VALUE"]).groupby(["region", "q"])["VALUE"].mean().reset_index()


def q_to_timestamp(period) -> pd.Timestamp:
    return pd.Timestamp(period.year, _QMONTH[period.quarter], 1)


def build(cache: Path, out: Path, do_download: bool = True) -> Path:
    if do_download:
        for pid in TABLES.values():
            download(pid, cache)

    # --- CPI: all-items, quarterly-average level -> q/q growth ---
    cpi = load(TABLES["cpi"], cache, ["REF_DATE", "GEO", "Products and product groups", "VALUE"])
    cpi = cpi[(cpi["Products and product groups"] == "All-items") & (cpi["GEO"].isin(PROVINCES))]
    cpi["region"] = cpi["GEO"].map(PROVINCES)
    cpi = quarter_mean(cpi[["region", "REF_DATE", "VALUE"]]).sort_values(["region", "q"])
    cpi["cpi_inflation"] = cpi.groupby("region")["VALUE"].pct_change()

    # --- LFS unemployment rate (SA), quarterly-average, /100 ---
    lfs = load(TABLES["lfs"], cache, ["REF_DATE", "GEO", "Labour force characteristics",
                                      "Gender", "Age group", "Statistics", "Data type", "UOM", "VALUE"])
    lfs = lfs[(lfs["Labour force characteristics"] == "Unemployment rate")
              & (lfs["Gender"] == "Total - Gender") & (lfs["Age group"] == "15 years and over")
              & (lfs["Statistics"] == "Estimate") & (lfs["Data type"] == "Seasonally adjusted")
              & (lfs["UOM"] == "Percent") & (lfs["GEO"].isin(PROVINCES))]
    lfs["region"] = lfs["GEO"].map(PROVINCES)
    lfs = quarter_mean(lfs[["region", "REF_DATE", "VALUE"]])
    lfs["unemployment_rate"] = lfs["VALUE"] / 100.0

    # --- NHPI total (house + land), quarterly-average level -> q/q growth ---
    nhpi = load(TABLES["nhpi"], cache, ["REF_DATE", "GEO", "New housing price indexes", "VALUE"])
    nhpi = nhpi[(nhpi["New housing price indexes"] == "Total (house and land)") & (nhpi["GEO"].isin(PROVINCES))]
    nhpi["region"] = nhpi["GEO"].map(PROVINCES)
    nhpi = quarter_mean(nhpi[["region", "REF_DATE", "VALUE"]]).sort_values(["region", "q"])
    nhpi["hpi_nominal_growth"] = nhpi.groupby("region")["VALUE"].pct_change()

    # --- JVWS job vacancy rate, /100 ---
    jv = load(TABLES["jvws"], cache, ["REF_DATE", "GEO", "Statistics", "UOM", "VALUE"])
    jv = jv[(jv["Statistics"] == "Job vacancy rate") & (jv["UOM"] == "Percentage") & (jv["GEO"].isin(PROVINCES))]
    jv["region"] = jv["GEO"].map(PROVINCES)
    jv = quarter_mean(jv[["region", "REF_DATE", "VALUE"]])
    jv["vacancy_rate"] = jv["VALUE"] / 100.0

    # --- merge to tidy panel ---
    panel = cpi[["region", "q", "cpi_inflation"]]
    panel = panel.merge(lfs[["region", "q", "unemployment_rate"]], on=["region", "q"], how="outer")
    panel = panel.merge(nhpi[["region", "q", "hpi_nominal_growth"]], on=["region", "q"], how="outer")
    panel = panel.merge(jv[["region", "q", "vacancy_rate"]], on=["region", "q"], how="outer")
    panel = panel[(panel["q"] >= pd.Period("1998Q1", "Q")) & (panel["q"] <= pd.Period("2024Q4", "Q"))]
    panel["date"] = panel["q"].apply(q_to_timestamp)
    panel = panel.sort_values(["region", "q"])[
        ["region", "date", "cpi_inflation", "unemployment_rate", "hpi_nominal_growth", "vacancy_rate"]
    ]

    out.mkdir(parents=True, exist_ok=True)
    dest = out / "provincial_macro_series.csv"
    panel.to_csv(dest, index=False)
    print(f"wrote {dest}  ({len(panel)} rows, {panel['region'].nunique()} provinces)")
    return dest


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", type=Path, default=here / "_statcan_cache",
                    help="Directory for downloaded raw table CSVs (default: new_raw_data/_statcan_cache).")
    ap.add_argument("--out", type=Path, default=here / "statcan_provincial",
                    help="Output directory for the tidy panel (default: new_raw_data/statcan_provincial).")
    ap.add_argument("--no-download", action="store_true", help="Use cached raw CSVs; do not fetch.")
    a = ap.parse_args()
    build(a.cache, a.out, do_download=not a.no_download)


if __name__ == "__main__":
    main()
