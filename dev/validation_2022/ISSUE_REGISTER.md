# MacroABM-CA validation — single issue register

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
| S-H7 | household investment into "other real assets" at 5%/q | A | residential investment does not build dwellings | link to the dwelling stock | P3 |
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
