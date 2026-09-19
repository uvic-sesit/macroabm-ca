"""MacroABM-CA publication collector -- SINGLE SOURCE OF TRUTH for schema + annualisation.

pub_stage.py owns arm execution and instrumentation; this module owns
  * what is measured (variable lists and their kind),
  * how one quarter is read off the model (collect_row),
  * the period/row convention (to_periods),
  * how quarters become years and windows (annualize / window_agg).

CONVENTIONS ENFORCED HERE
-------------------------
1. PERIOD LABELLING. collect() runs BEFORE model.iterate(t), so the state read at
   row t is everything produced by iterate(t-1) == period t-1. Row 0 is the
   pre-simulation initial state and is DROPPED. With q_run = 56 we get 57 rows;
   rows 1..56 == periods 0..55 == 2022Q1..2035Q4.
   ITC is active for iterate indices ACT0=16..ACT1=35 == periods 16..35 ==
   2026Q1..2030Q4 inclusive.

2. EVERY national variable is collected as a 13-vector over regions. National
   aggregates are formed by summing regions in post-processing, so any regional
   subsetting (e.g. the 10 provinces only, as the old diagnostics did) is
   reproducible without a rerun.

3. NATIONAL UNEMPLOYMENT = sum(unemployed) / sum(labour force). Never a mean of
   provincial rates, at any level of aggregation.

4. ALL 650 CELLS ARE PRESERVED. No screening, trimming, winsorization or
   denominator rule is applied at save time.
"""
from __future__ import annotations
import numpy as np

B = 1e9
N_SECTORS = 50
N_REGIONS = 13
N_CELLS = N_REGIONS * N_SECTORS          # 650
START_YEAR = 2022
N_PERIODS = 56                            # 2022Q1 .. 2035Q4
ACT0, ACT1 = 16, 35                       # ITC-active PERIODS == 2026Q1 .. 2030Q4
WINDOWS = {"w2026_30": (2026, 2030), "w2031_35": (2031, 2035), "w2026_35": (2026, 2035)}
ARMS = ("control", "uc_full", "uc_noB")

# ---------------------------------------------------------------- schema
# Region-level flows: summed over quarters within a year / window, summed over regions.
REG_FLOW = [
    "production", "real_gva", "nominal_gva",
    "desired_investment", "realized_investment", "eligible_purchases",
    "household_consumption", "imports_row", "exports_row_goods", "exports_row_services",
    "intermediate_use", "unmet_demand", "total_wage",
    "tax_revenue", "taxes_production", "taxes_vat", "taxes_cf", "taxes_corporate_income",
    "taxes_exports", "taxes_income", "taxes_employee_si", "taxes_employer_si",
    "benefits_transfers",
    "government_desired_purchases", "government_realized_purchases",
    "government_unrealized_purchases",
    "itc_refunds", "government_interest_expense", "deficit",
]
# Region-level stocks: period-end value within a year / window.
REG_STOCK = ["capital_stock", "inventory", "employed_agents", "unemployed_agents",
             "labour_force_agents", "debt"]
# Region-level rates/indices: diagnostics; aggregated with explicit weights.
REG_RATE = ["cpi", "ppi", "cfpi", "cpi_inflation", "ppi_inflation", "cfpi_inflation",
            "policy_rate", "firm_lending_rate"]
# Metadata: NEVER summed. `region_scale` is the number of real people represented by
# one agent in that region. It is 1000 for the ten provinces and 10 for YT/NT/NU,
# a deliberate variable-scale sampling design so the tiny territories still get
# enough agents to support a functioning labour market.
REG_META = ["region_scale"]
REG_ALL = REG_FLOW + REG_STOCK + REG_RATE + REG_META

# Head-count variables in PERSONS (agents x region_scale). These, not the raw
# *_agents counts, are the only valid cross-region head-count aggregates.
PERSON_VARS = ["employed_persons", "unemployed_persons", "labour_force_persons"]

# Provincial publication block (subset of REG_ALL reported per region in outputs).
PROV_VARS = ["real_gva", "nominal_gva", "production", "employed_agents", "unemployed_agents",
             "labour_force_agents", "realized_investment", "government_realized_purchases",
             "imports_row", "exports_row_goods", "exports_row_services"]

# Per-cell quarterly series (650-vectors) retained to build cell deltas.
CELL_FLOW = ["production", "real_gva", "realized_investment", "imports_row"]
CELL_STOCK = ["capital_stock"]
# Per-cell structural raw material, averaged over the pre-policy window.
CELL_STRUCT_RAW = ["employees", "output_value", "wage_bill", "intermediate_value",
                   "purchases_total", "purchases_row", "purchases_interprov",
                   "capital_total", "capital_eligible"]
CELL_ALL = CELL_FLOW + CELL_STOCK + CELL_STRUCT_RAW

PRE_POLICY = (2024, 2025)                 # baseline window for structural shares


def _v(x):
    return np.asarray(x, float).reshape(-1)


def _m(x, n=N_SECTORS):
    return np.asarray(x, float).reshape(-1, n)


# ---------------------------------------------------------------- one quarter
def collect_row(model, provs, p0, goods_mask, eligible):
    """Read one collect row.

    Returns (reg, cell, names):
      reg  : {var: np.ndarray(n_regions)}  for every name in REG_ALL
      cell : {var: np.ndarray(n_regions*50)} for every name in CELL_ALL

    p0[c] is the initial good-price vector for region c, used for constant-price
    (real) valuation. Nominal valuation uses current prices.
    """
    nreg = len(provs)
    reg = {k: np.zeros(nreg) for k in REG_ALL}
    cell = {k: [] for k in CELL_ALL}
    names = [str(c) for c in provs]

    for pi, c in enumerate(provs):
        co = model.countries[c]
        fg = co.firms
        econ = co.economy.ts
        gov = co.central_government.ts
        gent = co.government_entities.ts
        base, cur = p0[c], _v(econ.current("good_prices"))
        ind = fg.states["Industry"]
        fp_base, fp_cur = base[ind], cur[ind]

        q = _v(fg.ts.current("production"))
        ui = _m(fg.ts.current("used_intermediate_inputs"))
        ui_base = (ui * base[None, :]).sum(1)
        ui_cur = (ui * cur[None, :]).sum(1)
        rac = _m(fg.ts.current("real_amount_bought_as_capital_goods"))
        uci = _m(fg.ts.current("unconstrained_target_capital_inputs"))
        kst = _m(fg.ts.current("capital_inputs_stock"))
        buy = np.nan_to_num(_m(fg.ts.current("real_amount_bought")), nan=0.0)
        row_buy = np.nan_to_num(_m(fg.ts.current("real_amount_bought_from_ROW")), nan=0.0)
        wage = _v(fg.ts.current("total_wage"))
        try:
            emp_f = _v(fg.ts.current("number_of_employees"))
        except Exception:
            emp_f = np.zeros_like(q)

        # interprovincial sourcing: every CAN region other than this one
        inter = np.zeros_like(buy)
        for other in getattr(fg, "all_country_names", []):
            if other == "ROW" or other == str(c):
                continue
            try:
                inter += np.nan_to_num(_m(fg.ts.current("real_amount_bought_from_" + other)), nan=0.0)
            except Exception:
                pass

        # ---- per-cell blocks (650 preserved; no screen) ----
        c_prod = q * fp_base / B
        c_rgva = (q * fp_base - ui_base) / B
        c_inv = (rac * cur[None, :]).sum(1) / B
        c_imp = (row_buy * cur[None, :]).sum(1) / B
        c_k = (kst * cur[None, :]).sum(1) / B
        c_elig = (rac[:, eligible] * cur[eligible][None, :]).sum(1) / B
        for k, v in (("production", c_prod), ("real_gva", c_rgva),
                     ("realized_investment", c_inv), ("imports_row", c_imp),
                     ("capital_stock", c_k), ("employees", emp_f),
                     ("output_value", q * fp_cur / B), ("wage_bill", wage / B),
                     ("intermediate_value", ui_cur / B),
                     ("purchases_total", (buy * cur[None, :]).sum(1) / B),
                     ("purchases_row", c_imp),
                     ("purchases_interprov", (inter * cur[None, :]).sum(1) / B),
                     ("capital_total", c_inv), ("capital_eligible", c_elig)):
            cell[k].append(v)

        # ---- region-level ----
        status = np.asarray([a.name for a in co.individuals.states["Activity Status"]])
        emp = float((status == "EMPLOYED").sum())
        une = float((status == "UNEMPLOYED").sum())
        xr = _v(econ.current("exports_before_taxes_to_ROW"))
        xg = float(xr[goods_mask].sum()) / B if goods_mask is not None else float(xr.sum()) / B
        xs = float(xr[~goods_mask].sum()) / B if goods_mask is not None else 0.0

        desired_g = float(_v(gent.current("desired_consumption_in_lcu")).sum()) / B
        realized_g = float(np.asarray(gent.current("nominal_amount_spent_in_lcu"), float).sum()) / B
        unemp_ben = une * float(_v(gov.current("unemployment_benefits_by_individual"))[0])
        transfers = float(np.asarray(co.households.ts.current("income_social_transfers"), float).sum())
        benefits = (unemp_ben + transfers) / B

        def g(key):
            try:
                return float(_v(gov.current(key))[0]) / B
            except Exception:
                return 0.0

        revenue, refunds, deficit = g("revenue"), g("itc_refunds"), g("deficit")
        # residual identity: deficit = G + benefits + interest + refunds - revenue
        interest = deficit + revenue - realized_g - benefits - refunds

        vals = dict(
            production=float(c_prod.sum()), real_gva=float(c_rgva.sum()),
            nominal_gva=float((q * fp_cur - ui_cur).sum()) / B,
            desired_investment=float((uci * cur[None, :]).sum()) / B,
            realized_investment=float(c_inv.sum()),
            eligible_purchases=float(c_elig.sum()),
            household_consumption=float(_v(co.households.ts.current("total_consumption"))[0]) / B,
            imports_row=float(c_imp.sum()), exports_row_goods=xg, exports_row_services=xs,
            intermediate_use=float(ui_base.sum()) / B,
            unmet_demand=float(np.nan_to_num(_v(fg.ts.current("real_excess_demand")), nan=0.0).sum()) / B,
            total_wage=float(wage.sum()) / B,
            tax_revenue=revenue, taxes_production=g("taxes_production"), taxes_vat=g("taxes_vat"),
            taxes_cf=g("taxes_cf"), taxes_corporate_income=g("taxes_corporate_income"),
            taxes_exports=g("taxes_exports"), taxes_income=g("taxes_income"),
            taxes_employee_si=g("taxes_employee_si"), taxes_employer_si=g("taxes_employer_si"),
            benefits_transfers=benefits,
            government_desired_purchases=desired_g,
            government_realized_purchases=realized_g,
            government_unrealized_purchases=desired_g - realized_g,
            itc_refunds=refunds, government_interest_expense=interest, deficit=deficit,
            capital_stock=float(c_k.sum()),
            inventory=float(_v(fg.ts.current("inventory")).dot(fp_base)) / B,
            employed_agents=emp, unemployed_agents=une, labour_force_agents=emp + une,
            debt=g("debt"),
            region_scale=float(getattr(co, "scale", 1.0)),
        )
        for k in ("cpi", "ppi", "cfpi", "cpi_inflation", "ppi_inflation", "cfpi_inflation"):
            try:
                vals[k] = float(_v(econ.current(k))[0])
            except Exception:
                vals[k] = np.nan
        try:
            vals["policy_rate"] = float(_v(co.central_bank.ts.current("policy_rate"))[0])
        except Exception:
            vals["policy_rate"] = np.nan
        try:
            bk = co.banks.ts
            vals["firm_lending_rate"] = 0.5 * (
                float(_v(bk.current("average_interest_rates_on_short_term_firm_loans"))[0])
                + float(_v(bk.current("average_interest_rates_on_long_term_firm_loans"))[0]))
        except Exception:
            vals["firm_lending_rate"] = np.nan

        for k in REG_ALL:
            reg[k][pi] = vals[k]

    return reg, {k: np.concatenate(v) for k, v in cell.items()}, names


# ---------------------------------------------------------------- period handling
def to_periods(rows):
    """rows[t] holds the state produced by iterate(t-1) == period t-1.
    Drop row 0 (pre-simulation) so index p == period p == quarter START_YEAR + p/4."""
    return rows[1:]


def stack(rows, keys):
    """List-of-dict-of-vector rows -> {key: array(n_periods, n_regions_or_cells)}."""
    return {k: np.array([r[k] for r in rows], float) for k in keys}


def period_years(n_periods=N_PERIODS):
    return np.array([START_YEAR + p // 4 for p in range(n_periods)])


def quarter_labels(n_periods=N_PERIODS):
    return np.array(["%dQ%d" % (START_YEAR + p // 4, p % 4 + 1) for p in range(n_periods)])


# ---------------------------------------------------------------- aggregation
def national(reg, regions=None, names=None):
    """Sum region-level series to national. `regions` = list of region names to
    include (default: all). Rates are aggregated with explicit weights."""
    if regions is None or names is None:
        sel = np.arange(reg["real_gva"].shape[1])
    else:
        sel = np.array([i for i, n in enumerate(names) if n in regions])
    out = {}
    for k in REG_FLOW + REG_STOCK:
        out[k] = reg[k][:, sel].sum(1)
    # HEAD COUNTS: an agent represents `region_scale` people, and that scale differs
    # by region (1000 in the provinces, 10 in the territories). Summing raw agent
    # counts across regions therefore over-weights the territories 100-fold. Convert
    # to persons before any cross-region aggregation. Raw *_agents sums are retained
    # above for auditability only.
    sc = reg["region_scale"][:, sel]
    for a, p_ in (("employed_agents", "employed_persons"),
                  ("unemployed_agents", "unemployed_persons"),
                  ("labour_force_agents", "labour_force_persons")):
        out[p_] = (reg[a][:, sel] * sc).sum(1)
    w = reg["household_consumption"][:, sel]
    wsum = w.sum(1)
    for k in ("cpi", "ppi", "cfpi", "cpi_inflation", "ppi_inflation", "cfpi_inflation"):
        out[k] = np.where(wsum > 0,
                          np.nansum(reg[k][:, sel] * w, 1) / np.where(wsum > 0, wsum, 1.0),
                          np.nan)
    for k in ("policy_rate", "firm_lending_rate"):
        out[k] = np.nanmean(reg[k][:, sel], 1)
    lf = out["labour_force_persons"]
    out["unemployment_rate"] = np.where(lf > 0, out["unemployed_persons"] / lf * 100.0, np.nan)
    out["gva_deflator"] = np.where(out["real_gva"] > 0, out["nominal_gva"] / out["real_gva"], np.nan)
    return out


def annualize(nat, n_periods=N_PERIODS):
    """Annual paths. Flows summed; stocks at year end; unemployment = sum(U)/sum(LF)
    over the four quarters; indices averaged over the four quarters."""
    yr = period_years(n_periods)
    years = sorted(set(yr.tolist()))
    out = {"years": np.array(years)}
    for k in REG_FLOW:
        out[k] = np.array([np.nansum(nat[k][yr == y]) for y in years])
    for k in REG_STOCK + PERSON_VARS:
        out[k] = np.array([nat[k][np.where(yr == y)[0][-1]] for y in years])
    u = np.array([np.nansum(nat["unemployed_persons"][yr == y]) for y in years])
    l = np.array([np.nansum(nat["labour_force_persons"][yr == y]) for y in years])
    out["unemployment_rate"] = np.where(l > 0, u / l * 100.0, np.nan)
    for k in ("cpi", "ppi", "cfpi", "policy_rate", "firm_lending_rate"):
        out[k] = np.array([np.nanmean(nat[k][yr == y]) for y in years])
    # annual inflation: Q4-over-Q4 of the index (NaN in the first year)
    for idx, nm in (("cpi", "cpi_inflation"), ("ppi", "ppi_inflation"), ("cfpi", "cfpi_inflation")):
        lvl = np.array([nat[idx][np.where(yr == y)[0][-1]] for y in years])
        out[nm] = np.concatenate([[np.nan], lvl[1:] / lvl[:-1] - 1.0])
    out["gva_deflator"] = np.where(out["real_gva"] > 0, out["nominal_gva"] / out["real_gva"], np.nan)
    return out


def window_agg(nat, n_periods=N_PERIODS):
    yr = period_years(n_periods)
    out = {}
    for wname, (lo, hi) in WINDOWS.items():
        m = (yr >= lo) & (yr <= hi)
        end = np.where(yr == hi)[0][-1]
        for k in REG_FLOW:
            out["%s__%s" % (wname, k)] = float(np.nansum(nat[k][m]))
        for k in REG_STOCK + PERSON_VARS:
            out["%s__%s" % (wname, k)] = float(nat[k][end])
        lf = np.nansum(nat["labour_force_persons"][m])
        out["%s__unemployment_rate" % wname] = float(
            np.nansum(nat["unemployed_persons"][m]) / lf * 100.0) if lf > 0 else np.nan
        rg = np.nansum(nat["real_gva"][m])
        out["%s__gva_deflator" % wname] = float(np.nansum(nat["nominal_gva"][m]) / rg) if rg > 0 else np.nan
        for k in ("cpi", "ppi", "cfpi", "policy_rate", "firm_lending_rate"):
            out["%s__%s" % (wname, k)] = float(np.nanmean(nat[k][m]))
    return out


# ---------------------------------------------------------------- cell block
def structural_shares(cells, n_periods=N_PERIODS, provs=None, sector_codes=None):
    """Pre-policy (2024-25 control) structural characteristics for ALL cells."""
    yr = period_years(n_periods)
    pre = (yr >= PRE_POLICY[0]) & (yr <= PRE_POLICY[1])
    a = {k: cells[k][pre].mean(0) for k in CELL_STRUCT_RAW}
    a["baseline_scale"] = cells["production"][pre].mean(0)
    a["baseline_investment"] = cells["realized_investment"][pre].mean(0)
    a["baseline_imports"] = cells["imports_row"][pre].mean(0)
    a["baseline_capital_stock"] = cells["capital_stock"][pre].mean(0)

    def ratio(num, den):
        d = a[den]
        return np.where(d > 0, a[num] / np.where(d > 0, d, 1.0), np.nan)

    out = dict(baseline_scale=a["baseline_scale"],
               baseline_employment=a["employees"],
               baseline_investment=a["baseline_investment"],
               baseline_imports=a["baseline_imports"],
               baseline_capital_stock=a["baseline_capital_stock"],
               baseline_output_value=a["output_value"],
               import_share=ratio("purchases_row", "purchases_total"),
               interprov_sourcing_share=ratio("purchases_interprov", "purchases_total"),
               labour_intensity=ratio("wage_bill", "output_value"),
               intermediate_intensity=ratio("intermediate_value", "output_value"),
               eligible_capital_intensity=ratio("capital_eligible", "capital_total"))
    n_cells = a["baseline_scale"].shape[0]
    if provs is not None:
        out["province"] = np.repeat(np.array(provs), n_cells // len(provs))
        if sector_codes is not None and len(sector_codes) * len(provs) == n_cells:
            out["sector"] = np.array(list(sector_codes) * len(provs))
    return out


def cell_deltas(ctrl_cells, treat_cells, n_periods=N_PERIODS):
    """Window deltas for ALL cells. No screen, no denominator rule applied."""
    yr = period_years(n_periods)
    out = {}
    for wname, (lo, hi) in WINDOWS.items():
        m = (yr >= lo) & (yr <= hi)
        end = np.where(yr == hi)[0][-1]
        for k in CELL_FLOW:
            out["d_%s__%s" % (k, wname)] = treat_cells[k][m].sum(0) - ctrl_cells[k][m].sum(0)
        for k in CELL_STOCK:
            out["d_%s__%s" % (k, wname)] = treat_cells[k][end] - ctrl_cells[k][end]
    return out
