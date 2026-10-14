# Firm-sector audit — MacroABM-CA, 2022 start

Branch `feature/validation-2022` (local). Pickle `dev/pkl_files/io2022_phaseA.pkl` (rebuilt after F-X1 and F-I3;
previous builds kept as `_v1`…`_v3`). Configuration: shipped default (`CountryConfiguration.n_industry_default`),
13 regions, one firm per industry × region (50 × 13 = 650 firms), seed 0. Units: $B CAD; model flows are quarterly
and are shown ×4 where compared with annual benchmarks. Equations as in `STAGE1_MODEL_EQUATIONS.md` §3.3 (not
repeated). Scripts: `scripts/firm_t0_extract.py` (t0, no simulation), `battery/diag_firm_step.py` (stock-flow and
first-quarter checks), `battery/diag_firm_prices_rates.py`, `battery/mech_export_shock.py`; outputs in `outputs/`.

## 1. Initialisation vs Canadian benchmarks (2022)

Benchmarks: StatCan 36-10-0221 (income-based GDP, annual, Canada), 36-10-0104 (expenditure-based GDP, mean of
the four 2022 SAAR quarters), 36-10-0580 (national balance sheet, **non-financial private corporations**, market
value, 2022-Q4), all via DBnomics (`benchmarks/raw/`). Coverage note: the model's "firms" are **all producing
industries including public administration (O), education (P) and health (Q)**, i.e. corporations + unincorporated
business + government and NPISH producers; the balance-sheet benchmark covers private non-financial corporations
only.

| Concept | Benchmark | Model t0 | Gap | Class |
|---|---:|---:|---:|---|
| Gross output, basic prices | 5,104.2 (provincial IO table, source of the build) | 5,104.2 | 0 | by construction |
| GDP at basic prices / value added | 2,675.0 (GDP mp 2,864.2 − TLS on products 189.2) | 2,674.4 | −0.0% | ✓ |
| Compensation of employees | 1,387.0 (v1.1) | 1,386.4 (firm labour cost) | −0.0% | ✓ |
| Intermediate consumption | 2,403.5 implied by IO (output − VA − product taxes on inputs) | 2,355.2 | −48.3 | **F-D1** IO table unbalanced (rows 5,104.2 vs columns 5,055.9) |
| Product taxes on intermediate inputs | 26.5 (IO "TLS" row) | 26.4 (`taxes_paid_on_production`) | 0 | ✓ (concept: product, not production, taxes) |
| Other taxes less subsidies on production (D.29−D.39) | 100.5 (v1.11) | **0** | −100.5 | **F-A1** never charged to firms; inside VA, so inside firm GOS; missing from government revenue |
| GOS + gross mixed income | 1,187.4 (v1.4 874.6 + v1.8 312.8) | 1,336.2 (firm GOS) | **+148.8 (+12.5%)** | = F-A1 100.5 + F-D1 48.3 |
| Consumption of fixed capital | 459.0 (corp 278.5 + unincorp. 88.0 + gov/NPISH 92.4) | 398.9 (capital used) | −13% | model δ set so that t0 depreciation = t0 gross capital purchases (zero net investment, incl. folded inventory change) |
| Business GFCF / total GFCF + inventories | 556.4 / 716.8 | firm 398.9 + household 180.4 = 579.2 | IO FCF+ΔINV 680.0 vs model 579.2: **−100.8 ≈ government GFCF (101.4)** | **F-D2** to verify in the government audit (no agent buys government investment) |
| Net profits (after depreciation and interest) | NOS corp 503.7 + net mixed 224.8 = 728.5 | 862.3 | +18% | follows F-A1/F-D1 |
| Industries with negative t0 profit | — | 12 of 50 (I −38/yr, H53, R, H51, E, …) | | data (IO cost structure) |
| Inventories (finished goods, materials, WIP) | 398.8 (NFPC, v1.8.1.9) | finished goods **0**; input stock 588.8 (one quarter of all inputs, 56% services) | | **F-I1** `initial_inventory_to_input_fraction` = 0; input stock includes non-storable services |
| Capital stock | build source: StatCan net stock end-2021 by industry (`capital_stock_end2021_oecd50…`) | 2,936.0 | — | by construction; utilisation 1.0 ⇒ zero spare capacity at t0 |
| Deposits | 683.8 (NFPC Canadian currency & deposits, v1.8.1.17) | 684.3 | +0.1% | ✓ level; allocation fixed (F-I3) |
| Debt (bank loans) | external loans 1,281.6 (non-mortgage 925.3 + mortgages 356.3); bonds 644.2; intercompany loans 1,164.1; total loans 2,448.6 | 2,271.8 | +77% vs external loans | **F-I2** level ≈ total NFPC loans incl. intercompany claims scaled by VA ratio; allocated ∝ capital stock, so O/P/Q (government producers) hold 657 (29%) |
| Equity | NFPC net worth (equity) 5,427.4 at market value | 1,937.4 (book: deposits + stocks − debt) | | concept differs (book vs market); not used behaviourally |
| Interest paid on loans | t0 data 75/yr (3.3%) | Q1 model 10.8/yr (0.98%) | −86% | **F-R1** bank loan rate below policy rate (bank audit) |

Province × industry output, VA and compensation come from the 2022 provincial IO and StatCan detail VA
(macroabm-io2022 pipeline) and match by construction; they were not re-audited here.

## 2. Accounting and implementation

**Verified each quarter (2 quarters, `diag_firm_step.py`, `run_accounting_smoke.py`):** firm cash identity
(residual = deposit zeroing at insolvency only; none occurred); purchases vs input use (cash basis since A10);
inventory, intermediate-stock and capital-stock updates (no clipping by the `max(0, ·)` floors); profit ↔ GOS
bridge `GOS − (Π + p·K_used + interest) = sales + p·ΔINV − p·Q = 0`; goods-market settlement; loan stock identity;
write-offs charged to bank equity (A14). All residuals 0 to machine precision.

**Fixed in this stage (isolated commits, regression tests in `tests/test_validation_2022/`):**

| ID | Error | Effect before → after |
|---|---|---|
| F-X1 (`4ecbac0`) | CAD-native build (IO, prices and imports in CAD at par) but the model applied the market USD→CAD rate 1.30 to every goods-market transaction from Q1 | Q1 import prices +30% in CAD; good-price index +9.1%, CPI +4.85%, PPI +5.65%, firm input costs +6.4%, profits −22%, net external receipts −42B/q → CPI +0.31%, PPI +0.04%, input costs −0.6%, profits +5.8% (interest, F-R1), net external receipts +1.0B/q |
| F-I3 (`8bc9244`) | sector deposits split equally across firms (5.06B for every Ontario industry) | allocated ∝ output |
| F-A2 | an insolvent firm's overdraft was cancelled with no loss to the bank (reserve plug absorbed it) | queued as a bank loss (not a loan write-off) |
| G1, D6, A14, H6 | see issue register (goods settlement, negative investment weights, bank loss recognition, loan terms) | |

**First-quarter discontinuities remaining (national, $B/q, t0 → Q1 → Q2):** wage bill 346.6 → 343.1 → 340.7
(wage equalisation within firms, F-S5); interest 18.7 → 2.7 → 2.3 (F-R1); firm deposits 684 → 804 → 923
(+17%/q: retained profits, no dividends, A4); debt 2,272 → 2,234 → 2,196 (amortisation 37.9/q, no new credit,
F-S8); production 1,276.1 → 1,275.4 → 1,271.4 with inventories building up (sales < production).

## 3. Specification assessment (shipped default)

| Block | Rule (code) | Assessment | Verdict |
|---|---|---|---|
| Production | Q = min(Q*, L·a_L, S/A, K/B)·TFP, PureLeontief (`func/production.py:228`); utilisation rates 1.0 | Leontief with no substitution is defensible for a quarterly IO model; but **capital is fully utilised at t0**, so any Q* above t0 output is infeasible until capital grows | defensible form; **calibration questionable** (F-S1) |
| Target production | Q* = expected demand = last period's demand (`DefaultDemandEstimator` `demand_estimator.py:67`, both growth speeds 0); no inventory target (`target_inventory_to_production_fraction` 0, `target_production.py:228`) | purely adaptive; no growth expectation, no inventory management: unsold output accumulates, production follows sales down | executable, **economically weak** (F-S2) |
| Excess demand | maximum recordable excess demand = spare capital capacity (`ConstrainedExcessDemandSetter`, `excess_demand.py:83`, consider_capital 1.0) | at 100% utilisation the firm **cannot observe unmet demand**; demand signal is lost (shock test: +20% ROW demand recorded as +3.3% sales, 0 excess demand) | **implementation-level defect in combination with F-S1** (F-S3) |
| Input demand | intermediate target = Q*·A (`target_intermediate_inputs.py:109`, stock-gap fraction 0); stock of one quarter of every input incl. services | consistent with Leontief; storing services is not | questionable (F-I1) |
| Labour demand | L* = Q*/a_L constrained by capital (`desired_labour.py:66`) | consistent | defensible |
| Wages | real wage per worker = t0 **firm-average** per-capita wage × work effort, indexed fully to CPI; tightness markup scale 0 (`wage_setter.py:186`, active code ~l.300) | individual wage dispersion within a firm disappears at t=1; no Phillips-curve or productivity link | **behavioural decision** (F-S5) |
| Prices | p_t = p_{t−1}(1+ε)(1+π^e_PPI), ε~N(0,0.05); demand-pull and cost-push speeds 0 (`prices.py:108`) | prices ignore demand and costs; the 5% s.d. noise applies to a single firm per industry × region (whole provincial industry), giving ±13% quarterly moves and large buyer switching | **economically questionable** (F-S4) |
| Profits / GOS | accrual identities (§2) | correct; levels biased by F-A1/F-D1 | data |
| Investment | target capital purchases = Q*·δ (replacement only; `target_capital_inputs.py:287`, stock-gap fraction 0) | no accelerator; net investment only (Q*−Q)·δ; with F-S1 the economy cannot expand capacity | **behavioural decision** (F-S6) |
| Depreciation | δ calibrated so t0 depreciation = t0 capital purchases (incl. inventory change) | implies zero net investment; CFC 13% below national accounts | data/calibration (F-S7) |
| Financing | credit demand = max(0, input costs − deposits) and capital costs − remaining deposits (`target_credit.py:44`); no dividends | firms accumulate deposits (+17%/q) and never borrow; debt amortises to zero; credit channel inactive | **architecture** (A4, F-S8) |
| Insolvency | equity < 0 and deposits < 0 (`demography.py:73`, `firms.py:1762`); loans written off and overdraft cancelled (both now bank losses, A14 / F-A2), equity reset to 0; the firm keeps operating (no exit/entry) | rule plausible; never triggered in 2 quarters (deposits growing); 'zombie' continuation is a design choice | defensible, note |

## 4. Mechanism test: one-quarter +20% ROW demand for C29 (motor vehicles)

`mech_export_shock.py`, 3 quarters, same seed; C29 all regions vs baseline (%):

| | Q1 | Q2 | Q3 |
|---|---:|---:|---:|
| sales | +3.3 (inventory 0.78 exhausted) | +1.1 | +0.3 |
| recorded excess demand | 0 | 0 | 0 |
| production / employment / input & capital purchases | 0 | +3.3 | +1.1 |
| price | 0 | 0 | 0 |
| credit | 0 | 0 | 0 |
| other industries' production | 0 | 0 | +0.22B (one-quarter lag) |

The firm response is entirely quantity-adaptive with a one-quarter lag, bounded by inventories, with no price, wage,
investment or credit response; the demand that cannot be served from output and inventories is not recorded as excess demand, so it never reaches the firm's demand estimate. Baseline drift over two quarters:
C29 output −5.7%, national unemployment 6.13% → 6.54%, CPI −0.8% — the default firm block is mildly
contractionary from the corrected start (sales < production feeds back into lower targets).

## 5. Assessment

**What firms reliably do now:** reproduce 2022 output, value added and compensation by province and industry; pay
and receive every flow consistently (cash, inputs, taxes, loans, goods market at seller prices); propagate demand
changes through Leontief input demand with a one-quarter lag; keep stocks consistent.

**Economically questionable:** zero spare capacity plus a capacity-capped excess-demand signal (F-S1/F-S3) —
firms cannot see or meet demand above the t0 level, which is the "capacity lock" observed in earlier runs; purely
adaptive demand expectations without inventory targets (F-S2); price noise that dominates price dynamics while
demand and costs have no effect (F-S4); replacement-only investment (F-S6); wage equalisation and full CPI
indexation (F-S5); firms never pay out or borrow (A4, F-S8); operating surplus 12.5% too high (F-A1, F-D1); debt
level and allocation (F-I2), including corporate debt held by government producers.

**Decisions needed before government and banking:**
1. **F-A1** — levy other taxes less subsidies on production (100.5B) on firms (needs the D.29/D.39 split by
   industry × province from the io2022 VA detail) — changes firm GOS and government revenue.
2. **F-D1** — rebalance the provincial IO table in the io2022 pipeline (48.3B row/column imbalance) or accept.
3. **F-I2** — firm debt concept (external loans 1,282B vs total incl. intercompany 2,449B) and whether O/P/Q
   producers should carry corporate debt; allocation ∝ capital stock vs data by industry.
4. **F-S1/F-S3** — capacity utilisation at t0 < 1 (e.g. Bank of Canada capacity utilisation ~82%) and/or excess
   demand not capped by capital: decides whether the economy can respond to demand.
5. **F-S4/F-S2** — price rule (noise level; demand-pull / cost-push speeds) and expectation/inventory rule.
6. **F-S6/F-S8/A4** — investment (accelerator) and distribution of profits / use of credit: architecture.
7. **F-R1** — bank lending rate below the policy rate (banking audit).
8. **F-D2** — government GFCF (≈101B) has no purchaser (government audit).
