"""Accounting battery for MacroABM-CA (validation-2022).

Used as a Simulation post-hook: after every quarter it records, per region and nationally,

1. sector cash identities (households, firms): the change in deposits implied by the booked cash flows
   minus the actual change in deposits;
2. counterparty identities: wages (firm wage bill = household net receipts + PIT + SSC),
   rent (renters' payments = landlords' receipts + rental PIT + social-housing rent), house sales
   (price paid = proceeds received), government transfers (paid = received);
3. a decomposition of the change in the banks' reserve position R_b. R_b = D_f + D_h + E_b - L is a balancing
   residual in the model (banks.py compute_deposits), so a leak anywhere shows up only as unexplained dR_b.
   With complete counterparties, dR_b equals the government cash deficit (excluding the unpaid interest on
   debt, A11), plus net external receipts (ROW and other provinces), plus CB interest on reserves, plus the
   explicitly named boundary terms that have no counterparty in the model:
     - FA income received by households (A4: no payer) and PIT booked on it (A5),
     - net household saving into "other financial assets" (A7: no issuer), entered with a minus sign,
     - loan write-offs (A14: loans removed with no bank loss), firm-deposit zeroing at insolvency,
     - bank equity injections.
   The remaining "unexplained" term must be ~0; anything else is an unnamed leak.

All amounts are nominal CAD per quarter (model units).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def _cur(ts, key, default=0.0):
    try:
        return np.asarray(ts.current(key), dtype=float)
    except (KeyError, IndexError):
        return np.asarray(default, dtype=float)


def _prev(ts, key):
    return np.asarray(ts.prev(key), dtype=float)


@dataclass
class AccountingBattery:
    records: list = field(default_factory=list)
    _writeoffs_seen: dict = field(default_factory=dict)

    def __call__(self, sim, t, year, month):  # Simulation post-hook signature
        rows = []
        for name, c in sim.countries.items():
            cum = c.credit_market.states.get("cumulative_writeoffs", np.nan)
            w = cum - self._writeoffs_seen.get(str(name), 0.0)
            self._writeoffs_seen[str(name)] = cum
            rows.append(self.region_record(sim, name, c, t, writeoffs_explicit=w))
        self.records.extend(rows)

    # ------------------------------------------------------------------ per region
    @staticmethod
    def region_record(sim, name, c, t, writeoffs_explicit=np.nan):
        h, f, b, g, ge, e, ind = (c.households, c.firms, c.banks, c.central_government, c.government_entities,
                                  c.economy, c.individuals)
        st = g.states
        r = {"t": t, "region": str(name)}

        # ---------- households: cash identity (deposits)
        Y = _cur(h.ts, "income").sum()
        rent = _cur(h.ts, "rent").sum()
        spent = _cur(h.ts, "nominal_amount_spent_in_lcu").sum()
        vat = _cur(h.ts, "vat_paid").sum()
        inv = _cur(h.ts, "investment").sum(axis=1)
        tau_cf_paid = st["Capital Formation Tax"] * np.maximum(0.0, inv).sum()
        d_ofa = _cur(h.ts, "wealth_other_financial_assets").sum() - _prev(h.ts, "wealth_other_financial_assets").sum()
        int_h = _cur(h.ts, "interest_paid").sum()
        price = _cur(h.ts, "price_paid_for_property").sum()
        proceeds = _cur(h.ts, "property_sale_proceeds").sum()
        inst_h = _cur(h.ts, "debt_installments").sum()
        new_h = _cur(h.ts, "received_consumption_loans").sum() + _cur(h.ts, "received_mortgages").sum()
        dD_h = _cur(h.ts, "wealth_deposits").sum() - _prev(h.ts, "wealth_deposits").sum()
        implied_h = (Y - rent - spent) - d_ofa - int_h - price - inst_h + new_h - tau_cf_paid - vat + proceeds
        r.update(hh_income=Y, hh_consumption_basic=_cur(h.ts, "consumption").sum(), hh_vat_paid=vat,
                 hh_rent_paid=rent, hh_dDeposits=dD_h, hh_dOFA=d_ofa, hh_cash_identity_resid=dD_h - implied_h,
                 hh_new_loans=new_h, hh_principal=inst_h)

        # ---------- firms: cash identity (deposits)
        sold = _cur(f.ts, "nominal_amount_sold_in_lcu").sum()
        wb = _cur(f.ts, "total_wage").sum()
        bought = _cur(f.ts, "nominal_amount_spent_in_lcu").sum()
        tprod = _cur(f.ts, "taxes_paid_on_production").sum()
        tcorp = _cur(f.ts, "corporate_taxes_paid").sum()
        int_f = _cur(f.ts, "interest_paid").sum()
        itc = _cur(f.ts, "itc_refunds").sum()
        credit = _cur(f.ts, "received_credit").sum()
        inst_f = _cur(f.ts, "debt_installments").sum()
        dD_f = _cur(f.ts, "deposits").sum() - _prev(f.ts, "deposits").sum()
        implied_f = sold - wb - bought - tprod - tcorp - int_f + itc + credit - inst_f
        distributions = _cur(f.ts, "household_distributions", [0.0]).sum()
        bank_dividends = _cur(b.ts, "household_dividends", [0.0]).sum()
        implied_f -= distributions
        # Non-cash relief of an explicit overdraft liability is recognized
        # separately, not inferred from an unexplained cash residual.
        firm_od_relief = float(np.sum(f.states.get('overdraft_writeoff_current', 0.)))
        implied_f += firm_od_relief
        r['firm_overdraft_relief'] = firm_od_relief
        hh_distributions = sum(_cur(h.ts, k, [0.0]).sum() for k in
                               ("income_mixed", "income_dividends", "income_corporate_transfers"))
        distribution_tax = _cur(g.ts, "taxes_household_distributions", [0.0]).sum()
        r["household_distribution_counterparty_resid"] = distributions + bank_dividends - hh_distributions - distribution_tax
        r["imputed_housing_pair_resid"] = (_cur(h.ts, "income_imputed_housing", [0.0]).sum()
                                            - _cur(h.ts, "consumption_imputed_housing", [0.0]).sum())
        r.update(firm_distributions=distributions, bank_dividends=bank_dividends,
                 hh_distributions=hh_distributions, distribution_tax=distribution_tax)
        r.update(firm_wage_bill=wb, firm_sales=sold, firm_purchases=bought, firm_dDeposits=dD_f,
                 firm_cash_identity_resid=dD_f - implied_f)  # = - deposits zeroed at insolvency

        # ---------- counterparty: wages
        cpi = float(_cur(e.ts, "cpi")[0])
        hh_wages = _cur(h.ts, "income_employee").sum()
        labour_taxes = (_cur(g.ts, "taxes_employee_si")[0] + _cur(g.ts, "taxes_employer_si")[0]
                        + st["Income Tax"] * (1 - st["Employee Social Insurance Tax"]) * _cur(g.ts, "gross_wages", [0.0])[0])
        r.update(cpi=cpi, hh_wage_receipts=hh_wages, wage_counterparty_resid=wb - hh_wages - labour_taxes)

        # ---------- counterparty: rent (renters -> landlords + PIT on rent + social-housing rent to gov)
        rent_income = _cur(h.ts, "income_rental").sum()
        rent_pit = _cur(g.ts, "taxes_rental_income")[0]
        rent_gov = _cur(g.ts, "total_rent_received")[0]
        r.update(rent_counterparty_resid=rent - rent_income - rent_pit - rent_gov, hh_rental_income=rent_income)

        # ---------- counterparty: house sales; transfers
        r.update(house_sales_resid=price - proceeds, house_sales_value=price)
        ub_paid = _cur(g.ts, "unemployment_benefits_paid", [np.nan])[0]
        if not np.isfinite(ub_paid):  # pre-correction code: deficit books n_unemployed * UB per person
            from macromodel.agents.individuals.individual_properties import ActivityStatus
            n_u = np.sum(ind.states["Activity Status"] == ActivityStatus.UNEMPLOYED)
            ub_paid = n_u * _cur(g.ts, "unemployment_benefits_by_individual")[0]
        ub_recv = _cur(h.ts, "income_unemployment_benefits").sum()
        tr = _cur(h.ts, "income_social_transfers").sum()
        r.update(ub_counterparty_resid=ub_paid - ub_recv, hh_ub=ub_recv, hh_transfers=tr)

        # ---------- government cash deficit (excluding unpaid interest on debt, A11)
        G = _cur(ge.ts, "nominal_amount_spent_in_lcu").sum()
        rev = _cur(g.ts, "revenue")[0]
        itc_gov = _cur(g.ts, "itc_refunds", [0.0])[0]
        injection = _cur(g.ts, "bank_equity_injection", [0.0])[0]
        cash_deficit = ub_paid + tr + G + itc_gov + injection - rev
        r.update(gov_G=G, gov_revenue=rev, gov_cash_deficit=cash_deficit, gov_deficit_booked=_cur(g.ts, "deficit")[0])

        # ---------- external receipts (ROW and other provinces)
        ext = 0.0
        for other in list(sim.countries.keys()) + ["ROW"]:
            if str(other) == str(name):
                continue
            x = e.ts.dicts.get("exports_before_taxes_to_" + str(other))
            m = e.ts.dicts.get("imports_from_" + str(other))
            if x is not None:
                ext += np.asarray(x[-1], float).sum()
            if m is not None:
                ext -= np.asarray(m[-1], float).sum()
        r.update(net_external_receipts=ext)
        # goods market: what domestic firms receive minus what all buyers pay, net of cross-border flows
        # (sold - exports) - (hh + firm + gov purchases - imports); must be 0
        exp_tot = sum(np.asarray(e.ts.dicts["exports_before_taxes_to_" + str(o)][-1], float).sum()
                      for o in list(sim.countries.keys()) + ["ROW"]
                      if str(o) != str(name) and ("exports_before_taxes_to_" + str(o)) in e.ts.dicts)
        imp_tot = sum(np.asarray(e.ts.dicts["imports_from_" + str(o)][-1], float).sum()
                      for o in list(sim.countries.keys()) + ["ROW"]
                      if str(o) != str(name) and ("imports_from_" + str(o)) in e.ts.dicts)
        G_all = _cur(ge.ts, "nominal_amount_spent_in_lcu").sum()
        r["goods_market_gap"] = (sold - exp_tot) - (spent + bought + G_all - imp_tot)

        # ---------- bank reserve residual and its decomposition
        # R from its defining identity on both dates (banks.compute_deposits), so that the t0 data value of the
        # reserve position does not enter the first-quarter change.
        def _res(fn):
            return (fn(b.ts, "deposits_from_firms").sum() + fn(b.ts, "deposits_from_households").sum()
                    + fn(b.ts, "equity").sum() - fn(b.ts, "total_outstanding_loans").sum())
        R = np.atleast_1d(_res(_cur)); R_prev = np.atleast_1d(_res(_prev))
        R_prev_banks = _prev(b.ts, "deposits")
        rate = float(_cur(c.central_bank.ts, "policy_rate")[0])
        cb_interest = (rate * np.maximum(0, R_prev_banks) - rate * np.maximum(0, -R_prev_banks)).sum()
        L = _cur(b.ts, "total_outstanding_loans").sum(); L_prev = _prev(b.ts, "total_outstanding_loans").sum()
        # loan-stock identity: dL = new loans - principal repaid - write-offs (explicitly recorded by the credit
        # market; NaN on code without the counter). t=0 compares with the banks' t0 data stock, so it also shows
        # any initial inconsistency between bank loan data and the credit market's loan book.
        writeoffs = writeoffs_explicit if np.isfinite(writeoffs_explicit) else 0.0
        loan_identity_resid = (L - L_prev) - ((new_h + credit) - (inst_h + inst_f) - writeoffs)
        fai = _cur(h.ts, "income_financial_assets").sum()
        fai_pit = st["Income Tax"] * fai
        injection = _cur(g.ts, "bank_equity_injection", [0.0])[0]
        firm_zeroing = -(dD_f - implied_f)
        dR = R.sum() - R_prev.sum()
        # internal links of the reserve identity: the banks' deposit snapshot vs the agents' own balances, and
        # the change in bank equity vs after-tax profits (+ injections)
        r["bank_hh_deposit_snapshot_gap"] = _cur(b.ts, "deposits_from_households").sum() - _cur(h.ts, "wealth_deposits").sum()
        r["bank_firm_deposit_snapshot_gap"] = _cur(b.ts, "deposits_from_firms").sum() - _cur(f.ts, "deposits").sum()
        prof = _cur(b.ts, "profits")
        dE = _cur(b.ts, "equity").sum() - _prev(b.ts, "equity").sum()
        losses = float(np.sum(b.states.get("loan_losses_current", 0.0)))
        r["bank_loan_losses"] = losses
        bank_recap = float(np.sum(b.states.get('recapitalisation_current', 0.)))
        r['bank_recapitalisation'] = bank_recap
        r['bank_recapitalisation_counterparty_resid'] = injection - bank_recap
        r["bank_equity_unexplained"] = dE - (prof.sum() - st["Profit Tax"] * np.maximum(0, prof).sum() - losses - bank_dividends + bank_recap)
        # write-offs move R only to the extent that the lending bank does not recognise the loss (A14)
        named_boundary = fai + fai_pit - d_ofa + (writeoffs - losses) + firm_od_relief - firm_zeroing
        r['ofa_without_issuer'] = -d_ofa
        r['ofa_liquidation_without_issuer'] = float(np.sum(h.states.get('ofa_liquidation_without_issuer', 0.)))
        # an unexplained jump in the loan stock moves R one-for-one with opposite sign; it is reported separately
        # (loan_identity_resid) so that reserves_unexplained isolates deposit-side (payment) leaks
        explained = cash_deficit + ext + cb_interest + named_boundary - loan_identity_resid
        r.update(dR_bank=dR, cb_interest=cb_interest, writeoffs=writeoffs, loan_identity_resid=loan_identity_resid, fa_income_unfunded=fai,
                 fa_pit_phantom=fai_pit, firm_deposit_zeroing=firm_zeroing, bank_injection=injection,
                 named_boundary_total=named_boundary, reserves_unexplained=dR - explained,
                 hh_cash_identity_check=implied_h)
        return r

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.records)


IDENTITY_COLUMNS = [
    "bank_recapitalisation_counterparty_resid",
    "loan_identity_resid",
    "hh_cash_identity_resid", "wage_counterparty_resid", "rent_counterparty_resid", "house_sales_resid",
    "ub_counterparty_resid", "reserves_unexplained",
    "household_distribution_counterparty_resid", "imputed_housing_pair_resid",
]


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    """National (sum over regions) residuals per quarter, with scale for relative tolerance."""
    nat = df.groupby("t").sum(numeric_only=True, min_count=1)
    diag = [c for c in ("bank_loan_losses", "goods_market_gap", "bank_hh_deposit_snapshot_gap", "bank_firm_deposit_snapshot_gap", "bank_equity_unexplained")
            if c in nat]
    out = nat[IDENTITY_COLUMNS + diag + ["named_boundary_total", "firm_wage_bill", "gov_cash_deficit", "dR_bank",
                                  "net_external_receipts"]].copy()
    return out
