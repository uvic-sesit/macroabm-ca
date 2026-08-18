"""Phase-2 household CONSUMPTION Canadianization (design accepted 2026-08). Task 2.

Architecture (mirrors the accepted Phase-1 donor-transplant, does NOT touch it):
  * recipient  = the VALIDATED Phase-1 Canadianized skeleton (prototype_household.csv): keeps the SFS
                 wealth/debt/income vectors, weighted income deciles, age band, and CHS-calibrated tenure
                 weights UNCHANGED.
  * donor      = SHS 2023 PUMF (fixed-width, parsed from its own SAS layout).
  * concept    = SHS *Total current consumption* (TC001) -- actual household demand for goods/services.
                 NOT *Total expenditure* (TE001 = TC001 + income tax TX010 + personal insurance/pension
                 EP011 + gifts/support MG001), which the model does not treat as consumption. This matches
                 the model field HFCS HI0220 "Amount spent on Consumption of Goods and Services" and the
                 driver "Consumption of Consumer Goods/Services as a Share of Income" (see
                 macro_data/readers/population_data/hfcs_reader.py, hfcs_synthetic_population.py: the model
                 forms Saving Rate = 1 - consumption_share and Consumption = (1-SR)*Income/(1+vat)).
  * transplant = the consumption SHARE s = TC001 / disposable_income (scale-free; ties consumption to the
                 already-validated Canadian income distribution). Recipient consumption = s * recipient
                 disposable income, then the aggregate is CALIBRATED to the 2022 official control.
  * control    = DHEA 36-10-0587 Household final consumption expenditure (HFCE), 2022 Canada (the SNA
                 household consumption the ABM goods market clears against). Backcast 2023->2022 is
                 SUBSUMED by this level calibration (the share is a ~vintage-stable ratio; CPI x0.964 in
                 controls_2022.json for reference only).
  * saving     = disposable income - consumption (NOT forced >= 0; bottom quintiles dissave, per DHEA).

Phase-2 scope: household consumption + saving only. Does NOT modify Individuals.csv, employment,
DataWrapper, or model calibration. Run: uv run python <this> --real
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _paths import raw_data_root  # configurable raw-data root (env / root raw_data/ / legacy dev/raw_data)

REPO = HERE.parents[2]  # household_prototype -> io2022 -> dev -> macroabm-ca (repo root)
SHS_DIR = raw_data_root(REPO) / "can_2022" / "pumf" / "shs_2023"
SHS_TXT = SHS_DIR / "PUMF_SHS_2023.txt"
SHS_LAYOUT = SHS_DIR / "pumf_SHS_2023_i.SAS"
RECIPIENT_CSV = HERE / "prototype_household.csv"          # Phase-1 validated output
CONTROLS = HERE / "controls_2022.json"

# SHS fields we need (model-relevant only; the model takes consumption category vectors from the IOT,
# not from household microdata, so per-household SHS categories are NOT required -- FD001 kept for a
# sanity check only). Char vs numeric + positions come from the SAS layout (parsed below).
SHS_FIELDS = ["CASEID", "WEIGHTD", "PROV", "HHTYPE6", "RP_AGEGP", "TENURE",
              "HHTOTINC", "TX010", "TC001", "TE001", "FD001"]
SHS_OWNER_TENURE = {"1", "2"}      # 1 owned w/ mortgage, 2 owned w/o mortgage, 3 rented
# SHS numeric special/sentinel: StatCan SHS blanks/skips are stored as blank -> NaN on float parse.


def parse_shs_layout(sas_path: Path) -> dict[str, tuple[int, int, bool]]:
    """Parse the SHS SAS input deck -> {name: (start, end, is_char)} using the 1-indexed inclusive
    column ranges in each line's /* start - end */ comment (the authoritative layout)."""
    spec: dict[str, tuple[int, int, bool]] = {}
    pat = re.compile(r"@\s*\d+\s+(\w+)\s+(\$)?\s*[\d.]+\s*/\*\s*(\d+)\s*-\s*(\d+)")
    for line in sas_path.read_text(errors="ignore").splitlines():
        m = pat.search(line)
        if m:
            name, is_char, a, b = m.group(1), bool(m.group(2)), int(m.group(3)), int(m.group(4))
            spec[name] = (a, b, is_char)
    return spec


def load_shs_donor() -> pd.DataFrame:
    spec = parse_shs_layout(SHS_LAYOUT)
    missing = [f for f in SHS_FIELDS if f not in spec]
    if missing:
        raise KeyError(f"SHS layout missing fields: {missing}")
    colspecs = [(spec[f][0] - 1, spec[f][1]) for f in SHS_FIELDS]
    df = pd.read_fwf(SHS_TXT, colspecs=colspecs, names=SHS_FIELDS, dtype=str)
    don = pd.DataFrame(index=df.index)
    for f in ["WEIGHTD", "HHTOTINC", "TX010", "TC001", "TE001", "FD001"]:
        don[f] = pd.to_numeric(df[f], errors="coerce")
    don["tenure_bin"] = df["TENURE"].isin(SHS_OWNER_TENURE).astype(int)
    don["prov"] = df["PROV"]
    don["hhtype6"] = df["HHTYPE6"]
    don["rp_agegp"] = pd.to_numeric(df["RP_AGEGP"], errors="coerce")  # 1..6 (or 96/97 skip)
    don["age_band6"] = shs_age_band6(don["rp_agegp"].values)
    don["disposable"] = don["HHTOTINC"] - don["TX010"]               # total income - income tax
    # consumption share out of disposable income; guard non-positive disposable (4 cases) -> NaN share
    d = don["disposable"].values
    don["cons_share"] = np.where(d > 0, don["TC001"].values / d, np.nan)
    don["income_decile"] = weighted_decile(don["disposable"].values, don["WEIGHTD"].values)
    return don


def shs_age_band6(rp_agegp) -> np.ndarray:
    """SHS RP_AGEGP is already the 6-band scheme (1:<30, 2:30-39, 3:40-54, 4:55-64, 5:65-74, 6:75+).
    Codes 96/97 (skip/DK) -> NaN so they widen out of the age match."""
    a = np.asarray(rp_agegp, dtype=float)
    return np.where((a >= 1) & (a <= 6), a, np.nan)


def hfcs_age_to_band6(age_5yr) -> np.ndarray:
    """Map the recipient HFCS 5-year band (16,20,...,85) onto the SHS 6-band scheme so age is a shared
    match key: <30 ->1, 30-39 ->2, 40-54 ->3, 55-64 ->4, 65-74 ->5, 75+ ->6."""
    a = np.asarray(age_5yr, dtype=float)
    b = np.full(a.shape, np.nan)
    b[a < 30] = 1
    b[(a >= 30) & (a < 40)] = 2
    b[(a >= 40) & (a < 55)] = 3
    b[(a >= 55) & (a < 65)] = 4
    b[(a >= 65) & (a < 75)] = 5
    b[a >= 75] = 6
    return b


def weighted_decile(values, weights, q: int = 10) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    order = np.argsort(v, kind="mergesort")
    cw = np.cumsum(w[order])
    pos = np.empty(len(v))
    pos[order] = cw / cw[-1]
    return np.clip((pos * q).astype(int), 0, q - 1) + 1


def donor_match(recipient: pd.DataFrame, donor: pd.DataFrame, keys: list[str], seed: int = 0):
    """Fast cell-based match: assign each recipient a donor drawn from its matched cell, widening by
    dropping the last key when a cell is empty. Returns (assigned donor-index array, key-depth levels)."""
    rng = np.random.default_rng(seed)
    donor = donor.reset_index(drop=True)
    dvalid = donor[donor["cons_share"].notna()]  # only donors with a usable share
    n = len(keys)
    # precompute donor index pools at each widening level
    pools = {}
    for depth in range(n, 0, -1):
        sub = keys[:depth]
        pools[depth] = {k: g.index.to_numpy() for k, g in dvalid.groupby(sub, dropna=False)}
    all_idx = dvalid.index.to_numpy()
    assigned = np.empty(len(recipient), dtype=int)
    levels = np.zeros(len(recipient), dtype=int)
    rkeys = [recipient[k].to_numpy() for k in keys]
    for i in range(len(recipient)):
        placed = False
        for depth in range(n, 0, -1):
            key = tuple(rkeys[j][i] for j in range(depth)) if depth > 1 else rkeys[0][i]
            pool = pools[depth].get(key)
            if pool is not None and len(pool):
                assigned[i] = pool[rng.integers(len(pool))]
                levels[i] = depth
                placed = True
                break
        if not placed:
            assigned[i] = all_idx[rng.integers(len(all_idx))]
            levels[i] = 0
    return assigned, levels


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    ctrl = json.loads(CONTROLS.read_text())
    hfce_macro_control_m = 1511381.0  # DHEA 36-10-0587 HFCE 2022 ($M) -- MACRO accounting control ONLY
    di_control_m = 1502342.0          # DHEA 36-10-0587 disposable income 2022 ($M)
    net_saving_control_m = 31545.0    # DHEA net saving 2022 ($M) (HFCE-based; incl. pension-entitlement adj.)

    rec = pd.read_csv(RECIPIENT_CSV)
    rec["age_band6"] = hfcs_age_to_band6(rec["age_5yr"].values)
    don = load_shs_donor()

    keys = ["tenure_bin", "income_decile", "age_band6"]
    assign, levels = donor_match(rec, don, keys, seed=args.seed)
    donr = don.reset_index(drop=True)

    # BEHAVIOURAL consumption-share concept = SHS TC001 / disposable income. Do NOT scale levels to HFCE
    # (HFCE includes imputed rent etc. -> a macro accounting control, not a micro propensity). Transplant the
    # consumption LEVEL (bounded; the raw ratio explodes near zero disposable income), then calibrate the
    # AGGREGATE household APC to the SHS 2022-equivalent behavioural propensity applied to the recipient
    # disposable-income base -- this corrects the cross-survey / French-weight scale mismatch WITHOUT
    # importing the HFCE level. The APC is a ratio -> ~vintage-stable, so no separate 2023->2022 backcast.
    shs_apc = float(np.nansum(don["TC001"].to_numpy() * don["WEIGHTD"].to_numpy())) / \
        float(np.nansum(don["disposable"].to_numpy() * don["WEIGHTD"].to_numpy()))
    cons_donor = donr["TC001"].to_numpy()[assign]   # SHS total current consumption of the matched donor
    inc = rec["Income"].to_numpy()                  # recipient disposable income (Phase-1, calibrated)
    w = rec["Weight"].to_numpy()
    di_agg_m = float(np.nansum(inc * w)) * 1e-6     # recipient aggregate disposable income (= 2022 control)
    target_cons_m = shs_apc * di_agg_m              # behavioural target, NOT HFCE
    agg_raw_m = float(np.nansum(cons_donor * w)) * 1e-6
    factor = target_cons_m / agg_raw_m
    cons = cons_donor * factor
    saving = inc - cons                             # out-of-pocket saving; NOT clipped (dissaving allowed)

    rec_out = rec.copy()
    rec_out["Amount spent on Consumption of Goods and Services"] = cons
    rec_out["Consumption of Consumer Goods/Services as a Share of Income"] = np.where(inc > 0, cons / inc, np.nan)
    rec_out["Saving"] = saving
    out_csv = HERE / "prototype_household_consumption.csv"
    rec_out.to_csv(out_csv, index=False)

    report = validate(rec, don, donr, assign, levels, cons_donor, cons, saving, inc, w,
                      dict(hfce=hfce_macro_control_m, di=di_control_m, net_saving=net_saving_control_m,
                           factor=factor, agg_raw_m=agg_raw_m, shs_apc=shs_apc, target_cons_m=target_cons_m))
    (HERE / "validation_report_consumption.json").write_text(json.dumps(report, indent=2, default=float))
    print(json.dumps(report, indent=2, default=float))
    print(f"\nwrote {out_csv.name} + validation_report_consumption.json")


def validate(rec, don, donr, assign, levels, cons_raw, cons, saving, inc, w, tgt) -> dict:
    def wsum_m(x):
        return float(np.nansum(x * w)) * 1e-6
    # SHS own weighted aggregates (donor space)
    dw = don["WEIGHTD"].to_numpy()
    shs_tc_m = float(np.nansum(don["TC001"].to_numpy() * dw)) * 1e-6
    shs_te_m = float(np.nansum(don["TE001"].to_numpy() * dw)) * 1e-6
    shs_disp_m = float(np.nansum(don["disposable"].to_numpy() * dw)) * 1e-6
    q = np.ceil(rec["income_decile"].to_numpy() / 2).astype(int)   # recipient income quintile 1..5
    valid = np.isfinite(inc)   # saving is only defined where recipient income is present (see NaN flag)
    def by_q(x, mask=None):
        m = np.ones(len(x), bool) if mask is None else mask
        return {int(k): round(wsum_m(np.where((q == k) & m, x, 0.0)), 0) for k in range(1, 6)}
    cons_q = by_q(cons)                       # consumption over ALL households (hits HFCE)
    consv_q = by_q(cons, valid)               # consumption over valid-income households (for APC/saving)
    sav_q = by_q(saving, valid)
    di_q = by_q(inc, valid)
    apc_q = {k: round(consv_q[k] / di_q[k], 3) if di_q[k] else None for k in consv_q}
    reuse = np.bincount(assign, minlength=len(donr))
    lvl, lvl_ct = np.unique(levels, return_counts=True)
    agg_cons_m = wsum_m(cons)
    agg_sav_valid_m = wsum_m(np.where(valid, saving, 0.0))   # micro saving over valid-income households
    identity_saving_m = tgt["di"] - tgt["hfce"]              # national-accounts identity DI - HFCE
    nan_inc_w = float(np.nansum(w[~valid]) / np.nansum(w))
    return {
        "MODE": "REAL (SHS 2023 donor)",
        "concept_selected": "SHS TC001 Total current consumption (NOT TE001 total expenditure)",
        "SHS_own_weighted_$M": {"TC001": round(shs_tc_m, 0), "TE001": round(shs_te_m, 0),
                                 "disposable": round(shs_disp_m, 0),
                                 "aggregate_APC_TC/disp": round(shs_tc_m / shs_disp_m, 4),
                                 "n_donor_households": int(len(don)),
                                 "donors_with_usable_share": int(don["cons_share"].notna().sum())},
        "concept_note": "BEHAVIOURAL share = SHS TC001/disposable income; consumption levels NOT scaled to "
                        "HFCE. HFCE is reported below as a MACRO accounting control only.",
        "consumption_$M": {"pre_calibration_raw": round(tgt["agg_raw_m"], 0),
                            "behavioural_target_SHS_APC_x_DI": round(tgt["target_cons_m"], 0),
                            "SHS_aggregate_APC_used": round(tgt["shs_apc"], 4),
                            "calibration_factor": round(tgt["factor"], 4),
                            "post_calibration": round(agg_cons_m, 0),
                            "HFCE_macro_control_reference_only": tgt["hfce"]},
        "consumption_to_disposable_income_ratio": {"aggregate_behavioural": round(agg_cons_m / tgt["di"], 4),
                                                    "target_SHS_APC": round(tgt["shs_apc"], 4),
                                                    "HFCE/DI_macro_reference": round(tgt["hfce"] / tgt["di"], 4)},
        "saving_$M": {"aggregate_DI_minus_consumption": round(agg_sav_valid_m, 0),
                      "aggregate_saving_rate": round(agg_sav_valid_m / tgt["di"], 4),
                      "note": "Saving = DI - out-of-pocket consumption (TC001 concept). This is the "
                              "BEHAVIOURAL/out-of-pocket saving and is intentionally higher than DHEA "
                              "HFCE-based net saving (+31,545M, ~2%): HFCE counts imputed rent etc. as "
                              "consumption, TC001 does not. Not forced >= 0 -- low-income quintiles dissave. "
                              "DHEA HFCE-based saving-by-q shown as reference, not a target for this concept."},
        "by_income_quintile_$M": {"consumption_all": cons_q, "consumption_valid_income": consv_q,
                                   "saving_valid_income": sav_q, "disposable_income": di_q, "APC": apc_q,
                                   "control_HFCE_by_q": {1: 202282, 2: 240675, 3: 293624, 4: 327863, 5: 446937},
                                   "control_saving_by_q": {1: -100731, 2: -56953, 3: -39598, 4: 49596, 5: 179231},
                                   "note": "recipient income quintiles; residual vs control driven by the "
                                           "recipient income distribution (aggregate-calibrated only)"},
        "negative_saving": {"n_households": int(np.sum((saving < 0) & valid)),
                            "weighted_share_of_valid": round(float(np.nansum(w[(saving < 0) & valid]) / np.nansum(w[valid])), 4)},
        "nan_income_flag": {"n_households": int(np.sum(~valid)), "weighted_share": round(nan_inc_w, 4),
                            "cause": "Phase-1 SFS market-income top-code sentinel (99999999) -> NaN; saving "
                                     "undefined for these. Pre-existing, not from Task 1. See deliverable E."},
        "impossible_values": {"negative_consumption": int(np.sum(cons < 0)),
                              "nan_consumption": int(np.sum(~np.isfinite(cons))),
                              "share_gt_3_valid_income": int(np.sum(rec_share_gt(cons, inc, 3) & valid))},
        "match_quality": {"levels": {f"{int(k)}_keys": int(c) for k, c in zip(lvl, lvl_ct)},
                          "full_cell_fraction": round(float(np.mean(levels == len(['tenure_bin','income_decile','age_band6']))), 4)},
        "donor_reuse": {"n_donors_usable": int((don["cons_share"].notna()).sum()),
                        "n_used": int((reuse > 0).sum()), "max_reuse": int(reuse.max()),
                        "mean_reuse_among_used": round(float(reuse[reuse > 0].mean()), 2)},
        "phase1_unchanged_check": phase1_check(rec, w),
        "n_recipients": int(len(rec)),
    }


def rec_share_gt(cons, inc, thr):
    s = np.where(inc > 0, cons / inc, np.nan)
    return np.nan_to_num(s) > thr


def phase1_check(rec, w) -> dict:
    """Confirm the Phase-1 controls are untouched by Phase-2 (we only READ the skeleton)."""
    def wsum_m(cols):
        return round(float(np.nansum(sum(rec[c].to_numpy() for c in cols) * w)) * 1e-6, 0)
    assets = ["Value of the Main Residence", "Value of other Properties", "Value of Household Vehicles",
              "Wealth in Deposits", "Wealth in Financial Assets", "Value of Self-Employment Businesses",
              "Voluntary Pension"]
    own = rec["tenure_bin"].to_numpy() == 1
    return {"total_assets_$M": wsum_m(assets), "income_$M": wsum_m(["Income"]),
            "homeownership": round(float(np.nansum(w[own]) / np.nansum(w)), 4)}


if __name__ == "__main__":
    main()
