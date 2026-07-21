#!/usr/bin/env python3
"""Build the province-level effective tax-rate file used by ProvincialTaxReader.

Computes, per province and year, two *effective* tax rates from the Statistics Canada
Provincial and Territorial Economic Accounts (PTEA). Both are ratios of tax actually
paid to the relevant income base, because the MacroABM model applies a tax rate FLAT
(rate x base, with no brackets / deductions / small-business rate / abatement) when it
computes government revenue and firm/household net-of-tax positions -- so the scalar the
model needs is an effective rate, not a statutory one.

    corporate_tax_rate       = corporate income tax paid / corporate net operating surplus
    personal_income_tax_rate = household personal income tax / primary household income

Both are computed as *pooled* ratios over a centered multi-year window (sum of tax over the
window / sum of the income base over the window), rather than a single-year ratio. Pooling is
essential for the corporate rate: corporate net operating surplus collapses in downturns
(e.g. Alberta in the 2015-16 oil bust), so a single-year tax/surplus ratio spikes to
implausible values (>70%) purely because the denominator is momentarily tiny. Pooling several
years' tax and surplus together recovers the structural effective rate and halves the
year-to-year volatility. The personal rate is already stable; the same window is applied to it
for methodological consistency (it barely changes the result).

Sources (StatsCan bulk CSV, one PID each):
    36-10-0450  General governments revenue/expenditure (PTEA).
                Numerator: Estimates = "From corporations and government business
                enterprises, liabilities" (the corporate income-tax line), at
                Levels of government = "General governments" (federal + provincial/
                territorial + local, consolidated and allocated to the province).
    36-10-0221  GDP income-based, provincial and territorial, annual.
                Denominator: Estimates = "Net operating surplus: corporations".
    36-10-0224  Household sector, current accounts, provincial and territorial, annual.
                Numerator:   Estimates = "Personal income tax".
                Denominator: Estimates = "Primary household income".

Output: new_raw_data/statcan_provincial/provincial_tax_rates.csv
        columns: region, year, corporate_tax_rate, personal_income_tax_rate  (decimals)

Coverage: 2007-2024 (36-10-0450 begins in 2007). The provincial model consumes the
base-year (2014) value; ProvincialTaxReader clamps to the nearest available year for
out-of-range start years.

See docs/provincial_raw_data.md (tax section) for provenance and assumptions.
"""
from __future__ import annotations

import argparse
import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

BULK = "https://www150.statcan.gc.ca/n1/tbl/csv/{pid}-eng.zip"

PID_GOV = "36100450"   # general governments revenue/expenditure (corporate income tax numerator)
PID_INC = "36100221"   # income-based provincial GDP (corporate net operating surplus denominator)
PID_HH = "36100224"    # household sector current accounts (personal tax + income)

MIN_YEAR = 2007        # 36-10-0450 starts in 2007; below this the corporate numerator is absent
WINDOW_HALF = 2        # centered pooled window half-width (2 => 5-year window Y-2..Y+2)

# StatsCan Estimates member labels
CORP_TAX = "From corporations and government business enterprises, liabilities"
CORP_NOS = "Net operating surplus: corporations"
PERSONAL_TAX = "Personal income tax"
PRIMARY_HH_INCOME = "Primary household income"
GG_LEVEL = "General governments"  # consolidated federal + provincial/territorial + local

PROVINCES = {
    "Alberta": "CAN_AB", "British Columbia": "CAN_BC", "Manitoba": "CAN_MB",
    "New Brunswick": "CAN_NB", "Newfoundland and Labrador": "CAN_NL", "Nova Scotia": "CAN_NS",
    "Ontario": "CAN_ON", "Prince Edward Island": "CAN_PE", "Quebec": "CAN_QC", "Saskatchewan": "CAN_SK",
}


def download(pid: str, cache: Path) -> Path:
    dest = cache / f"{pid}.csv"
    if dest.exists():
        return dest
    cache.mkdir(parents=True, exist_ok=True)
    url = BULK.format(pid=pid)
    print(f"  downloading {url}")
    with urllib.request.urlopen(url, timeout=300) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        member = next(n for n in zf.namelist() if n.endswith(f"{pid}.csv"))
        dest.write_bytes(zf.read(member))
    return dest


def _read(pid: str, cache: Path, do_download: bool) -> pd.DataFrame:
    csv = download(pid, cache) if do_download else cache / f"{pid}.csv"
    df = pd.read_csv(csv, dtype=str, encoding="utf-8-sig", encoding_errors="replace")
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
    df["yr"] = pd.to_numeric(df["REF_DATE"], errors="coerce")
    return df


def build(cache: Path, out: Path, do_download: bool = True) -> Path:
    gov = _read(PID_GOV, cache, do_download)
    inc = _read(PID_INC, cache, do_download)
    hh = _read(PID_HH, cache, do_download)

    gov = gov[gov["Levels of government"] == GG_LEVEL]

    def series(df: pd.DataFrame, geo: str, estimate: str) -> dict[int, float]:
        """Annual {year: value} for one province/estimate."""
        sub = df[(df["GEO"] == geo) & (df["Estimates"] == estimate)]
        return dict(zip(sub["yr"].astype("Int64").astype(int), sub["VALUE"]))

    def pooled_rate(num: dict[int, float], den: dict[int, float], year: int, all_years: list[int]) -> float:
        """Effective rate for `year` = sum(numerator) / sum(denominator) over a centered
        window (clamped to the available panel). Robust to single-year denominator collapse."""
        window = [y for y in range(year - WINDOW_HALF, year + WINDOW_HALF + 1) if y in all_years]
        num_sum = sum(num[y] for y in window if y in num and num[y] == num[y])
        den_sum = sum(den[y] for y in window if y in den and den[y] == den[y])
        return num_sum / den_sum if den_sum > 0 else float("nan")

    years = list(range(MIN_YEAR, int(max(gov["yr"].max(), inc["yr"].max(), hh["yr"].max())) + 1))

    rows = []
    for geo, code in PROVINCES.items():
        corp_tax = series(gov, geo, CORP_TAX)
        corp_nos = series(inc, geo, CORP_NOS)
        pers_tax = series(hh, geo, PERSONAL_TAX)
        prim_inc = series(hh, geo, PRIMARY_HH_INCOME)
        for year in years:
            corp_rate = pooled_rate(corp_tax, corp_nos, year, years)
            pers_rate = pooled_rate(pers_tax, prim_inc, year, years)
            # Skip a province-year only if BOTH rates are unavailable.
            if corp_rate != corp_rate and pers_rate != pers_rate:
                continue
            rows.append((code, int(year),
                         round(corp_rate, 6) if corp_rate == corp_rate else "",
                         round(pers_rate, 6) if pers_rate == pers_rate else ""))

    panel = pd.DataFrame(rows, columns=["region", "year", "corporate_tax_rate", "personal_income_tax_rate"])
    panel = panel.sort_values(["region", "year"])
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "provincial_tax_rates.csv"
    panel.to_csv(dest, index=False)
    print(f"wrote {dest}  ({len(panel)} rows, years {panel['year'].min()}-{panel['year'].max()}, "
          f"{panel['region'].nunique()} provinces)")
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
