"""CAN-2022 Canadianized-household schema adapter (MVP DataWrapper integration).

Maps the validated national Canadian household file (SFS 2023 balance sheet + CIS 2022 income + CHS 2022
tenure + SHS 2023 behavioural consumption; weights rescaled to 15.455M households -- see
dev/io2022/household_prototype/) onto the model's full HFCS household schema, WITHOUT changing any validated
economic magnitude. This is a *schema adapter*, not new economic data:

  * direct 1:1 for every field the Canadianized file already carries (CAD-native);
  * financial-asset COMPONENTS (Mutual Funds/Bonds/Shares/...) are only summed downstream
    (hfcs_synthetic_population.set_household_other_financial_assets), so the validated SFS aggregate
    "Wealth in Financial Assets" is placed in one component (Mutual Funds) with the rest 0 -> identical sums;
  * household INCOME COMPONENTS (financial/pension/transfers) are recovered from CIS 2022 family-level
    source shares by after-tax income decile (CIS has the detail SFS lacks) applied to each household's
    validated total Income -> the split is Canadian-sourced; totals unchanged;
  * RENTAL income is NOT separately recoverable from Canadian data: in CIS/SFS (and Canadian tax
    accounting) net rental income is subsumed in "Investment income" (CIS INVA) -- which is already mapped
    to "Income from Financial Assets" -- so a separate Canadian rental figure would double-count. But the
    model REQUIRES a positive rental field: set_housing_df (matching_households_with_houses) divides by the
    sum of "Rental Income from Real Estate" at BUILD time, so an all-zero field is a divide-by-zero. The
    same routine then RESCALES total rental income to observed "Rent Paid" minus taxes -- so the assumed
    yield sets only the *cross-landlord allocation* (proportional to secondary-property value), NOT the
    aggregate magnitude. It is therefore exposed as the explicit `rental_gross_yield` parameter (documented
    residual), not an embedded constant, and is not a free economic magnitude;
  * the household<->individual LINKAGE ("Corresponding Individuals ID") and two non-Canadianized residual
    fields ("Rent Paid", "Number of Properties...") are carried from the retained French HFCS household row
    by ID (individuals stay the French skeleton for this MVP).

Currency: every column here is CAD-native, so the CAN path must skip the EUR->CAD household conversion
(hfcs_synthetic_population applies it only when the reader is NOT cad_native). Individuals remain French EUR
and keep their conversion. Legacy/raw-HFCS builds never call this adapter.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# CIS 2022 family-level income-source share of total income, by after-tax income decile (1..10).
# Computed from CIS2022_PUMF (weighted, economic-family aggregation). Rows: decile 1..10.
CIS_INCOME_SHARES_BY_DECILE = {
    #        investment, private pension, govt transfers
    1:  (0.051, 0.019, 0.569),
    2:  (0.031, 0.071, 0.511),
    3:  (0.024, 0.112, 0.342),
    4:  (0.027, 0.135, 0.282),
    5:  (0.034, 0.140, 0.226),
    6:  (0.038, 0.138, 0.185),
    7:  (0.038, 0.113, 0.149),
    8:  (0.038, 0.082, 0.107),
    9:  (0.040, 0.058, 0.076),
    10: (0.102, 0.036, 0.034),
}
# Explicit documented residual parameter (see module docstring). Only sets the cross-landlord allocation of
# rental income (the model rescales the total to observed Rent Paid), and only needs to be > 0 so the
# housing-market build does not divide by zero. Overridable via build_canadianized_households_df(...).
DEFAULT_RENTAL_GROSS_YIELD = 0.045

# The full model household schema (order matches the reader's households_df; see New_Household_provincial).
FINANCIAL_COMPONENTS_ZERO = ["Bonds", "Value of Private Businesses", "Shares", "Managed Accounts",
                             "Money owed to Households", "Other Assets"]
CARRY_FROM_HFCS = ["Corresponding Individuals ID", "Rent Paid",
                   "Number of Properties other than Household Main Residence"]


def build_canadianized_households_df(csv_path: Path, hfcs_households_df: pd.DataFrame,
                                     rental_gross_yield: float = DEFAULT_RENTAL_GROSS_YIELD) -> pd.DataFrame:
    """Return a households_df in the model schema, built from the Canadianized CSV. `hfcs_households_df`
    is the retained pooled-European HFCS households frame (same HFCS IDs) used only to carry the linkage +
    two residual columns. No economic magnitude from the HFCS frame enters the Canadianized balance sheet.
    `rental_gross_yield` is the one explicit documented residual (see module docstring): it only sets the
    cross-landlord allocation of rental income (the model rescales the total to observed Rent Paid)."""
    df = pd.read_csv(csv_path)
    out = pd.DataFrame()
    out["ID"] = df["id"].values
    # --- direct 1:1 (CAD-native, validated) ---
    direct = ["Type", "Weight", "Income", "Tenure Status of the Main Residence",
              "Value of the Main Residence", "Value of other Properties", "Value of Household Vehicles",
              "Wealth in Deposits", "Value of Self-Employment Businesses", "Voluntary Pension",
              "Outstanding Balance of HMR Mortgages", "Outstanding Balance of Mortgages on other Properties",
              "Outstanding Balance of Credit Line", "Outstanding Balance of Credit Card Debt",
              "Outstanding Balance of other Non-Mortgage Loans",
              "Amount spent on Consumption of Goods and Services",
              "Consumption of Consumer Goods/Services as a Share of Income"]
    for c in direct:
        out[c] = df[c].values
    # --- financial-asset components: SFS aggregate -> Mutual Funds; rest 0 (downstream only sums them) ---
    out["Mutual Funds"] = df["Wealth in Financial Assets"].values
    for c in FINANCIAL_COMPONENTS_ZERO:
        out[c] = 0.0
    out["Value of Household Valuables"] = 0.0   # SFS folds valuables into other real assets
    # --- household income components from CIS decile shares applied to validated total Income ---
    dec = pd.to_numeric(df["income_decile"], errors="coerce").fillna(1).astype(int).clip(1, 10).values
    inv = np.array([CIS_INCOME_SHARES_BY_DECILE[d][0] for d in dec])
    pen = np.array([CIS_INCOME_SHARES_BY_DECILE[d][1] for d in dec])
    tr = np.array([CIS_INCOME_SHARES_BY_DECILE[d][2] for d in dec])
    income = pd.to_numeric(df["Income"], errors="coerce").fillna(0.0).values
    out["Income from Financial Assets"] = income * inv
    out["Income from Pensions"] = income * pen
    out["Regular Social Transfers"] = income * tr
    # --- rental income: documented residual (yield on secondary-property value, owners only) ---
    other_prop = pd.to_numeric(df["Value of other Properties"], errors="coerce").fillna(0.0).values
    out["Rental Income from Real Estate"] = np.where(other_prop > 0, rental_gross_yield * other_prop, 0.0)
    # Preserve the validated Canadian household income: set_household_income() OVERWRITES "Income" with a
    # component sum whose labour term comes from the pooled-European members. reconcile_labour_income()
    # (SyntheticHFCSPopulation) reads this column to back out a Canadian labour-income target so the
    # pre-matching household Income matches the validated Canadian distribution. Presence of this column is
    # the gate for that reconciliation (Canadianized path only).
    out["Validated Income"] = pd.to_numeric(df["Income"], errors="coerce").values
    # --- derived aggregates the schema carries (synthetic pop recomputes these from components anyway) ---
    out["Wealth"] = df["Net Worth"].values
    out["Debt"] = df["Total Debt"].values
    # --- linkage + residual fields carried from the retained French HFCS row by ID ---
    # HFCSReader.read_csv sets "ID" as the index; support both index and column forms.
    if hfcs_households_df.index.name == "ID" or "ID" not in hfcs_households_df.columns:
        carry = hfcs_households_df
    else:
        carry = hfcs_households_df.set_index("ID")
    for c in CARRY_FROM_HFCS:
        if c in carry.columns:
            out[c] = out["ID"].map(carry[c]).values
        else:
            out[c] = 0.0
    # Number of Properties fallback if the HFCS frame lacked it: infer from secondary-property ownership.
    if out["Number of Properties other than Household Main Residence"].isna().all():
        out["Number of Properties other than Household Main Residence"] = (other_prop > 0).astype(int)
    out["Number of Properties other than Household Main Residence"] = (
        out["Number of Properties other than Household Main Residence"].fillna(0)
    )
    out["Rent Paid"] = pd.to_numeric(out.get("Rent Paid", 0.0), errors="coerce").fillna(0.0)
    # Match the reader convention (HFCSReader.read_csv sets "ID" as the index): sampling links individuals
    # via household index == individuals' "Corresponding Household ID", so the HFCS id MUST be the index.
    out = out.set_index("ID")
    return out
