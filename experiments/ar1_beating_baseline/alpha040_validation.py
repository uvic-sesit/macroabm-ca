"""Decisive 10-seed historical validation for alpha=0.40, using the existing
finalize_results conventions. No model runs here (reads saved seeds). No tuning.

Parts:
 A. National GVA/unemployment RMSE/MAE (10 seeds) for baseline (frozen c0), E16
    (E16_unclamped_input_planning), alpha=0.40 (ABL7), AR(1); % vs AR(1).
 B. National paper table (per-seed, mean[min,max]): cumulative real GVA growth 2023 & 2024
    from 2022; unemployment change from own 2022 level for 2023 & 2024; model 2022 level.
 C. Provincial scorecard (alpha=0.40): 2022->2024 real GVA growth, employment growth,
    2024 unemployment vs observed (reused from c0_provincial_validation_n10.csv);
    sign match, RMSE/MAE, Spearman rank correlation.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
OFFICIAL = REPO / "dev/working_paper/ar1_benchmark/outputs/quarterly_forecasts_and_realizations.csv"
FROZEN = REPO / "dev/publication_runs/c0/seeds"
OUTPUTS = HERE / "outputs"
C0_PROV = REPO.parent / "macroabm-ca/dev/working_paper/preliminary/c0_provincial_validation_n10.csv"  # observed provincial benchmark (read-only)
PROV = ["CAN_NL","CAN_PE","CAN_NS","CAN_NB","CAN_QC","CAN_ON","CAN_MB","CAN_SK","CAN_AB","CAN_BC"]


def rmse_mae(a, f):
    a = np.asarray(a, float); f = np.asarray(f, float)
    m = np.isfinite(a) & np.isfinite(f)
    e = f[m] - a[m]
    return float(np.sqrt(np.mean(e**2))), float(np.mean(np.abs(e)))


# ---------- per-seed national series ----------
def baseline_seeds():
    out = {}
    for p in sorted(FROZEN.glob("seed*.npz")):
        d = np.load(p, allow_pickle=False)
        q = d["quarters"].astype(str)
        gva = np.asarray(d["reg__real_gva"], float).sum(axis=1)
        ur = 100.0 * np.asarray(d["reg__unemployed_agents"], float).sum(axis=1) / np.asarray(d["reg__labour_force_agents"], float).sum(axis=1)
        out[int(d["seed"])] = pd.DataFrame({"quarter": q, "real_gva": gva, "unemployment_rate": ur})
    return out


def experiment_seeds(exp):
    out = {}
    for p in sorted((OUTPUTS / exp).glob("seed*/national_quarterly.csv")):
        s = int(p.parent.name.removeprefix("seed"))
        out[s] = pd.read_csv(p)
    return out


def ensemble(seeds: dict):
    df = pd.concat([f.assign(seed=s) for s, f in seeds.items()])
    df["gva_growth"] = df.groupby("seed")["real_gva"].transform(lambda x: 100 * np.log(x).diff())
    return df.groupby("quarter", as_index=False).mean(numeric_only=True)


# ---------- Part A ----------
def part_A(specs):
    off = pd.read_csv(OFFICIAL)
    rows = []
    ar = None
    for label, seeds in specs.items():
        ens = ensemble(seeds)
        m = off.merge(ens, on="quarter", how="left")
        gr, gm = rmse_mae(m["real_gva_growth_realized"].iloc[1:], m["gva_growth"].iloc[1:])
        ur, um = rmse_mae(m["unemployment_rate_realized"], m["unemployment_rate"])
        rows.append((label, len(seeds), gr, gm, ur, um))
    # AR1
    agr, agm = rmse_mae(off["real_gva_growth_realized"].iloc[1:], off["real_gva_growth_ar1"].iloc[1:])
    aur, aum = rmse_mae(off["unemployment_rate_realized"], off["unemployment_rate_ar1"])
    rows.append(("Frozen AR(1)", 1, agr, agm, aur, aum))
    print("\n=== PART A: national 10-seed historical fit (like-for-like) ===")
    print(f"{'model':26s}{'seeds':>6s}{'GVA RMSE':>10s}{'GVA MAE':>10s}{'U RMSE':>9s}{'U MAE':>9s}")
    for lab, n, gr, gm, ur, um in rows:
        print(f"{lab:26s}{n:6d}{gr:10.4f}{gm:10.4f}{ur:9.4f}{um:9.4f}")
    print("\nrelative % vs AR(1) (positive = higher error):")
    for lab, n, gr, gm, ur, um in rows[:-1]:
        print(f"{lab:26s}{'':6s}{100*(gr-agr)/agr:9.1f}%{100*(gm-agm)/agm:9.1f}%{100*(ur-aur)/aur:8.1f}%{100*(um-aum)/aum:8.1f}%")
    return rows


# ---------- Part B ----------
def annual(df, col):
    d = df.copy(); d["year"] = d["quarter"].str[:4].astype(int)
    return d.groupby("year")[col].mean()


def part_B(label, seeds):
    cum23, cum24, du23, du24, u22 = [], [], [], [], []
    for s, df in seeds.items():
        g = annual(df, "real_gva"); u = annual(df, "unemployment_rate")
        cum23.append(100 * (g[2023] / g[2022] - 1)); cum24.append(100 * (g[2024] / g[2022] - 1))
        du23.append(u[2023] - u[2022]); du24.append(u[2024] - u[2022]); u22.append(u[2022])
    def mm(x): return (np.mean(x), np.min(x), np.max(x))
    print(f"\n--- {label} (n={len(seeds)}) national validation, mean [min, max] ---")
    for nm, x in [("cum. real GVA growth 2023 (%)", cum23), ("cum. real GVA growth 2024 (%)", cum24),
                  ("unemp change from 2022, 2023 (pp)", du23), ("unemp change from 2022, 2024 (pp)", du24),
                  ("model 2022 unemployment level (%)", u22)]:
        me, lo, hi = mm(x); print(f"  {nm:38s} {me:6.2f} [{lo:6.2f}, {hi:6.2f}]")
    return dict(cum23=mm(cum23), cum24=mm(cum24), du23=mm(du23), du24=mm(du24), u22=mm(u22))


# ---------- Part C ----------
def part_C(exp):
    obs = pd.read_csv(C0_PROV).set_index("province")
    reg = []
    for p in sorted((OUTPUTS / exp).glob("seed*/regional_quarterly.csv")):
        s = int(p.parent.name.removeprefix("seed")); r = pd.read_csv(p); r["seed"] = s; reg.append(r)
    R = pd.concat(reg); R["year"] = R["quarter"].str[:4].astype(int)
    rows = []
    for code in PROV:
        prov = obs.index[obs.index == code.replace("CAN_", "")]
        key = code.replace("CAN_", "")
        sub = R[R["province"] == code]
        g = sub.groupby(["seed", "year"])["real_gva"].mean().unstack()
        emp = sub.groupby(["seed", "year"])["employed_persons"].mean().unstack()
        ur = sub.groupby(["seed", "year"])["unemployment_rate"].mean().unstack()
        ggrowth = 100 * (g[2024] / g[2022] - 1)
        egrowth = 100 * (emp[2024] / emp[2022] - 1)
        rows.append(dict(province=key,
                         obs_gva=obs.loc[key, "observed_gva_growth"], model_gva=ggrowth.mean(), model_gva_sd=ggrowth.std(),
                         obs_emp=obs.loc[key, "observed_emp_growth"], model_emp=egrowth.mean(),
                         obs_u2024=obs.loc[key, "observed_unemp_2024"], model_u2024=ur[2024].mean()))
    t = pd.DataFrame(rows)
    from scipy.stats import spearmanr
    sign_match = int((np.sign(t.model_gva) == np.sign(t.obs_gva)).sum())
    gr, gm = rmse_mae(t.obs_gva, t.model_gva)
    rho = spearmanr(t.obs_gva, t.model_gva).correlation
    ur_r, ur_m = rmse_mae(t.obs_u2024, t.model_u2024)
    print(f"\n=== PART C: provincial scorecard, alpha=0.40 (10 seeds; 10 provinces) ===")
    print(t.round(2).to_string(index=False))
    print(f"\n  GVA-growth sign match: {sign_match}/10")
    print(f"  GVA-growth RMSE {gr:.2f}  MAE {gm:.2f}  Spearman(obs,model) {rho:+.2f}")
    print(f"  2024 unemployment RMSE {ur_r:.2f}  MAE {ur_m:.2f} (vs observed)")
    return t


def main():
    base = baseline_seeds()
    e16 = experiment_seeds("E16_unclamped_input_planning")
    a040 = experiment_seeds("ABL7_full_alpha040")
    print(f"seed counts: baseline={len(base)} E16={len(e16)} alpha040={len(a040)}")
    specs = {"Original MacroABM baseline": base, "Exact E16 (a=1.00)": e16, "Alpha=0.40 leading": a040}
    part_A(specs)
    print("\n=== PART B: national validation outputs for the paper ===")
    part_B("Original baseline (method check vs manuscript 1.03/2.41; 2.26/2.94; 7.07)", base)
    part_B("Alpha=0.40 leading", a040)
    part_C("ABL7_full_alpha040")


if __name__ == "__main__":
    main()
