"""Two manuscript robustness exercises on the finalized alpha=0.40 specification.

Reuses pub_stage_a040's build + instrumentation + pub_collector schema VERBATIM, adding
only two knobs: policy rule (constant / poledna-Taylor) and eta_I. Writes to isolated
directories; never touches outputs/pub_a040_richer (the main 10-seed package).

  1. taylor : seeds 0-4, Poledna(Taylor) rule, eta_I=0.50, control/full/no_B per seed.
  2. eta    : seed 0, constant rate, eta_I in {0.20,0.35,0.50,0.75,1.00}. Control run ONCE
              (eta-independent, constant rate) and its own-demand cache reused for every
              eta's no_B, so the A/B decomposition is available at each eta.

Everything else (four case-7 changes, demand_smoothing=0.40, richer closure, ITC design
tau=0.30 / C27-C28 / 2026Q1-2030Q4 / pre-stock multiplier, timing, collector) is identical
to the definitive constant-rate package.
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pub_stage_a040 as PS          # build_arm machinery, instrumentation, PC/C/UC/P/R, ALPHA
from macromodel.agents.central_bank.func.policy_rate import ConstantPolicyRate, PolednaPolicyRate

PC, C, UC, P = PS.PC, PS.C, PS.UC, PS.P
B = PS.B
Q_RUN = PS.Q_RUN
N_PERIODS = PS.N_PERIODS
_v = PS._v

TAYLOR_OUT = HERE / "outputs" / "robust_taylor_a040"
ETA_OUT = HERE / "outputs" / "robust_eta_a040"


# ---------------------------------------------------------------- build / run one arm
def build_arm(arm, seed, rule, eta):
    model, provs = C.build_closure_model(
        q=Q_RUN, seed=seed, price_dp=PS.PRICE_DP, itc_rate=0.0,
        eligible_indices=C.ELIGIBLE_INDICES,
        household_investment="exogenous", government_consumption="exogenous")
    PS.apply_case7_a040(model, provs)                     # four changes + demand_smoothing=0.40
    UC.ETA = eta                                          # eta_I for treatment arms
    UC.set_uc_params(model, provs, treatment=(arm != "control"))
    rl = PolednaPolicyRate if rule == "poledna" else ConstantPolicyRate
    for c in provs:
        model.countries[c].central_bank.functions["policy_rate"] = rl()
    return model, provs


def run_arm(arm, seed, rule, eta, cache=None, want_impulse=False):
    treat = arm != "control"
    model, provs = build_arm(arm, seed, rule, eta)
    rec = PS.install_recorder(model, provs) if arm == "control" else None
    if arm == "uc_noB":
        PS.install_narrow_freeze(model, provs, cache)
    store = {str(c): [] for c in provs}
    if want_impulse:
        PS.install_direct_impulse(model, provs, store)
    p0 = {c: _v(model.countries[c].economy.ts.current("good_prices")) for c in provs}
    gm = getattr(P, "GOODS_MASK", None)
    elig = np.asarray(C.ELIGIBLE_INDICES, int)
    reg_rows, cell_rows, names, active = [], [], None, []
    for t in range(Q_RUN + 1):
        r, cl, names = PC.collect_row(model, provs, p0, gm, elig)
        reg_rows.append(r); cell_rows.append(cl)
        if t < Q_RUN:
            act = UC.ACT0 <= t <= UC.ACT1
            active.append(act)
            UC.set_policy_active(model, provs, treatment=treat, active=act)
            model.iterate(t)
    reg = PC.stack(PC.to_periods(reg_rows), PC.REG_ALL)
    cells = PC.stack(PC.to_periods(cell_rows), PC.CELL_ALL)
    di = None
    if want_impulse:
        n_calls = min(len(v) for v in store.values())
        di = np.stack([np.concatenate([store[str(c)][k] for c in provs]) for k in range(n_calls)])
    return dict(reg=reg, cells=cells, provs=names, cache=rec, direct_impulse=di,
                policy_active=np.array(active, bool))


def _windows(name, arm, summ, ann, provs):
    nat = PC.national(arm["reg"])
    nat10 = PC.national(arm["reg"], regions=P.PROV10, names=provs)
    for k, v in PC.window_agg(nat, N_PERIODS).items():
        summ["%s__%s" % (name, k)] = v
    for k, v in PC.window_agg(nat10, N_PERIODS).items():
        summ["%s__prov10__%s" % (name, k)] = v
    for k, v in PC.annualize(nat, N_PERIODS).items():
        ann["%s__%s" % (name, k)] = v
    for k in PC.REG_ALL:
        ann["%s__reg__%s" % (name, k)] = arm["reg"][k]
    ann["%s__nat_q__unemployment_rate" % name] = nat["unemployment_rate"]


# ---------------------------------------------------------------- exercise 1: Taylor
def run_taylor_seed(seed):
    d = TAYLOR_OUT
    if all((d / sub / ("seed%03d.npz" % seed)).exists() for sub in ("summary", "annual")):
        print("SKIP taylor seed %d" % seed, flush=True); return
    t0 = time.time()
    ctrl = run_arm("control", seed, "poledna", 0.50)  # eta ignored for control arm
    print("  taylor s%d control %.1fm" % (seed, (time.time() - t0) / 60), flush=True)
    full = run_arm("uc_full", seed, "poledna", 0.50)
    print("  taylor s%d full %.1fm" % (seed, (time.time() - t0) / 60), flush=True)
    nob = run_arm("uc_noB", seed, "poledna", 0.50, cache=ctrl["cache"])
    print("  taylor s%d no_b %.1fm" % (seed, (time.time() - t0) / 60), flush=True)
    provs = ctrl["provs"]
    summ, ann = {}, {}
    for name, arm in (("control", ctrl), ("uc_full", full), ("uc_noB", nob)):
        _windows(name, arm, summ, ann, provs)
    summ["seed"] = seed; summ["family"] = "taylor_a040"; summ["alpha"] = PS.ALPHA; summ["eta"] = 0.50
    ann["provinces"] = np.array(provs); ann["quarters"] = PC.quarter_labels(N_PERIODS)
    ann["policy_active_periods"] = ctrl["policy_active"][:N_PERIODS]
    for sub in ("summary", "annual"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / "summary" / ("seed%03d.npz" % seed), **summ)
    np.savez_compressed(d / "annual" / ("seed%03d.npz" % seed), **ann)
    print("SAVED taylor seed %d (%.1fm)" % (seed, (time.time() - t0) / 60), flush=True)


# ---------------------------------------------------------------- exercise 2: eta sweep
ETAS = (0.20, 0.35, 0.50, 0.75, 1.00)


def run_eta_sweep(seed=0):
    d = ETA_OUT
    (d / "summary").mkdir(parents=True, exist_ok=True)
    # ---- control ONCE (constant rate, eta-independent); reuse its cache for every no_B ----
    t0 = time.time()
    ctrl = run_arm("control", seed, "constant", 0.50)
    print("  eta control %.1fm" % ((time.time() - t0) / 60), flush=True)
    provs = ctrl["provs"]
    for eta in ETAS:
        tag = "eta%03d" % int(round(eta * 100))
        p = d / "summary" / ("%s.npz" % tag)
        if p.exists():
            print("SKIP %s" % tag, flush=True); continue
        te = time.time()
        full = run_arm("uc_full", seed, "constant", eta)
        nob = run_arm("uc_noB", seed, "constant", eta, cache=ctrl["cache"])
        summ = {}
        for name, arm in (("control", ctrl), ("uc_full", full), ("uc_noB", nob)):
            a2 = {}
            _windows(name, arm, summ, a2, provs)
        summ["seed"] = seed; summ["family"] = "eta_a040"; summ["alpha"] = PS.ALPHA; summ["eta"] = eta
        np.savez_compressed(p, **summ)
        print("SAVED %s (%.1fm)" % (tag, (time.time() - te) / 60), flush=True)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("taylor", "all"):
        for s in range(5):
            run_taylor_seed(s)
    if which in ("eta", "all"):
        run_eta_sweep(0)
    print("robustness_a040 complete", flush=True)


if __name__ == "__main__":
    main()
