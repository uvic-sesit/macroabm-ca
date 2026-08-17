"""Extract the official 2022 controls from the downloaded StatCan tables and write controls_2022.json.
Balance-sheet snapshot = Q4 2022 (2022-10); flows = 2022 annual. Values in millions CAD unless noted."""
import json
from pathlib import Path
import pandas as pd

CTRL = Path(__file__).resolve().parent.parent.parent / "raw_data" / "can_2022" / "controls"
OUT = Path(__file__).resolve().parent / "controls_2022.json"
Q = "2022-10"   # Q4 2022 balance-sheet snapshot


def nbsa(cat, side="asset"):
    """NBSA Households, Market value, Q4 2022. Loan/credit/mortgage categories appear TWICE (an
    asset-claim row and a liability row); side='liability' takes the larger (the household owes)."""
    df = pd.read_csv(CTRL / "36100580.csv", low_memory=False)
    m = df[(df["Sectors"] == "Households") & (df["Valuation"] == "Market value")
           & (df["Categories"] == cat) & (df["REF_DATE"] == Q) & (df["GEO"] == "Canada")]
    if len(m) == 0:
        return None
    vals = m["VALUE"].astype(float).values
    return float(vals.max()) if side == "liability" else float(vals[0])  # millions CAD


def dhea_income_2022():
    df = pd.read_csv(CTRL / "36100587.csv", low_memory=False)
    m = df[(df["REF_DATE"].astype(str) == "2022") & (df["Characteristics"] == "All households")
           & (df["Statistics"] == "Value") & (df["GEO"] == "Canada")
           & (df["Income, consumption and savings"] == "Household disposable income")]
    return None if len(m) == 0 else float(m["VALUE"].iloc[0])


def dhea_quintile_shares(wealth_cat="Net worth"):
    df = pd.read_csv(CTRL / "36100660.csv", low_memory=False)
    quints = ["Lowest income quintile", "Second income quintile", "Third income quintile",
              "Fourth income quintile", "Highest income quintile"]
    out = {}
    sub = df[(df["REF_DATE"] == Q) & (df["Statistics"] == "Distribution of value")
             & (df["Wealth"].astype(str).str.contains(wealth_cat, case=False, na=False))]
    for qn in quints:
        r = sub[sub["Characteristics"] == qn]
        out[qn] = float(r["VALUE"].iloc[0]) if len(r) else None
    return out


def annual_index(pid, geo_contains="Canada", extra=None):
    df = pd.read_csv(CTRL / f"{pid}.csv", low_memory=False)
    df = df[df["GEO"].astype(str).str.contains(geo_contains, na=False)]
    if extra:
        for col, val in extra.items():
            if col in df:
                df = df[df[col].astype(str).str.contains(val, case=False, na=False)]
    def yr(y):
        s = df[df["REF_DATE"].astype(str).str.startswith(str(y))]
        return float(s["VALUE"].mean()) if len(s) else None
    return yr(2022), yr(2023)


controls = {
    "vintages": {"SFS_donor": "2023 (13M0006X)", "CIS_income": "2022 (72M0003X)",
                 "controls_snapshot": f"balance sheet Q4 2022 ({Q}); flows 2022 annual"},
    "provenance": {"balance_sheet": "36-10-0580 Households, Market value",
                   "quintiles": "36-10-0660 Distribution of value",
                   "backcast": "18-10-0205 NHPI, 18-10-0004 CPI (2022 vs 2023 annual)"},
    "aggregate_totals_millions_CAD_2022Q4": {
        "Total assets": nbsa("Total assets"),
        "Dwellings": nbsa("Dwellings"),
        "Land underlying dwellings": nbsa("Land underlying dwellings"),
        "Consumer durables": nbsa("Consumer durables"),
        "Total currency and deposits": nbsa("Total currency and deposits"),
        "Total financial assets": nbsa("Total financial assets"),
        "Equity and investment fund shares": nbsa("Equity and investment fund shares"),
        "Life insurance and pensions": nbsa("Life insurance and pensions"),
        "Mortgages (liability)": nbsa("Mortgages", "liability"),
        "Consumer credit (liability)": nbsa("Consumer credit", "liability"),
        "Non-mortgage loans (liability)": nbsa("Non-mortgage loans", "liability"),
        "Total liabilities (= assets - net worth)": (nbsa("Total assets") - nbsa("Net worth")) if (nbsa("Total assets") and nbsa("Net worth")) else None,
        "Net worth": nbsa("Net worth"),
    },
    "model_field_mapping": {
        "Value of the Main Residence + other Properties": "Dwellings + Land underlying dwellings (calibrate the SUM; donor keeps the within-class split)",
        "Value of Household Vehicles": "Consumer durables (approx)",
        "Wealth in Deposits": "Total currency and deposits",
        "Wealth in Financial Assets": "Equity and investment fund shares (+ residual financial ex deposits/pensions)",
        "Voluntary Pension": "Life insurance and pensions",
        "Value of Self-Employment/Private Businesses": "part of Equity (unincorporated) -- approximate; prefer SFS donor level",
        "Outstanding Balance of HMR + other Mortgages": "Mortgages (Residential + Non-residential)",
        "Consumer debt (Credit Line + Card + other)": "Consumer credit + Non-mortgage loans",
        "Income": "CIS 2022 / DHEA disposable income 2022",
        "Net Worth": "Net worth",
    },
    "quintile_shares_net_worth_2022Q4_pct": dhea_quintile_shares("Net worth"),
    "backcast_2023_to_2022": {},
    "flows_2022": {"household_disposable_income_millions_CAD": dhea_income_2022()},
    "not_available_in_these_tables": {
        "homeownership_rate_2022": "not in 36-10-0580/0660; source Census 2021 (98-10-*) or Canadian Housing Survey 46-25-0001",
        "households_by_province_2022": "17-10-0009 is population (persons); household COUNTS need Census families 98-10-* or est.",
    },
}
nhpi22, nhpi23 = annual_index("18100205", extra={"New housing price indexes": "Total"} )
cpi22, cpi23 = annual_index("18100004", extra={"Products and product groups": "All-items"})
controls["backcast_2023_to_2022"] = {
    "housing_NHPI": {"2022": nhpi22, "2023": nhpi23, "factor_2022_over_2023": (nhpi22 / nhpi23) if (nhpi22 and nhpi23) else None},
    "general_CPI": {"2022": cpi22, "2023": cpi23, "factor_2022_over_2023": (cpi22 / cpi23) if (cpi22 and cpi23) else None},
}
# --- model-field calibration targets (what --real consumes); grouped where NBSA can't split -------
A = controls["aggregate_totals_millions_CAD_2022Q4"]
controls["model_field_targets_millions_CAD"] = {
    "_note": "targets in $M CAD; groups calibrate the SUM of listed model fields (donor keeps within-group split).",
    "groups": {
        "residential_real_estate": {"fields": ["Value of the Main Residence", "Value of other Properties"],
                                     "target": (A["Dwellings"] + A["Land underlying dwellings"])},
        "mortgages": {"fields": ["Outstanding Balance of HMR Mortgages", "Outstanding Balance of Mortgages on other Properties"],
                      "target": A["Mortgages (liability)"]},
        "consumer_debt": {"fields": ["Outstanding Balance of Credit Line", "Outstanding Balance of Credit Card Debt", "Outstanding Balance of other Non-Mortgage Loans"],
                          "target": A["Consumer credit (liability)"] + A["Non-mortgage loans (liability)"]},
    },
    "singles": {
        "Wealth in Deposits": A["Total currency and deposits"],
        "Wealth in Financial Assets": A["Total financial assets"] - A["Total currency and deposits"] - A["Life insurance and pensions"],
        "Voluntary Pension": A["Life insurance and pensions"],
        "Value of Household Vehicles": A["Consumer durables"],
        "Net Worth": A["Net worth"],
        # business/other-assets = residual plug so total assets reconcile to NBSA Total assets
        # (unincorporated business equity is not cleanly separable in NBSA at this granularity).
        "Value of Self-Employment Businesses": (
            A["Total assets"] - (A["Dwellings"] + A["Land underlying dwellings"]) - A["Total currency and deposits"]
            - (A["Total financial assets"] - A["Total currency and deposits"] - A["Life insurance and pensions"])
            - A["Life insurance and pensions"] - A["Consumer durables"]),
        "Income": controls["flows_2022"]["household_disposable_income_millions_CAD"],  # cross-check; primary = CIS 2022
    },
}
OUT.write_text(json.dumps(controls, indent=2))
print("wrote controls_2022.json")
print("disposable income 2022 ($M):", controls["flows_2022"]["household_disposable_income_millions_CAD"])
print("model_field group targets:", {k: round(v["target"]) for k, v in controls["model_field_targets_millions_CAD"]["groups"].items()})
