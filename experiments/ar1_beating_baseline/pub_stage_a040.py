"""Definitive 10-seed ITC package for the alpha=0.40 leading specification.

Ports the publication arm-executor into the forecast clone (whose macromodel carries the
four case-7 structural changes) and reuses pub_collector.py verbatim, so the per-seed
summary/annual/cells npz schema is identical to the previous definitive package and every
existing table/figure can be regenerated.

Build per arm: richer closure (endogenous household consumption, exogenous household
investment + government target, existing price dynamics), constant policy rate, ITC design
tau=0.30 / eta_I=0.50 / C27-C28 / 2026Q1-2030Q4 / pre-stock multiplier / same refund
accounting. Only difference from the old package: the four case-7 changes + demand_smoothing
= 0.40 applied to ALL arms (they are the new structural baseline).
"""
from __future__ import annotations
import os, sys, tempfile, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault("NUMBA_CACHE_DIR", str(Path(tempfile.gettempdir()) / "macroabm_forecast_numba_cache"))
for p in [str(REPO), str(HERE), str(REPO / "experiments/itc_endogenous_closure"), str(REPO / "dev/validation")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import closure_feedback_exp as C
C.DATA_REPO = REPO.parent / "macroabm-ca"          # shared read-only reference data
import run_uc_closure_comparison as UC
import provincial_validation_2022 as P
import pub_collector as PC
import case7_itc_run as R                           # validated _apply_common_changes
from macromodel.agents.central_bank.func.policy_rate import ConstantPolicyRate

B = PC.B
PRICE_DP = 0.05
Q_RUN = 56
N_PERIODS = PC.N_PERIODS                            # 56
ALPHA = 0.40
OUT = HERE / "outputs" / "pub_a040_richer"


def _v(x):
    return np.asarray(x, float).reshape(-1)


def apply_case7_a040(model, provs):
    R._apply_common_changes(model, provs)           # four substantive case-7 changes
    for c in provs:
        model.countries[c].firms.functions["demand_estimator"].demand_smoothing = ALPHA


# ---- instrumentation (verbatim from the definitive pub_stage) ----
def install_direct_impulse(model, provs, store):
    for c in provs:
        setter = model.countries[c].firms.functions["target_capital_inputs"]
        orig = setter.compute_unconstrained_target_capital_inputs
        key = str(c)

        def wrapped(*a, _s=setter, _o=orig, _k=key, **kw):
            out = _o(*a, **kw)
            rate = _s.itc_user_cost_rate
            if rate > 0.0:
                _s.itc_user_cost_rate = 0.0
                try:
                    base = _o(*a, **kw)
                finally:
                    _s.itc_user_cost_rate = rate
                pp = _v(kw.get("previous_good_prices"))
                store[_k].append(((np.asarray(out, float) - np.asarray(base, float)) * pp[None, :]).sum(1) / B)
            else:
                store[_k].append(np.zeros(np.asarray(out, float).shape[0]))
            return out

        setter.compute_unconstrained_target_capital_inputs = wrapped


def install_recorder(model, provs):
    cache = {str(c): [] for c in provs}
    for c in provs:
        fg = model.countries[c].firms
        orig = fg.compute_estimated_demand
        key = str(c)

        def rec(current_estimated_growth, _fg=fg, _o=orig, _k=key):
            cache[_k].append(np.array(_fg.ts.current("demand"), float))
            return _o(current_estimated_growth=current_estimated_growth)

        fg.compute_estimated_demand = rec
    return cache


def install_narrow_freeze(model, provs, cache):
    ctr = {str(c): [0] for c in provs}
    for c in provs:
        fg = model.countries[c].firms
        key = str(c)

        def growth_by_firm(previous_average_good_prices, min_growth=-0.2, max_growth=0.2, _fg=fg, _k=key):
            if len(_fg.ts.historic("inventory")) == 1:
                prev_supply = _fg.ts.current("production") + _fg.ts.current("inventory")
            else:
                prev_supply = _fg.ts.current("production") + _fg.ts.prev("inventory")
            g = _fg.functions["growth_estimator"].compute_growth(
                prev_average_good_prices=previous_average_good_prices,
                prev_firm_prices=_fg.ts.current("price"),
                prev_supply=prev_supply,
                prev_demand=cache[_k][ctr[_k][0]],
                current_firm_sectors=_fg.states["Industry"])
            return np.maximum(min_growth, np.minimum(max_growth, g))

        def est_demand(current_estimated_growth, _fg=fg, _k=key):
            out = _fg.functions["demand_estimator"].compute_estimated_demand(
                previous_demand=cache[_k][ctr[_k][0]],
                current_estimated_growth=current_estimated_growth,
                estimated_growth_by_firm=_fg.ts.current("estimated_growth_by_firm"))
            ctr[_k][0] += 1
            return out

        fg.compute_estimated_growth_by_firm = growth_by_firm
        fg.compute_estimated_demand = est_demand


def build_arm(arm, seed):
    model, provs = C.build_closure_model(
        q=Q_RUN, seed=seed, price_dp=PRICE_DP, itc_rate=0.0,
        eligible_indices=C.ELIGIBLE_INDICES,
        household_investment="exogenous", government_consumption="exogenous")
    apply_case7_a040(model, provs)
    UC.set_uc_params(model, provs, treatment=(arm != "control"))
    for c in provs:
        model.countries[c].central_bank.functions["policy_rate"] = ConstantPolicyRate()
    return model, provs


def run_arm(arm, seed, cache=None, want_impulse=False):
    treat = arm != "control"
    model, provs = build_arm(arm, seed)
    rec = install_recorder(model, provs) if arm == "control" else None
    if arm == "uc_noB":
        install_narrow_freeze(model, provs, cache)
    store = {str(c): [] for c in provs}
    if want_impulse:
        install_direct_impulse(model, provs, store)
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


def run_seed(seed):
    d = OUT
    if all((d / sub / ("seed%03d.npz" % seed)).exists() for sub in ("summary", "annual", "cells")):
        print("SKIP seed %d (complete)" % seed, flush=True); return
    t0 = time.time()
    ctrl = run_arm("control", seed)
    print("  s%d control %.1fm" % (seed, (time.time() - t0) / 60), flush=True); t1 = time.time()
    full = run_arm("uc_full", seed, want_impulse=True)
    print("  s%d full %.1fm" % (seed, (time.time() - t1) / 60), flush=True); t2 = time.time()
    nob = run_arm("uc_noB", seed, cache=ctrl["cache"])
    print("  s%d no_b %.1fm" % (seed, (time.time() - t2) / 60), flush=True)

    provs = ctrl["provs"]
    cells = PC.structural_shares(ctrl["cells"], N_PERIODS, provs=provs,
                                 sector_codes=getattr(P, "SECTOR_CODES", None))
    cells.update(PC.cell_deltas(ctrl["cells"], full["cells"], N_PERIODS))
    di = full["direct_impulse"]
    yr = PC.period_years(N_PERIODS); act = (yr >= 2026) & (yr <= 2030)
    cells["direct_impulse_cum"] = di[:N_PERIODS][act].sum(0) if di is not None else np.zeros(cells["baseline_scale"].shape[0])
    cells["direct_impulse_total"] = di[:N_PERIODS].sum(0) if di is not None else np.zeros(cells["baseline_scale"].shape[0])
    n_sec = cells["baseline_scale"].shape[0] // len(provs)
    cells["cell_scale"] = np.repeat(ctrl["reg"]["region_scale"][0], n_sec)

    summ, ann = {}, {}
    for name, arm in (("control", ctrl), ("uc_full", full), ("uc_noB", nob)):
        nat = PC.national(arm["reg"])
        nat10 = PC.national(arm["reg"], regions=P.PROV10, names=provs)
        for k, v in PC.window_agg(nat, N_PERIODS).items():
            summ["%s__%s" % (name, k)] = v
        for k, v in PC.window_agg(nat10, N_PERIODS).items():
            summ["%s__prov10__%s" % (name, k)] = v
        for k, v in PC.annualize(nat, N_PERIODS).items():
            ann["%s__%s" % (name, k)] = v
        for k, v in PC.annualize(nat10, N_PERIODS).items():
            ann["%s__prov10__%s" % (name, k)] = v
        for k in PC.REG_ALL:
            ann["%s__reg__%s" % (name, k)] = arm["reg"][k]
        ann["%s__nat_q__unemployment_rate" % name] = nat["unemployment_rate"]
    summ["seed"] = seed; summ["family"] = "richer_a040"; summ["alpha"] = ALPHA
    ann["provinces"] = np.array(provs); ann["quarters"] = PC.quarter_labels(N_PERIODS)
    ann["policy_active_periods"] = ctrl["policy_active"][:N_PERIODS]

    for sub in ("summary", "annual", "cells"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "summary" / ("seed%03d.npz" % seed), **summ)
    np.savez_compressed(OUT / "annual" / ("seed%03d.npz" % seed), **ann)
    np.savez_compressed(OUT / "cells" / ("seed%03d.npz" % seed), **cells)
    print("SAVED seed %d (%.1fm total)" % (seed, (time.time() - t0) / 60), flush=True)


def main():
    seeds = range(10) if len(sys.argv) < 2 else [int(x) for x in sys.argv[1:]]
    for s in seeds:
        run_seed(s)
    print("pub_a040 package: complete", flush=True)


if __name__ == "__main__":
    main()
