"""Consolidate the two policy experiments (broad C27/C28 30%, Clean Electricity D 15%), eps=1.
Existing scenario outputs only. Conventions: FLOWS=calendar-year SUM(4q); STOCKS=year-end;
RATES=avg; employment=model agents (year-end); fiscal='implied realized ITC fiscal cost'.
Writes analysis CSVs + a decomposition npz into outputs/.

    uv run python experiments/itc/analysis/consolidate.py

Requires: scenario_broad (control, treat, treat 0.5, treat 1.5), scenario_clean_electricity
(control, treat), and trace_edges (control, treat).
"""
import numpy as np, csv
from pathlib import Path
OUT = Path(__file__).resolve().parents[1] / "outputs"
def L(f): return dict(np.load(OUT / f, allow_pickle=True))
Bc, Bt = L("mvp2c_control.npz"), L("mvp2c_treat.npz")
Ec, Et = L("mvp2ce_control.npz"), L("mvp2ce_treat.npz")
TR = L("mvp2ctr_treat.npz")
SEC = list(Ec['sectors']); cB = list(Bc['cells']); cE = list(Ec['cells'])
YEARS = {y: 16 + 4 * (y - 2026) for y in range(2026, 2036)}
C27, C28 = SEC.index("C27"), SEC.index("C28"); D = SEC.index("D"); B05, B06 = SEC.index("B05"), SEC.index("B06")
def ysum(a, y, d=1.0): i = YEARS[y]; return float(np.nansum(np.asarray(a)[i:i+4])) / d
def yend(a, y, d=1.0): i = YEARS[y]; return float(np.asarray(a)[i+3]) / d
def yavg(a, y): i = YEARS[y]; return float(np.nanmean(np.asarray(a)[i:i+4]))
def csum(a, i0, i1, d=1.0): return float(np.nansum(np.asarray(a)[i0:i1])) / d
def wcsv(name, rows, hdr):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(hdr)
        for r in rows: w.writerow(r)
    print("saved", name)
def decomp(Rt, Rc):
    x = np.asarray(Rt['x']); tpT = np.asarray(Rt['tp']); tpC = np.asarray(Rc['tp'])
    dtot = np.nansum(tpT[16:] - tpC[16:], 0); direct = np.zeros(x.shape[1])
    for t in range(16, 36): direct += np.nan_to_num(x[t] * tpT[t] / (1 + x[t]))
    return dtot / 1e9, direct / 1e9, (dtot - direct) / 1e9

itc_broad = 0.30 * (TR['SELL'][:, C27, 2] + TR['SELL'][:, C28, 2])
DcE = [cE.index(f"{str(p)[-2:]}/D") for p in Ec['provorder']]
itc_ce = 0.15 * np.asarray(Et['inv'])[:, DcE].sum(1)

# ================= TASK 1 =================
def headline(name, Rt, Rc, itc):
    tpT = np.asarray(Rt['tp']).sum(1); tpC = np.asarray(Rc['tp']).sum(1)
    rpT = np.asarray(Rt['rp']).sum(1); rpC = np.asarray(Rc['rp']).sum(1)
    dg = np.asarray(Rt['nat_gva']) - np.asarray(Rc['nat_gva'])
    dtp = tpT - tpC; drp = rpT - rpC
    div = np.asarray(Rt['inv']).sum(1) - np.asarray(Rc['inv']).sum(1)
    dim = np.asarray(Rt['imp']).sum(1) - np.asarray(Rc['imp']).sum(1)
    dem = np.asarray(Rt['emp']).sum(1) - np.asarray(Rc['emp']).sum(1)
    dK = np.asarray(Rt['nat_Ktot']) - np.asarray(Rc['nat_Ktot'])
    du = np.asarray(Rt['nat_unemp']) - np.asarray(Rc['nat_unemp'])
    dun = np.asarray(Rt['nat_unmet']) - np.asarray(Rc['nat_unmet'])
    dtot, dc, di = decomp(Rt, Rc)
    return dict(case=name, dGVA2030=ysum(dg, 2030), dTgt2030=ysum(dtp, 2030, 1e9), dReal2030=ysum(drp, 2030, 1e9),
        dInv2030=ysum(div, 2030, 1e9), dKstock2030_yrend=yend(dK, 2030), dEmp2030_yrend=yend(dem, 2030),
        dUnemp2030_avg=yavg(du, 2030), dImp2030=ysum(dim, 2030, 1e9), dUnmet2030=ysum(dun, 2030),
        ITC2030=ysum(itc, 2030, 1e9), GVA_over_ITC_2030=ysum(dg, 2030) / ysum(itc, 2030, 1e9),
        cumGVA2630=sum(ysum(dg, y) for y in range(2026, 2031)), cumITC2630=csum(itc, 16, 36, 1e9),
        cumGVA2635=csum(dg, 16, 56), cumTgt2635=csum(dtp, 16, 56, 1e9), cumReal2635=csum(drp, 16, 56, 1e9),
        cumGVA_over_ITC=csum(dg, 16, 56) / csum(itc, 16, 36, 1e9), directShare=dc.sum() / dtot.sum(),
        indirectShare=di.sum() / dtot.sum(), cumRealiz=csum(drp, 16, 56) / csum(dtp, 16, 56),
        postExpShare=csum(drp, 36, 56) / csum(drp, 16, 56),
        peakTgtYr=2026 + int(np.argmax([ysum(dtp, y, 1e9) for y in range(2026, 2036)])),
        peakRealYr=2026 + int(np.argmax([ysum(drp, y, 1e9) for y in range(2026, 2036)])))
rB = headline("Broad_C27C28_30pct", Bt, Bc, itc_broad); rE = headline("CleanElec_D_15pct", Et, Ec, itc_ce)
print("### TASK1 HEADLINE ###")
for k in rB:
    if k == "case": continue
    print(f"  {k:20} broad={rB[k]:>10.3f}   CE={rE[k]:>10.3f}")
wcsv("consol_policy_headline.csv", [[rB[k] for k in rB], [rE[k] for k in rB]], list(rB.keys()))

# ================= TASK 2: CE provincial incidence =================
xE = np.asarray(Et['x'])
DINTc, DINTt = np.asarray(Ec['DINT']), np.asarray(Et['DINT'])
def fshare(DI, pi, y): b = DI[YEARS[y]:YEARS[y]+4, pi, :].sum(0); s = b.sum(); return (b[B05]+b[B06])/s if s > 0 else 0.0
tot_itc = csum(itc_ce, 16, 36, 1e9)
rowsE = []
for pi, p in enumerate(Ec['provorder']):
    pp = str(p)[-2:]; j = cE.index(f"{pp}/D")
    baseD = ysum(Bc['tp'][:, j], 2030, 1e9)                       # LEVEL 2030
    xce = xE[16:36, j].mean()
    realD_lvl = ysum(Et['inv'][:, j], 2030, 1e9)                  # realized D capital LEVEL 2030
    realD_dch = ysum(Et['inv'][:, j] - Ec['inv'][:, j], 2030, 1e9)  # change in realized D capital
    itc_p = csum(0.15 * Et['inv'][:, j], 16, 36, 1e9)             # implied ITC cumulative 26-30
    dtgt = csum(Et['tp'][:, j] - Ec['tp'][:, j], 16, 56, 1e9)     # cumulative change in target
    dreal = csum(Et['rp'][:, j] - Ec['rp'][:, j], 16, 56, 1e9)
    rr = dreal / dtgt if abs(dtgt) > 1e-6 else float('nan')
    fb = fshare(DINTc, pi, 2030)
    dfuel = csum(DINTt[:, pi, [B05, B06]].sum(1) - DINTc[:, pi, [B05, B06]].sum(1), 16, 36, 1e9)
    dimp = csum(Et['imp'][:, j] - Ec['imp'][:, j], 16, 56, 1e9)
    rowsE.append([pp, round(baseD, 3), round(xce, 4), round(realD_lvl, 3), round(realD_dch, 3),
                  round(itc_p, 3), round(100*itc_p/tot_itc, 1), round(dtgt, 3), round(dreal, 3),
                  round(rr, 3), round(fb, 3), round(dfuel, 4), round(dimp, 3)])
rowsE.sort(key=lambda r: -r[2])
hdrE = ["prov", "baseD_lvl30", "x_CE", "realDcap_lvl30", "dRealDcap30", "cumITC2630", "pctCEfisc",
        "cumDtgt2635", "cumDreal2635", "realizRatio", "baseFossShare", "cumDfossil", "cumDimp"]
print("\n### TASK2 CE PROVINCIAL INCIDENCE ###\n  " + " ".join(f"{h:>11}" for h in hdrE))
for r in rowsE: print("  " + " ".join(f"{str(v):>11}" for v in r))
wcsv("consol_ce_provincial.csv", rowsE, hdrE)

# ================= TASK 3: broad cell heterogeneity =================
dtotB, dcB, diB = decomp(Bt, Bc)
xmB = np.asarray(Bt['x'])[16:36].mean(0)
baseB = np.array([ysum(Bc['tp'][:, i], 2030, 1e9) for i in range(len(cB))])
drealB = np.nansum(np.asarray(Bt['rp'])[16:] - np.asarray(Bc['rp'])[16:], 0) / 1e9
dinvB = np.nansum(np.asarray(Bt['inv'])[16:] - np.asarray(Bc['inv'])[16:], 0) / 1e9
dimpB = np.nansum(np.asarray(Bt['imp'])[16:] - np.asarray(Bc['imp'])[16:], 0) / 1e9
rrB = np.divide(drealB, dtotB, out=np.full_like(drealB, np.nan), where=np.abs(dtotB) > 0.01)
rowsB = [[cB[i], round(xmB[i], 5), round(baseB[i], 3), round(dcB[i], 3), round(diB[i], 3),
          round(dtotB[i], 3), round(drealB[i], 3), round(rrB[i], 3), round(dinvB[i], 3), round(dimpB[i], 3)]
         for i in range(len(cB))]
rowsB.sort(key=lambda r: -r[5])
hdrB = ["cell", "x", "baseScale30", "directTgt", "indirectTgt", "totDtgt", "dReal", "realizRatio", "dInv", "dImp"]
wcsv("consol_broad_cell_heterogeneity.csv", rowsB, hdrB)
print(f"\n### TASK3 broad cell table saved ({len(rowsB)} cells) ; top by totDtgt:")
for r in rowsB[:6]: print("  ", r)

# ================= TASK 4: descriptive drivers =================
def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float); ok = ~np.isnan(a) & ~np.isnan(b)
    return float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 2 else float('nan')
print("\n### TASK4 DESCRIPTIVE DRIVERS (broad, across 650 cells) ###")
print(f"  corr(totDtgt, baseScale)={corr(dtotB, baseB):.2f}  corr(totDtgt, x)={corr(dtotB, xmB):.2f} "
      f"corr(totDtgt, x*baseScale)={corr(dtotB, xmB*baseB):.2f}")
print(f"  corr(realizRatio, baseScale)={corr(rrB, baseB):.2f}  corr(realizRatio, x)={corr(rrB, xmB):.2f}  "
      f"corr(dImp, totDtgt)={corr(dimpB, dtotB):.2f}")
secB = np.array([c.split('/')[1] for c in cB]); prv = np.array([c.split('/')[0] for c in cB])
print("  dtarget by sector (top): " + ", ".join(f"{s}={dtotB[secB==s].sum():.1f}" for s in sorted(set(secB), key=lambda s: -dtotB[secB==s].sum())[:6]))
print("  dtarget by province (top): " + ", ".join(f"{p}={dtotB[prv==p].sum():.1f}" for p in sorted(set(prv), key=lambda p: -dtotB[prv==p].sum())[:6]))
fb_arr = np.array([r[10] for r in rowsE]); xce_arr = np.array([r[2] for r in rowsE]); rr_arr = np.array([r[9] for r in rowsE])
print(f"  CE: corr(baseFossil, x_CE)={corr(fb_arr, xce_arr):.2f}  corr(baseFossil, realizRatio)={corr(fb_arr, rr_arr):.2f}")

# ================= TASK 5: strong contrasts (printed) =================
print("\n### TASK5 STRONG CONTRASTS ###")
def cellrow(nm):
    i = cB.index(nm); return f"{nm}: x={xmB[i]:.4f} base={baseB[i]:.1f} tot={dtotB[i]:.1f} dir={dcB[i]:.1f} ind={diB[i]:.1f} realiz={rrB[i]:.2f} dImp={dimpB[i]:.1f}"
for nm in ["SK/B06", "AB/B06", "ON/F", "ON/K", "NL/B06", "QC/F"]:
    print("  ", cellrow(nm))

# save decomposition npz
np.savez_compressed(OUT / "consol_decomp.npz",
                    cells=np.array(cB), broad_x=xmB, broad_base=baseB, broad_direct=dcB, broad_indirect=diB,
                    broad_totDtgt=dtotB, broad_dReal=drealB, broad_realiz=rrB, broad_dImp=dimpB,
                    ce_prov=np.array([str(p)[-2:] for p in Ec['provorder']]),
                    itc_broad_q=itc_broad, itc_ce_q=itc_ce)
print("\nsaved consol_decomp.npz")
