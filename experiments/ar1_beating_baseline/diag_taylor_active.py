"""Saved-output-only consistency check: Taylor vs constant, 2026-2030 ONLY. Read-only."""
import numpy as np
from pathlib import Path
np.set_printoptions(suppress=True, linewidth=200)
HERE = Path(__file__).resolve().parent
TAY = HERE / "outputs" / "robust_taylor_a040"
CON = HERE / "outputs" / "pub_a040_richer"
SEEDS = [0, 1, 2, 3, 4]
W = "w2026_30"
P16, P36 = 16, 36                       # active window periods (2026Q1..2030Q4 = 16..35)

FIN = ["realized_investment", "household_consumption", "imports_row",
       "production", "real_gva", "intermediate_use", "exports_row_goods",
       "exports_row_services", "government_realized_purchases", "unmet_demand", "total_wage"]


def summ(d, s):
    z = np.load(d / "summary" / f"seed{s:03d}.npz", allow_pickle=True)
    return {k: z[k] for k in z.files}


def dwin(S, var, a="uc_full", b="control"):
    return float(S[f"{a}__{W}__{var}"] - S[f"{b}__{W}__{var}"])


def natq(d, s, arm, var):
    a = np.load(d / "annual" / f"seed{s:03d}.npz", allow_pickle=True)
    return a[f"{arm}__reg__{var}"].sum(1)          # national quarterly (56)


def natq_wpr(d, s, arm, idx):                       # consumption-weighted price index
    a = np.load(d / "annual" / f"seed{s:03d}.npz", allow_pickle=True)
    w = a[f"{arm}__reg__household_consumption"]; x = a[f"{arm}__reg__{idx}"]
    ws = w.sum(1); return np.where(ws > 0, (x * w).sum(1) / np.where(ws > 0, ws, 1), np.nan)


def natq_rate(d, s, arm, var):                      # simple regional mean rate
    a = np.load(d / "annual" / f"seed{s:03d}.npz", allow_pickle=True)
    return np.nanmean(a[f"{arm}__reg__{var}"], axis=1)


def natq_persons(d, s, arm, _var=None):             # employed agents x region_scale -> persons
    a = np.load(d / "annual" / f"seed{s:03d}.npz", allow_pickle=True)
    return (a[f"{arm}__reg__employed_agents"] * a[f"{arm}__reg__region_scale"]).sum(1)


def natq_urate(d, s, arm, _var=None):               # saved national quarterly unemployment rate
    a = np.load(d / "annual" / f"seed{s:03d}.npz", allow_pickle=True)
    return a[f"{arm}__nat_q__unemployment_rate"]


# ---------- 1. per-seed sign consistency (is the pattern robust or noise?) ----------
print("=" * 96)
print("1. PER-SEED treatment-control active-window (2026-2030) effect, Taylor vs constant")
Tay = {s: summ(TAY, s) for s in SEEDS}
Con = {s: summ(CON, s) for s in SEEDS}
for var in ["realized_investment", "household_consumption", "production", "real_gva",
            "imports_row", "intermediate_use", "employed_persons", "unemployment_rate"]:
    t = [dwin(Tay[s], var) for s in SEEDS]; c = [dwin(Con[s], var) for s in SEEDS]
    print(f"  {var:22s} Tay {np.mean(t):9.2f} per-seed[{' '.join(f'{x:7.1f}' for x in t)}]")
    print(f"  {'':22s} con {np.mean(c):9.2f} per-seed[{' '.join(f'{x:7.1f}' for x in c)}]")

# ---------- 2. supply=use accounting identity (levels, window sums, both regimes) ----------
print("\n" + "=" * 96)
print("2. SUPPLY-USE IDENTITY check (window-sum levels): production+imports vs interm+C+I+G+X")
for name, d in (("TAYLOR", TAY), ("CONSTANT", CON)):
    for arm in ("control", "uc_full"):
        def wl(v):
            return np.mean([float((Tay if name == "TAYLOR" else Con)[s][f"{arm}__{W}__{v}"]) for s in SEEDS])
        supply = wl("production") + wl("imports_row")
        use = (wl("intermediate_use") + wl("household_consumption") + wl("realized_investment")
               + wl("government_realized_purchases") + wl("exports_row_goods") + wl("exports_row_services"))
        print(f"  {name:9s} {arm:8s} supply(prod+imp)={supply:11.1f}  use(int+C+I+G+X)={use:11.1f}"
              f"  resid={supply-use:9.1f}  ({100*(supply-use)/supply:5.2f}%)")

# ---------- 3. decompose the treatment-control PRODUCTION effect by use component ----------
print("\n" + "=" * 96)
print("3. WHERE does the treatment-control effect go? (window-sum, treatment-control, 5-seed mean)")
print(f"  {'component':30s} {'TAYLOR':>10s} {'CONSTANT':>10s}")
for v in ["production", "real_gva", "intermediate_use", "household_consumption",
          "realized_investment", "government_realized_purchases", "exports_row_goods",
          "exports_row_services", "imports_row", "unmet_demand", "total_wage"]:
    t = np.mean([dwin(Tay[s], v) for s in SEEDS]); c = np.mean([dwin(Con[s], v) for s in SEEDS])
    print(f"  {v:30s} {t:10.2f} {c:10.2f}")
# identity on the DELTAS: d_production + d_imports  ?=  d_interm + d_C + d_I + d_G + d_X
for name, D in (("TAYLOR", Tay), ("CONSTANT", Con)):
    def dd(v): return np.mean([dwin(D[s], v) for s in SEEDS])
    lhs = dd("production") + dd("imports_row")
    rhs = (dd("intermediate_use") + dd("household_consumption") + dd("realized_investment")
           + dd("government_realized_purchases") + dd("exports_row_goods") + dd("exports_row_services"))
    print(f"  [{name}] d(prod+imp)={lhs:8.2f}  d(int+C+I+G+X)={rhs:8.2f}  gap={lhs-rhs:7.2f}")

# ---------- 4. quarterly treatment-control paths, active window, 5-seed mean ----------
print("\n" + "=" * 96)
print("4. QUARTERLY treatment-control (full-control), 5-seed mean, periods 16-35 (2026Q1-2030Q4)")


def qmean(d, var, kind="flow"):
    fn = {"flow": natq, "price": natq_wpr, "rate": natq_rate,
          "persons": natq_persons, "urate": natq_urate}[kind]
    F = np.mean([fn(d, s, "uc_full", var) for s in SEEDS], axis=0)
    C_ = np.mean([fn(d, s, "control", var) for s in SEEDS], axis=0)
    return (F - C_)[P16:P36]


qs = [str(x) for x in np.load(TAY / "annual" / "seed000.npz", allow_pickle=True)["quarters"][P16:P36]]
for var, kind in (("production", "flow"), ("real_gva", "flow"), ("realized_investment", "flow"),
                  ("household_consumption", "flow"), ("imports_row", "flow"),
                  ("intermediate_use", "flow"), ("employed_persons", "persons"),
                  ("unemployment_rate", "urate")):
    t = qmean(TAY, var, kind); c = qmean(CON, var, kind)
    print(f"\n  {var} (Taylor row then constant row):")
    print("   T " + " ".join(f"{x:6.1f}" for x in t))
    print("   C " + " ".join(f"{x:6.1f}" for x in c))
print("\n  quarters: " + " ".join(f"{q:>6s}" for q in qs))

# prices and rates: treatment-control quarterly, window mean
print("\n" + "=" * 96)
print("5. PRICES & RATES treatment-control, window-mean over 2026-2030 (5-seed mean)")
for var, kind, sc in (("cpi", "price", 1), ("ppi", "price", 1), ("cfpi", "price", 1),
                      ("policy_rate", "rate", 100), ("firm_lending_rate", "rate", 100)):
    t = np.nanmean(qmean(TAY, var, kind)) * sc; c = np.nanmean(qmean(CON, var, kind)) * sc
    print(f"  {var:20s} Taylor {t:9.4f}   constant {c:9.4f}   (units: {'pp' if sc==100 else 'index level'})")

# ---------- 6. A/B decomposition quarterly, active window ----------
print("\n" + "=" * 96)
print("6. CHANNEL A/B window-sum (A=noB-ctrl, B=full-noB), 5-seed mean, 2026-2030")
for var in ["production", "real_gva", "realized_investment", "household_consumption",
            "intermediate_use", "imports_row"]:
    for name, D in (("TAYLOR", Tay), ("CONSTANT", Con)):
        A = np.mean([dwin(D[s], var, "uc_noB", "control") for s in SEEDS])
        tot = np.mean([dwin(D[s], var, "uc_full", "control") for s in SEEDS])
        print(f"  {var:22s} {name:9s} A={A:8.2f}  B={tot-A:8.2f}  tot={tot:8.2f}")
