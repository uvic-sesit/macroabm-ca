"""Report for the definitive 10-seed alpha=0.40 ITC package + figure-regeneration check.
Reads outputs/pub_a040_richer/{summary,annual,cells}. No model runs."""
from __future__ import annotations
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
NEW = HERE / "outputs" / "pub_a040_richer"
OLD = REPO.parent / "macroabm-ca/dev/publication_runs/richer"       # old published baseline package
OLD_SUMMARY_CSV = REPO.parent / "macroabm-ca-itc-monetary-diagnostic/experiments/itc_monetary_diagnostic/results/final_richer_uc_constant_summary.csv"
A040_SEED0 = HERE / "outputs" / "case7_itc" / "a040" / "seed000"    # earlier one-seed diagnostic


def load_summaries(d):
    out = {}
    for p in sorted((d / "summary").glob("seed*.npz")):
        z = np.load(p, allow_pickle=True)
        out[int(z["seed"])] = {k: z[k] for k in z.files}
    return out


def mm(vals):
    v = np.array([x for x in vals if np.isfinite(x)], float)
    return (float(np.mean(v)), float(np.min(v)), float(np.max(v))) if len(v) else (np.nan, np.nan, np.nan)


def delta(S, w, var, a="uc_full", b="control"):
    return [S[s][f"{a}__{w}__{var}"] - S[s][f"{b}__{w}__{var}"] for s in sorted(S)]


def show(label, vals, fmt="%.2f"):
    me, lo, hi = mm(vals)
    print(f"  {label:34s} {fmt % me}  [{fmt % lo}, {fmt % hi}]")


def main():
    S = load_summaries(NEW)
    seeds = sorted(S)
    print(f"=== DEFINITIVE alpha=0.40 package: {len(seeds)} seeds {seeds} ===")
    if not seeds:
        print("no seeds yet"); return

    # ---- active window 2026-2030 ----
    w = "w2026_30"
    print(f"\n===== ACTIVE WINDOW 2026-2030 (treatment-control; 10-seed mean [min,max]; $B unless noted) =====")
    show("desired investment", delta(S, w, "desired_investment"))
    show("realized investment", delta(S, w, "realized_investment"))
    show("capital stock gap end-2030", delta(S, w, "capital_stock"))
    show("real production", delta(S, w, "production"))
    show("real GVA", delta(S, w, "real_gva"))
    show("household consumption", delta(S, w, "household_consumption"))
    show("imports", delta(S, w, "imports_row"))
    show("gross ITC refunds", [S[s][f"uc_full__{w}__itc_refunds"] for s in seeds])
    show("employment effect (persons)", delta(S, w, "employed_persons"), "%.0f")
    show("unemployment effect (pp)", delta(S, w, "unemployment_rate"), "%.3f")

    # ---- post policy 2031-2035 ----
    w2 = "w2031_35"
    print(f"\n===== POST-POLICY 2031-2035 (treatment-control) =====")
    show("investment", delta(S, w2, "realized_investment"))
    show("production", delta(S, w2, "production"))
    show("real GVA", delta(S, w2, "real_gva"))
    show("household consumption", delta(S, w2, "household_consumption"))
    show("imports", delta(S, w2, "imports_row"))
    show("capital stock gap end-2035", delta(S, w2, "capital_stock"))
    show("employment effect (persons)", delta(S, w2, "employed_persons"), "%.0f")
    show("unemployment effect (pp)", delta(S, w2, "unemployment_rate"), "%.3f")

    # ---- channels ----
    print("\n===== CHANNEL DECOMPOSITION (A=noB-control, B=full-noB) =====")
    for wname, wl in (("2026-2030", "w2026_30"), ("2031-2035", "w2031_35")):
        print(f"  -- {wname} --")
        for var, lab in (("realized_investment", "investment"), ("production", "production"), ("real_gva", "GVA")):
            A = delta(S, wl, var, a="uc_noB", b="control")
            tot = delta(S, wl, var, a="uc_full", b="control")
            Bv = [tot[i] - A[i] for i in range(len(tot))]
            Bsh = [100 * Bv[i] / tot[i] if abs(tot[i]) > 1e-9 else np.nan for i in range(len(tot))]
            am, _, _ = mm(A); bm, _, _ = mm(Bv); sm, sl, sh = mm(Bsh)
            print(f"    {lab:11s} A={am:8.2f}  B={bm:8.2f}  Bshare={sm:5.1f}% [{sl:.1f},{sh:.1f}]")

    # ---- per-$ refund + %control-GVA ----
    print("\n===== EFFICIENCY / NORMALIZATION (2026-2030) =====")
    ref = np.array([S[s][f"uc_full__w2026_30__itc_refunds"] for s in seeds])
    for var, lab in (("realized_investment", "investment"), ("production", "production"),
                     ("real_gva", "GVA"), ("imports_row", "imports")):
        d = np.array(delta(S, "w2026_30", var))
        show(f"{lab} per $ gross refund", (d / ref).tolist(), "%.3f")
    ctlgva = np.array([S[s]["control__w2026_30__real_gva"] for s in seeds])
    dgva = np.array(delta(S, "w2026_30", "real_gva"))
    show("GVA effect as % of control GVA", (100 * dgva / ctlgva).tolist(), "%.3f")

    # ---- desired vs realized identical? ----
    print("\n===== desired vs realized investment (are they the same object?) =====")
    di = np.array([S[s]["uc_full__w2026_30__desired_investment"] for s in seeds])
    ri = np.array([S[s]["uc_full__w2026_30__realized_investment"] for s in seeds])
    print(f"  max |desired-realized| over seeds = {np.max(np.abs(di-ri)):.6g}  "
          f"({'IDENTICAL' if np.allclose(di, ri) else 'DISTINCT series'})")

    # ---- capital reversal + annual paths + dispersion (from annual npz) ----
    print("\n===== CAPITAL REVERSAL + ANNUAL PATHS =====")
    rev_any = {}
    ann_paths = {v: [] for v in ("realized_investment", "production", "real_gva", "capital_stock")}
    for s in seeds:
        z = np.load(NEW / "annual" / f"seed{s:03d}.npz", allow_pickle=True)
        capf = z["uc_full__reg__capital_stock"].sum(1); capc = z["control__reg__capital_stock"].sum(1)
        gap = capf - capc
        rev_any[s] = bool((gap[16:] < -1e-6).any())
        yrs = z["control__years"] if "control__years" in z.files else None
        for v in ann_paths:
            ann_paths[v].append(z[f"uc_full__{v}"] - z[f"control__{v}"])
    print("  treatment capital below control after 2026 (per seed):",
          {s: rev_any[s] for s in seeds})
    print("  any reversal in any seed:", any(rev_any.values()))
    zyears = np.load(NEW / "annual" / f"seed{seeds[0]:03d}.npz", allow_pickle=True)
    years = list(range(2022, 2036))
    for v, lab in (("realized_investment", "investment"), ("production", "production"),
                   ("real_gva", "GVA"), ("capital_stock", "capital")):
        arr = np.array(ann_paths[v])  # (nseed, nyears)
        m = arr.mean(0)
        # capital annual path is a stock (annualize took year-end); flows are annual sums
        print(f"  annual d_{lab:10s}: " + " ".join(f"{years[i]}:{m[i]:.1f}" for i in range(4, 14)))

    # ---- non-finite check ----
    bad = 0
    for s in seeds:
        for arm in ("control", "uc_full", "uc_noB"):
            for w_ in ("w2026_30", "w2031_35"):
                for var in ("real_gva", "production", "realized_investment", "capital_stock", "imports_row"):
                    if not np.isfinite(S[s][f"{arm}__{w_}__{var}"]):
                        bad += 1
    print(f"\n  non-finite window aggregates across all seeds/arms: {bad}")

    # ---- comparison with old published baseline ----
    print("\n===== COMPARISON vs OLD PUBLISHED BASELINE (2026-2030) =====")
    import pandas as pd
    if OLD_SUMMARY_CSV.exists():
        ob = pd.read_csv(OLD_SUMMARY_CSV); ob = ob[ob.window == "2026-2030"].iloc[0]
        pairs = [("realized investment", "realized_investment", "d_realized_investment"),
                 ("real production", "production", "d_realized_production"),
                 ("real GVA", "real_gva", "d_gva"),
                 ("household consumption", "household_consumption", "d_household_consumption"),
                 ("imports", "imports_row", "d_imports"),
                 ("gross refunds", None, "gross_itc_refunds")]
        print(f"  {'outcome':24s}{'old':>9s}{'a040':>9s}{'diff':>9s}")
        for lab, var, obk in pairs:
            if var is None:
                a = np.mean([S[s]["uc_full__w2026_30__itc_refunds"] for s in seeds])
            else:
                a = np.mean(delta(S, "w2026_30", var))
            o = float(ob[obk])
            print(f"  {lab:24s}{o:9.2f}{a:9.2f}{a-o:9.2f}")

    # ---- figure-regeneration schema check ----
    print("\n===== FIGURE-REGENERATION SCHEMA CHECK (new vs old package keys) =====")
    for sub in ("summary", "annual", "cells"):
        try:
            old = set(np.load(sorted((OLD / sub).glob("seed*.npz"))[0], allow_pickle=True).files)
            new = set(np.load(sorted((NEW / sub).glob("seed*.npz"))[0], allow_pickle=True).files)
            missing = old - new
            print(f"  {sub}: old={len(old)} new={len(new)} | missing from new: "
                  f"{sorted(missing) if missing else 'NONE (all old keys present)'}")
        except Exception as e:
            print(f"  {sub}: check failed ({e})")


if __name__ == "__main__":
    main()
