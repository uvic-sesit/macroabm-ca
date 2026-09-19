"""Report the two alpha=0.40 robustness exercises. Reads only saved npz. No model runs.

  Exercise 1 (Taylor)  : outputs/robust_taylor_a040/{summary,annual}/seed00N.npz
                         constant-rate comparison from outputs/pub_a040_richer/summary (seeds 0-4)
                         old constant/Taylor comparison from the preliminary CSVs.
  Exercise 2 (eta)     : outputs/robust_eta_a040/summary/etaXXX.npz
                         old-eta comparison from the preliminary eta_table.csv.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TAY = HERE / "outputs" / "robust_taylor_a040"
ETA = HERE / "outputs" / "robust_eta_a040"
MAIN = HERE / "outputs" / "pub_a040_richer"          # constant-rate 10-seed package
PRELIM = REPO.parent / "macroabm-ca/dev/working_paper/preliminary"

FLOWS = ["realized_investment", "production", "real_gva", "household_consumption", "imports_row"]
SEEDS = [0, 1, 2, 3, 4]


def load(d, fname):
    z = np.load(d / fname, allow_pickle=True)
    return {k: z[k] for k in z.files}


def dlt(S, w, var, a="uc_full", b="control"):
    return float(S["%s__%s__%s" % (a, w, var)] - S["%s__%s__%s" % (b, w, var)])


def mean_over(seeds_S, w, var, a="uc_full", b="control"):
    return float(np.mean([dlt(S, w, var, a, b) for S in seeds_S]))


def channels(S, w, var):
    A = dlt(S, w, var, a="uc_noB", b="control")
    tot = dlt(S, w, var, a="uc_full", b="control")
    return A, tot - A, tot


# ============================================================ EXERCISE 1: TAYLOR
def exercise_taylor():
    ts = [f for f in [TAY / "summary" / ("seed%03d.npz" % s) for s in SEEDS] if f.exists()]
    cs = [f for f in [MAIN / "summary" / ("seed%03d.npz" % s) for s in SEEDS] if f.exists()]
    if not ts:
        print("[taylor] no outputs yet"); return
    T = [load(TAY / "summary", p.name) for p in ts]
    Cc = [load(MAIN / "summary", p.name) for p in cs]
    seeds_present = [int(S["seed"]) for S in T]
    print("=" * 78)
    print("EXERCISE 1  TAYLOR-RULE ROBUSTNESS  (alpha=0.40, eta_I=0.50, seeds %s)" % seeds_present)
    print("=" * 78)

    def table(w, label):
        print("\n--- treatment-control effect, %s ($B unless noted; 5-seed mean) ---" % label)
        print("  %-24s %10s %10s %9s" % ("variable", "Taylor", "constant", "attnu.%"))
        for var in FLOWS + ["capital_stock"]:
            t = mean_over(T, w, var)
            c = mean_over(Cc, w, var) if Cc else float("nan")
            att = 100 * (1 - t / c) if c not in (0, float("nan")) and abs(c) > 1e-9 else float("nan")
            print("  %-24s %10.2f %10.2f %9.1f" % (var, t, c, att))
        # employment (persons) and unemployment (pp)
        for var, fmt, sc in (("employed_persons", "%10.0f", 1), ("unemployment_rate", "%10.3f", 1)):
            t = mean_over(T, w, var); c = mean_over(Cc, w, var) if Cc else float("nan")
            att = 100 * (1 - t / c) if abs(c) > 1e-9 else float("nan")
            print(("  %-24s " + fmt + " " + fmt + " %9.1f") % (var, t, c, att))
        # refunds (level, treatment only)
        tr = float(np.mean([S["uc_full__%s__itc_refunds" % w] for S in T]))
        cr = float(np.mean([S["uc_full__%s__itc_refunds" % w] for S in Cc])) if Cc else float("nan")
        print("  %-24s %10.2f %10.2f" % ("gross_itc_refunds", tr, cr))

    table("w2026_30", "2026-2030 (active window)")
    table("w2031_35", "2031-2035 (post-policy)")

    # ---- channel A/B attenuation ----
    print("\n--- Channel decomposition (A=noB-ctrl, B=full-noB), 2026-2030, 5-seed mean ---")
    print("  %-14s %8s %8s %8s | %8s %8s %8s" % ("var", "Tay A", "Tay B", "Tay tot", "con A", "con B", "con tot"))
    for var in ["realized_investment", "production", "real_gva"]:
        tA, tB, tt = np.mean([channels(S, "w2026_30", var) for S in T], axis=0)
        if Cc:
            cA, cB, ct = np.mean([channels(S, "w2026_30", var) for S in Cc], axis=0)
        else:
            cA = cB = ct = float("nan")
        print("  %-14s %8.2f %8.2f %8.2f | %8.2f %8.2f %8.2f" % (var, tA, tB, tt, cA, cB, ct))

    # ---- monetary block: policy rate / lending rate / inflation index diffs ----
    print("\n--- Monetary block treatment-control diffs, 2026-2030 window-mean (5-seed mean) ---")
    for var, lab, sc in (("policy_rate", "policy rate (pp)", 100), ("firm_lending_rate", "firm lending rate (pp)", 100),
                         ("cpi", "CPI index (level)", 1), ("ppi", "PPI index (level)", 1), ("cfpi", "capital-formation PI", 1)):
        t = mean_over(T, "w2026_30", var) * sc
        c = mean_over(Cc, "w2026_30", var) * sc if Cc else float("nan")
        print("  %-24s Taylor %9.4f   constant %9.4f" % (lab, t, c))
    # absolute policy-rate LEVELS (context: Taylor moves, constant is fixed)
    print("\n--- policy-rate levels, window-mean (control vs treatment), 2026-2030 ---")
    for lab, arr in (("Taylor", T), ("constant", Cc)):
        if not arr:
            continue
        pc = float(np.mean([S["control__w2026_30__policy_rate"] for S in arr])) * 100
        pf = float(np.mean([S["uc_full__w2026_30__policy_rate"] for S in arr])) * 100
        lc = float(np.mean([S["control__w2026_30__firm_lending_rate"] for S in arr])) * 100
        lf = float(np.mean([S["uc_full__w2026_30__firm_lending_rate"] for S in arr])) * 100
        print("  %-9s policy ctrl %6.3f full %6.3f | lending ctrl %6.3f full %6.3f (pp)" % (lab, pc, pf, lc, lf))

    # ---- old-vs-new note ----
    old = PRELIM / "taylor_seed_effects_n5.csv"
    if old.exists():
        import csv
        rows = list(csv.DictReader(open(old)))
        ov = {k: np.mean([float(r[k]) for r in rows]) for k in FLOWS + ["itc_refunds"]}
        print("\n--- OLD Taylor robustness (alpha=0.30 old closure, seeds 0-4 mean) for reference ---")
        print("  " + "  ".join("%s=%.2f" % (k, ov[k]) for k in FLOWS + ["itc_refunds"]))


# ============================================================ EXERCISE 2: ETA
def exercise_eta():
    files = sorted((ETA / "summary").glob("eta*.npz"))
    if not files:
        print("\n[eta] no outputs yet"); return
    E = {}
    for f in files:
        S = load(ETA / "summary", f.name)
        E[float(S["eta"])] = S
    etas = sorted(E)
    print("\n" + "=" * 78)
    print("EXERCISE 2  eta_I SENSITIVITY  (alpha=0.40, constant rate, seed 0, eta=%s)" % etas)
    print("=" * 78)
    w = "w2026_30"
    print("\n--- 2026-2030 treatment-control effects by eta_I ($B unless noted) ---")
    hdr = "  %-6s" % "eta" + "".join("%10s" % h for h in
          ["invest", "product", "GVA", "cons", "imports", "refunds", "emp(k)", "unemp_pp"])
    print(hdr)
    for e in etas:
        S = E[e]
        row = [dlt(S, w, v) for v in FLOWS]
        ref = float(S["uc_full__%s__itc_refunds" % w])
        emp = dlt(S, w, "employed_persons") / 1000.0
        un = dlt(S, w, "unemployment_rate")
        print("  %-6.2f" % e + "".join("%10.2f" % x for x in row) + "%10.2f%10.2f%10.3f" % (ref, emp, un))

    print("\n--- response per $ gross refund, and Channel B share (2026-2030) ---")
    print("  %-6s %10s %10s %10s %10s %10s" % ("eta", "inv/ref", "gva/ref", "prod/ref", "Bshare_gva%", "Bshare_inv%"))
    for e in etas:
        S = E[e]
        ref = float(S["uc_full__%s__itc_refunds" % w])
        inv = dlt(S, w, "realized_investment"); gva = dlt(S, w, "real_gva"); prod = dlt(S, w, "production")
        Ag, Bg, tg = channels(S, w, "real_gva")
        Ai, Bi, ti = channels(S, w, "realized_investment")
        print("  %-6.2f %10.4f %10.4f %10.4f %10.1f %10.1f" %
              (e, inv / ref, gva / ref, prod / ref,
               100 * Bg / tg if abs(tg) > 1e-9 else float("nan"),
               100 * Bi / ti if abs(ti) > 1e-9 else float("nan")))

    # ---- linearity check: ratio of effect to eta ----
    print("\n--- linearity check: effect / eta (flat => linear in eta_I) ---")
    print("  %-6s %10s %10s %10s" % ("eta", "inv/eta", "gva/eta", "prod/eta"))
    for e in etas:
        S = E[e]
        print("  %-6.2f %10.2f %10.2f %10.2f" %
              (e, dlt(S, w, "realized_investment") / e, dlt(S, w, "real_gva") / e, dlt(S, w, "production") / e))

    # ---- compare with old eta table ----
    old = PRELIM / "eta_sensitivity" / "eta_table.csv"
    if old.exists():
        import csv
        rows = {float(r["eta"]): r for r in csv.DictReader(open(old))}
        print("\n--- vs OLD eta table (alpha=0.30 old closure, seed 0): GVA effect & Bshare ---")
        print("  %-6s %12s %12s %12s %12s" % ("eta", "GVA new", "GVA old", "Bsh new%", "Bsh old%"))
        for e in etas:
            S = E[e]
            Ag, Bg, tg = channels(S, w, "real_gva")
            o = rows.get(e)
            og = float(o["real_gva"]) if o else float("nan")
            obsh = float(o["Bshare"]) if o else float("nan")
            print("  %-6.2f %12.2f %12.2f %12.1f %12.1f" %
                  (e, tg, og, 100 * Bg / tg if abs(tg) > 1e-9 else float("nan"), obsh))


if __name__ == "__main__":
    exercise_taylor()
    exercise_eta()
