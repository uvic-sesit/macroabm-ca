"""Provincial/meso validation: control vs candidate, per-region real GVA / employment /
unemployment, aligned to 2023 & 2024, vs StatCan 36-10-0402 (real GVA) + 14-10-0327 (LFS).

Compute rule: one seed each (control, candidate); no new 5-seed battery.

    uv run python dev/validation/provincial_validation_2022.py run --config control --seed 0
    uv run python dev/validation/provincial_validation_2022.py run --config candidate --seed 0
    uv run python dev/validation/provincial_validation_2022.py report
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "dev" / "io2022"))
sys.path.insert(0, str(REPO / "dev" / "validation"))
from macro_data import DataWrapper
from macromodel.simulation import Simulation
from save_baseline_2022 import build_config
from growth_mechanism_retest_2022 import labour_index_2022

PKL = REPO / "dev" / "pkl_files" / "io2022_13prov_2022_canadianized.pkl"
OUT = REPO / "dev" / "validation" / "prov_2022"
Q = 13
HH_GROWTH = 0.02
PROV10 = ["CAN_NL", "CAN_PE", "CAN_NS", "CAN_NB", "CAN_QC", "CAN_ON", "CAN_MB", "CAN_SK", "CAN_AB", "CAN_BC"]
GEO = {"CAN_NL": "Newfoundland and Labrador", "CAN_PE": "Prince Edward Island", "CAN_NS": "Nova Scotia",
       "CAN_NB": "New Brunswick", "CAN_QC": "Quebec", "CAN_ON": "Ontario", "CAN_MB": "Manitoba",
       "CAN_SK": "Saskatchewan", "CAN_AB": "Alberta", "CAN_BC": "British Columbia"}


# ---------- Step 1: province-specific observed demand-growth paths (36-10-0222, chained 2017$) ----------
# Maps each region's exogenous HH-consumption / Government-consumption / HH-investment (residential)
# level path to the OBSERVED provincial annual real growth 2022->2023 and 2022->2024.
_PROV222 = {
    "HHC": "Household final consumption expenditure",
    "GOV": "General governments final consumption expenditure",
    "HHI": "Residential structures",
}


def prov_demand_growth():
    """{region: {'HHC':(g23,g24),'GOV':(...),'HHI':(...)}} real annual growth fractions from 36-10-0222."""
    d = pd.read_csv(REPO / "dev" / "statcan" / "36100222.csv", low_memory=False)
    d = d[d.Prices == "Chained (2017) dollars"]
    out = {p: {} for p in PROV10}
    for key, est in _PROV222.items():
        piv = d[d.Estimates == est].pivot_table(index="GEO", columns="REF_DATE", values="VALUE", aggfunc="first")
        for p in PROV10:
            v22, v23, v24 = piv.loc[GEO[p], 2022], piv.loc[GEO[p], 2023], piv.loc[GEO[p], 2024]
            out[p][key] = (v23 / v22 - 1.0, v24 / v22 - 1.0)
    return out


def _block_factor(nrows, g23, g24):
    """Per-quarter multiplier on the base level path: annual blocks 2022=1, 2023=1+g23, 2024/25=1+g24."""
    fac = np.ones(nrows)
    if nrows > 4:
        fac[4:min(8, nrows)] = 1.0 + g23
    if nrows > 8:
        fac[8:nrows] = 1.0 + g24
    return fac


def configure(cfg, provs, candidate: bool):
    if not candidate:
        return
    lf = labour_index_2022(Q)
    for c in provs:
        cc = cfg.country_configurations[c]
        cc.firms.functions.demand_estimator.parameters.update(
            {"firm_growth_adjustment_speed": 1.0, "sectoral_growth_adjustment_speed": 1.0, "demand_smoothing": 0.3})
        cc.firms.functions.demand_for_goods.parameters.update({"unmet_demand_weight": 0.25})
        cc.firms.functions.excess_demand.parameters.update({"consider_capital_inputs": 0.0})
        cc.firms.functions.target_capital_inputs.parameters.update(
            {"rolling_reference": True, "target_capital_inputs_fraction": 0.1, "credit_gap_fraction": 0.0})
        if str(c) in lf:
            cc.individuals.functions.demography.name = "ExogenousLabourForcePath"
            cc.individuals.functions.demography.parameters = {"labour_force_index": lf[str(c)]}
        cc.government_entities.functions.consumption.name = "ExogenousGovernmentConsumptionSetter"
        cc.households.functions.consumption.name = "ExogenousHouseholdConsumption"
        cc.households.functions.investment.name = "ExogenousHouseholdInvestment"


HHC_COLS = ["Real Household Consumption (Value)", "Household Consumption (Value)"]
HHI_COLS = ["Real Household Investment (Value)", "Household Investment (Value)"]
GOV_COLS = ["Real Government Consumption (Value)", "Government Consumption (Value)"]

# 50 OECD/ISIC sector codes (model industry order). Goods = A/B/C/D/E; services = F..T.
SECTOR_CODES = ["A01", "A02", "A03", "B05", "B06", "B07", "B08", "B09", "C10T12", "C13T15", "C16",
                "C17_18", "C19", "C20", "C21", "C22", "C23", "C24A", "C24B", "C25", "C26", "C27",
                "C28", "C29", "C301", "C302T309", "C31T33", "D", "E", "F", "G", "H49", "H50", "H51",
                "H52", "H53", "I", "J58T60", "J61", "J62_63", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"]
GOODS_MASK = np.array([c[0] in "ABCDE" for c in SECTOR_CODES])  # True = goods (merchandise)


# ---------- Step 2: province × {goods,services} international external-demand index E[p,grp,t] ----------
# Source: 36-10-0222 chained-2017$ 'Exports of goods/services to other countries', per province.
def prov_export_growth():
    """{region: {'goods':(g23,g24),'services':(g23,g24)}} real annual growth fractions."""
    d = pd.read_csv(REPO / "dev" / "statcan" / "36100222.csv", low_memory=False)
    d = d[d.Prices == "Chained (2017) dollars"]
    ests = {"goods": "Exports of goods to other countries", "services": "Exports of services to other countries"}
    out = {p: {} for p in PROV10}
    for key, est in ests.items():
        piv = d[d.Estimates == est].pivot_table(index="GEO", columns="REF_DATE", values="VALUE", aggfunc="first")
        for p in PROV10:
            v22, v23, v24 = piv.loc[GEO[p], 2022], piv.loc[GEO[p], 2023], piv.loc[GEO[p], 2024]
            out[p][key] = (v23 / v22 - 1.0, v24 / v22 - 1.0)
    return out


def _E_matrix(order_keys):
    """Emat[t] shape (n_countries, n_industries): external-demand index per origin (province) per sector.
    Annual blocks: t0-3=2022(=1), 4-7=2023, 8-11=2024, 12-13=2024. Non-PROV10 origins & ROW = 1."""
    pg = prov_export_growth()
    nC = len(order_keys); nS = len(SECTOR_CODES)
    Emat = np.ones((Q + 1, nC, nS))
    def block_val(g23, g24, t):
        return 1.0 if t < 4 else (1.0 + g23) if t < 8 else (1.0 + g24)
    for ci, key in enumerate(order_keys):
        if key not in pg:
            continue
        gg = pg[key]["goods"]; gs = pg[key]["services"]
        for t in range(Q + 1):
            Emat[t, ci, GOODS_MASK] = block_val(*gg, t)
            Emat[t, ci, ~GOODS_MASK] = block_val(*gs, t)
    return Emat


def install_external_demand(m, provs):
    """Option A: absolute province-specific ROW export demand via the existing province->ROW legs.
    (1) scale ROW national import demand by F[s,t]=sum_p base_prop[p,ROW,s]*E[p,grp,t];
    (2) set origin_trade_proportions[:,ROW,:] to E-adjusted shares base_prop*E/F.
    Together the (p,ROW) leg demand = base_desired[s]*base_prop[p,ROW,s]*E[p,grp,t] (absolute).
    Only the [:,ROW,:] column is touched; interprovincial legs untouched; E==1 => identity."""
    gm = m.goods_market; ri = gm.row_index; row = m.rest_of_the_world
    order_keys = list(gm.goods_market_participants.keys())          # origin/participant order for the axis
    assert m.countries[provs[0]].firms.n_industries == len(SECTOR_CODES)
    base_prop = np.asarray(gm.states["origin_trade_proportions"][:, ri, :]).copy()   # (nC, nS)
    Emat = _E_matrix(order_keys)                                    # (T, nC, nS)
    T = Q + 1
    Fmat = np.einsum("ps,tps->ts", base_prop, Emat)                 # (T, nS) national scale per sector
    Fsafe = np.where(Fmat > 0, Fmat, 1.0)
    PROPmat = (base_prop[None] * Emat) / Fsafe[:, None, :]          # (T, nC, nS), columns sum to 1

    orig_imports = row.functions["imports"]

    class _ImportsW:  # scale ROW national demand by F[:,t]
        def compute_imports(self, **kw):
            base = orig_imports.compute_imports(**kw)
            t = min(int(kw["current_time"]), T - 1)
            return base * Fmat[t]
        def __getattr__(self, a):
            return getattr(orig_imports, a)
    row.functions["imports"] = _ImportsW()

    clr = gm.functions["clearing"]
    orig_clear = clr.clear

    def wrapped_clear(**kw):  # pass a writable copy with E-adjusted ROW column for current t (state is read-only)
        t = min(len(row.ts.historic("total_exports")), T - 1)
        otp = np.array(kw["default_origin_trade_proportions"], copy=True)
        otp[:, ri, :] = PROPmat[t]
        kw["default_origin_trade_proportions"] = otp
        return orig_clear(**kw)
    clr.clear = wrapped_clear


def post_build(m, provs, config: str):
    if config == "control":
        return
    pg = prov_demand_growth() if config == "candidate_prov" else None
    for c in provs:
        exog = m.countries[c].exogenous
        frame = exog.national_accounts_during.copy()
        if len(frame) < Q + 1:
            last = frame.index[-1]
            ext = pd.DataFrame([frame.iloc[-1].copy() for _ in range(Q + 1 - len(frame))],
                               index=[last + pd.DateOffset(months=3 * (k + 1)) for k in range(Q + 1 - len(frame))])
            frame = pd.concat([frame, ext], axis=0)
        n = len(frame)
        if config == "candidate_prov" and str(c) in pg:
            # B: observed province-specific real growth on HH consumption, government, HH investment
            gr = pg[str(c)]
            groups = [(HHC_COLS, _block_factor(n, *gr["HHC"])),
                      (GOV_COLS, _block_factor(n, *gr["GOV"])),
                      (HHI_COLS, _block_factor(n, *gr["HHI"]))]
        else:
            # A (and non-scored regions under B): common uniform +2%/yr overlay on HH cons + investment
            fac = (1.0 + HH_GROWTH) ** (np.arange(n) / 4.0)
            groups = [(HHC_COLS, fac), (HHI_COLS, fac)]
        for cols, fac in groups:
            for col in cols:
                if col in frame.columns:
                    frame[col] = frame[col].values * fac
        exog.national_accounts_during = frame


def run(config: str, seed: int):
    OUT.mkdir(parents=True, exist_ok=True)
    d = DataWrapper.init_from_pickle(PKL)
    provs, cfg = build_config(d, seed, Q)
    cand = config in ("candidate", "candidate_prov", "candidate_ext")
    configure(cfg, provs, cand)
    m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)
    demand_cfg = "candidate_prov" if config == "candidate_ext" else config
    post_build(m, provs, demand_cfg)
    if config == "candidate_ext":
        install_external_demand(m, provs)
    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in provs}
    order = [str(c) for c in provs]

    def snap():
        rg, em, un, xg, xs = {}, {}, {}, {}, {}
        for c in provs:
            f = m.countries[c].firms
            q = np.array(f.ts.current("production"), float); ui = np.array(f.ts.current("used_intermediate_inputs"), float)
            rg[str(c)] = (float((q * p0[c]).sum()) - (float((ui * p0[c][None, :]).sum()) if ui.ndim == 2 else 0.0)) / 1e9
            nm = np.asarray([x.name for x in m.countries[c].individuals.states["Activity Status"]])
            em[str(c)] = int((nm == "EMPLOYED").sum())
            un[str(c)] = float(np.asarray(m.countries[c].economy.ts.current("unemployment_rate"), float).reshape(-1)[0]) * 100
            xr = np.asarray(m.countries[c].economy.ts.current("exports_before_taxes_to_ROW"), float).reshape(-1)
            xg[str(c)] = float(xr[GOODS_MASK].sum()) / 1e9; xs[str(c)] = float(xr[~GOODS_MASK].sum()) / 1e9
        return rg, em, un, xg, xs

    R = {k: [] for k in order}; E = {k: [] for k in order}; U = {k: [] for k in order}
    XG = {k: [] for k in order}; XS = {k: [] for k in order}
    for t in range(Q + 1):
        rg, em, un, xg, xs = snap()
        for k in order:
            R[k].append(rg[k]); E[k].append(em[k]); U[k].append(un[k]); XG[k].append(xg[k]); XS[k].append(xs[k])
        if t < Q:
            m.iterate(t)
    reg = np.array(order)
    np.savez_compressed(OUT / f"prov_{config}_s{seed}.npz",
                        regions=reg, rgva=np.array([R[k] for k in order]),
                        emp=np.array([E[k] for k in order]), unemp=np.array([U[k] for k in order]),
                        xrow_goods=np.array([XG[k] for k in order]), xrow_serv=np.array([XS[k] for k in order]))
    print(f"{config} s{seed}: saved {len(order)} regions x {Q+1} q")


# ---------- observed ----------
def observed():
    # real provincial GVA (36-10-0402, chained, all industries)
    g = pd.read_csv(REPO / "dev" / "statcan" / "36100402.csv", low_memory=False)
    est_col = "North American Industry Classification System (NAICS)" if "North American Industry Classification System (NAICS)" in g.columns else None
    gv = g[(g["Prices"].astype(str).str.contains("hained", na=False))]
    ind = "All industries [T001]"
    icol = [c for c in gv.columns if "NAICS" in c or "Industry" in c]
    icol = icol[0] if icol else None
    if icol:
        gv = gv[gv[icol].astype(str).str.startswith("All industries")]
    gv = gv[gv.REF_DATE.isin([2022, 2023, 2024])]
    gva = gv.pivot_table(index="GEO", columns="REF_DATE", values="VALUE", aggfunc="first")
    # LFS employment + unemployment (14-10-0327, annual)
    l = pd.read_csv(REPO / "dev" / "statcan" / "14100327.csv", low_memory=False)
    l = l[(l["Age group"] == "15 years and over") & (l["Gender"] == "Total - Gender") & (l.REF_DATE.isin([2022, 2023, 2024]))]
    emp = l[l["Labour force characteristics"] == "Employment"].pivot_table(index="GEO", columns="REF_DATE", values="VALUE", aggfunc="first")
    un = l[(l["Labour force characteristics"] == "Unemployment rate") & (l.UOM == "Percent")].pivot_table(index="GEO", columns="REF_DATE", values="VALUE", aggfunc="first")
    return gva, emp, un


def report():
    cf = {c: np.load(OUT / f"prov_{c}_s0.npz", allow_pickle=True) for c in ("control", "candidate") if (OUT / f"prov_{c}_s0.npz").exists()}
    if len(cf) < 2:
        print("need both control & candidate runs"); return
    gva_o, emp_o, un_o = observed()

    def blk(a, i):  # per-region annual-block growth vs 2022 for horizon year i (2023 or 2024)
        y22 = a[:, 0:4].mean(1); yb = a[:, {2023: slice(4, 8), 2024: slice(8, 12)}[i]].mean(1)
        return (yb / y22 - 1) * 100

    def blk_un(a, i):  # unemployment-rate CHANGE (pp) vs 2022
        return a[:, {2023: slice(4, 8), 2024: slice(8, 12)}[i]].mean(1) - a[:, 0:4].mean(1)

    from scipy.stats import spearmanr
    print("Provincial validation (10 provinces, seed 0), horizon 2022->2024\n")
    for cfg in ("control", "candidate"):
        z = cf[cfg]; regs = list(z["regions"]); idx = [regs.index(p) for p in PROV10]
        mg = blk(z["rgva"], 2024)[idx]; me = blk(z["emp"], 2024)[idx]; mu = blk_un(z["unemp"], 2024)[idx]
        og = np.array([gva_o.loc[GEO[p], 2024] / gva_o.loc[GEO[p], 2022] - 1 for p in PROV10]) * 100
        oe = np.array([emp_o.loc[GEO[p], 2024] / emp_o.loc[GEO[p], 2022] - 1 for p in PROV10]) * 100
        ou = np.array([un_o.loc[GEO[p], 2024] - un_o.loc[GEO[p], 2022] for p in PROV10])
        sign = np.mean(np.sign(mg) == np.sign(og))
        rho = spearmanr(mg, og).correlation
        print(f"=== {cfg.upper()} : real GVA growth 2022->2024 (%) ===")
        print(f"  {'prov':7}{'obs':>7}{'model':>7}{'err':>7}")
        for j, p in enumerate(PROV10):
            print(f"  {p:7}{og[j]:>+7.1f}{mg[j]:>+7.1f}{mg[j]-og[j]:>+7.1f}")
        print(f"  sign-match {sign:.0%}  Spearman {rho:+.2f}  disp sd model {np.std(mg):.2f} vs obs {np.std(og):.2f}")
        # national contribution / offsetting
        w = np.array([gva_o.loc[GEO[p], 2022] for p in PROV10]); w = w / w.sum()
        net = float(np.sum(w * (mg - og))); gross = float(np.sum(w * np.abs(mg - og)))
        print(f"  weighted net GVA-growth error {net:+.2f}pp  gross {gross:.2f}pp  offset {1-abs(net)/gross:.0%}")
        print(f"  employment sign-match {np.mean(np.sign(me)==np.sign(oe)):.0%}  Spearman {spearmanr(me,oe).correlation:+.2f}")
        print(f"  unemployment-change Spearman {spearmanr(mu,ou).correlation:+.2f}\n")


def _metrics(z, gva_o, emp_o, un_o):
    from scipy.stats import spearmanr
    regs = list(z["regions"]); idx = [regs.index(p) for p in PROV10]

    def blk(a, i):
        y22 = a[:, 0:4].mean(1); yb = a[:, {2023: slice(4, 8), 2024: slice(8, 12)}[i]].mean(1)
        return (yb / y22 - 1) * 100

    def blk_un(a, i):
        return a[:, {2023: slice(4, 8), 2024: slice(8, 12)}[i]].mean(1) - a[:, 0:4].mean(1)

    mg = blk(z["rgva"], 2024)[idx]; me = blk(z["emp"], 2024)[idx]; mu = blk_un(z["unemp"], 2024)[idx]
    og = np.array([gva_o.loc[GEO[p], 2024] / gva_o.loc[GEO[p], 2022] - 1 for p in PROV10]) * 100
    oe = np.array([emp_o.loc[GEO[p], 2024] / emp_o.loc[GEO[p], 2022] - 1 for p in PROV10]) * 100
    ou = np.array([un_o.loc[GEO[p], 2024] - un_o.loc[GEO[p], 2022] for p in PROV10])
    w = np.array([gva_o.loc[GEO[p], 2022] for p in PROV10]); w = w / w.sum()
    return dict(mg=mg, og=og, me=me, oe=oe, mu=mu, ou=ou, w=w,
                rho=spearmanr(mg, og).correlation, sign=np.mean(np.sign(mg) == np.sign(og)),
                disp=float(np.std(mg)), disp_o=float(np.std(og)),
                emp_rho=spearmanr(me, oe).correlation, un_rho=spearmanr(mu, ou).correlation,
                net=float(np.sum(w * (mg - og))), gross=float(np.sum(w * np.abs(mg - og))),
                natl=float(np.sum(w * mg)), natl_o=float(np.sum(w * og)))


def report_step1():
    """Before/after: A = candidate (common paths) vs B = candidate_prov (observed province-specific)."""
    need = {k: OUT / f"prov_{k}_s0.npz" for k in ("candidate", "candidate_prov")}
    miss = [k for k, p in need.items() if not p.exists()]
    if miss:
        print("missing runs:", miss); return
    A = np.load(need["candidate"], allow_pickle=True); B = np.load(need["candidate_prov"], allow_pickle=True)
    gva_o, emp_o, un_o = observed()
    a = _metrics(A, gva_o, emp_o, un_o); b = _metrics(B, gva_o, emp_o, un_o)
    print("STEP 1 — province-specific observed demand/labour paths (seed 0, 10 provinces, 2022->2024)\n")
    print("Per-province real GVA growth 2022->2024 (%):")
    print(f"  {'prov':7}{'obs':>8}{'A_com':>8}{'B_prov':>8}{'A_err':>8}{'B_err':>8}")
    for j, p in enumerate(PROV10):
        print(f"  {p:7}{a['og'][j]:>+8.1f}{a['mg'][j]:>+8.1f}{b['mg'][j]:>+8.1f}"
              f"{a['mg'][j]-a['og'][j]:>+8.1f}{b['mg'][j]-b['og'][j]:>+8.1f}")
    print("\nScorecard                         A(common)   B(province)")
    rows = [("GVA Spearman rho", "rho"), ("GVA sign-match", "sign"), ("GVA dispersion sd (obs %.2f)" % a["disp_o"], "disp"),
            ("employment Spearman", "emp_rho"), ("unemp-change Spearman", "un_rho"),
            ("weighted net GVA err (pp)", "net"), ("weighted gross GVA err (pp)", "gross"),
            ("national wtd GVA growth (obs %.2f)" % a["natl_o"], "natl")]
    for lab, k in rows:
        print(f"  {lab:32}{a[k]:>+10.2f}{b[k]:>+10.2f}")
    print("\nMajor provinces real GVA err (model-obs, pp):")
    for p in ["CAN_AB", "CAN_SK", "CAN_NL", "CAN_PE", "CAN_ON", "CAN_QC", "CAN_BC"]:
        j = PROV10.index(p)
        print(f"  {p:7} obs{a['og'][j]:>+6.1f}  A{a['mg'][j]-a['og'][j]:>+6.1f}  B{b['mg'][j]-b['og'][j]:>+6.1f}")


def _blk_growth(a, i):
    y22 = a[:, 0:4].mean(1); yb = a[:, {2023: slice(4, 8), 2024: slice(8, 12)}[i]].mean(1)
    return (yb / y22 - 1) * 100


def report_step2():
    """Before/after: B = candidate_prov vs C = candidate_ext (province-specific intl external demand)."""
    need = {k: OUT / f"prov_{k}_s0.npz" for k in ("candidate_prov", "candidate_ext")}
    miss = [k for k, p in need.items() if not p.exists()]
    if miss:
        print("missing runs:", miss); return
    B = np.load(need["candidate_prov"], allow_pickle=True); C = np.load(need["candidate_ext"], allow_pickle=True)
    gva_o, emp_o, un_o = observed()
    b = _metrics(B, gva_o, emp_o, un_o); c = _metrics(C, gva_o, emp_o, un_o)
    print("STEP 2 — province-specific international external demand (Option A, seed 0, 2022->2024)\n")
    print("Per-province real GVA growth 2022->2024 (%):")
    print(f"  {'prov':7}{'obs':>8}{'B_prov':>8}{'C_ext':>8}{'B_err':>8}{'C_err':>8}")
    for j, p in enumerate(PROV10):
        print(f"  {p:7}{b['og'][j]:>+8.1f}{b['mg'][j]:>+8.1f}{c['mg'][j]:>+8.1f}"
              f"{b['mg'][j]-b['og'][j]:>+8.1f}{c['mg'][j]-c['og'][j]:>+8.1f}")
    print("\nScorecard                         B(prov)     C(ext)")
    rows = [("GVA Spearman rho", "rho"), ("GVA sign-match", "sign"), ("GVA dispersion sd (obs %.2f)" % b["disp_o"], "disp"),
            ("employment Spearman", "emp_rho"), ("unemp-change Spearman", "un_rho"),
            ("weighted net GVA err (pp)", "net"), ("weighted gross GVA err (pp)", "gross"),
            ("national wtd GVA growth (obs %.2f)" % b["natl_o"], "natl")]
    for lab, k in rows:
        print(f"  {lab:32}{b[k]:>+10.2f}{c[k]:>+10.2f}")
    print("\nDIAGNOSTIC — realized province->ROW GOODS exports, real growth 2022->2024 (%), + observed 36-10-0222:")
    peg = prov_export_growth()
    regsB = list(B["regions"]); regsC = list(C["regions"])
    iB = [regsB.index(p) for p in PROV10]; iC = [regsC.index(p) for p in PROV10]
    bg = _blk_growth(B["xrow_goods"], 2024)[iB]; cg = _blk_growth(C["xrow_goods"], 2024)[iC]
    bs = _blk_growth(B["xrow_serv"], 2024)[iB]; cs = _blk_growth(C["xrow_serv"], 2024)[iC]
    print(f"  {'prov':7}{'obsGds':>8}{'B_gds':>8}{'C_gds':>8}{'dC-B':>8}   | {'obsSvc':>7}{'B_svc':>7}{'C_svc':>7}")
    for j, p in enumerate(PROV10):
        og = peg[p]["goods"][1] * 100; os_ = peg[p]["services"][1] * 100
        print(f"  {p:7}{og:>+8.1f}{bg[j]:>+8.1f}{cg[j]:>+8.1f}{cg[j]-bg[j]:>+8.1f}   | {os_:>+7.1f}{bs[j]:>+7.1f}{cs[j]:>+7.1f}")
    # national ROW export sanity
    natB = B["xrow_goods"].sum(0) + B["xrow_serv"].sum(0); natC = C["xrow_goods"].sum(0) + C["xrow_serv"].sum(0)
    print(f"\n  national realized ROW exports growth 22->24:  B {_blk_growth(natB[None,:],2024)[0]:+.1f}%   C {_blk_growth(natC[None,:],2024)[0]:+.1f}%")
    from scipy.stats import spearmanr
    obg = np.array([peg[p]["goods"][1] for p in PROV10]) * 100
    print(f"  province goods-export signal survival (Spearman C_gds vs obs): {spearmanr(cg, obg).correlation:+.2f}  (B: {spearmanr(bg, obg).correlation:+.2f})")
    print(f"  AB/SK/NL goods dC-B: AB {cg[PROV10.index('CAN_AB')]-bg[PROV10.index('CAN_AB')]:+.1f}  "
          f"SK {cg[PROV10.index('CAN_SK')]-bg[PROV10.index('CAN_SK')]:+.1f}  NL {cg[PROV10.index('CAN_NL')]-bg[PROV10.index('CAN_NL')]:+.1f} pp")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["run", "report", "report_step1", "report_step2"])
    ap.add_argument("--config", choices=["control", "candidate", "candidate_prov", "candidate_ext"], default="control")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.mode == "run":
        run(a.config, a.seed)
    elif a.mode == "report_step1":
        report_step1()
    elif a.mode == "report_step2":
        report_step2()
    else:
        report()


if __name__ == "__main__":
    main()
