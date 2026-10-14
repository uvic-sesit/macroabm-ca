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
