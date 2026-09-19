"""Convergence + dispersion report for alpha=0.40 historical fit (30 seeds).
Same scoring as the validated workflow: ensemble-mean path, GVA growth over quarters 2..12
(first dropped), unemployment level over all 12 quarters. No model runs, no tuning."""
from __future__ import annotations
import numpy as np
import pandas as pd
import alpha040_validation as V

A040 = "ABL7_full_alpha040"
NS = [3, 5, 10, 20, 30]


def ensemble_score(seeds_dict, seed_ids):
    off = pd.read_csv(V.OFFICIAL)
    sub = {s: seeds_dict[s] for s in seed_ids}
    ens = V.ensemble(sub)
    m = off.merge(ens, on="quarter", how="left")
    gr, gm = V.rmse_mae(m["real_gva_growth_realized"].iloc[1:], m["gva_growth"].iloc[1:])
    ur, um = V.rmse_mae(m["unemployment_rate_realized"], m["unemployment_rate"])
    return gr, gm, ur, um


def main():
    a = V.experiment_seeds(A040)
    e16 = V.experiment_seeds("E16_unclamped_input_planning")
    ids = sorted(a)
    print(f"alpha=0.40 seeds available: {len(ids)}  |  E16 seeds: {len(e16)}")

    # AR(1)
    off = pd.read_csv(V.OFFICIAL)
    agr, agm = V.rmse_mae(off["real_gva_growth_realized"].iloc[1:], off["real_gva_growth_ar1"].iloc[1:])
    aur, aum = V.rmse_mae(off["unemployment_rate_realized"], off["unemployment_rate_ar1"])

    # --- convergence table (ensemble of seeds 0..n-1) ---
    print("\n=== CONVERGENCE of alpha=0.40 metrics (ensemble-mean scoring) ===")
    print(f"{'n':>4s}{'GVA RMSE':>10s}{'GVA MAE':>10s}{'U RMSE':>9s}{'U MAE':>9s}")
    conv = {}
    for n in NS:
        if len(ids) >= n:
            gr, gm, ur, um = ensemble_score(a, ids[:n])
            conv[n] = (gr, gm, ur, um)
            print(f"{n:4d}{gr:10.4f}{gm:10.4f}{ur:9.4f}{um:9.4f}")

    # --- final comparison ---
    print("\n=== FINAL comparison (like-for-like) ===")
    e16_ids = sorted(e16)
    rows = [("alpha=0.40 (n=30)", conv.get(30)),
            ("alpha=0.40 (n=10)", conv.get(10)),
            ("Exact E16 (n=10)", ensemble_score(e16, e16_ids[:10]) if len(e16_ids) >= 10 else None),
            ("Frozen AR(1)", (agr, agm, aur, aum))]
    print(f"{'model':22s}{'GVA RMSE':>10s}{'GVA MAE':>10s}{'U RMSE':>9s}{'U MAE':>9s}")
    for lab, v in rows:
        if v: print(f"{lab:22s}{v[0]:10.4f}{v[1]:10.4f}{v[2]:9.4f}{v[3]:9.4f}")
    if conv.get(30):
        v = conv[30]
        print("\nalpha=0.40 (n=30) relative % vs AR(1):")
        print(f"  GVA RMSE {100*(v[0]-agr)/agr:+.1f}%  GVA MAE {100*(v[1]-agm)/agm:+.1f}%  "
              f"U RMSE {100*(v[2]-aur)/aur:+.1f}%  U MAE {100*(v[3]-aum)/aum:+.1f}%")

    # --- change n=10 -> 20, 30 ---
    if all(k in conv for k in (10, 20, 30)):
        print("\n=== change from n=10 (absolute and %) ===")
        names = ["GVA RMSE", "GVA MAE", "U RMSE", "U MAE"]
        for target, n in (("n=20", 20), ("n=30", 30)):
            d = [conv[n][i] - conv[10][i] for i in range(4)]
            p = [100 * d[i] / conv[10][i] for i in range(4)]
            print(f"  {target}: " + "  ".join(f"{names[i]} {d[i]:+.4f} ({p[i]:+.1f}%)" for i in range(4)))

    # --- dispersion: per-seed metric distribution + bootstrap SE of the n=30 ensemble ---
    print("\n=== DISPERSION / Monte Carlo error (n=30) ===")
    per = np.array([ensemble_score(a, [s]) for s in ids])  # score each seed alone
    names = ["GVA RMSE", "GVA MAE", "U RMSE", "U MAE"]
    print("  single-seed fit distribution (score each seed alone):")
    for i, nm in enumerate(names):
        print(f"    {nm:9s} mean {per[:,i].mean():.4f}  SD {per[:,i].std(ddof=1):.4f}  "
              f"[min {per[:,i].min():.4f}, max {per[:,i].max():.4f}]")
    rng = np.random.default_rng(0)
    B = 1000
    boot = np.empty((B, 4))
    for b in range(B):
        pick = list(rng.choice(ids, size=len(ids), replace=True))
        boot[b] = ensemble_score(a, pick)
    print(f"  bootstrap SE of the 30-seed ENSEMBLE metric (B={B}, resampling seeds):")
    for i, nm in enumerate(names):
        print(f"    {nm:9s} {conv[30][i]:.4f}  +/- {boot[:,i].std(ddof=1):.4f}  "
              f"(95% CI [{np.percentile(boot[:,i],2.5):.4f}, {np.percentile(boot[:,i],97.5):.4f}])")


if __name__ == "__main__":
    main()
