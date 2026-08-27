"""Epsilon-sensitivity report for the broad C27/C28 scenario: compares eps = 0.5 / 1 / 1.5
(treatment vs control) on levels, dynamics, direct/indirect split, and heterogeneity.
Reads the scenario outputs; runs no simulation.

    uv run python experiments/itc/analysis/report_eps.py

Requires: scenario_broad.py run control ; run treat ; run treat 0.5 ; run treat 1.5
"""
import numpy as np
from pathlib import Path
OUT = Path(__file__).resolve().parents[1] / "outputs"
C = dict(np.load(OUT / "mvp2c_control.npz", allow_pickle=True))
R = {0.5: dict(np.load(OUT / "mvp2c_treat_e05.npz", allow_pickle=True)),
     1.0: dict(np.load(OUT / "mvp2c_treat.npz", allow_pickle=True)),
     1.5: dict(np.load(OUT / "mvp2c_treat_e15.npz", allow_pickle=True))}
cells = list(C['cells']); YEARS = {y: 16 + 4 * (y - 2026) for y in range(2026, 2036)}
def yb(a, y): i = YEARS[y]; return float(np.asarray(a)[i:i+4].mean())
def d(T, k, y): return yb(T[k], y) - yb(C[k], y)
mets = [("GVA", "nat_gva"), ("target prod", "nat_tprod"), ("realized prod", "nat_prod"), ("investment", "nat_inv"),
        ("capital stock", "nat_Ktot"), ("employed", "nat_emp"), ("unemp pp", "nat_unemp"), ("imports", "nat_imp"), ("unmet", "nat_unmet")]
print("== A. 2030 / 2035 (treatment-control) ==")
for y in (2030, 2035):
    print(f"-- {y} --   eps=0.5   eps=1.0   eps=1.5   (1.5/1.0)  (0.5/1.0)")
    for lbl, k in mets:
        v = {e: d(R[e], k, y) for e in (0.5, 1.0, 1.5)}
        r15 = v[1.5] / v[1.0] if abs(v[1.0]) > 1e-6 else float('nan'); r05 = v[0.5] / v[1.0] if abs(v[1.0]) > 1e-6 else float('nan')
        print(f"  {lbl:14}{v[0.5]:9.2f}{v[1.0]:9.2f}{v[1.5]:9.2f}   {r15:6.2f}   {r05:6.2f}")
print("\n== dynamics ==")
def peak(T, k): a = [yb(T[k], y) - yb(C[k], y) for y in range(2026, 2036)]; return 2026 + int(np.argmax(a))
for e in (0.5, 1.0, 1.5):
    T = R[e]
    dtp = np.array([d(T, 'nat_tprod', y) for y in range(2026, 2036)]); drp = np.array([d(T, 'nat_prod', y) for y in range(2026, 2036)])
    cumr = drp.sum() / dtp.sum()
    post = drp[5:].sum() / drp.sum()
    print(f"  eps={e}: peak target={peak(T,'nat_tprod')} peak realized={peak(T,'nat_prod')} "
          f"cumRealiz={cumr:.3f} post-expiry realized share={post:.2f}")
print("\n== direct/indirect decomposition ==")
for e in (0.5, 1.0, 1.5):
    T = R[e]; x = T['x']; tp = T['tp']
    dtot = np.nansum(tp[16:] - C['tp'][16:]) / 1e9
    direct = 0.0
    for t in range(16, 36): direct += np.nansum(x[t] * e * tp[t] / (1 + e * x[t])) / 1e9
    ind = dtot - direct
    postind = np.nansum(tp[36:] - C['tp'][36:]) / 1e9
    print(f"  eps={e}: dtgt={dtot:7.1f} direct={direct:7.1f} ({100*direct/dtot:3.0f}%) indirect={ind:7.1f} ({100*ind/dtot:3.0f}%) post-exp indirect={postind:6.1f}")
print("\n== heterogeneity ==")
for e in (0.5, 1.0, 1.5):
    T = R[e]; x = T['x']; xm = x[16:36].mean(0)
    dtp = np.nansum(T['tp'][16:] - C['tp'][16:], 0); base = np.nansum(C['tp'][16:], 0)
    rel = np.divide(dtp, base, out=np.zeros_like(dtp), where=base > 1); ok = base > 1
    cr = np.corrcoef(xm[ok], rel[ok])[0, 1]
    direct = np.zeros(len(cells))
    for t in range(16, 36): direct += np.nan_to_num(x[t] * e * T['tp'][t] / (1 + e * x[t]))
    drp = np.nansum(T['rp'][16:] - C['rp'][16:], 0); dtp2 = np.nansum(T['tp'][16:] - C['tp'][16:], 0)
    nz = xm > 1e-9; qs = np.quantile(xm[nz], [0, .25, .5, .75, 1.0]); rr = np.divide(drp, dtp2, out=np.full_like(drp, np.nan), where=np.abs(dtp2) > 1e7)
    q4 = nz & (xm >= qs[3]); q1 = nz & (xm >= qs[0]) & (xm <= qs[1])
    print(f"  eps={e}: corr(x,relDtgt)={cr:.3f}  realiz Q1low={np.nanmean(rr[q1]):.3f} Q4high={np.nanmean(rr[q4]):.3f}")
print("\n== ranking stability (top-8 cells by dtarget) ==")
for e in (0.5, 1.0, 1.5):
    T = R[e]; dtp = np.nansum(T['tp'][16:] - C['tp'][16:], 0)
    top = [cells[i] for i in np.argsort(dtp)[::-1][:8]]
    print(f"  eps={e}: {top}")
