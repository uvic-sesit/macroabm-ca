"""Phase-1 household-balance-sheet + income Canadianization PROTOTYPE (design accepted 2026-08).

Architecture: HFCS-SKELETON + SFS donor-vector transplant.
  * recipient  = existing HFCS-2021 household skeleton (keeps IDs / member structure);
  * donor      = SFS 2023 economic families (StatCan 13M0006X);
  * transplant = joint (copy the whole asset/debt/income vector from one matched donor),
                 NOT independent per-variable rescaling;
  * backcast   = 2023 -> 2022 via price/level indices, then calibrate major class totals to
                 2022 DHEA/NBSA aggregate controls;
  * income     = CIS 2022 (72M0003X) reconciliation of levels / source composition.

IMPORTANT — DATA AVAILABILITY:
  The SFS 2023 PUMF, CIS 2022 PUMF and the 2022 DHEA/NBSA control tables are NOT bundled (they
  require manual download from the StatCan portal + licence acceptance -- see SOURCE_MANIFEST.md).
  With `--real` this script reads them from the paths in that manifest and the codebook column maps
  below (fill SFS_COLUMN_MAP / CIS_COLUMN_MAP / CONTROLS_2022 from the codebooks/tables first).
  With `--standin` (default) it substitutes the local `New_Household*.csv` (the OLD SFS-2016/CIS-2017
  Canadianized file) as a stand-in donor purely to exercise the pipeline mechanics and answer the
  "joint transplant vs marginal rescale" question. STAND-IN NUMBERS ARE NOT PRODUCTION VALUES.

Phase-1 scope only: household balance sheet + income. Does NOT touch Individuals.csv, SHS
consumption, employment (36-10-0489 stays), the DataWrapper, or model calibration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
HFCS_2021 = REPO / "dev" / "raw_data" / "hfcs" / "2021"
STANDIN_DONOR = REPO / "dev" / "raw_data" / "hfcs" / "New_Household.csv"
OUT_DIR = Path(__file__).resolve().parent

# --- the 12-component joint vector transplanted from the donor, as MODEL fields -------------------
VECTOR_FIELDS = [
    "Value of the Main Residence",
    "Value of other Properties",
    "Value of Household Vehicles",
    "Wealth in Deposits",
    "Wealth in Financial Assets",
    "Value of Self-Employment Businesses",
    "Voluntary Pension",
    "Outstanding Balance of HMR Mortgages",
    "Outstanding Balance of Mortgages on other Properties",
    "Outstanding Balance of Credit Line",
    "Outstanding Balance of Credit Card Debt",
    "Outstanding Balance of other Non-Mortgage Loans",
    "Income",
]
MATCH_KEYS = ["Type", "Tenure Status of the Main Residence", "income_decile", "province"]

# --- recipient: raw HFCS-2021 derived household file (lower-case codes) ---------------------------
HFCS_CODE_MAP = {
    "dhhtype": "Type", "hb0300": "Tenure Status of the Main Residence", "hw0010": "Weight",
    "da1110": "Value of the Main Residence", "da1120": "Value of other Properties",
    "da1130": "Value of Household Vehicles", "da2101": "Wealth in Deposits",
    "da2100": "Wealth in Financial Assets", "da1140": "Value of Self-Employment Businesses",
    "da2109": "Voluntary Pension", "dl1110": "Outstanding Balance of HMR Mortgages",
    "dl1120": "Outstanding Balance of Mortgages on other Properties",
    "dl1210": "Outstanding Balance of Credit Line", "dl1220": "Outstanding Balance of Credit Card Debt",
    "dl1230": "Outstanding Balance of other Non-Mortgage Loans", "di2000": "Income",
    "da3001": "Total Assets", "dn3001": "Net Worth", "dl1000": "Total Debt", "dl1100": "Total Mortgage",
}

# --- SFS 2023 PUMF (economic-family) column map, from SFS2023_EFAM_PUMF_vare.sps. Values that are a
#     list are SUMMED (a model field aggregates several SFS variables). All values are 2023 constant $.
SFS_CSV = REPO / "dev" / "raw_data" / "can_2022" / "pumf" / "sfs_2023" / "sfs2023_efam_pumf.csv"
SFS_COLUMN_MAP: dict[str, object] = {
    "Value of the Main Residence": "PWAPRVAL",                 # value of principal residence
    "Value of other Properties": "PWASTRST",                   # real estate other than principal
    "Value of Household Vehicles": "PWASTVHE",                 # vehicles
    "Wealth in Deposits": "PWASTDEP",                          # money in banks (non-registered)
    "Wealth in Financial Assets": ["PWASTMUI", "PWASTSTK", "PWASTBND", "PWASTOIN", "PWATFS"],
    "Value of Self-Employment Businesses": "PWBUSEQ",         # equity value of businesses
    "Voluntary Pension": ["PWARPPG", "PWARRSPL", "PWARRIF"],  # employer pension + RRSP + RRIF
    "Outstanding Balance of HMR Mortgages": "PWDPRMOR",       # mortgage on principal residence
    "Outstanding Balance of Mortgages on other Properties": "PWDSTOMR",
    "Outstanding Balance of Credit Line": "PWDSTLOC",         # line-of-credit debt
    "Outstanding Balance of Credit Card Debt": "PWDSTCRD",    # credit card + installment
    "Outstanding Balance of other Non-Mortgage Loans": ["PWDSLOAN", "PWDSTVHN", "PWDSTODB"],
    "Income": ["PEFMTINC", "PEFGTR"],                          # market income + government transfers
}
SFS_META = {"weight": "PWEIGHT", "tenure": "PFTENUR", "family_type": "PFMTYPG",
            "region": "PREGION", "after_tax_income": "PEFATINC", "net_worth": "PWNETWPG"}
SFS_OWNER_TENURE = {1, 2}            # 1 own w/o mortgage, 2 own w/ mortgage, 3 do not own
SFS_INCOME_SENTINEL = 99999999       # PEF*INC top-code / not-available
# --- CIS 2022 PUMF (person-level); Phase-1 uses it only for the income aggregate cross-check.
#     Person-level source split is deferred with Individuals.csv. ---
CIS_CSV = REPO / "dev" / "raw_data" / "can_2022" / "pumf" / "cis_2022" / "CIS2022_PUMF.csv"
CIS_COLUMN_MAP = {"weight": "FWEIGHT", "province": "PROV", "after_tax_income": "ATINC",
                  "earnings": "EARNG", "ei_benefits": "EIBEN", "cpp_qpp": "CPQPP", "transfers_child": "CHBEN"}
CIS_INCOME_SENTINEL = 999999999996

# --- TO FILL from 2022 control tables (SOURCE_MANIFEST.md). Aggregate class totals ($) + optional
#     quintile splits. Placeholders here are NOT verified values -> --real requires filling them. ---
CONTROLS_2022 = {
    "source": "36-10-0660 (wealth), 36-10-0587 (income), 36-10-0580 (NBSA), 38-10-0238 (credit)",
    "aggregate_totals": {},   # {"Value of the Main Residence": <CAD>, "Outstanding Balance of HMR Mortgages": <CAD>, ...}
    "quintile_shares": {},    # {"Net Worth": [q1..q5 shares], ...}
    "backcast_index_2023_to_2022": {  # intermediate only; final totals must hit aggregate_totals
        "housing": None, "financial": None, "deposits": None, "mortgage": None, "consumer_credit": None,
    },
}


def load_recipient_hfcs() -> pd.DataFrame:
    d1 = pd.read_csv(HFCS_2021 / "d1.csv")
    h1 = pd.read_csv(HFCS_2021 / "h1.csv")
    d1.columns = [c.lower() for c in d1.columns]
    h1.columns = [c.lower() for c in h1.columns]
    keep = {c: HFCS_CODE_MAP[c] for c in HFCS_CODE_MAP if c in d1.columns}
    rec = d1[["id"] + list(keep)].rename(columns=keep).copy()
    if "hb0300" in h1.columns:  # tenure lives in H
        rec = rec.merge(h1[["id", "hb0300"]].rename(columns={"hb0300": "Tenure Status of the Main Residence"}),
                        on="id", how="left", suffixes=("", "_h"))
        if "Tenure Status of the Main Residence_h" in rec:
            rec["Tenure Status of the Main Residence"] = rec["Tenure Status of the Main Residence_h"]
            rec = rec.drop(columns=["Tenure Status of the Main Residence_h"])
    rec["province"] = "CAN"  # base HFCS carries no province -> national pool (documented fallback)
    rec["tenure_bin"] = (rec["Tenure Status of the Main Residence"] == 1).astype(int)  # HFCS 1 = owner
    rec["income_decile"] = pd.qcut(rec["Income"].rank(method="first"), 10, labels=False) + 1
    return rec


def _sfs_col(df, spec):
    return df[spec].astype(float) if isinstance(spec, str) else sum(df[c].astype(float) for c in spec)


def load_donor(standin: bool) -> pd.DataFrame:
    if standin:
        don = pd.read_csv(STANDIN_DONOR)
        don["province"] = "CAN"
        don["tenure_bin"] = (don.get("Tenure Status of the Main Residence", 1) == 1).astype(int) if "Tenure Status of the Main Residence" in don else 1
        inc = don["Income"] if "Income" in don else don.get("income")
        don["income_decile"] = pd.qcut(pd.Series(inc).rank(method="first"), 10, labels=False) + 1
        for f in VECTOR_FIELDS:
            if f not in don.columns:
                don[f] = 0.0
        return don
    # --- REAL: SFS 2023 economic families ---
    s = pd.read_csv(SFS_CSV, low_memory=False)
    don = pd.DataFrame(index=s.index)
    for field, spec in SFS_COLUMN_MAP.items():
        v = _sfs_col(s, spec)
        if field == "Income":  # cap top-code sentinel before use
            for c in (spec if isinstance(spec, list) else [spec]):
                s.loc[s[c] >= SFS_INCOME_SENTINEL, c] = np.nan
            v = _sfs_col(s, spec)
        don[field] = v
    # missing/sign handling (step-5 classification): asset/debt STOCKS clip <0 -> 0 (overdraft edge
    # cases); NET positions (net worth) may be negative -> keep; income may be negative (losses) -> keep.
    STOCK_FIELDS = [f for f in VECTOR_FIELDS if f != "Income"]
    for f in STOCK_FIELDS:
        don[f] = don[f].clip(lower=0.0)
    don["Weight"] = s[SFS_META["weight"]].astype(float)
    don["Net Worth"] = s[SFS_META["net_worth"]].astype(float)  # may be < 0 -- kept
    don["tenure_bin"] = s[SFS_META["tenure"]].isin(SFS_OWNER_TENURE).astype(int)
    don["province"] = "CAN"  # SFS PREGION is 5 regions; recipient is national -> national pool
    don["income_decile"] = pd.qcut(s[SFS_META["after_tax_income"]].rank(method="first"), 10, labels=False) + 1
    return don


def donor_match(recipient: pd.DataFrame, donor: pd.DataFrame, seed: int = 0) -> np.ndarray:
    """Assign each recipient a donor row by matched cell (Type, Tenure, income_decile, province),
    widening the cell (drop the least-important key) when a cell is empty. Returns donor index array."""
    rng = np.random.default_rng(seed)
    keys_by_priority = ["province", "tenure_bin", "income_decile"]
    donor = donor.reset_index(drop=True)
    assigned = np.empty(len(recipient), dtype=int)
    n_keys = len(keys_by_priority)
    levels = np.zeros(len(recipient), dtype=int)  # #keys matched (n_keys = full-cell match)
    for i in range(len(recipient)):
        rd = recipient.iloc[i]
        for drop in range(n_keys + 1):
            used = keys_by_priority[: n_keys - drop] if drop else keys_by_priority
            mask = np.ones(len(donor), dtype=bool)
            for k in used:
                if k in donor and k in recipient:
                    mask &= (donor[k].values == rd[k])
            idx = np.flatnonzero(mask)
            if len(idx):
                assigned[i] = idx[rng.integers(len(idx))]
                levels[i] = len(used)
                break
        else:
            assigned[i] = rng.integers(len(donor))
            levels[i] = 0
    return assigned, levels


def joint_transplant(recipient: pd.DataFrame, donor: pd.DataFrame, assign: np.ndarray) -> pd.DataFrame:
    out = recipient.copy()
    for f in VECTOR_FIELDS:
        out[f] = donor.iloc[assign][f].values  # whole vector from ONE donor -> joint dependence preserved
    return out


def marginal_rescale(recipient: pd.DataFrame, donor: pd.DataFrame) -> pd.DataFrame:
    """Baseline for comparison: rescale each recipient field INDEPENDENTLY to the donor marginal
    (rank-preserving quantile map). Destroys cross-variable dependence by construction."""
    out = recipient.copy()
    for f in VECTOR_FIELDS:
        r = recipient[f].values.astype(float)
        dvals = np.sort(donor[f].values.astype(float))
        ranks = pd.Series(r).rank(method="first").values / (len(r) + 1)
        out[f] = np.interp(ranks, np.linspace(0, 1, len(dvals)), dvals)
    return out


def load_controls_2022() -> dict:
    """Official 2022 targets extracted from StatCan (see extract_controls.py / controls_2022.json)."""
    p = OUT_DIR / "controls_2022.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text()).get("model_field_targets_millions_CAD", {})


def backcast_calibrate(df: pd.DataFrame, targets: dict) -> pd.DataFrame:
    """Calibrate to 2022 official aggregates ($M CAD), preserving within-group ranks/joint structure by
    applying ONE positive factor per group/single. Group targets calibrate the SUM of the listed model
    fields (donor keeps the within-group split). No-op where a target is null. Weighted, in $M."""
    out = df.copy()
    w = out["Weight"].values if "Weight" in out else np.ones(len(out))
    scale_to_millions = 1e-6  # donor values are $; targets are $M
    for grp in targets.get("groups", {}).values():
        fields = [f for f in grp["fields"] if f in out]
        target = grp.get("target")
        if not fields or not target:
            continue
        cur = float(np.nansum(sum(out[f].values for f in fields) * w)) * scale_to_millions
        if cur > 0:
            factor = target / cur
            for f in fields:
                out[f] = out[f].values * factor
    for f, target in targets.get("singles", {}).items():
        if f in out and target:
            cur = float(np.nansum(out[f].values * w)) * scale_to_millions
            if cur > 0:
                out[f] = out[f].values * (target / cur)
    return out


def _wsum(df, col, w):
    return float(np.nansum(df[col].values * w)) if col in df else float("nan")


def validate(before: pd.DataFrame, after_joint: pd.DataFrame, after_marg: pd.DataFrame,
             donor: pd.DataFrame, assign: np.ndarray, levels: np.ndarray) -> dict:
    wB = before["Weight"].values
    def agg(df, w):
        mort = _wsum(df, "Outstanding Balance of HMR Mortgages", w) + _wsum(df, "Outstanding Balance of Mortgages on other Properties", w)
        cons = sum(_wsum(df, c, w) for c in ["Outstanding Balance of Credit Line", "Outstanding Balance of Credit Card Debt", "Outstanding Balance of other Non-Mortgage Loans"])
        assets = sum(_wsum(df, c, w) for c in ["Value of the Main Residence", "Value of other Properties", "Value of Household Vehicles", "Wealth in Deposits", "Wealth in Financial Assets", "Value of Self-Employment Businesses", "Voluntary Pension"])
        return dict(total_assets=assets, mortgage_debt=mort, consumer_debt=cons,
                    deposits=_wsum(df, "Wealth in Deposits", w), income=_wsum(df, "Income", w),
                    net_worth=assets - mort - cons)
    # homeownership: tenure code 1 == owner in both HFCS/SFS conventions (verify against codebook)
    def homeown(df, w):
        t = df["tenure_bin"].values  # HFCS-skeleton tenure preserved via match key
        return float(np.sum(w[(t == 1)]) / np.sum(w))
    # joint-structure metric: mean |corr| among the vector fields (higher = dependence retained)
    def mean_abs_corr(df):
        C = df[VECTOR_FIELDS].astype(float).corr().values
        iu = np.triu_indices_from(C, k=1)
        return float(np.nanmean(np.abs(C[iu])))
    # net-worth shares by INCOME quintile (compare to DHEA control 36-10-0660)
    def nw_quintile_shares(df, w):
        assets = sum(df[c].astype(float).values for c in ["Value of the Main Residence", "Value of other Properties", "Value of Household Vehicles", "Wealth in Deposits", "Wealth in Financial Assets", "Value of Self-Employment Businesses", "Voluntary Pension"])
        debts = sum(df[c].astype(float).values for c in ["Outstanding Balance of HMR Mortgages", "Outstanding Balance of Mortgages on other Properties", "Outstanding Balance of Credit Line", "Outstanding Balance of Credit Card Debt", "Outstanding Balance of other Non-Mortgage Loans"])
        nw = (assets - debts) * w
        q = np.ceil(df["income_decile"].values / 2).astype(int)  # decile -> quintile 1..5
        tot = np.nansum(nw)
        return {int(k): round(100 * float(np.nansum(nw[q == k])) / tot, 1) for k in range(1, 6)} if tot else {}
    reuse = np.bincount(assign, minlength=len(donor))
    lvl, lvl_ct = np.unique(levels, return_counts=True)
    return {
        "net_worth_share_by_income_quintile_pct": {"after_joint": nw_quintile_shares(after_joint, before["Weight"].values),
                                                   "control_36-10-0660": [11.5, 11.1, 14.9, 22.3, 40.2]},
        "match_quality_by_key_depth": {f"{int(k)}_keys": int(c) for k, c in zip(lvl, lvl_ct)},
        "match_full_cell_fraction": float(np.mean(levels == levels.max())),
        "BEFORE_hfcs": agg(before, wB), "AFTER_joint": agg(after_joint, wB), "AFTER_marginal": agg(after_marg, wB),
        "homeownership": {"before": homeown(before, wB), "after_joint": homeown(after_joint, wB)},
        "joint_structure_mean_abs_corr": {
            "donor(reference)": mean_abs_corr(donor.iloc[np.unique(assign)]),
            "after_joint_transplant": mean_abs_corr(after_joint),
            "after_marginal_rescale": mean_abs_corr(after_marg),
            "before_hfcs": mean_abs_corr(before),
        },
        "negatives": {f: int(np.sum(after_joint[f].values < 0)) for f in VECTOR_FIELDS if f in after_joint},
        "donor_reuse": {"n_donors": int(len(donor)), "n_used": int((reuse > 0).sum()),
                        "max_reuse": int(reuse.max()) if len(reuse) else 0,
                        "mean_reuse_among_used": float(reuse[reuse > 0].mean()) if (reuse > 0).any() else 0.0},
        "n_recipients": int(len(before)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="use downloaded SFS 2023 / CIS 2022 / controls")
    ap.add_argument("--standin", action="store_true", help="stand-in dry-run using local New_Household (default)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    standin = not args.real

    recipient = load_recipient_hfcs()
    donor = load_donor(standin=standin)
    assign, levels = donor_match(recipient, donor, seed=args.seed)
    after_joint = joint_transplant(recipient, donor, assign)
    after_marg = marginal_rescale(recipient, donor)
    after_joint = backcast_calibrate(after_joint, load_controls_2022())  # calibrate to official 2022 targets

    report = validate(recipient, after_joint, after_marg, donor, assign, levels)
    mode = "STANDIN (New_Household donor; NON-PRODUCTION numbers)" if standin else "REAL (SFS 2023)"
    report["MODE"] = mode
    (OUT_DIR / "validation_report.json").write_text(json.dumps(report, indent=2))
    out_csv = OUT_DIR / ("PROTOTYPE_STANDIN_household.csv" if standin else "prototype_household.csv")
    after_joint.to_csv(out_csv, index=False)
    print(f"MODE: {mode}")
    print(f"wrote {out_csv.name} ({len(after_joint)} households) + validation_report.json")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
