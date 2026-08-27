"""Mechanism trace for the broad C27/C28 scenario: rerun the IDENTICAL control+treat
cell-scale treatment (eps=1) with rich capture for the direct/indirect decomposition
and the production-network tracing. Same policy as scenario_broad (no new scenario);
adds per-cell behavioral variables and buyer-sector x seller-good flow matrices
(intermediate & capital) for customer-origin analysis and figures.

    uv run python experiments/itc/trace_edges.py run control
    uv run python experiments/itc/trace_edges.py run treat
"""
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "dev" / "io2022"))
sys.path.insert(0, str(REPO / "dev" / "validation"))
import provincial_validation_2022 as P
from macromodel.simulation import Simulation
import scenario_broad as M                                         # shares build() and compute_x()

OUT = REPO / "experiments" / "itc" / "outputs"
SEC = P.SECTOR_CODES
Q_LR = M.Q_LR
ACT0, ACT1 = 16, 35                                              # active policy window (2026-2030)
EPS = 1.0


def g(fg, fld):
    return np.asarray(fg.ts.current(fld), float)


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
                    out = out * (1.0 + EPS * M.compute_x(fg, econ))
                return out
            st.compute_target_production = wrapped
    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}
    # per-cell fields
    F = ["estdem", "pretgt", "inv_stock", "sales", "desint", "realint", "descap", "realcap", "emp", "imp"]
    CELL = {k: [] for k in F}
    # buyer-sector x seller-good national matrices (value), intermediate & capital
    MINT = []; MCAP = []; SELL = []  # SELL: per-good [total_sales, firm_int, firm_cap, row_imp]
    cells = None
    for t in range(Q_LR + 1):
        cur[0] = t
        rowc = {k: [] for k in F}
        mint = np.zeros((50, 50)); mcap = np.zeros((50, 50))
        sell = np.zeros((50, 4)); lab = []
        for c in provs:
            fg = m.countries[c].firms; econ = m.countries[c].economy.ts
            pr = np.asarray(econ.current("good_prices"), float).reshape(-1)
            ind = np.asarray(fg.states["Industry"]).reshape(-1)
            q = g(fg, "production").reshape(-1)
            tp = g(fg, "target_production").reshape(-1)
            xx = M.compute_x(fg, m.countries[c].economy)
            pretgt = np.divide(tp, 1 + EPS * xx, out=tp.copy(), where=(t >= ACT0) & (t <= ACT1))
            ed = g(fg, "estimated_demand").reshape(-1) if "estimated_demand" in fg.ts.dicts else np.full(q.size, np.nan)
            inv = g(fg, "inventory").reshape(-1)
            bint = g(fg, "real_amount_bought_as_intermediate_inputs").reshape(-1, 50)
            bcap = g(fg, "real_amount_bought_as_capital_goods").reshape(-1, 50)
            tint = g(fg, "target_intermediate_inputs").reshape(-1, 50) if "target_intermediate_inputs" in fg.ts.dicts else np.zeros((q.size, 50))
            tcap = g(fg, "unconstrained_target_capital_inputs").reshape(-1, 50)
            brow = g(fg, "real_amount_bought_from_ROW").reshape(-1, 50)
            nemp = g(fg, "number_of_employees").reshape(-1)
            rowc["estdem"].append(ed * p0[c]); rowc["pretgt"].append(pretgt * p0[c])
            rowc["inv_stock"].append(inv * p0[c]); rowc["sales"].append(q * p0[c])
            rowc["desint"].append((tint * pr[None, :]).sum(1)); rowc["realint"].append((bint * pr[None, :]).sum(1))
            rowc["descap"].append((tcap * pr[None, :]).sum(1)); rowc["realcap"].append((bcap * pr[None, :]).sum(1))
            rowc["emp"].append(nemp); rowc["imp"].append((brow * pr[None, :]).sum(1))
            # edges: buyer sector = ind[i]; seller good = column. value-weighted
            for i in range(q.size):
                mint[ind[i]] += bint[i] * pr
                mcap[ind[i]] += bcap[i] * pr
            sell[:, 0] += q * pr                      # total sales value by good
            sell[:, 1] += (bint * pr[None, :]).sum(0)  # firm intermediate demand for good
            sell[:, 2] += (bcap * pr[None, :]).sum(0)  # firm capital demand for good
            sell[:, 3] += (brow * pr[None, :]).sum(0)  # ROW imports of good
            lab += [f"{str(c)[-2:]}/{SEC[i]}" for i in range(q.size)]
        for k in F:
            CELL[k].append(np.concatenate(rowc[k]))
        MINT.append(mint); MCAP.append(mcap); SELL.append(sell)
        if cells is None:
            cells = np.array(lab)
        if t < Q_LR:
            m.iterate(t)
    np.savez_compressed(OUT / f"mvp2ctr_{cfgname}.npz", cells=cells, sectors=np.array(SEC),
                        MINT=np.array(MINT), MCAP=np.array(MCAP), SELL=np.array(SELL),
                        **{f"c_{k}": np.array(v) for k, v in CELL.items()})
    print(f"{cfgname}: saved trace")


if __name__ == "__main__":
    run(sys.argv[2] if len(sys.argv) > 2 else "control")
