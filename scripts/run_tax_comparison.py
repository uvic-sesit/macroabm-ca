"""Provincial effective-tax-rate incremental comparison (candidate baseline).

Produces the two comparisons requested for the effective corporate/personal income tax
upgrade, using the same candidate growth baseline and per-province capture as
`run_candidate_baseline.py`:

  Comparison 1 (tax vs original baseline):        Baseline            vs  +tax
  Comparison 2 (tax on top of #1+#6):             +#1+#6              vs  +#1+#6+tax

Each *arm* is a DataWrapper pickle that differs ONLY in which provincial `new_raw_data`
files were present when it was built (the overrides bake into the pkl at build time, exactly
as documented in `provincial_candidate_baseline_comparison.md`). This script does NOT build
the pkls — build them with your normal provincial builder while staging `new_raw_data` so
that each arm sees only its files, e.g.:

    # Arm "baseline": temporarily move ALL three provincial CSVs out of
    #   new_raw_data/statcan_provincial/, then:
    python scenarios/run_canada_provincial.py --input-path <raw_data> --skip-simulation \
        --pkl-path <out>/arm_baseline.pkl --force-rebuild-pickle
    # Arm "tax": stage only provincial_tax_rates.csv -> arm_tax.pkl
    # Arm "macro_inv": stage provincial_macro_series.csv + provincial_investment_fractions.csv
    # Arm "macro_inv_tax": stage all three CSVs
    # (see build_arms() below for a helper that automates the staging + build)

Then run:
    python scripts/run_tax_comparison.py \
        --baseline <out>/arm_baseline.pkl --tax <out>/arm_tax.pkl \
        --macro-inv <out>/arm_macro_inv.pkl --macro-inv-tax <out>/arm_macro_inv_tax.pkl \
        [--quarters 53] [--seed 0]

Outputs (real numbers, generated from the runs — nothing is hand-written):
    docs/provincial_comparison_plots/tax_real_gva_by_province.png
    docs/provincial_comparison_plots/tax_unemployment_by_province.png
    docs/provincial_tax_comparison.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from macro_data import DataWrapper
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.configurations.growth_baseline_preset import apply_candidate_growth_baseline
from macromodel.simulation import Simulation

REPO = Path(__file__).resolve().parents[1]
PLOTS = REPO / "docs" / "provincial_comparison_plots"
DOC = REPO / "docs" / "provincial_tax_comparison.md"
HH_COLS = ["Real Household Consumption (Value)", "Household Consumption (Value)",
           "Real Household Investment (Value)", "Household Investment (Value)"]
HOUSEHOLD_DEMAND_GROWTH = 0.02
PROV_LABEL = {f"CAN_{a}": a for a in ["AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK"]}


def _extend_exogenous_national_accounts(model, required_length: int) -> None:
    """Hold the last real quarter of exogenous national accounts flat past the data tail."""
    for country in model.countries.values():
        frame = country.exogenous.national_accounts_during.copy()
        if len(frame) >= required_length:
            continue
        last_index = frame.index[-1]
        rows, index = [], []
        for step in range(required_length - len(frame)):
            rows.append(frame.iloc[-1].copy())
            index.append(last_index + pd.DateOffset(months=3 * (step + 1)))
        country.exogenous.national_accounts_during = pd.concat(
            [frame, pd.DataFrame(rows, index=index)], axis=0)


def capture_arm(pkl: Path, quarters: int, seed: int) -> pd.DataFrame:
    """Run the candidate baseline for one arm; return per-province real GVA + unemployment.

    Mirrors run_candidate_baseline.py exactly, but records the double-deflated real GVA
    (real output - real intermediate, at base-year prices) and unemployment *per province*.
    """
    data = DataWrapper.init_from_pickle(pkl)
    country_names = [c for c in data.all_country_names if c.startswith("CAN_")]
    if not country_names:
        raise SystemExit(f"{pkl}: could not determine province keys.")

    cfg = SimulationConfiguration(
        seed=seed,
        country_configurations={
            c: CountryConfiguration.n_industry_default(n_industries=data.n_industries) for c in country_names
        },
        t_max=quarters,
    )
    for i, c in enumerate(country_names):
        apply_candidate_growth_baseline(
            cfg.country_configurations[c],
            use_observed_labour_path=True, province=c, n_quarters=quarters + 1,
            demography_seed=1000 + i + 100 * seed,
        )

    m = Simulation.from_datawrapper(datawrapper=data, simulation_configuration=cfg)
    _extend_exogenous_national_accounts(m, required_length=quarters + 1)
    for country in m.countries.values():
        fr = country.exogenous.national_accounts_during
        fac = (1.0 + HOUSEHOLD_DEMAND_GROWTH) ** (np.arange(len(fr)) / 4.0)
        for col in HH_COLS:
            if col in fr.columns:
                fr[col] = fr[col].values * fac

    p0 = {c: np.array(m.countries[c].economy.ts.current("good_prices"), float).reshape(-1) for c in country_names}
    ro = {c: np.zeros(quarters) for c in country_names}
    ri = {c: np.zeros(quarters) for c in country_names}
    u = {c: np.zeros(quarters) for c in country_names}
    for t in range(quarters):
        m.iterate(t)
        for c in country_names:
            f = m.countries[c].firms
            base = p0[c]
            qr = np.array(f.ts.current("production"), float)
            ui = np.array(f.ts.current("used_intermediate_inputs"), float)
            ro[c][t] += float((qr * base).sum())
            ri[c][t] += float((ui * base[None, :]).sum()) if ui.ndim == 2 else 0.0
            u[c][t] = float(np.array(m.countries[c].economy.ts.current("unemployment_rate"),
                                     float).reshape(-1)[0])

    yrs = (quarters - 1) / 4.0
    rows = []
    for c in country_names:
        rva = ro[c] - ri[c]
        growth = ((rva[-1] / rva[0]) ** (1 / yrs) - 1) * 100 if rva[0] > 0 else np.nan
        rows.append({"province": PROV_LABEL.get(c, c), "rva_growth_pct_yr": growth,
                     "rva0": rva[0], "rva_end": rva[-1],
                     "u0": u[c][0], "u_end": u[c][-1], "u_mean": float(np.mean(u[c]))})
    return pd.DataFrame(rows).set_index("province").sort_index()


def _plot_by_province(arms: dict[str, pd.DataFrame], metric: str, title: str, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    provinces = sorted(next(iter(arms.values())).index)
    x = np.arange(len(provinces))
    width = 0.8 / len(arms)
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, (name, df) in enumerate(arms.items()):
        ax.bar(x + i * width, df.loc[provinces, metric].values, width, label=name)
    ax.set_xticks(x + width * (len(arms) - 1) / 2)
    ax.set_xticklabels(provinces)
    ax.set_title(title)
    ax.legend()
    ax.axhline(0, color="k", lw=0.5)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)


def _delta_table(before: pd.DataFrame, after: pd.DataFrame, col: str) -> pd.DataFrame:
    t = pd.DataFrame({"before": before[col], "after": after[col]})
    t["delta"] = t["after"] - t["before"]
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--tax", type=Path, required=True)
    ap.add_argument("--macro-inv", type=Path, required=True)
    ap.add_argument("--macro-inv-tax", type=Path, required=True)
    ap.add_argument("--quarters", type=int, default=53)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    arms = {
        "Baseline": capture_arm(a.baseline, a.quarters, a.seed),
        "+tax": capture_arm(a.tax, a.quarters, a.seed),
        "+#1+#6": capture_arm(a.macro_inv, a.quarters, a.seed),
        "+#1+#6+tax": capture_arm(a.macro_inv_tax, a.quarters, a.seed),
    }

    # Comparison 1: tax vs original baseline ; Comparison 2: tax on top of #1+#6
    _plot_by_province({"Baseline": arms["Baseline"], "+tax": arms["+tax"]},
                      "rva_growth_pct_yr", "Comparison 1 — real GVA growth (%/yr): Baseline vs +tax",
                      PLOTS / "tax_real_gva_by_province.png")
    _plot_by_province({"+#1+#6": arms["+#1+#6"], "+#1+#6+tax": arms["+#1+#6+tax"]},
                      "u_mean", "Comparison 2 — mean unemployment: +#1+#6 vs +#1+#6+tax",
                      PLOTS / "tax_unemployment_by_province.png")

    c1 = _delta_table(arms["Baseline"], arms["+tax"], "rva_growth_pct_yr")
    c2 = _delta_table(arms["+#1+#6"], arms["+#1+#6+tax"], "rva_growth_pct_yr")

    def national(df: pd.DataFrame) -> tuple[float, float]:
        rva0, rvae = df["rva0"].sum(), df["rva_end"].sum()
        yrs = (a.quarters - 1) / 4.0
        return ((rvae / rva0) ** (1 / yrs) - 1) * 100, float(df["u_mean"].mean())

    lines = ["# Provincial Data — Effective Tax-Rate Incremental Comparison", "",
             f"Auto-generated by `scripts/run_tax_comparison.py` (seed {a.seed}, {a.quarters}q). "
             "Same candidate growth baseline and per-province double-deflated real-GVA capture as "
             "`provincial_candidate_baseline_comparison.md`; arms differ only in which provincial "
             "data is baked into the pkl.", "",
             "## National aggregate", "",
             "| Arm | Real GVA growth (%/yr) | Mean unemployment |", "|---|---:|---:|"]
    for name, df in arms.items():
        g, um = national(df)
        lines.append(f"| {name} | {g:.2f} | {um*100:.1f}% |")
    lines += ["", "## Comparison 1 — new tax data vs original baseline", "",
              "Per-province real GVA growth (%/yr):", "",
              "| Prov | Baseline | +tax | Δ |", "|---|---:|---:|---:|"]
    for p in c1.index:
        lines.append(f"| {p} | {c1.loc[p,'before']:.2f} | {c1.loc[p,'after']:.2f} | {c1.loc[p,'delta']:+.2f} |")
    lines += ["", "![Comparison 1](provincial_comparison_plots/tax_real_gva_by_province.png)", "",
              "## Comparison 2 — tax on top of #1+#6 (vs #1+#6 only)", "",
              "Per-province real GVA growth (%/yr):", "",
              "| Prov | +#1+#6 | +#1+#6+tax | Δ |", "|---|---:|---:|---:|"]
    for p in c2.index:
        lines.append(f"| {p} | {c2.loc[p,'before']:.2f} | {c2.loc[p,'after']:.2f} | {c2.loc[p,'delta']:+.2f} |")
    lines += ["", "![Comparison 2](provincial_comparison_plots/tax_unemployment_by_province.png)", "",
              "## Caveats", "",
              "- Single seed; per-province trajectories carry seed noise (confirm with a sweep).",
              "- The national corporate rate shifts statutory→effective in the tax arm, so part of the "
              "corporate-side movement in Comparison 1 is this concept correction, not cross-province "
              "reallocation. Comparison 2 isolates the tax effect on top of #1+#6.",
              "- Full-employment ceiling compresses long-horizon unemployment (see the candidate-baseline doc).",
              ""]
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {DOC}")
    print(f"wrote {PLOTS/'tax_real_gva_by_province.png'} and {PLOTS/'tax_unemployment_by_province.png'}")


if __name__ == "__main__":
    main()
