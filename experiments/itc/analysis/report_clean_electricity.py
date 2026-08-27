"""Report for the stylized Clean Electricity ITC (sector D, 15%, eps=1): provincial
incidence, macro effects, timing, direct/indirect split, implied fiscal cost, and the
fossil-input post-analysis. Reads the scenario outputs; runs no simulation.
Convention: FLOW annual = calendar-year SUM of 4 quarters; rates/stocks = annual AVERAGE.

    uv run python experiments/itc/analysis/report_clean_electricity.py

Requires: scenario_clean_electricity.py run control ; run treat
"""
import numpy as np
from pathlib import Path
OUT = Path(__file__).resolve().parents[1] / "outputs"
C = dict(np.load(OUT / "mvp2ce_control.npz", allow_pickle=True))
T = dict(np.load(OUT / "mvp2ce_treat.npz", allow_pickle=True))
SEC = list(C['sectors']); cells = list(C['cells']); provo = [str(p) for p in C['provorder']]
YEARS = {y: 16 + 4 * (y - 2026) for y in range(2026, 2036)}
D = SEC.index("D"); B05 = SEC.index("B05"); B06 = SEC.index("B06")
ACT = range(16, 36); EPS = 1.0
def asum(a, y): i = YEARS[y]; return float(np.nansum(np.asarray(a)[i:i+4]))
def aavg(a, y): i = YEARS[y]; return float(np.nanmean(np.asarray(a)[i:i+4]))
def csum(a, i0, i1): return float(np.nansum(np.asarray(a)[i0:i1]))
dpr = [p[-2:] for p in provo]
Dcell = {pp: cells.index(f"{pp}/D") for pp in dpr}

print("### A. DIRECT EXPOSURE BY PROVINCE (D cell) ###")
xD = {pp: np.asarray(T['x'])[16:36, Dcell[pp]].mean() for pp in dpr}
baseD = {pp: aavg(np.asarray(C['tp'])[:, Dcell[pp]] / 1e9, 2030) for pp in dpr}
invD = {pp: asum(np.asarray(T['inv'])[:, Dcell[pp]] / 1e9, 2030) for pp in dpr}
print(f"  {'prov':5}{'x_CE':>9}{'baseD tp30 $B':>15}{'realD cap30 $B':>16}")
for pp in sorted(dpr, key=lambda z: -xD[z]):
    print(f"  {pp:5}{xD[pp]:>9.4f}{baseD[pp]:>15.2f}{invD[pp]:>16.3f}")

print("\n### B. MACRO (treat-control, annual; flows=SUM, stocks/rates=AVG) ###")
tp_n = lambda R: np.asarray(R['tp']).sum(1) / 1e9; rp_n = lambda R: np.asarray(R['rp']).sum(1) / 1e9
inv_n = lambda R: np.asarray(R['inv']).sum(1) / 1e9; imp_n = lambda R: np.asarray(R['imp']).sum(1) / 1e9
emp_n = lambda R: np.asarray(R['emp']).sum(1)
SER = {"GVA": (np.asarray(T['nat_gva'])-np.asarray(C['nat_gva']), asum),
       "target prod": (tp_n(T)-tp_n(C), asum), "realized prod": (rp_n(T)-rp_n(C), asum),
       "investment": (inv_n(T)-inv_n(C), asum), "capital stock": (np.asarray(T['nat_Ktot'])-np.asarray(C['nat_Ktot']), aavg),
       "employed": (emp_n(T)-emp_n(C), aavg), "unemp pp": (np.asarray(T['nat_unemp'])-np.asarray(C['nat_unemp']), aavg),
       "imports": (imp_n(T)-imp_n(C), asum), "unmet": (np.asarray(T['nat_unmet'])-np.asarray(C['nat_unmet']), asum)}
print("  " + f"{'metric':14}" + "".join(f"{y%100:>7}" for y in range(2026, 2036)))
for lbl, (ser, agg) in SER.items():
    print(f"  {lbl:14}" + "".join(f"{agg(ser, y):>7.2f}" for y in range(2026, 2036)))

print("\n### C. TIMING ###")
dtp = tp_n(T)-tp_n(C); drp = rp_n(T)-rp_n(C)
atp = [asum(dtp, y) for y in range(2026, 2036)]; arp = [asum(drp, y) for y in range(2026, 2036)]
print(f"  peak target year={2026+int(np.argmax(atp))}  peak realized year={2026+int(np.argmax(arp))}")
print(f"  cumulative realization sum(dreal)/sum(dtgt) (q16-55)={csum(drp,16,56)/csum(dtp,16,56):.3f}")
print(f"  post-2030 realized share={csum(drp,36,56)/csum(drp,16,56):.2f}")

print("\n### D. DIRECT/INDIRECT ###")
x = np.asarray(T['x']); tpT = np.asarray(T['tp']); tpC = np.asarray(C['tp'])
dtot_c = np.nansum(tpT[16:]-tpC[16:], 0)/1e9
direct_c = np.zeros(len(cells))
for t in ACT: direct_c += np.nan_to_num(x[t]*EPS*tpT[t]/(1+EPS*x[t]))/1e9
indir_c = dtot_c - direct_c
Dtot = dtot_c.sum(); Dd = direct_c.sum(); Di = indir_c.sum()
print(f"  cumulative dtgt={Dtot:.1f}B direct={Dd:.1f} ({100*Dd/Dtot:.0f}%) indirect={Di:.1f} ({100*Di/Dtot:.0f}%)")
print(f"  post-expiry indirect (q36-55)={np.nansum(tpT[36:]-tpC[36:])/1e9:.1f}B")
print("  top indirect responders:")
for i in np.argsort(indir_c)[::-1][:8]:
    print(f"    {cells[i]:10} dir={direct_c[i]:+7.2f} ind={indir_c[i]:+7.2f} tot={dtot_c[i]:+7.2f}")

print("\n### E. IMPLIED REALIZED CLEAN-ELECTRICITY ITC FISCAL COST (not recorded) ###")
Didx = [Dcell[pp] for pp in dpr]
eligD_q = np.asarray(T['inv'])[:, Didx].sum(1)          # realized D capital purchases (all provinces), $
itc = 0.15 * eligD_q
print(f"  annual 2026-30 ITC ($B): " + " ".join(f"{y}:{asum(itc,y)/1e9:.2f}" for y in range(2026, 2031)))
cumitc = csum(itc, 16, 36)/1e9
print(f"  cumulative 2026-30 ITC = {cumitc:.2f}B")
dgva = np.asarray(T['nat_gva'])-np.asarray(C['nat_gva'])
print(f"  2030 dGVA/ITC = {asum(dgva,2030)/(asum(itc,2030)/1e9):.2f}")
print(f"  sum-dGVA(26-35)/sum-ITC(26-30) = {csum(dgva,16,56)/cumitc:.2f}  (sum-dGVA26-35={csum(dgva,16,56):.1f}B)")

print("\n### F. FOSSIL INTENSITY (post-analysis; denominator = total D intermediate inputs, all goods) ###")
DINTc = np.asarray(C['DINT']); DINTt = np.asarray(T['DINT'])   # (T,13,50)
def fshare(DI, pi, y):
    i = YEARS[y]; blk = DI[i:i+4, pi, :].sum(0); den = blk.sum()
    return (blk[B05]+blk[B06])/den if den > 0 else np.nan
print(f"  {'prov':5}{'baseFoss30':>11}{'treatFoss30':>12}{'d_foss':>8}{'d_B05+B06$B':>12}")
foss_base = {}
for pi, pp in enumerate(dpr):
    fb = fshare(DINTc, pi, 2030); ft = fshare(DINTt, pi, 2030)
    dfuel = (DINTt[YEARS[2030]:YEARS[2030]+4, pi, [B05, B06]].sum() - DINTc[YEARS[2030]:YEARS[2030]+4, pi, [B05, B06]].sum())/1e9
    foss_base[pp] = fb
    print(f"  {pp:5}{fb:>11.3f}{ft:>12.3f}{ft-fb:>8.3f}{dfuel:>12.3f}")
# correlations across provinces: baseline fossil vs treatment outcomes
fb_arr = np.array([foss_base[pp] for pp in dpr])
xarr = np.array([xD[pp] for pp in dpr])
dtgtD = np.array([asum(np.asarray(T['tp'])[:, Dcell[pp]]/1e9, 2030)-asum(np.asarray(C['tp'])[:, Dcell[pp]]/1e9, 2030) for pp in dpr])
drealD = np.array([asum(np.asarray(T['rp'])[:, Dcell[pp]]/1e9, 2030)-asum(np.asarray(C['rp'])[:, Dcell[pp]]/1e9, 2030) for pp in dpr])
rr = np.divide(drealD, dtgtD, out=np.full_like(drealD, np.nan), where=np.abs(dtgtD) > 0.01)
def corr(a, b):
    ok = ~np.isnan(a) & ~np.isnan(b); return np.corrcoef(a[ok], b[ok])[0, 1] if ok.sum() > 2 else np.nan
print(f"  corr(baseFossil, x_CE)={corr(fb_arr,xarr):.2f}  corr(baseFossil, d_tgtD)={corr(fb_arr,dtgtD):.2f} "
      f"corr(baseFossil, d_realD)={corr(fb_arr,drealD):.2f} corr(baseFossil, realizRatio)={corr(fb_arr,rr):.2f}")
