"""Short matched smoke test of the broad C27/C28 cell-level scale treatment.
x_{ir} = TAU * planned eligible C27+C28 investment expenditure / total production cost
  (prev-quarter unconstrained_target_capital_inputs; total cost = wL+interm+capital+prodtax).
Q*/Q* wedge = (1 + eps*x) applied per representative firm; eps=1. Acquisition OFF, no
TFP/credit/ROW/tech-coeff changes. Frozen CAN-2022 baseline, QH quarters (fast, no long run).
Runs control then treatment in one process and prints the comparison. Saves nothing.

    uv run python experiments/itc/smoke_test.py
"""
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "dev" / "io2022"))
sys.path.insert(0, str(REPO / "dev" / "validation"))
import provincial_validation_2022 as P
from macro_data import DataWrapper
from save_baseline_2022 import build_config
from macromodel.simulation import Simulation
import projection as PR

SEC = P.SECTOR_CODES
E_K = [P.SECTOR_CODES.index("C27"), P.SECTOR_CODES.index("C28")]   # eligible capital goods
TAU = 0.30                                                        # ITC rate
QH = 13; EPS = 1.0                                               # short horizon, eps=1


def build():
    P.Q = QH; orig = P._E_matrix
    P._E_matrix = lambda ok: orig(ok) * PR._qf(orig(ok).shape[0], PR.GX)[:, None, None]
    try:
        d = DataWrapper.init_from_pickle(P.PKL); provs, cfg = build_config(d, 0, QH)
        P.configure(cfg, provs, True)
        m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)
        P.post_build(m, provs, "candidate_prov")
        for c in provs:
            frame = m.countries[c].exogenous.national_accounts_during; n = len(frame)
            for col, g in ([(x, PR.GC) for x in P.HHC_COLS] + [(x, PR.GI) for x in P.HHI_COLS] + [(x, PR.GG) for x in P.GOV_COLS]):
                if col in frame.columns:
                    frame[col] = frame[col].values * PR._qf(n, g)
            m.countries[c].exogenous.national_accounts_during = frame
            dem = m.countries[c].individuals.functions["demography"]
            lf = np.asarray(dem.labour_force_index, float); dem.labour_force_index = list(lf * PR._qf(len(lf), PR.GL))
        P.install_external_demand(m, provs)
    finally:
        P._E_matrix = orig; P.Q = 13
    return m, provs


def compute_x(fg, econ):
    uci = np.asarray(fg.ts.current("unconstrained_target_capital_inputs"), float).reshape(-1, 50)
    pr = np.asarray(econ.ts.current("good_prices"), float).reshape(-1)
    ielig = (uci[:, E_K] * pr[E_K]).sum(1)
    tw = np.asarray(fg.ts.current("total_wage"), float).reshape(-1)
    iic = np.asarray(fg.ts.current("used_intermediate_inputs_costs"), float).reshape(-1)
    ucc = np.asarray(fg.ts.current("used_capital_inputs_costs"), float).reshape(-1)
    txp = np.asarray(fg.ts.current("taxes_paid_on_production"), float).reshape(-1)
    tc = tw + iic + ucc + txp
    x = TAU * np.divide(ielig, tc, out=np.zeros_like(tc), where=tc > 0)
    return np.nan_to_num(x)


def run(treat):
    m, provs = build()
    if treat:
        for c in provs:
            fg = m.countries[c].firms; econ = m.countries[c].economy
            st = fg.functions["target_production"]; orig = st.compute_target_production
            def wrapped(orig=orig, fg=fg, econ=econ, **kw):
                out = np.array(orig(**kw), float)
                x = compute_x(fg, econ)
                return out * (1.0 + EPS * x)
            st.compute_target_production = wrapped
    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}
    nat = {k: [] for k in ["tprod", "prod", "gva", "inv", "emp", "imp", "unmet"]}
    cell_x = []; cell_tp = []; cell_rp = []; provsec = None
    for t in range(QH + 1):
        acc = {k: 0.0 for k in nat}; xs = []; tps = []; rps = []; ps = []
        for c in provs:
            fg = m.countries[c].firms; econ = m.countries[c].economy.ts
            pr = np.asarray(econ.current("good_prices"), float).reshape(-1)
            q = np.asarray(fg.ts.current("production"), float).reshape(-1)
            tp = np.asarray(fg.ts.current("target_production"), float).reshape(-1)
            ui = np.asarray(fg.ts.current("used_intermediate_inputs"), float)
            acc["prod"] += float((q * p0[c]).sum()) / 1e9
            acc["gva"] += (float((q * p0[c]).sum()) - (float((ui * p0[c][None, :]).sum()) if ui.ndim == 2 else 0.0)) / 1e9
            acc["tprod"] += float((tp * p0[c]).sum()) / 1e9
            rac = np.asarray(fg.ts.current("real_amount_bought_as_capital_goods"), float).reshape(-1, 50)
            brow = np.asarray(fg.ts.current("real_amount_bought_from_ROW"), float).reshape(-1, 50)
            acc["inv"] += float((rac * pr[None, :]).sum()) / 1e9
            acc["imp"] += float((brow * pr[None, :]).sum()) / 1e9
            exd = np.asarray(fg.ts.current("real_excess_demand"), float).reshape(-1)
            acc["unmet"] += float((exd[P.GOODS_MASK] * pr[P.GOODS_MASK]).sum()) / 1e9
            nm = np.asarray([a.name for a in m.countries[c].individuals.states["Activity Status"]])
            acc["emp"] += int((nm == "EMPLOYED").sum())
            x = compute_x(fg, m.countries[c].economy)
            xs.append(x); tps.append(tp * p0[c]); rps.append(q * p0[c])
            ps += [f"{str(c)[-2:]}/{SEC[i]}" for i in range(len(x))]
        for k in acc:
            nat[k].append(acc[k])
        cell_x.append(np.concatenate(xs)); cell_tp.append(np.concatenate(tps)); cell_rp.append(np.concatenate(rps))
        if provsec is None:
            provsec = np.array(ps)
        if t < QH:
            m.iterate(t)
    return {k: np.array(v) for k, v in nat.items()} | {
        "x": np.array(cell_x), "tp": np.array(cell_tp), "rp": np.array(cell_rp), "cell": provsec}


def main():
    print("running control..."); C = run(False)
    print("running treatment (eps=1)..."); T = run(True)
    x = T["x"]; xmean = x.mean(0)
    print(f"\n=== EXPOSURE x across {x.shape[1]} cells (treatment, time-avg) ===")
    v = xmean; nz = v > 1e-9
    pct = np.percentile(v[nz], [0, 25, 50, 75, 100]) if nz.any() else [0] * 5
    print(f"  zero-x share = {1-nz.mean():.1%}  (nonzero) min={pct[0]:.4f} p25={pct[1]:.4f} med={pct[2]:.4f} p75={pct[3]:.4f} max={pct[4]:.4f}")
    print(f"  imposed dQ*/Q* = eps*x : same dist (eps=1). heterogeneity over time: sd of xmean={v.std():.4f}; "
          f"corr(x_t1,x_tlast)={np.corrcoef(x[1], x[-1])[0,1]:.3f}")
    print("\n=== NATIONAL treatment - control ($B; last quarter t=13) ===")
    for k in ["tprod", "prod", "gva", "inv", "imp", "unmet", "emp"]:
        d_last = T[k][-1] - C[k][-1]; d_mean = (T[k] - C[k])[1:].mean()
        u = "" if k != "emp" else " (agents)"
        print(f"  d{k:7} last={d_last:+10.3f}  mean={d_mean:+10.3f}{u}")
    dtp = (T["tprod"] - C["tprod"]); drp = (T["prod"] - C["prod"])
    print(f"  national realization dRealized/dTarget (cum t1..13) = {drp[1:].sum()/dtp[1:].sum():.3f}")
    order = np.argsort(xmean)[::-1]
    hi = order[:10]; lo = np.array([i for i in order if xmean[i] <= 1e-9][:10])
    dtp_cell = np.nansum(T["tp"][1:] - C["tp"][1:], axis=0); drp_cell = np.nansum(T["rp"][1:] - C["rp"][1:], axis=0)
    base_tp = np.nansum(C["tp"][1:], axis=0)
    rel_tp = np.divide(dtp_cell, base_tp, out=np.zeros_like(dtp_cell), where=base_tp > 1)
    ok = base_tp > 1
    print(f"\n  corr(x, relative dtarget) over cells = {np.corrcoef(xmean[ok], rel_tp[ok])[0,1]:.3f}  (n={int(ok.sum())})")
    print("\n=== MOST-exposed cells: x, dtargetSum, drealizedSum ($, cum) ===")
    for i in hi:
        rr = drp_cell[i] / dtp_cell[i] if abs(dtp_cell[i]) > 1 else float('nan')
        print(f"  {T['cell'][i]:10} x={xmean[i]:.4f}  dtgt={dtp_cell[i]/1e9:+8.3f}B  dreal={drp_cell[i]/1e9:+8.3f}B  realiz={rr:.2f}")
    print("=== ZERO-exposure cells: direct target shock should be ~0 ===")
    for i in lo:
        print(f"  {T['cell'][i]:10} x={xmean[i]:.4f}  dtgt={dtp_cell[i]/1e9:+8.4f}B  dreal={drp_cell[i]/1e9:+8.4f}B")
    zero = xmean <= 1e-9
    ind_tp = np.abs(dtp_cell[zero]).sum() / 1e9; ind_rp = np.abs(drp_cell[zero]).sum() / 1e9
    print(f"\n  ZERO-x cells aggregate |dtarget|={ind_tp:.3f}B  |drealized|={ind_rp:.3f}B  (indirect/GE if >0)")


if __name__ == "__main__":
    main()
