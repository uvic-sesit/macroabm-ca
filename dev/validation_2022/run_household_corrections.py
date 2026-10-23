"""Sequential household attribution and saving diagnostic arms; no Phase B."""
import argparse
import hashlib
import json
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).parent / "battery"))
from accounting import AccountingBattery, IDENTITY_COLUMNS, summarise
from macro_data import DataWrapper
from macromodel.agents.households.func.consumption import ExogenousHouseholdConsumption
from macromodel.configurations import CountryConfiguration, SimulationConfiguration
from macromodel.simulation import Simulation


def run(args):
    warnings.filterwarnings("ignore")
    source_paths = sorted((REPO / "macromodel").rglob("*.py")) + [Path(__file__),
                    Path(__file__).parent / "battery" / "accounting.py"]
    source_hashes = {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    data = DataWrapper.init_from_pickle(args.pickle)
    names = [n for n in data.all_country_names if str(n).startswith("CAN_")]
    configs = {n: CountryConfiguration.n_industry_default(n_industries=data.n_industries) for n in names}
    for cfg in configs.values():
        cfg.household_closure.credit_enabled = args.arm in ("iii","iv","v","d1","deposit")
        cfg.household_closure.income_enabled = args.arm in ("iv","v","d1","deposit")
        cfg.household_closure.distress_enabled = args.arm == "v"
        cfg.household_closure.rent_offset_enabled = args.arm in ("d1","deposit")
        cfg.household_closure.deposit_only_saving = args.arm == "deposit"
    cfg = SimulationConfiguration(country_configurations=configs, t_max=args.quarters, seed=args.seed)
    sim = Simulation.from_datawrapper(data, cfg)
    battery = AccountingBattery()
    sim.posthooks.append(battery)
    calibration = {str(n):dict(required_ratio=c.household_closure.required_payout_ratio,
                    actual_ratio=c.household_closure.payout_ratio,
                    benchmark_shortfall=c.household_closure.benchmark_shortfall,
                    quarterly_dividend_target=c.configuration.household_closure.dividends_by_region[str(n)]/4,
                    initial_dividend_request=float(c.household_closure.requested_firm_payments[2].sum()+c.household_closure.bank_payout.sum()))
                   for n,c in sim.countries.items() if getattr(c,"household_closure",None) is not None}
    rows = []
    for t in range(args.quarters):
        sim.iterate(t)
        for name, c in sim.countries.items():
            h, e = c.households, c.economy
            value = lambda a, k: float(np.asarray(a.ts.current(k)).sum())
            f = c.firms
            L = f.states["Industry"] == 41
            y = value(h, "income")
            cash_c = value(h, "total_consumption") + value(h, "rent")
            net_interest = value(h, "interest_paid")
            cash_di = y - net_interest
            rows.append(dict(household_writeoffs=float(c.credit_market.states.get("household_writeoffs_current",0.)),
                             bank_loan_losses=float(np.asarray(c.banks.states.get("loan_losses_current",0.)).sum()),
                             L_sales=float(f.ts.current("nominal_amount_sold_in_lcu")[L].sum()),
                             L_employment=float(f.ts.current("number_of_employees")[L].sum())*c.scale,
                             L_offset=float(np.asarray(h.states.get("rent_L_offset_cash",0.)).sum()),
                             L_unoffset=float(np.asarray(h.states.get("rent_L_unoffset_cash",0.)).sum()),
                             principal=value(h,"debt_installments"),
                             mixed=value(h,"income_mixed") if args.arm in ("iv","v","d1","deposit") else 0.,
                             dividends=value(h,"income_dividends") if args.arm in ("iv","v","d1","deposit") else 0.,
                             transfers=value(h,"income_corporate_transfers") if args.arm in ("iv","v","d1","deposit") else 0.,
                             t=t, region=str(name), gdp_output=value(e, "gdp_output"),
                             gdp_income=value(e, "gdp_income"), gdp_expenditure=value(e, "gdp_expenditure"),
                             cash_income=y, cash_disposable_income=cash_di, consumption_cash=cash_c,
                             cash_saving=cash_di-cash_c, deposits=value(h, "wealth_deposits"),
                             debt=float(c.credit_market.states["cons_loans"][0].sum()
                                        + c.credit_market.states["mort_loans"][0].sum()),
                             recorded_household_debt=value(h, "debt"), imputed_housing=value(h, "rent_imputed"),
                             overdrawn_fraction=float(np.mean(h.ts.current("wealth_deposits") < 0)),
                             represented_households=value(h, "n_households") * c.scale,
                             calibrated_saving_propensity=h.states["average_saving_rate"],
                             new_credit=value(h, "received_consumption_loans") + value(h, "received_mortgages"),
                             restructurings=value(e, "household_insolvency_rate"),
                             cpi=value(e, "cpi")))
        print(f"{args.arm} seed={args.seed} quarter={t+1}/{args.quarters}", flush=True)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{args.arm}_q{args.quarters}_s{args.seed}"
    frame = battery.frame()
    frame.to_csv(out / f"{tag}_accounting_regions.csv", index=False)
    summarise(frame).to_csv(out / f"{tag}_accounting_national.csv")
    panel = pd.DataFrame(rows)
    panel.to_csv(out / f"{tag}_households_regions.csv", index=False)
    national = panel.groupby("t").sum(numeric_only=True)
    for col in ("overdrawn_fraction", "calibrated_saving_propensity", "restructurings", "cpi"):
        national[col] = panel.groupby("t").apply(
            lambda group: np.average(group[col], weights=group.represented_households), include_groups=False)
    national["cash_saving_rate"] = national.cash_saving / national.cash_disposable_income
    national.to_csv(out / f"{tag}_households_national.csv")
    checks = IDENTITY_COLUMNS + ["bank_hh_deposit_snapshot_gap", "bank_firm_deposit_snapshot_gap",
                                  "bank_equity_unexplained", "goods_market_gap"]
    # Test each region and period, never a signed national sum that can cancel.
    scale = frame[["hh_income", "firm_sales"]].abs().max(axis=1).clip(lower=1)
    errors = frame[checks].abs().div(scale, axis=0)
    finite = bool(np.isfinite(frame[checks].to_numpy()).all() and np.isfinite(panel.select_dtypes(include="number").to_numpy()).all())
    result = dict(dividend_calibration=calibration, arm=args.arm, seed=args.seed, quarters=args.quarters, finite=finite,
                  max_relative_identity_error=float(errors.max().max()),
                  max_absolute_identity_errors=frame[checks].abs().max().to_dict(),
                  accounting_pass=bool(finite and errors.max().max() < 1e-8),
                  pickle=str(args.pickle.resolve()), pickle_sha256=hashlib.sha256(args.pickle.read_bytes()).hexdigest(),
                  source_sha256=source_hashes,
                  head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                  working_tree_changes=subprocess.check_output(["git", "diff", "--stat"], cwd=REPO, text=True),
                  closure_configs={str(k): v.household_closure.model_dump() for k, v in configs.items()},
                  fixed_consumption_tail="last available real observation carried forward" if args.arm == "fixed" else None,
                  caveat="Scenario specification, not estimated or empirically validated; diagnostic rates use household weights.")
    (out / f"{tag}_checks.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ("arm", "quarters", "finite", "max_relative_identity_error",
                                             "accounting_pass", "pickle_sha256")}, indent=2), flush=True)
    if not result["accounting_pass"]:
        raise SystemExit("Accounting acceptance failed; inspect regional residuals")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pickle", type=Path, required=True)
    ap.add_argument("--arm", choices=("i","ii","iii","iv","v","d1","deposit"), default="i")
    ap.add_argument("--quarters", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "outputs" / "household_corrections")
    run(ap.parse_args())
