"""Stylized Clean Electricity ITC approximation (NOT a statutory replication).
Sector D only, 15% rate, ALL planned D capital investment treated as eligible:
x_CE_Dr = RATE * planned D capital / D production cost. Q*_Dr *= (1 + eps * x_CE),
eps=1, window 2026-2030 (quarters 16-35). Non-D firms: x=0. Acquisition OFF, same
frozen CAN-2022 baseline/architecture. Captures cell arrays + per-province D
intermediate-input vector (for the fossil B05/B06 post-analysis) + buyer-seller edges.

    uv run python experiments/itc/scenario_clean_electricity.py run control
    uv run python experiments/itc/scenario_clean_electricity.py run treat
"""
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))          # experiments/itc
sys.path.insert(0, str(REPO / "dev" / "io2022"))
sys.path.insert(0, str(REPO / "dev" / "validation"))
import provincial_validation_2022 as P
from macromodel.simulation import Simulation
import projection as PR
import scenario_broad as M                                         # shares the frozen-baseline build()

OUT = REPO / "experiments" / "itc" / "outputs"

# ---- policy-specific parameters (stylized Clean Electricity ITC) ----
RATE = 0.15                                                       # ITC rate
ACT0, ACT1 = 16, 35                                              # active policy window (2026-2030)
EPS = 1.0                                                        # scale elasticity
SEC = P.SECTOR_CODES
D_IDX = SEC.index("D")                                           # eligible sector (electricity)
B05 = SEC.index("B05"); B06 = SEC.index("B06")                  # fossil-input goods (post-analysis only)
Q_LR = PR.Q_LR


def g(fg, f): return np.asarray(fg.ts.current(f), float)


def compute_x_ce(fg, econ):
    uci = g(fg, "unconstrained_target_capital_inputs").reshape(-1, 50)
    pr = np.asarray(econ.ts.current("good_prices"), float).reshape(-1)
    planned_cap = (uci * pr[None, :]).sum(1)                     # total planned capital investment per firm
    tc = (g(fg, "total_wage").reshape(-1) + g(fg, "used_intermediate_inputs_costs").reshape(-1)
          + g(fg, "used_capital_inputs_costs").reshape(-1) + g(fg, "taxes_paid_on_production").reshape(-1))
    ind = np.asarray(fg.states["Industry"]).reshape(-1)
    x = np.zeros(planned_cap.shape[0])
    dmask = (ind == D_IDX) & (tc > 0)
    x[dmask] = RATE * planned_cap[dmask] / tc[dmask]
    return np.nan_to_num(x)


def run(cfgname):
    OUT.mkdir(parents=True, exist_ok=True)
    treat = cfgname == "treat"
    m, provs = M.build()
    cur = [0]
    if treat:
        for c in provs:
            fg = m.countries[c].firms; econ = m.countries[c].economy
            st = fg.functions["target_production"]; orig = st.compute_target_production
            def wrapped(orig=orig, fg=fg, econ=econ, **kw):
                out = np.array(orig(**kw), float)
                if ACT0 <= cur[0] <= ACT1:
                    out = out * (1.0 + EPS * compute_x_ce(fg, econ))
                return out
            st.compute_target_production = wrapped
    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}
    F = ["x", "tp", "rp", "inv", "emp", "imp"]
    CELL = {k: [] for k in F}
    NAT = {k: [] for k in ["gva", "Ktot", "unemp", "unmet"]}
    DINT = []          # (T,13,50) D-sector intermediate purchases by good, valued
    MINT = []; MCAP = []; SELL = []
    cells = None; provorder = [str(c) for c in provs]
    for t in range(Q_LR + 1):
        cur[0] = t
        rc = {k: [] for k in F}; dint = np.zeros((len(provs), 50))
        ngva = nKtot = nunmet = 0.0; unl = []
        mint = np.zeros((50, 50)); mcap = np.zeros((50, 50)); sell = np.zeros((50, 4)); lab = []
        for pi, c in enumerate(provs):
            fg = m.countries[c].firms; econ = m.countries[c].economy.ts
            pr = np.asarray(econ.current("good_prices"), float).reshape(-1)
            ind = np.asarray(fg.states["Industry"]).reshape(-1)
            q = g(fg, "production").reshape(-1); tp = g(fg, "target_production").reshape(-1)
            rac = g(fg, "real_amount_bought_as_capital_goods").reshape(-1, 50)
            bint = g(fg, "real_amount_bought_as_intermediate_inputs").reshape(-1, 50)
            brow = g(fg, "real_amount_bought_from_ROW").reshape(-1, 50)
            Kst = g(fg, "capital_inputs_stock").reshape(-1, 50)
            nemp = g(fg, "number_of_employees").reshape(-1)
            rc["x"].append(compute_x_ce(fg, m.countries[c].economy)); rc["tp"].append(tp * p0[c])
            rc["rp"].append(q * p0[c]); rc["inv"].append((rac * pr[None, :]).sum(1))
            rc["emp"].append(nemp); rc["imp"].append((brow * pr[None, :]).sum(1))
            ui = g(fg, "used_intermediate_inputs")
            ngva += (float((q * p0[c]).sum()) - (float((ui * p0[c][None, :]).sum()) if ui.ndim == 2 else 0.0)) / 1e9
            nKtot += float((Kst * pr[None, :]).sum()) / 1e9
            exd = g(fg, "real_excess_demand").reshape(-1)
            nunmet += float((exd[P.GOODS_MASK] * pr[P.GOODS_MASK]).sum()) / 1e9
            unl.append(float(np.asarray(econ.current("unemployment_rate"), float).reshape(-1)[0]) * 100)
            di = np.where(ind == D_IDX)[0]
            if di.size:
                dint[pi] = (bint[di[0]] * pr)                  # D firm intermediate purchases by good ($)
            for i in range(q.size):
                mint[ind[i]] += bint[i] * pr; mcap[ind[i]] += rac[i] * pr
            sell[:, 0] += q * pr; sell[:, 1] += (bint * pr[None, :]).sum(0)
            sell[:, 2] += (rac * pr[None, :]).sum(0); sell[:, 3] += (brow * pr[None, :]).sum(0)
            lab += [f"{str(c)[-2:]}/{SEC[i]}" for i in range(q.size)]
        for k in F:
            CELL[k].append(np.concatenate(rc[k]))
        NAT["gva"].append(ngva); NAT["Ktot"].append(nKtot); NAT["unmet"].append(nunmet); NAT["unemp"].append(float(np.mean(unl)))
        DINT.append(dint); MINT.append(mint); MCAP.append(mcap); SELL.append(sell)
        if cells is None:
            cells = np.array(lab)
        if t < Q_LR:
            m.iterate(t)
    np.savez_compressed(OUT / f"mvp2ce_{cfgname}.npz", cells=cells, sectors=np.array(SEC),
                        provorder=np.array(provorder),
                        DINT=np.array(DINT), MINT=np.array(MINT), MCAP=np.array(MCAP), SELL=np.array(SELL),
                        **{f"nat_{k}": np.array(v) for k, v in NAT.items()},
                        **{k: np.array(v) for k, v in CELL.items()})
    print(f"{cfgname}: saved CE")


if __name__ == "__main__":
    run(sys.argv[2] if len(sys.argv) > 2 else "control")
