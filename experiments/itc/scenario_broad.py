"""Broad C27/C28 ITC — full 2022-2035 cell-level (sector x province) scale treatment.
x_{ir,t} = TAU * planned eligible C27+C28 investment expenditure / total production cost
           (previous-quarter unconstrained target capital inputs),
Q*_{ir} *= (1 + eps * x), applied per representative firm, GATED to the 2026-2030 policy
window (quarters 16-35). Acquisition OFF, TFP OFF, credit/ROW/tech-coeff unchanged;
frozen CAN-2022 candidate baseline (tag pre-itc-validation-2026-08-22), seed 0.

    uv run python experiments/itc/scenario_broad.py run control
    uv run python experiments/itc/scenario_broad.py run treat        # eps=1 (central)
    uv run python experiments/itc/scenario_broad.py run treat 0.5    # eps sensitivity
    uv run python experiments/itc/scenario_broad.py run treat 1.5
    uv run python experiments/itc/scenario_broad.py report
"""
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))          # experiments/itc (projection)
sys.path.insert(0, str(REPO / "dev" / "io2022"))                  # save_baseline_2022, macro_data
sys.path.insert(0, str(REPO / "dev" / "validation"))              # provincial_validation_2022 (tracked baseline)
import provincial_validation_2022 as P
from macro_data import DataWrapper
from save_baseline_2022 import build_config
from macromodel.simulation import Simulation
import projection as PR                                            # shared projection utilities

OUT = REPO / "experiments" / "itc" / "outputs"

# ---- policy-specific parameters (broad C27/C28 ITC) ----
TAU = 0.30                                                        # ITC rate
ACT0, ACT1 = 16, 35                                              # active policy window (2026-2030)
E_K = [P.SECTOR_CODES.index("C27"), P.SECTOR_CODES.index("C28")]  # eligible capital goods
EPS = 1.0                                                        # scale elasticity (default; set per run)

# ---- shared projection horizon ----
Q_LR = PR.Q_LR
SEC = P.SECTOR_CODES
YEARS = {y: 16 + 4 * (y - 2026) for y in range(2026, 2036)}


def build():
    P.Q = Q_LR; orig = P._E_matrix
    P._E_matrix = lambda ok: orig(ok) * PR._qf(orig(ok).shape[0], PR.GX)[:, None, None]
    try:
        d = DataWrapper.init_from_pickle(P.PKL); provs, cfg = build_config(d, 0, Q_LR)
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
    tc = (np.asarray(fg.ts.current("total_wage"), float).reshape(-1)
          + np.asarray(fg.ts.current("used_intermediate_inputs_costs"), float).reshape(-1)
          + np.asarray(fg.ts.current("used_capital_inputs_costs"), float).reshape(-1)
          + np.asarray(fg.ts.current("taxes_paid_on_production"), float).reshape(-1))
    return np.nan_to_num(TAU * np.divide(ielig, tc, out=np.zeros_like(tc), where=tc > 0))


def run(cfgname, eps=1.0):
    global EPS
    EPS = eps
    OUT.mkdir(parents=True, exist_ok=True)
    treat = cfgname == "treat"
    m, provs = build()
    cur = [0]
    if treat:
        for c in provs:
            fg = m.countries[c].firms; econ = m.countries[c].economy
            st = fg.functions["target_production"]; orig = st.compute_target_production
            def wrapped(orig=orig, fg=fg, econ=econ, **kw):
                out = np.array(orig(**kw), float)
                if ACT0 <= cur[0] <= ACT1:
                    out = out * (1.0 + EPS * compute_x(fg, econ))
                return out
            st.compute_target_production = wrapped
    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}
    NAT = {k: [] for k in ["tprod", "prod", "gva", "inv", "Ktot", "emp", "unemp", "imp", "unmet"]}
    CX = []; CTP = []; CRP = []; CINV = []; CEMP = []; CIMP = []; cells = None
    for t in range(Q_LR + 1):
        cur[0] = t
        acc = {k: 0.0 for k in NAT if k != "unemp"}; un = []
        xs = []; tps = []; rps = []; invs = []; emps = []; imps = []; lab = []
        for c in provs:
            fg = m.countries[c].firms; econ = m.countries[c].economy.ts
            pr = np.asarray(econ.current("good_prices"), float).reshape(-1)
            q = np.asarray(fg.ts.current("production"), float).reshape(-1)
            tp = np.asarray(fg.ts.current("target_production"), float).reshape(-1)
            ui = np.asarray(fg.ts.current("used_intermediate_inputs"), float)
            rac = np.asarray(fg.ts.current("real_amount_bought_as_capital_goods"), float).reshape(-1, 50)
            brow = np.asarray(fg.ts.current("real_amount_bought_from_ROW"), float).reshape(-1, 50)
            Kst = np.asarray(fg.ts.current("capital_inputs_stock"), float).reshape(-1, 50)
            nemp = np.asarray(fg.ts.current("number_of_employees"), float).reshape(-1)
            exd = np.asarray(fg.ts.current("real_excess_demand"), float).reshape(-1)
            acc["prod"] += float((q * p0[c]).sum()) / 1e9
            acc["gva"] += (float((q * p0[c]).sum()) - (float((ui * p0[c][None, :]).sum()) if ui.ndim == 2 else 0.0)) / 1e9
            acc["tprod"] += float(np.nansum(tp * p0[c])) / 1e9
            acc["inv"] += float((rac * pr[None, :]).sum()) / 1e9
            acc["Ktot"] += float((Kst * pr[None, :]).sum()) / 1e9
            acc["imp"] += float((brow * pr[None, :]).sum()) / 1e9
            acc["unmet"] += float((exd[P.GOODS_MASK] * pr[P.GOODS_MASK]).sum()) / 1e9
            nm = np.asarray([a.name for a in m.countries[c].individuals.states["Activity Status"]])
            acc["emp"] += int((nm == "EMPLOYED").sum())
            un.append(float(np.asarray(econ.current("unemployment_rate"), float).reshape(-1)[0]) * 100)
            xs.append(compute_x(fg, m.countries[c].economy)); tps.append(tp * p0[c]); rps.append(q * p0[c])
            invs.append((rac * pr[None, :]).sum(1)); emps.append(nemp); imps.append((brow * pr[None, :]).sum(1))
            lab += [f"{str(c)[-2:]}/{SEC[i]}" for i in range(q.size)]
        for k in acc:
            NAT[k].append(acc[k])
        NAT["unemp"].append(float(np.mean(un)))
        CX.append(np.concatenate(xs)); CTP.append(np.concatenate(tps)); CRP.append(np.concatenate(rps))
        CINV.append(np.concatenate(invs)); CEMP.append(np.concatenate(emps)); CIMP.append(np.concatenate(imps))
        if cells is None:
            cells = np.array(lab)
        if t < Q_LR:
            m.iterate(t)
    suffix = "" if (cfgname == "control" or eps == 1.0) else f"_e{int(eps*10):02d}"
    np.savez_compressed(OUT / f"mvp2c_{cfgname}{suffix}.npz",
                        cells=cells, x=np.array(CX), tp=np.array(CTP), rp=np.array(CRP),
                        inv=np.array(CINV), emp=np.array(CEMP), imp=np.array(CIMP),
                        **{f"nat_{k}": np.array(v) for k, v in NAT.items()})
    print(f"{cfgname} eps={eps}: saved")


def yb(a, y):
    i = YEARS[y]; return float(np.asarray(a)[i:i + 4].mean())


def report():
    C = dict(np.load(OUT / "mvp2c_control.npz", allow_pickle=True))
    T = dict(np.load(OUT / "mvp2c_treat.npz", allow_pickle=True))
    print("=== A. NATIONAL annual (treatment - control, $B; unemp=pp, emp=agents) ===")
    rows = [("GVA", "nat_gva"), ("target prod", "nat_tprod"), ("realized prod", "nat_prod"),
            ("investment", "nat_inv"), ("capital stock", "nat_Ktot"), ("employment", "nat_emp"),
            ("unemp %", "nat_unemp"), ("imports", "nat_imp"), ("unmet", "nat_unmet")]
    yrs = list(range(2026, 2036))
    print("  " + f"{'metric':14}" + "".join(f"{y%100:>7}" for y in yrs))
    for lbl, k in rows:
        print(f"  {lbl:14}" + "".join(f"{yb(T[k], y) - yb(C[k], y):>7.2f}" for y in yrs))
    print("  " + f"{'realiz ratio':14}" + "".join(
        f"{(yb(T['nat_prod'],y)-yb(C['nat_prod'],y))/max(1e-9,(yb(T['nat_tprod'],y)-yb(C['nat_tprod'],y))):>7.2f}" for y in yrs))

    print("\n=== D/E. cell exposure-response (cum 2026-2035, active+post) ===")
    xm = T["x"][YEARS[2026]:YEARS[2030] + 4].mean(0)   # avg exposure during active window
    dtp = np.nansum(T["tp"][16:] - C["tp"][16:], 0); drp = np.nansum(T["rp"][16:] - C["rp"][16:], 0)
    base = np.nansum(C["tp"][16:], 0); rel = np.divide(dtp, base, out=np.zeros_like(dtp), where=base > 1)
    ok = base > 1
    print(f"  corr(x, relative dtarget) = {np.corrcoef(xm[ok], rel[ok])[0,1]:.3f}")
    nz = xm > 1e-9
    rr = np.divide(drp, dtp, out=np.full_like(drp, np.nan), where=np.abs(dtp) > 1e7)
    print(f"  realization ratio by exposure quartile (nonzero cells):")
    qs = np.quantile(xm[nz], [0, .25, .5, .75, 1.0])
    for lo, hi, nm in [(qs[0], qs[1], "Q1 low"), (qs[1], qs[2], "Q2"), (qs[2], qs[3], "Q3"), (qs[3], qs[4], "Q4 high")]:
        msk = nz & (xm >= lo) & (xm <= hi) & (np.abs(dtp) > 1e7)
        print(f"    {nm:8} x=[{lo:.4f},{hi:.4f}] n={int(msk.sum()):3d}  meanRealiz={np.nanmean(rr[msk]):.3f}  "
              f"sumDtgt={dtp[msk].sum()/1e9:8.2f}B sumDreal={drp[msk].sum()/1e9:8.2f}B")

    def show(idx, lbl):
        print(f"  {lbl}")
        for i in idx:
            print(f"    {str(T['cells'][i]):10} x={xm[i]:.4f} dtgt={dtp[i]/1e9:+8.3f}B dreal={drp[i]/1e9:+8.3f}B "
                  f"realiz={drp[i]/dtp[i] if abs(dtp[i])>1e7 else float('nan'):.2f}")
    print("\n=== E. top/bottom cells ===")
    show(np.argsort(dtp)[::-1][:8], "largest DIRECT target response:")
    show(np.argsort(drp)[::-1][:8], "largest REALIZED response:")
    unreal = dtp - drp
    show(np.argsort(unreal)[::-1][:8], "largest UNREALIZED response:")
    print("\n=== F. zero-exposure cells (indirect) ===")
    zero = xm <= 1e-9
    zt = dtp[zero].sum() / 1e9; zr = drp[zero].sum() / 1e9
    print(f"  zero-x cells: n={int(zero.sum())}  sumDtarget={zt:+.3f}B  sumDrealized={zr:+.3f}B")
    zi = np.where(zero)[0]
    top_ind = zi[np.argsort(np.abs(drp[zi]))[::-1][:8]]
    show(top_ind, "largest |indirect realized| among zero-exposure cells:")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "run":
        run(sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 1.0)
    else:
        report()
