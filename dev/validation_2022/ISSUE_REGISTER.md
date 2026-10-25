# MacroABM-CA validation — single issue register

Latest household review: [D timing / D1 household gate, staged steps 1–3](CLOSURE_DF_2026-10-23.md).
The dated updates below supersede the original issue descriptions where marked.

Branch `feature/validation-2022` @ `ab87ee2`. Created 2026-10-13. Statuses: **C** confirmed (code read and,
where marked, quantified on the t0 state) · **S** suspected (code read only; needs a Stage-4 test).
Priority: P1 (blocks attribution of dynamics) · P2 (material bias) · P3 (document/limitation).
Numbers are annual $B at t0, branch-rebuilt pickle, unless stated. "Remedy" lists options only; no change has
been made.

## Accounting (A)

| ID | Sector | Location | Evidence | St. | Consequence | Test / remedy | Pri |
|---|---|---|---|---|---|---|---|
| A1 | HH↔Gov | `central_government.py:290`; `wealth.py:412-421`; goods market at basic prices | VAT = τ_vat·C booked as revenue (≈39B/yr at t0); no household debit | C | HH saving +VAT, gov deficit −VAT; money created by booking | per-step check ΔD_h vs flows. Remedy: debit VAT from household deposits (or remove it from revenue) | P1 |
| A2 | HH↔Firm↔Gov | `firms.py:1000`; `country.py:1248-1251`; `central_government.py:312-325`; `wage_setter.py:310-317` | Firms pay cpi·Θ·Σw; households receive Σw (no cpi); PIT/SSC on the net base Σw. Unrecorded 32.3B (2.3% of WB) at cpi=1, growing with cpi | C | Household labour income does not index to prices; firm cash leaves the system; gov taxes understated (PIT 95 vs 107 on gross, SSC 182 vs 203) | identity: WB_f = W_h + PIT_w + SSC. Remedy: pay households cpi·Σw; tax the gross base | P1 |
| A3 | Gov→HH | `central_government.py:422-437`; `households.py:568-585` | UB counted in deficit (≈12–17B) but never credited to households; in expected income only | C | money destroyed; consumption planned on income never received | remedy: add UB to realised household income (sum over members) | P1 |
| A4 | Firm/Bank→HH | `firms.py:1712`; `banks.py:453`; `income.py:259-275`; `financial_assets.py:134-145` | No dividends/withdrawals paid; investor individuals = 0; FA income c_FA·OFA (≈98B) has no payer | C | profits accumulate in firms and banks; household property income is created from nothing | remedy: dividend/withdrawal flow from firm and bank profits; link FA income to it | P1 |
| A5 | HH↔Gov | `central_government.py:312-319` | PIT on FA income (≈9B) booked, not paid | C | phantom revenue | remedy: debit, or exclude from revenue | P2 |
| A6 | HH↔HH (rent) | `households.py:481-513`; `central_government.py:312-320` | Rental PIT withheld from landlords (net receipt) and booked by gov | C (consistent) | none | — | — |
| A7 | HH portfolio | `wealth.py:286-382, 385-421` | Saving into OFA leaves deposits with no issuer; dissaving from OFA pays firms with no buyer | C | money destroyed/created; OFA not a claim on anyone | remedy: explicit issuer (equity/bonds) or all saving to deposits (`SimpleWealthSetter`) | P1 |
| A8 | Housing | `households.py:896-900`; `housing_market.py:471-500`; `wealth.py:417` | Buyer debited P; seller never credited; buyer debited even if the transfer is rejected | C | money destroyed with every sale | per-step check. Remedy: credit the seller; debit only executed sales | P1 |
| A9 | HH/GDP | `economy.py:993-1001, 1209-1217, 1268-1278`; `default_readers.py:497-513` | L in the HH consumption vector 312.7B ≈ paid+imputed 317.4B; imputed rent 218B added again to all GDP measures; imputed rent bought in cash by owners | C (data) | GDP double count (~218B, ≈8%); owner saving understated | remedy: remove imputed rent from the L FD column in the provincial path or book it on both sides | P1 |
| A10 | Firms | `firms.py:1712-1737` vs `1402-1429` | Deposits debited for inputs used and capital consumed, not for goods bought | C (code) | money created ≈ net investment + input-stock build-up | Stage-4 identity; firm audit | P1 |
| A11 | Gov | `central_government.py:428` | r_policy·B paid to nobody; B has no holder | C | phantom expenditure | firm/bank/CB audit | P2 |
| A12 | ROW | `rest_of_the_world.py` | no ROW financial account; imports/exports settled against deposits only | C | net foreign assets untracked | ROW audit | P2 |
| A13 | Banks | `banks.py:490-505` | bank reserve R_b = D_f + D_h + E_b − L is a plug | C | bank balance sheets balance by construction; leaks invisible at bank level | Stage-4: ΔR_b vs DEF + ROW + leak terms | P1 (test design) |
| A14 | HH↔Bank | `credit_market.py:557-572`; `insolvency.py:88-111`; `firms.py:1760-1805` | Loans written off with no loss to bank equity; firm deposits zeroed | C (code) | absorbed by R_b; bank equity overstated | bank audit | P2 |
| A15 | Firms (reporting) | `country.py:1180-1183` | capital-stock value computed with the intermediate-stock function | C | K value series wrong (no dynamic effect) | fix reporting | P3 |

## Data / initialisation (I) — households

| ID | Location | Evidence | St. | Consequence | Remedy / test | Pri |
|---|---|---|---|---|---|---|
| I-0 | canonical pickle vs `43089de` | canonical pickle TR 516.4B vs 239.6B with branch code | C | runs on the canonical pickle use a superseded transfer level | adopt the branch-rebuilt pickle as reference | P1 |
| I-1 | `hfcs_synthetic_population.py:219`; `synthetic_country.py:468-470` | 17.78M households vs 15.455M (+15.0%); allocated by VA share (AB ×1.85, NS ×0.78) | C | all household aggregates +15%; regional distortions | count from CHS 46-10-0083 (+ territories) | P1 |
| I-2 | `normalise_household_consumption` | regional s from −10% to 61%; corr with count ratio 0.83 | C | regional multipliers are artefacts | fix I-1 then recalibrate | P1 |
| I-3 | `oecd_economic_data.py:601-627` | τ_inc = 0.09 (OECD-average default); PIT 112 vs 348 | C | wage wedge, PIT, net rent mis-set | Canadian effective PIT (e.g. PIT / taxable income from 36-10-0224) | P2 |
| I-4 | `hfcs_synthetic_population.py:619-665`; `default_readers.py:791-808` | private pensions folded into gov transfers; TR+UB 256 vs 287; WB GDP ends 2021; gov UB total ≠ individual UB sum (12.2 vs 16.7) | C | transfer level and incidence | separate pensions; 2022 GDP; reconcile UB | P2 |
| I-5 | adapter / `set_household_income` | "Income" calibrated to DI but used as a hybrid concept | C | saving concept ambiguous | define income concept explicitly | P2 |
| I-6 | `reconcile_labour_income` after firm matching | HH labour 1,383.6 vs firm-consistent 1,076.9 (−22% at t=1; SK −52%); 196B on non-employed | C | first-step income jump | reconcile against the firm wage bill, or let non-labour components absorb the residual | P1 |
| I-7 | `households.py:217`; `saving_rates.py:89` | s̄ = unweighted mean (0.083 national incw vs 0.155 implied); static C jump −8.5% (prov. −30%…+2%) | C | first-step C jump | income-weighted s or household-specific s | P1 |
| I-8 | `canadianized_household_adapter.py:62,113-123` | Rent Paid from French HFCS: 13.3B vs 81.5B | C | rent and landlord income −84% | Canadian rent source (SHS shelter, CHS) | P2 |
| I-9 | `hfcs_synthetic_population.py:442-446` | credit lines/cards zeroed; consumer debt 380 vs 730 | C | liabilities −15% (count-adj) | keep consumer credit | P2 |
| I-10 | `hfcs_synthetic_population.py:667-685` | c_FA = 1.25%/yr on OFA incl. pensions; FA income 98 vs 247 property income | C | property income −60% | link to returns by asset class | P3 |
| I-11 | bank t0 data | mortgage 0.97%/yr < policy 1.48%; consumer 3.06% | S | interest paid 35 vs 84 | retrieve BoC effective rates | P2 |
| I-12 | sampling / tenure | owners 71.8% vs 65.4%; code 4 counted as owner; code 2 ≈3%; uniform across provinces; no social housing | C | housing tenure mis-set | provincial CHS tenure control | P2 |
| I-13 | provincial IO path | imputed rent not removed from L FD (see A9) | C | see A9 | see A9 | P1 |
| I-14 | build | French individuals and consumption-by-income weights; payout ratio 1.116; zero investor individuals | C | distributional detail non-Canadian | Canadianise individuals | P3 |

## Specification (S) — households

| ID | Equation | Verdict | Consequence | Alternative | Pri |
|---|---|---|---|---|---|
| S-H1 | H1/H2 fixed propensity, regional mean | E (calibration, income concept); form S | MPC = APC uniform; no wealth or liquidity channel | household-specific s; income + liquid-wealth rule | P2 |
| S-H2 | expected income (E1–E3) | E | systematic over-forecast that grows with inflation | define Y^e on the realised concept | P1 |
| S-H3 | missing accounts (mixed income, dividends, corp. transfers, D.8) | E/S | household income about −15% of DI; profits never distributed | distribution flows | P2 |
| S-H4 | portfolio φ on normalised levels | E/A | scale-dependent shares; A7 | ratio-based rule or all-deposit | P2 |
| S-H5 | housing: constant prices/rents; tenure codes 0/1 vs 1–4; transactions | E/A | renters never move; owners churn; real rents fall | consistent codes; indexation | P2 |
| S-H6 | credit screens LTI/LTV/DSTI = 0.05 | E (calibration) | household credit shut; forced deleveraging | Canadian B-20-type limits | P2 |
| S-H7 | household investment into "other real assets"; 5%/q is depreciation, not the investment propensity | A | residential investment does not build dwellings | link to the dwelling stock | P3 |
| S-H8 | equal transfers; UB ratchet | A / E | incidence lost; UB cannot fall | fitted shares; symmetric rule | P2 |
| S-H9 | no mixed income | E | see S-H3 | withdrawal flow | P2 |
| S-H10 | one national file for all provinces | A | provincial behaviour = residuals | provincial controls | P3 |

## Firm / bank / government / ROW items noted in passing (for later audits; not assessed)

| ID | Location | Note | St. |
|---|---|---|---|
| F1 | `prices.py:108-210` | prices follow expected PPI inflation + 5% noise; demand-pull and cost-push speeds 0 → no price-feedback channel; AR(1) inflation expectations on pre-sample history | C (code) |
| F2 | `demand_estimator.py` | expected demand = last demand (speeds 0) | C (code) |
| F3 | `firms_configuration.py:388-410` | `depreciation_rates` default 0 (inventory) vs capital depreciation matrix | S |
| G1 | `government_entities/func/consumption.py:133-218` | G follows a log-AR forecast of own history, price-indexed (prior baseline G +26%) | C (code) |
| G2 | `social_benefits.py:188` | UB ratchet | C |

---

## Phase A status (2026-10-14, `feature/validation-2022`, pickle `dev/pkl_files/io2022_phaseA.pkl`)

Verification: `tests/test_validation_2022` (16 tests) and the accounting battery
(`battery/run_accounting_smoke.py`, shipped-default config, seed 0, 2 quarters), against the pre-correction
reference (tag `validation-2022-precorrection`, branch-rebuilt pickle). Battery residuals are national, nominal
CAD per quarter.

### Fixed

| ID | Fix | Evidence after fix |
|---|---|---|
| A1 | VAT debited from household deposits (`update_wealth(tau_vat)`) | HH cash identity 0 |
| A2 | households receive cpi·Σw; PIT/SSC levied on the gross base | wage counterparty 44.1/48.6B → 0 |
| A3 | UB credited to household income (no cpi/inflation factor); deficit books UB actually paid | UB counterparty 3.1/3.9B → 0 |
| A8 | sales executed only if feasible; seller credited; buyer debited for executed sales only | house-sales residual 9.3/4.9B → 0 |
| A9/I-13 | provincial IO path flagged `housing_services_in_household_io`; rent no longer added again in GDP | GDP double count removed (−218B/yr) |
| A10 | firm deposits debited for purchases (cash), not for inputs used | firm cash identity = − deposit zeroing only |
| A16 (new) | `wealth.py`: deposit use netted against OFA use incorrectly; spending beyond deposits went unrecorded | HH cash identity 1.9/28.6B → 0 |
| A17 (new) | bank deposit interest computed on bank-level net balances, agents pay on individual balances | bank interest = customers' payments + CB interest; Q2 reserve residual −0.19 → −0.06B |
| H5 (new) | build matched some renters to rental units their own household owns (10 households nationally); rent then paid to nobody once the OO flag is recomputed | rent counterparty 3.85M/q → 0 (pickle rebuilt) |
| I-1 | household counts from CHS 2022 (provinces) + Census 2021 (territories) | 15.50M (+0.3%) |
| I-3 | Canadian effective PIT 0.1736 (36-10-0224) | PIT on gross base |
| I-6 | t0 wages renormalised to firm wage bills | static Q1 labour-income jump −22% → 0.001% |
| I-7 | income-weighted average saving rate | static Q1 consumption jump −8.5% → 0.001% |
| I-9 | credit lines/cards kept as non-mortgage loans | consumer credit 743B |
| I-12 | tenure codes; provincial owner-rate stratification | owners 65.5% |
| H1 (new) | `get_histogram`/`fillna(-1)` bug set every property inhabitant/owner to −1 at t0: no renting ever occurred in prior 2022 runs | occupancy restored |
| H2 (new) | property-demand rule used tenure codes 0/1; renters = 3, owners = 1,2,4 | unit test |
| H3 (new) | matching: buyers matched above WTP; self-purchase; infeasible pairs | unit test |
| H4 (new) | listings and vacancy (−1) logic; "newly up for rent" mask | unit test |
| D1 (new) | French property counts zeroed SFS other-property values (dwellings −12.9%) | dwellings 0.0% vs 36-10-0580 |
| D2 (new) | other-property mortgages (653B) missing from the loan book | loan identity −652.7B → 0 |
| D3 (new) | rental-income rescale summed over social renters → NaN; `remove_outliers` dropped valid households | rebuild completes |
| B1 | accounting battery with ΔR decomposition and explicit write-off counter | `battery/accounting.py` |

### Remaining (escalated; decisions needed)

| ID | Issue | Why not fixed here |
|---|---|---|
| I-8 / A9 | paid rent: 81.5B sits inside household purchases of sector L; no corporate landlords; ≈10% of households sent to social housing; Canadian rent levels give household landlords ≈10% gross yields | accounting-boundary decision (sector L vs housing module) |
| S-H3 / A4 | no mixed income (225B), dividends or corporate transfers → HH income 1,335B vs DI 1,502B; calibrated s = −9.8% | new income flows = architecture |
| A14 / N1 | insolvency rule (NW<0 and deposits<0) writes off 268B (Q1) and 43B (Q2); previously hidden by A16 | behavioural rule |
| A4, A7, A11, A12 | FA income without payer; OFA without issuer; unpaid interest on public debt; no ROW financial account | named boundary terms in the battery; architecture |
| S-H6 | credit screens 0.05 | calibration of behaviour |
| I-10, I-11 | FA return, bank rates | data, after boundary decisions |
| N2 | owner moves: high churn of owner-occupiers through the market | mobility parameter (behaviour) |
| N3 | provincial income distribution from one national file | data/architecture |
| D6 (new) | goods market: buyers pay the industry average price, sellers receive own price × quantity; −0.053/−0.056B/q (0.005–0.07% of sales). This is now the entire `reserves_unexplained` | changes market-clearing payments (escalate) |

---

## Post-Phase-A batch (2026-10-14): goods settlement, write-offs

Pickle `io2022_phaseA.pkl` rebuilt (sha `543b1c02…c3d9`; previous kept as `_v2`). Battery 2 quarters, national, $B/q.

### Fixed

| ID | Fix | Evidence |
|---|---|---|
| D6 | goods payments settled at the sellers' realised prices after clearing (`markets/goods_market/func/settlement.py`; real allocation unchanged; switch `GoodsMarketConfiguration.settle_at_seller_prices`) | pre-settlement price gap ≈0.6M USD/q, settled to 0 |
| G1 (new) | household investment weights from the IO GFCF column had negative entries (CAN_NL B07 −0.95%, CAN_ON C24A −0.15%, …): negative purchases were executed against sellers but clipped to 0 by `Agent.record` on the buyer side (+162M/q booked by buyers, −10M/q of firm sales lost) | negative weights set to 0 and renormalised; `goods_market_gap` −0.058 → 0; real quantity gap 12.7M → 0.06 units |
| A14 | written-off loan principal charged to the lending bank's equity (balance-sheet write-down, no profit-tax effect), for household and firm defaults (`credit_market.pending_writeoffs_by_bank`, `Banks.compute_equity(loan_losses)`) | bank losses 229.1 / 67.2; write-offs no longer move the reserve plug; no bank insolvency in 2 quarters |
| H6 (new) | initial household loan maturities (12 / 120 periods; documented as months) gave obligated principal 4.1x (non-mortgage) and 1.2x (mortgage) StatCan 11-10-0065-01 2022; CAN-2022 terms set to 49 / 145 quarters to reproduce observed principal payments | write-offs Q1 267 → 230 (diagnostic, before A14) |

Battery after the batch: every identity 0 (wage, UB, rent, house sales, household cash, loans, bank links, goods
market); `reserves_unexplained` 0.000 / 0.000.

### Write-off diagnosis (Q1, `battery/diag_household_writeoffs.py`)

| Driver | Evidence | Class |
|---|---|---|
| t0 negative net worth | 1,365 of 19,687 agents (6.9%); file 3.5% (weighted), SFS 2023 PUMF 3.9% | data (sampling + below) |
| underwater mortgages at t0 | prototype file: 12.7% of HMR mortgagors and 26% of other-property mortgagors owe more than the property value (excess 40.5B and 102.1B); SFS 2023 PUMF: 0.8% and 9.1%. Cause: `prepare_household_canadianization.backcast_calibrate` scales real estate (x0.85) and mortgages (x1.05) to NBSA totals with separate factors; with the prototype weights every LTV rises ~1.38x (median HMR LTV 0.41 → 0.57) | **data construction (H7, escalate)** |
| forced amortisation | consumer-credit principal 62B/q vs 15B/q observed | data (H6, fixed) |
| deposits below zero | 4,383 agents (22%) overdrawn after one quarter: uniform negative saving rate (−9.7%) from missing income accounts (D2) and no new household credit (D4) | specification (D2, D4) |
| rule | default as soon as NW<0 and deposits<0; debt forgiven, assets kept | specification (D3, unchanged) |

Defaults are therefore mostly *legitimate under the current rule* given a starting point that is partly a data
artefact (H7). Not suppressed.

### New escalation

| ID | Issue | Options |
|---|---|---|
| H7 | household file: independent calibration of real estate and mortgages to NBSA totals breaks the SFS joint LTV distribution (underwater 0.8% → 12.7%) | (a) one common factor for real estate and mortgages (keeps LTV; mortgages −19% vs NBSA); (b) calibrate real estate to NBSA and scale mortgages by the same factor, then add the NBSA mortgage gap pro rata to equity-rich mortgagors; (c) keep NBSA totals and cap per-record LTV at the SFS maximum; (d) accept |

---

## Firm-sector audit (2026-10-14) — see `STAGE_FIRMS_AUDIT.md`

Pickle rebuilt (F-X1, F-I3); battery 2 quarters: every identity 0, `reserves_unexplained` 0.

### Fixed

| ID | Fix | Commit |
|---|---|---|
| F-X1 | CAD-native build: model exchange rate rebased to the build numeraire (was market 1.30 → imports +30% in CAD at t=1; CPI +4.85% → +0.31% in Q1) | `4ecbac0` |
| F-I3 | firm deposits allocated ∝ output (were equal per firm) | `8bc9244` |
| F-A2 | insolvent firm's cancelled overdraft recognised as a bank loss (not a loan write-off) | this batch |

### Remaining (decisions)

| ID | Issue | Evidence | Class |
|---|---|---|---|
| F-A1 | other taxes less subsidies on production (100.5B/yr, 36-10-0221 v1.11) never charged to firms; inside VA, so inside firm GOS; missing from government revenue | firm GOS 1,336 vs GOS + GMI 1,187 (+12.5%) | accounting/data (needs D.29/D.39 by industry × province) |
| F-D1 | provincial IO table unbalanced: row output 5,104.2 vs column inputs + VA 5,055.9 (48.3B/yr), lands in firm GOS | `icio_2022_can_provinces.csv` | data (io2022 pipeline) |
| F-D2 | government GFCF (~101B/yr) has no purchaser: IO FCF + ΔINV 680.0 vs model firm + household investment 579.2 | | data/architecture (government audit) |
| F-I1 | finished-goods inventories 0 at t0 (NFPC inventories 398.8B); input stock = one quarter of all inputs incl. non-storable services (56%) | | data/calibration |
| F-I2 | firm debt 2,272B ≈ total NFPC loans incl. intercompany (2,449B) × VA ratio, vs external loans 1,282B; allocated ∝ capital, so O/P/Q (government producers) hold 657B | 36-10-0580 1.8.1.67–71 | data/coverage |
| F-R1 | firm loan rate 0.245%/q below the policy rate 0.369%/q; deposits earn the policy rate; t0 data interest 3.3%/yr → model 0.98%/yr (−86% in Q1) | | banking audit |
| F-S1 | capital utilisation 1.0 at t0: zero spare capacity | | calibration |
| F-S2 | target production = last demand (growth speeds 0), no inventory target; unsold output accumulates, production follows sales down | baseline C29 −5.7% in 2 quarters | behaviour |
| F-S3 | recordable excess demand capped by spare capital capacity (= 0): unmet demand is invisible to firms | export shock: +20% ROW demand → +3.3% sales, 0 excess demand | implementation × calibration |
| F-S4 | prices ignore demand and costs; N(0, 0.05) quarterly noise on a single firm per industry × region (±13%) | | behaviour |
| F-S5 | wages: firm-average real wage per worker, full CPI indexation, tightness markup 0 → within-firm dispersion lost at t=1 | wage bill −1% in Q1 | behaviour |
| F-S6 | investment = replacement only (stock-gap fraction 0), no accelerator | | behaviour |
| F-S7 | depreciation calibrated to t0 capital purchases (zero net investment, incl. inventory change); CFC 399 vs 459 | | calibration |
| F-S8 | firms never borrow (credit = shortfall of deposits) and never pay out (A4): deposits +17%/q, debt amortises | | architecture |


## Household closure correction review ? 22 October 2026

Supersedes the uncommitted wider candidate; see
[HOUSEHOLD_CLOSURE_2026-10-22.md](HOUSEHOLD_CLOSURE_2026-10-22.md) and
`outputs/household_corrections/`. Branch remains `feature/validation-2022`,
base `4bdef06`. All behavioural components are opt-in; the mechanical quota fix
is also in the default. No Phase B, C_dp_005 port or push.

| Item | Revised state | Remaining issue |
|---|---|---|
| Loan quota units | Fixed by default in both allocators, c4862de; fractions become currency budgets, regression passes | Changes the corrected-default attribution relative to the old candidate's control |
| H7 | Fixed-weight property/mortgage common scaling plus capped pro-rata mortgage gap; 4cea6e2 | Underwater shares 0.616%/9.260%; other-property mortgage share 28.771% vs SFS 23.099%; quintile fit remains imperfect. No entropy weights in default. Other liabilities leave derived net worth 36.880B above NBSA. |
| D4 | Opt-in uninsured-only 80% LTV; 49/145-quarter effective amortization reconciled with initial stock; 1fdedd2 | Insured originations need insurer/premiums/guarantees. Income/service caps remain scenarios, not a literal 2022 regulatory specification. OSFI LTI is a 2025 portfolio measure. |
| D2 / A4?A5 | Gross dividend receipt target 92.052B from StatCan 36-10-0482, 2022; provincial payout calibration replaces 20%; funded counterparties, 4e9ac88 | Ownership/pension recipient proxies; missing pension institution and remaining interest/property-income scope. No invented withdrawals residual; no saving-rate fitting. |
| D1 / A9 | Narrow private-rent offset against each renter's L purchases, f549246; L retained, no new housing producer | Q12 unabsorbed rent 0.313B (rent exceeds some renters' L budgets); owner-occupied cash/noncash and net SNA reconciliation remain open. Wider boundary not approved or implemented. |
| D3 / A14 | Separate persistent-distress scenario, 8fabeee; old rule in arms i?iv | On hold after the four-check review below. Earlier iv/v totals 488.848B/178.915B are historical; large cancellations alone do not validate D3. Initial closure, overdrafts and bank capital/resolution remain unresolved. |
| Saving overshoot | New paired old-insolvency Q12 effects: D2 +5.006pp, D1 +0.485pp, deposit-only +2.149pp. Full narrow/deposit arm cash saving ?7.220%. Historical +13.48%/+21.89% decomposed separately in report. | One seed, ordered differences include endogenous/random path effects. Pension-adjusted observed cash comparison ?0.602%, versus published net saving 2.100%; remaining concept gaps preclude claiming fit. |

Five 2-quarter accounting diagnostics preceded five 12-quarter attribution runs;
two further 12-quarter pairs measure D1 and deposit saving. All 12 runs are finite
and pass regional accounting. Write-off and bank-loss quarterly panels, debt
bridges and hashes are retained. Focused tests passed at every commit (44 at f).
Final full-suite results are recorded in the report and `full_tests.xml`.

Final full suite: 381 passed, 30 known NaN failures, 2 extra temporary-directory
setup errors. Both extra cases pass when rerun with a workspace-local pytest
`--basetemp` (2 passed). All 30 failure messages match
`Nan in transactor_total_real_supply`; 29 simulation cases plus the sampler.
No additional unresolved test regression. Raw full-suite XML/log and the two-case
rerun are retained; no test was skipped.

## Four pre-D3 diagnostic checks — 22 October 2026

Supersedes the preceding D3 retention recommendation. D3 and Phase B remain
**on hold**. Full line bridge, cohort group tables, origination records, quarterly
firms/banks, seed checks and revised iv/v losses:
[HOUSEHOLD_CLOSURE_PRE_D3_2026-10-22.md](HOUSEHOLD_CLOSURE_PRE_D3_2026-10-22.md).

**Additional blocking finding (bank resolution):** both final D1 seed-1/seed-2
runs complete but fail accounting. Ontario bank resolution cancels 1,320.852B
in seed 1 Q11 and 1,356.011B in seed 2 Q10; the loan stock updates a quarter
later and the cancellation lacks by-bank equity-loss recognition. Seed 2 has
another 14.131B cancellation at Q12. Maximum normalized residuals are 2.939 and
3.073. Eight of ten final runs pass; these two are retained as failed diagnostics.
No cross-seed D1 acceptance is possible. Booked bank equity remaining positive
does not establish solvency. Choosing loan transfer versus forgiveness and the
equity/deposit/fiscal loss allocation is a resolution decision; no replacement
was silently implemented.

| Item | Finding / correction | Review decision |
|---|---|---|
| H-C1 income/consumption | Original iv Q1 annualized cash DI 1,478.170B vs 1,502.340B; C 1,620.402B vs 1,511.382B. Income explains 1.645pp and spending 7.375pp of the 9.020pp D.8-free saving gap. Gross SNA gaps include noncash and missing outflow counterparts. Initial D2 cash series are zero while the inherited propensity and unfunded FA-income proxy reflect an earlier closure. | Consistent initialization and consumption rule; no cash residual or saving-rate retuning applied. |
| H-C1 Q1 cohort | 1,228 simulated / 1,035,940 represented HH, 171.143B term debt in original iv. None meet both old-rule conditions at t0; 68.10% have negative net worth and hold 93.88% of debt later cancelled. Spending/service/rent push deposits negative. | Choose collateral/recovery treatment; large cancellations do not validate D3. |
| H-C2 screens | d7a2110 counts overdraft principal in LTI, overdraft interest plus actual remaining installment service in service screens, and adds consumer service capacity in both allocators. Regression coverage. | Automatic overdraft settlement still unbounded; facility/arrears policy needs approval. |
| H-C2 liability state | 37cf590 synchronizes household debt/net worth immediately after old-rule loan cancellation. Previously forgiven liabilities remained in household decision records. Regression; old trigger unchanged. | No behavioural change to insolvency approved. |
| F-C3 payout | Cash caps prevent payouts from creating overdrafts; requests use lagged profit, so current loss-makers may pay. Original iv Q9 loss 222.785B = HH 28.940 + firm loans 133.399 + firm overdraft 60.446. Utilities in ON/BC dominate term-debt losses. | Positive retained profit / available cash net obligations and reserve is a proposed rule only. Mixed income/pensions need a separate institutional boundary. |
| B-C3 capital | Every region starts at 506.210B, sum 6,580.730B. 59a37ef repairs missing regional multiplier in bank-equity getter returns. Getter ASS/F5 selects banks' equity asset holdings, not own capital. Existing pickle unchanged. Canadian NBSA 2022Q4 book equity: chartered 405.572B, quasi 50.649B, combined 456.221B (36-10-0580, vectors retained with provenance). No negative bank equity in runs is not validation. | Select Canadian bank boundary, book-equity source and regional/balance-sheet allocation, then authorize fresh validation input and reruns. |
| H-C4 sector L | Paired iv/D1 seeds 0/1/2, quarterly P×Q, inventory/employment and domestic buyer splits retained. Noise-driven prices and constrained quantities require separating nominal sales from real activity; see final table. | Narrow D1 remains opt-in; no wider producer block. |

Final seed-0 iv/v household write-offs are **485.027B / 176.932B**; bank losses
are **926.139B / 534.627B**, with quarterly panels in the linked report. Both
iv/v paths pass accounting. Original iii/iv/D1 twelve-quarter replays match the
previous results to within one cent. The original D1 L-sales increase of 26.697B
decomposes into +30.219B national price/unit-value effect and -3.522B quantity
effect; province-level decomposition also confirms that prices dominate.

52 focused tests passed. Full suite: **391 passed, 30 known NaN failures, zero
additional failures or setup errors**. The sampler fixture's initial internal
parallelism was discovered after its case finished; its one-worker rerun confirms
the same known NaN. `run_pre_D3_tests.py` enforces one sampler worker in future
suites without skipping tests. All household diagnostic simulations were serial.
No original-repository, ITC/user-cost or input-pickle modifications; no push,
Phase B or C_dp_005.

## Household A–D review — 23 October 2026

This update supersedes the pending capital/facility decisions in the pre-D3
review above. Full tables, provenance, seeds and proposals are in
[HOUSEHOLD_CLOSURE_ABCD_2026-10-23.md](HOUSEHOLD_CLOSURE_ABCD_2026-10-23.md).

| Issue / decision | Implemented correction and evidence | Status / next decision |
|---|---|---|
| B-C3 / A: capital | f8e9854 replaces Canadian 2022 asset-F5 equity with 456.221B liability-side NBSA book capital, allocated jointly by initial loans. New `io2022_household_agreed_bankcap.pkl`; all initial E/(L+R) ratios 11.85–17.47% exceed the 5% trigger. Four focused regressions pass. | Corrected candidate input. Accepted old pickles unchanged. Loan/creditor boundary still subject to F. |
| B-C4 / B: resolution | c977e16 preserves loan/deposit contracts in a same-agent bridge bank, records government support in deficit/debt and bank equity/reserves, and adds a recapitalisation counterparty identity. Six focused tests pass. Both original failing D1 seeds pass with old input (errors 6.79e-14 and 5.23e-14); new-input D1 seeds also pass. | Mechanical accounting corrected. Support targets model minima plus an explicit 1-point buffer; these are not Canadian CET1/RWA ratios. |
| H-C1 / C: propensity | c2c0120 includes funded expected D2 receipts, removes the unfunded financial-income proxy from that base, and preserves the income-weighted constant-propensity calibration. Weighted national propensity -9.726% → -0.439%; initial goods C target 1,511.382B/year. Six focused tests pass. | D2-off calibration unchanged; Q1 cash saving -4.52% remains below the D.8-free SNA comparison (-0.60%). Cash rent/IO housing and other account boundaries remain. |
| H-C2 / D: overdraft | 788f84f adds an opt-in proportional goods-budget cap, reserves senior payments first, and records payment distress. User-selected proxy: zero unused capacity. Thirteen focused tests pass. Uses settled cash at goods clearing; no D4 headroom. | Strict diagnostic bound, not a validated Canadian facility. Q12 saving about 30–32% and severe consumption rationing prevent economic acceptance. |
| D sensitivity | Quick primary-source search did not establish defensible separate card and general-LOC utilisation rates. TransUnion warns balances/limits can misstate utilisation; HELOC-only data do not identify all LOCs. | Omitted as explicitly authorized; no inferred utilisation rates or D4 substitute implemented. |
| H-C3 / E: defaults and collateral | Old-rule ACD household cancellation 133–136B over 12 quarters; v-ACD 54–55B, across seeds 0–2. D3 still lacks a collateral sale/recovery cash path. | D3 stays on hold. E's payment ledger, workout/foreclosure and uncovered-principal recovery specification is proposal only. |
| F-I2 / F: firm claims | 2,271.807B initial model firm debt includes an illustrative 1,080.006B intercompany component under the NBSA loan-instrument bridge. Public administration/education/health hold 657.208B. Firm trigger includes current-price noncash assets. | F remains proposal only: separate creditor instruments and public producers, and distinguish revaluation from payment failure. External loans are not identifiable as bank-only from borrower instrument totals. |

Seed-0 twelve-quarter household write-offs / bank losses (CAD B): iv-A
452.964 / 761.100; iv-AC 384.235 / 799.086; iv-ACD 133.439 / 429.784;
v-ACD 54.098 / 349.014. Firm loan plus overdraft losses account for about
69–80% of ACD bank losses and 83–85% of v-ACD losses across seeds. Recapitalisation
is reported separately, not netted against losses. Low losses under the strict
cash cap are not sufficient evidence of a plausible closure.

All requested two-quarter, twelve-quarter and seed accounting runs pass 1e-8.
Full `tests/` suite through `run_pre_D3_tests.py`: **398 passed, 30 known NaN
failures, zero additional failures/errors**; the failed test identities match
the prior suite exactly. Sampler worker count was one, and simulations were
serial. No push, original-repository/ITC/user-cost edits, or protected-pickle
changes. D3, Phase B and the C_dp_005 port remain on hold. Stop for review.

## D timing and D1 household gate — 23 October 2026, staged steps 1–3

The hand-over explicitly permits completing steps 1–3 as a staged pass. This
update claims **no F implementation or F results**. The approved firm-debt
boundary/new pickle, payment-based firm rule and F remeasurement (steps 4–6)
are next-pass work. See [CLOSURE_DF_2026-10-23.md](CLOSURE_DF_2026-10-23.md).

| Step / issue | Correction and evidence | Status |
|---|---|---|
| D timing | 54709c9 budgets current declared net wages, benefits/transfers, net rent and funded D2 distributions along with opening cash and executed financing flows. Payroll CPI is fixed at declaration and shared by firm debits, HH receipts and withholding; D2 commitments are paid once and cannot be revoked after purchases. Optional asset saving cannot divert senior-payment cash. 23 focused tests pass. | Mechanical timing corrected; zero unused capacity retained, no new parameter or D4-headroom proxy. |
| Narrow D1 | 3d54d44 enables the existing renter-specific L offset in both new candidate arms; all other L purchases stay in the goods market. Six focused tests pass. Q1 offset 3.763–3.768B/quarter across seeds. | On in iv-ACD′ and v-ACD′; no wider housing producer block. |
| Gate / measurement | ed02f71 adds the serial paired run driver and fixes diagnostic NumPy-boolean serialization (3 regressions pass). Both arms, seeds 0–2, each have a 2Q accounting run immediately before 12Q. | All 12 runs pass accounting; Q1 consumption shortfall 3.20–3.83%, within the 5% gate. Declared and actual HH receipts agree every quarter. |
| Household closure | Old-rule 12Q write-offs 212.829–218.691B; D3 36.587–38.854B. Q1 cash saving 1.45–1.99%; Q12 12.71–15.53%, versus the D.8-free 2022 comparison -0.60%. | Gate passed, economic validation still incomplete. E is still needed; D3 remains on hold. |
| Firm / bank losses | Old-rule bank losses 511.782–564.016B; D3 364.379–481.893B. Recapitalisations 282.345–460.563B / 200.778–353.071B, respectively. These retain legacy firm debt and default mechanics. | No plausibility claim. F remains approved next-pass work; no new firm-debt input was built. |

All six 2Q/12Q pairs reproduce their first two quarters within floating-point
tolerance. Payout declarations are checked against opening payer cash;
subsequent operating cash shortfalls are not mislabelled as declaration-date
funding. Source/input hashes and all quarterly seed, loss, support, lending,
rent-offset and constraint panels are retained under `outputs/DF/`. Borrower
microdata stay ignored locally. Full suite: **407 passed, the same 30 known NaN
failures, zero additional failures/errors** (437 cases). Failed test identities
match the prior suite, and the sampler used one worker. Evidence is in the linked
report and `outputs/DF/full_test_execution.json`.
No protected pickle, original-repository or ITC/user-cost file was modified;
no push, E implementation, Phase B or C_dp_005 port. Stop for staged review.


## A/F/E gated asset-budget follow-up ? 23 October 2026

Latest report: [CLOSURE_AFE_2026-10-23.md](CLOSURE_AFE_2026-10-23.md).
Accepted D timing and narrow D1 are retained. The step-1 asset drawdown is
implemented, but **both economic gate conditions fail on every seed**. Under
the explicit ordered gates, F and E did not start. D3, Phase B and C_dp_005
remain on hold. No new firm-debt pickle was built.

| Issue / step | Commit and evidence | Status / next decision |
|---|---|---|
| D: existing liquid assets | 393bff8 adds opt-in cash-first non-pension OFA drawdown before proportional C/I cuts, zero unused credit capacity. Existing OFA usage books one exact stock transfer, named OFA without issuer. Pension scale/components audited. 16 focused checks pass. | Mechanical resource extension measured; off by default. No parameter or consumption refit. |
| Household group diagnostic | f140ae2 fixes regional total consumption being broadcast to each household, and tests individual-to-regional reconciliation. Nine focused checks pass. Initial measurements superseded; all six final runs repeated. | Source/input hashes, funded D2 declarations and paired-run replay checks pass. Superseded local outputs excluded from conclusions. |
| Step-1 gate | Seed 0/1/2 constrained share Q4 ? Q12: 33.36 ? 50.01%, 33.81 ? 50.44%, 33.18 ? 50.25%. Q12 cash saving 9.74/9.79/9.96%, benchmark -0.602%; gaps 10.34/10.39/10.56 points. All six accounting runs pass 1e-8, maximum 8.67e-15. | FAIL: do not proceed to F or E. Asset drawdown improves levels but leaves upward drift. |
| Saving/constraint diagnosis | Initial non-pension OFA ?10k households are 45.24% of population and about 74% of Q12 constraints, with 60?65% of cash saving. Deciles 6?10 contribute 80?84% of saving; higher-income/low-asset intersection contributes 44?45%. Large assets remain concentrated elsewhere. | Review C versus discretionary investment priority and heterogeneous spending rules; no such behavior implemented. Cash saving excludes principal/capital purchases and is not financial-asset accumulation. |
| Legacy losses | 12Q HH write-offs 219.21?222.97B; bank losses 525.42?664.84B; recapitalisation 376.51?494.30B. Legacy firm/default boundary remains. | No plausibility acceptance; F/E not tested because gate fails. Phase B not ready. |

Quarterly constraints/cuts, liquidation, the net OFA boundary, consumption, DI,
saving and GDP are retained for all seeds, along with household/firm losses,
resolution events, min capital ratios and industry losses. Decile/asset and
cross-panel data plus the cash-saving-to-financial-stock bridge are in
outputs/AFE/. Options in the report are proposals only; no benchmark or gate
was redefined to improve results. Full suite: **416 passed, the same 30 known NaN failures, zero additional failures/errors** (446 cases). Sampler worker count was one. Failed test identities are checked against the accepted DF suite; final audit, JUnit and logs are retained in outputs/AFE/.


## Household investment / revised F?E gates ? 23 October 2026

Latest: [CLOSURE_IFE_2026-10-23.md](CLOSURE_IFE_2026-10-23.md).
**Step 1 complete; Gate 1 fails on all three seeds. F and E did not start.**
Saving and constrained-share trends are diagnostics here, not this gate's
criterion. The heterogeneous buffer-stock rule, Phase B and C_dp_005 stay deferred.

| Issue / step | Commit, test evidence and measurement | Status |
|---|---|---|
| S-H7 description / ledger | de244bc read-only individual cash ledger, 1 regression passes. Seed-0 Q12 paid investment is directly 50.700811B including CF tax, confirming the bridge. Old rates are 13.64?25.33% of expected income, region-specific; 5%/q is depreciation. | Correct the earlier issue description. All quarterly individual/group flows close; micro ledgers local, aggregate panels traceable. |
| Initial GFCF level | f1e7b60; 3 focused checks pass. StatCan 36-10-0112 v62305994, 2022 mean SAAR 242.393B/year = 60.59825B/quarter. Common rate multiplier 0.95537 approximately, initial desired level exactly matched; existing relative propensities/industry mix remain. | Source, vector, date and full upstream/local hashes in benchmarks/IFE/provenance.json. Realized flows are not used for calibration. |
| Discretionary investment | b75d4a7; 12 focused priority/budget/asset/calibration checks plus gate regression pass. Under D, investment is cut before consumption, including VAT/CF-tax cash costs. | Opt-in candidate only; zero unused credit capacity and asset drawdown retained. No new numeric behavioral parameter. |
| Gate 1 | Q1 realized I seeds 0/1/2 = 50.916/49.775/49.383B, 15.98/17.86/18.51% below benchmark. All six candidate 2Q/12Q runs pass 1e-8, maximum error 1.19e-14. | FAIL: stop before F/E. Do not inflate desired investment to reverse affordability cuts. |
| Saving / constraints | Q12 saving 3.49/4.18/5.53%, improved from A's 9.74?9.96%; constrained share still rises to about 50%. It includes households cutting investment only; consumption-specific series also reported. | Reported, not gating at step 1. Need for a buffer-stock rule is not established independently of capital-project allocation/funding and remaining firm feedback. |
| Dwelling-stock half of S-H7 | Proposal splits new construction, renovations, transfer costs and business capital, with builder costs, WIP, finance, ownership/property IDs and distinct structure/land/depreciation. | Proposal only: generic other-real-assets stock and 5% depreciation remain. Full asset-category concept mapping unresolved. |
| F/E loss behavior | Legacy debt/default retained; 12Q HH cancellations about 234B and bank losses 567?586B. | No new firm-debt pickle or new default/recovery parameter; losses/recaps not accepted as plausible. Phase B not ready. |

The household GFCF target includes unincorporated enterprises and residential
capital; private consumer durables remain consumption in SNA. The retained IO
capital basket is an aggregate proxy and cannot identify new dwellings versus
renovations, productive vehicles versus personal durables, or each service's
capital use. No consumer-durable reclassification is introduced to fit the
benchmark. The numerical gate fails regardless of that unresolved detail.

Per-quarter household ledgers, cash uses/funding, I/C cuts, liquidation, C/DI,
saving, GDP, household/firm/bank losses and support are under outputs/IFE/.
The seed-0 ledger replay uses de244bc; corrected pairs use b75d4a7. Initial
source snapshots and accepted input hashes are audited; original repository,
ITC/user-cost files and accepted pickles are unchanged. Nothing pushed.
Full tests/ through run_pre_D3_tests.py: **421 passed, the same 30 known NaN failures, zero additional failures/errors** (451 cases). Sampler worker count was one; failed identities are checked against AFE. Final audit, exact source/input hashes, raw-ledger hash inventory, JUnit and logs are retained under outputs/IFE/.


## F continuation - 24 October 2026 UTC (23 October local), execution pending

Historical checkpoint: the execution block below was resolved by the user's
clarification that serialization applies within this validation task. See the
completed F measurements at the end of this register.

The review accepts planned initial investment, not realized investment, as
Gate 1: 60.59825B/quarter versus 36-10-0112 v62305994. This **supersedes the
FAIL status in the earlier IFE entry**. Investment is income-based; the 5%
quarterly rate is depreciation. Consumption priority remains accepted.

- F-I2: 12987e6 builds the new firmdebt pickle, external firm bank-loan proxy
  1,281.615B versus 2,271.807B; K/O/P/Q/T excluded; 33-10-0225 industry vectors
  and output regional shares, with explicit mortgage/holder assumptions.
  Consolidation equity credit +1,164.071B and separate scope adjustment
  -173.879B give net +990.192B equity. Bonds 625.741B are a named boundary.
  All accepted pickle hashes unchanged; initial bank ratios above threshold.
- F default: 923f107, candidate flag default off; N=3, haircut=20% provisional
  assumptions. Continuing producer retains collateral-covered contracts;
  only uncovered bank principal is written down. Existing overdrafts survive.
  43bd9f9 includes overdraft interest in scheduled service. Revaluation alone
  cannot default a firm. Collateral-covered principal is not a cash recovery.
- bd72103 / 9a26aeb add diagnostic and gate machinery; read-only follow-up
  separates employment and firm-income receipts. Eleven focused tests pass.
- Final 2Q/12Q seeds 0-2 and the full suite are pending. A 2Q seed-0 pilot
  passes at 3.91e-15 but is not final serial evidence: another BDA workflow
  was discovered active. Automatic approval review rejected starting final
  measurements under a global one-simulation-at-a-time interpretation.
  Clarification of scope is pending; no external workflow was altered.
- No claim that F losses or bank support are plausible; E not started.
  Positive Q4-Q12 constrained-share slope on any seed will stop E.
  Buffer-stock spending remains proposal only. Phase B and C_dp_005 held.

Details, initial industry/bank tables, assumptions and resumption scripts:
[CLOSURE_FE_2026-10-24.md](CLOSURE_FE_2026-10-24.md).


## F measured - 24 October 2026 UTC; stop before E

The user clarified: keep this task's validation runs serial; the separate BDA
workflow may continue. Six final runs (2Q then 12Q, seeds 0-2) completed
sequentially at a039998. Source/input hashes and paired prefixes match.
Maximum normalized accounting error is 6.67e-15, including explicit firm cash
and overdraft-relief counterparties. Accepted input pickles remain unchanged.

| Decision / issue | Commit or evidence | Result / next decision |
|---|---|---|
| Planned initial I / S-H7 wording | 9a26aeb; benchmark v62305994 | Initial planned 60.59825B/q exactly matches; Gate 1 passes. Investment is income-based; 5% is depreciation. |
| F-I2 external loan boundary | 12987e6; new bankcap_firmdebt input | 1,281.615B vs 2,271.807B; +1,164.071B consolidation equity credit, -173.879B separate scope adjustment. Industry vectors/output allocation and holder/mortgage proxies documented. |
| F payment distress | 923f107, 43bd9f9 | N=3, capital haircut 20%, provisional assumptions. Equity revaluation alone never triggers default. |
| F uncovered overdraft principal | a039998; 12 focused tests pass | Corrects the loan-only shortfall omission. Formal loans and overdrafts share collateral and losses; exact lender loss and non-cash overdraft relief. Covered contracts/debit balances survive; recovery cash is zero. Superseded loan-only runs excluded. |
| F gate | outputs/FE/gates_and_comparison.csv | Accounting passes all runs; firm losses fall 41.8% / 20.2% / 34.6%. Seed 1 misses our predeclared 25% materiality assessment (the user did not specify a numeric threshold). |
| Household continuation check | Q4-Q12 OLS, unrounded | Slopes +2.126 / +2.088 / +2.061 percentage points/q. FAIL on all seeds; E does not start regardless of the firm-materiality interpretation. |
| Household saving / constraints | final quarterly tables | Q12 cash saving 2.94% / 3.31% / 3.86% vs -0.6%; constrained share 50.52% / 50.32% / 49.68%. Consumption-only cuts are separately reported. |
| Firm risk / bank support | final loss and resolution tables | Firm losses 205.4 / 265.0 / 230.0B, HH write-offs 236.5 / 237.1 / 237.0B, bank losses 441.9 / 502.1 / 467.0B, recapitalisations 220.1 / 310.2 / 235.2B over 12Q. Not accepted as normal Canadian loss/support magnitudes. |
| Remaining firm mechanisms | firm_loss_industry_diagnosis.csv, largest_firm_loss_events.csv | Accommodation/food-service losses 67-75B across seeds; seed 1 also has food-manufacturing/refining stress. About 98-99% of losses occur with negative current profit; payouts at loss events are zero. Earlier payouts/operating deficits and continuing overdrafts remain relevant. No causal claim that D2 is harmless. |
| Public producer financing | final leverage_industry.csv | Initial and Q12 O/P/Q formal loans are zero; operating overdrafts can still reappear in inherited settlement. A strict no-private-credit operating boundary needs an explicit government working-capital counterparty; proposal only. |
| Household diagnosis / spending option | bd72103, 980c8cd; constraint tables | Restoring Q1 income relieves 6-9% of current constraints; 39-42% have persistent plan/income gaps with assets down. Much of the residual began with zero liquid assets. Wages, jobs and D2 receipts separately reported by fixed decile/assets. Buffer-stock rule specified as a proposal, not implemented. |
| E / Phase B / C_dp_005 | not started | Remain held. Decide on a liquid-wealth spending response and remaining firm cash/workout/public-financing design before reopening E or Phase B. |

Full-suite result: 433 passed / 30 failed out of 463; all failures are the known Nan in transactor_total_real_supply cases, no additional failures; sampler n_cores=1.
See CLOSURE_FE_2026-10-24.md for per-quarter losses, planned/realized
investment, GDP/consumption/saving, bank support/capital, initial industry debt,
resolution events, leverage, firm-default cells and the three-seed diagnosis.

## Buffer-stock B and prudent payouts - 24 October 2026 UTC

Supersedes the FE proposal-only status for B. F remains an accepted candidate.
Gate B fails on all seeds; E, Phase B and C_dp_005 have not started.

| Check / decision | Commit / evidence | Finding / decision needed |
|---|---|---|
| Fixed SFS buffer response | 2948b08, 47e6002; 5 regressions | Default off, candidate on; kappa .10, smoothing .25, fixed SFS decile/age buffers; initial contractual service replaces unset interest TS. |
| t0 consumption level | buffer_calibration.csv | Matches 377.8455B/q exactly. Common level is -83,544.52 CAD/household/q. It shifts the effective buffer threshold and clips widespread positive-income goods demand to zero; review this distributional anchor before accepting the candidate. |
| Gate B | 1e83c42; 2 diagnostic/gate regressions | Saving fails in every base seed and all four one-factor sensitivities. No coefficient or SFS cell was refitted to the gate. |
| Firm t0 costs | 6a973a6; industry_costs.csv | I cost/price=1.323, H53=1.295, A02=1.082 at t0. Positive GOS is outweighed by inherited investment-proxy depreciation. No proven mechanical t0 data error; empirical CFC bridge remains needed. |
| Prudent discretionary dividends | 95cf3e6; 3 regressions and exact payout ledger audit | Positive retained profit plus cash above next service/wage reserve. Mixed income and corporate transfers retain treatment. Firm-loss effect differs across seeds. |
| E / pricing / entry | not implemented | E held by Gate B; pricing and producer adjustment remain specified proposals only. |

| seed | constrained_slope_pp | Q12_constrained_pct | Q12_saving_pct | gate_passed |
| --- | --- | --- | --- | --- |
| 0 | 0.040 | 0.679 | 48.222 | False |
| 1 | 0.039 | 0.678 | 47.408 | False |
| 2 | 0.050 | 0.743 | 48.239 | False |

| seed | firm_loss_B | firm_loss_P | payout_B | payout_P | Q12_GDP_B | Q12_GDP_P | Q12_income_B | Q12_income_P |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 281.057 | 244.728 | 727.589 | 742.999 | 531.724 | 517.005 | 310.198 | 310.366 |
| 1 | 241.029 | 292.927 | 742.445 | 722.057 | 525.032 | 531.788 | 311.016 | 308.412 |
| 2 | 255.954 | 246.033 | 707.765 | 728.285 | 483.763 | 510.995 | 296.556 | 310.952 |

All 16 serial runs pass accounting (max 1.44e-14); protected inputs and paired prefixes match. Full suite: 443 passed / 30 known failures / 0 extra failures, 473 cases; sampler one worker.

Recommendation: do not accept this anchored B candidate or declare household losses plausible. Firm losses combine a starting capital-cost proxy with price/demand/continuation behaviour; they can be disclosed in exploratory work, not treated as a validated closure. Phase B remains gated.

[CLOSURE_BE_2026-10-24.md](CLOSURE_BE_2026-10-24.md) contains the full quarterly, sensitivity, industry and seed evidence. Stop for review.

<!-- B2-2026-10-24 -->
## B2 and independent firm-data reconciliation — 2026-10-24

B2 fails. E, Phase B and C_dp_005 remain on hold. Per clarification, independent Step 2 was completed on accepted FE arm F (e386f4e lineage), with P off. No parameter tuning or push.

| Item | Evidence / commit | Status |
|---|---|---|
| B2 form | c2c3eb8, ea3485a; 6 regressions | One c0 rescale .961350238407, no additive intercept; zero-goods gate passes; base G2–G4 fail every seed |
| G3 clarification | DHEA 36-10-0587 primary, SHS 11-10-0223 secondary | Gate uses quintile shares, not dollar levels. Source-specific equivalence/ranking applied; full DHEA income remains a cash proxy, housing scope caveat disclosed |
| Regional rank scaling | d40e353; scale-invariance regression | Corrected national per-household income ranks; 15 diagnostic replays require identical original macro paths. Original misranked tables retained but superseded |
| Initial acquisitions vs CFC | 2237cb1; 1 regression | Clear mechanical separation; new CFC does not overwrite accepted initial purchases; default legacy fallback unchanged |
| Observed CFC | c3df2d9; 2 allocation regressions | New cfc_v2 pickle; 377.244B/year allocated versus 377.319B source; missing-stock boundary explicit. I/H53/A02 national costs below price |
| F-A1 / F-D1 | 55fb64a, b3227ea; 5 regressions | 100.504B/year missing signed taxes and 48.338B/year row–column discrepancy confirmed. Experimental correction not promoted: fails GDP initialisation. CFC-only retains unresolved bridge |
| Step 2 gate | 409 gross-margin exceptions >1 pp; 87 above-price cells with nonnegative IO GOS | Fails; neither data boundary nor remaining losses declared validated |
| E | no implementation | Step 1 gate prevents dependent work |

| seed | constrained_slope_pp | Q12_saving_pct | max_zero_positive_pct | G1 | G2 | G3 | G4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1.031 | 0.179 | 1.686 | True | False | False | False |
| 1 | 1.176 | -0.346 | 1.686 | True | False | False | False |
| 2 | 1.222 | -3.664 | 1.686 | True | False | False | False |

| seed | F_firm_losses_B | CFC_firm_losses_B | loss_change_pct | F_recap_B | CFC_recap_B | GDP_change_pct | C_change_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 205.399 | 84.372 | -58.923 | 220.141 | 165.205 | -2.402 | -4.893 |
| 1 | 265.003 | 138.852 | -47.603 | 310.153 | 199.720 | -3.277 | -3.430 |
| 2 | 229.988 | 91.380 | -60.267 | 235.207 | 99.958 | -7.473 | -6.310 |

Firm losses fall 48–60% under observed CFC; household write-offs stay about 233B over 12 quarters. Remaining firm losses mix data/concept limitations with price, demand and default behaviour; initial-condition diagnostics are not a causal behavioural decomposition. Bank recapitalisations remain large.

Full tests: 458 passed / 30 known failures / 488 cases; sampler one worker. Exact failure IDs checked against BE baseline in the final audit.

[CLOSURE_B2_2026-10-24.md](CLOSURE_B2_2026-10-24.md) contains every gate, quarterly losses, resolutions, seed comparisons, quintile raw levels and shares, source definitions/hashes, and remaining limitations. Stop for review; not ready for Phase B.
