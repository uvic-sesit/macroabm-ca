# Stage 1 — MacroABM-CA as implemented: accounting, equations, timing

Branch `feature/validation-2022` @ `ab87ee2` (= `feature/itc-user-cost`). Documentation is secondary; every
statement below is read from the code at the cited `file:line`. Paths are relative to the repository root.

**Selected baseline ("shipped default").** `CountryConfiguration.n_industry_default(n_industries)` for every
`CAN_*` region (`dev/io2022/save_baseline_2022.py:47-57`), seed 0, 13 regions, quarterly step. With no bundles
this gives, among others: `DefaultHouseholdConsumption`, `AverageSavingRatesSetter`, `EqualSocialTransfersSetter`,
`DefaultWealthSetter`, `DefaultHouseholdInvestment`, `ConstantRentSetter`, `DefaultHouseholdDemandForProperty`,
`AutomaticHousingMarketClearer`, `WaterBucketCreditMarketClearer`, `WaterBucketGoodsMarketClearer`,
`PolednaLabourMarketClearer`, `WorkEffortFirmWageSetter`, `DefaultPriceSetter`, `PureLeontief`,
`AutoregressiveGovernmentConsumptionSetter`, `GrowthSocialBenefitsSetter`, `ConstantPolicyRate`,
`NoAging`, `NoOpTFPGrowth`, `GrowthRoWExportsSetter`, `InflationRoWImportsSetter`,
`InfinityExcessDemandSetter` (ROW), constant exchange rate (`macromodel/configurations/*.py`).

Status tags: **[active]** used in the selected baseline · **[optional]** implemented, off by default ·
**[bypassed]** computed but has no effect on state · **[identity]** accounting definition ·
**[behaviour]** decision rule · **[institutional]** policy/institutional rule · **[market]** matching/rationing ·
**[calibration]** set at t0 from data or residual.

Notation: subscripts *h* household, *i* individual, *f* firm, *b* bank, *g* industry/good, *r* region;
*t* quarter. All monetary stocks are CAD; flows are CAD per quarter; `cpi`, `p` are indices (=1 at t0).

---

## 1. Within-quarter sequence (timing and information)

`Simulation.iterate` (`macromodel/simulation.py:300`) runs, for every region:

| # | Phase | Code | What happens | Information used |
|---|---|---|---|---|
| 0 | pre-hooks | `simulation.py:321` | policy hooks (ITC off) | — |
| 1 | initialisation | `country.py:461` | exchange rate (constant), firm count | — |
| 2 | estimation | `country.py:473-495` | economy forecasts growth, PPI/CPI/HPI inflation (AR(1) on exogenous pre-sample history + realised history); firm-level growth/demand estimates | realised t−1 aggregates |
| 3 | target setting | `country.py:497-536` | firm limiting inputs, target production (= expected demand), desired labour, input targets, wage-tightness markup; individual reservation wages | t−1 stocks, demand t−1 |
| 4 | labour market | `country.py:538-550` | Poledna clearing: hires/fires, activity status, `Offered Wage of Accepted Job` | targets from 3 |
| 5 | planning metrics | `country.py:552-776` | expected profits; gov benefit levels (UB per person, total other transfers); UB assigned to unemployed; labour inputs; policy rate; **wages set** (`:634`); **production realised** (`:660-662`) **before** goods are sold; **prices set** (`:667`); unconstrained input demands; individual & household **expected income** (`:698-733`); household **target consumption** (`:742`) and **target investment** (`:765`) | current employment; t−1 prices/CPI; expected inflation |
| 6 | regional sync | `simulation.py:337-339` | one policy rate for all regions (output-weighted CPI inflation/growth) | — |
| 7 | housing | `country.py:778-814, 847-873` | property values updated; move/buy/rent decisions; rents; clearing; ownership/occupancy transfer; rent paid recorded | expected income, financial wealth t−1 |
| 8 | credit | `country.py:816-845, 875-933` | loan demand (firms, households), bank rates, clearing, **installments**, interest, debt stocks | target consumption, rent, income t−1 |
| 9 | goods (prep) | `country.py:935-970` | buy/sell orders: firms (inputs, capital), households (C+I targets), government, ROW | — |
| 10 | goods market | `simulation.py:363-373` | global water-bucket clearing at seller prices; ROW absorbs excess demand | — |
| 11 | realised metrics | `country.py:972-1444` | distribution of bought goods; price indices; inventories; wage bill; sales; profits; taxes; **firm deposits**; insolvency; **household income** (`:1228-1268`); C and I booking (`:1295`); **household wealth** (`:1305`); household insolvency; banks; **government taxes, revenue, deficit, debt** (`:1371-1410`); GDP (`:1412`) | realised t |
| 12 | demography | `simulation.py:379-380` | `NoAging` → no change | — |

Key timing facts:

* **T1 — production precedes sales.** Output is fixed in phase 5 from target production = last quarter's
  demand (`DefaultDemandEstimator` with both adjustment speeds 0, `firms_configuration.py:100-115`); unsold
  output goes to inventory (`firms.py:1457`).
* **T2 — households plan on expected income, settle on realised income.** Target C and I (phase 5) use
  `expected_income`; deposits are updated in phase 11 on `income` (§3.1). The two incomes are defined
  differently (§3.1, items E1–E3), so the planning error is structural, not stochastic.
* **T3 — wages are set before the goods market and paid after it**, at the end-of-quarter CPI
  (`firms.py:1000`, `country.py:1125-1132`).
* **T4 — taxes are booked by the government after all private balance sheets are closed**
  (`country.py:1371`). No private deposit is reduced by the VAT or by taxes on financial or social income;
  see accounting issues A1–A5.
* **T5 — housing and credit clear before goods**, so property purchases are paid from deposits (phase 11) that
  already include the period's consumption outflow.

---

## 2. Balance-sheet matrix as implemented (end of quarter)

`+` asset, `−` liability. "—" = not held/not modelled. The bank column is closed by a residual (B1).

| Instrument | Households | Firms | Banks | Central gov. | Central bank | ROW | Σ |
|---|---|---|---|---|---|---|---|
| Deposits (hh) `wealth_deposits` | +D_h | | −D_h | | | | 0 |
| Deposits (firms) `deposits` | | +D_f | −D_f | | | | 0 |
| Bank "deposits" at CB (residual) `banks.deposits` | | | +R_b = D_h + D_f + E_b − L | | — (no CB balance sheet) | | **≠0** |
| Mortgages `mortgage_debt` | −M | | +M | | | | 0 |
| Consumption loans `consumption_loan_debt` | −L_c | | +L_c | | | | 0 |
| Firm ST/LT loans | | −L_f | +L_f | | | | 0 |
| "Other financial assets" `wealth_other_financial_assets` | +OFA | — | — | — | — | — | **≠0 (no issuer)** |
| Government debt `central_government.debt` | — | — | — | −B | — | — | **≠0 (no holder)** |
| Firm equity / bank equity | — (no ownership claim) | E_f (residual) | E_b | | | | not distributed |
| Dwellings `properties.Value` | +H (main + other) | | | (social housing implicit) | | | |
| Other real assets (vehicles, valuables, self-employment businesses) | +K_h | | | | | | |
| Fixed capital, input stocks, inventories | | +K_f, +S_f, +INV_f (real, valued at p) | | | | | |
| Net foreign assets | — | — | — | — | — | — (not tracked) | |

Stock identities in code:

* Household net wealth: `NW_h = H_main + H_other + K_h + D_h + OFA − (M + L_c)` (`households.py:1252-1256, 1314-1319, 1458-1469`). [identity]
* Firm equity: `E_f = p·INV + p_g·S_f + p_g·K_f + D_f − Debt_f` (`firms.py:1807-1830`) — a residual, revalued at current prices. [identity]
* Bank equity: `E_b,t = E_b,t−1 + Π_b − τ_π·max(0, Π_b)` (`banks.py:453-471`); bank reserve **residual**
  `R_b = D_f + D_h + E_b − L_b` (`banks.py:490-505`). [identity — **plug**]
* Government debt: `B_t = B_{t−1} + DEF_t` (`central_government.py:439`). [identity]

**B1. The bank reserve position is a plug.** Because `R_b` is defined as the residual, every bank balance
sheet balances by construction. Any money created or destroyed elsewhere (A1–A10) shows up only as a drift
in `R_b` with no counterpart in a CB or government account. Bank-level SFC checks therefore cannot detect
leaks; the informative test is `ΔR_b = DEF − (net ROW payments) + (other explicitly modelled flows)`, which
is a Stage-4 identity test.

Not modelled at all: central-bank balance sheet, holder of government debt, equity claims of households on
firms/banks, pension entitlements, insurance technical reserves, foreign assets/liabilities, trade credit.

---

## 3. Transactions-flow structure and sector budget constraints

### 3.1 Households

Realised income (`households.py:568-585`, `country.py:1241-1268`):

```
Y_h,t = W_h,t + TR_h,t + RENT_h,t + FAI_h,t                                   [identity]
W_h,t   = Σ_{i∈h} w_i,t                     (individual employee_income, households.py:370-390)
TR_h,t  = cpi_t · TOT_OTHER_t / N_h          (EqualSocialTransfersSetter, social_transfers.py:89; households.py:459)
RENT_h,t= (1−τ_inc) · Σ_{rented-out dwellings owned by h} rent   (households.py:481-513)
FAI_h,t = (1+ε) · c_FA · OFA_h,t−1           (financial_assets.py:134-145; ε~N(0,0) by default)
```

Expected income used for decisions (`households.py:549-566`, `individuals/func/income.py:129-203`):

```
Y^e_h,t = Σ_{i∈h} [(1+π^e)·cpi·w_i·1{emp} + (1+π^e)·cpi·UB_i] + (1+π^e)·cpi·TOT_OTHER/N_h + RENT_h + c_FA·OFA_h
```

* **E1.** `w_i` is a **real, net-of-tax** wage (`wage_setter.py:300-317` divides by the tax wedge and indexes
  to the base-year real wage per head). Expected income multiplies it by `(1+π^e)·cpi`; realised household
  income does **not** multiply by `cpi`. With CPI rising, planned income systematically exceeds received income.
* **E2.** Unemployment benefits `UB_i` enter expected income but **not** realised household income
  (realised individual `income` incl. UB is computed at `country.py:1228` but is used only for a histogram).
* **E3.** Dividends: individuals with status FIRM/BANK_INVESTOR would receive `payout·(1−τ_inc)(1−τ_π)·Π^+`
  (`income.py:259-275`), but (i) that series never feeds household income, and (ii) the 2022 pickle has zero such
  individuals (Stage 2). Firms and banks distribute nothing.

Outlays and stock-flow (`households.py:1087-1222, 1224-1319`, `wealth.py:286-421`):

```
C_h  = Σ_g min(spent_h,g, C*_h,g)              (basic prices; households.py:1120)
I_h  = Σ_g (spent_h,g − C_h,g)                 (households.py:1176)
S^cash_h = Y_h − rent_paid_h − (C_h + I_h)     ("new"/"used-up" wealth, households.py:1259-1284)
ΔOFA_h = (1−φ_h)·max(0,S^cash) − min(OFA, max(0,−S^cash))                     (wealth.py:286-382)
ΔD_h   = φ_h·max(0,S^cash) − used_dep − int_h − P_house,h − inst_h + newloans_h − τ_cf·I_h   (wealth.py:385-421)
ΔK_h   = −δ_K·K_h + I_h            (δ_K = 0.05 per quarter, households_configuration.py:203)
ΔH_h   = (ownership transfers at market price; values constant, value.py)
ΔM_h, ΔL_c,h from credit market (installments, write-offs)
```

with `φ_h = clip(model.predict(x/Σx), 0, 1)`, `x = [Income, Debt]` normalised by their cross-sectional sums
(`wealth.py:302-311`), and `int_h = r_L·loans − r_D·max(D,0) − r_OD·min(D,0)` (`households.py:1004-1040`).

What the household budget constraint *should* contain but does not (cross-referenced to the issue register):
VAT on consumption (A1), personal income tax and SSC on non-wage income (A5), UB receipts (A3),
dividends/withdrawals from firms (A4), sale proceeds of dwellings sold (A8), the imputed-rent income that
offsets owner-occupiers' purchase of L-sector output (A9). OFA changes have no counterparty (A7).

### 3.2 Individuals

* Activity status ∈ {EMPLOYED=1, UNEMPLOYED=2, NOT_ECONOMICALLY_ACTIVE=3, FIRM_INVESTOR=4, BANK_INVESTOR=5};
  changed only by the labour market (`NoAging` keeps population fixed).
* Wage of employed `i` at firm `f` (`wage_setter.py:300-317`) [behaviour/institutional]:
  `w_i,t = (1+μ_f,t)·TFP_f·λ_f,t·w̄^real_f,0 / Θ`, `Θ = (1+τ_er)/((1−τ_ee)(1−τ_inc))`, μ = tightness
  markup (scale 0 by default → μ=0), λ = labour-productivity factor (work effort). **All employees of a firm
  receive the same wage**; the t0 individual wage distribution is overwritten at t=1.
* Reservation wage: `DefaultReservationWageSetter` (unemployed timespan 0). UB per person: §3.5.

### 3.3 Firms (one firm per industry×region cell unless configured otherwise)

```
Q*_f = D^e_f = D_f,t−1                              (target_production.py, demand_estimator.py; speeds 0)  [behaviour]
Q_f  = min(Q*_f, Q^L, Q^S, Q^K)·TFP                 (PureLeontief, production.py:228+)                      [identity/technology]
p_f,t = p_f,t−1·(1+ε_f)·(1+1.0·π^e_PPI)             (DefaultPriceSetter prices.py:108-210; ε~N(0,0.05);
                                                     demand-pull and cost-push speeds = 0)                    [behaviour]
WB_f = cpi·Θ·Σ_{i∈f} w_i                            (firms.py:1000)                                         [identity]
Sales_f = nominal_amount_sold_f                     (goods market)
Π_f = p_f·Q_f − WB_f − p·used_int − p·used_cap − T^prod_f − int_f        (firms.py:1657)                    [identity]
GOS_f = Sales_f + p_f·ΔINV_f − WB_f − p·used_int − T^prod_f              (firms.py:1739)                    [identity]
ΔD_f = Sales_f − WB_f − p·used_int − p·used_cap − T^prod − τ_π·Π^+ − int_f + ITC + newcredit − installments  (firms.py:1712) [identity]
INV_f,t = (1−δ)·max(0, INV + Q − sold)              (firms.py:1457)
S_f,t   = max(0, S − used_int + bought_int);  K_f,t = max(0, K − used_cap + bought_cap(delay))  (firms.py:1516, 1599)
```

* **A10.** Firm deposits are debited for inputs **used** and capital **consumed** (accrual), not for inputs and
  capital goods **purchased** (cash). Purchases are credited to the selling firm, so `Σ (bought − used)` is
  money creation (net investment + input-stock build-up). (`firms.py:1712-1737` vs `firms.py:1402-1429`.)
* No dividends, no equity issuance; insolvent firms have deposits and equity set to 0 and their loans removed
  (`firms.py:1760-1805`) — a write-off with no explicit loss to banks (absorbed by `R_b`).
* Capital-stock **value** series is computed with the intermediate-stock function (`country.py:1180-1183`) —
  reporting bug, no behavioural effect.

### 3.4 Banks and central bank

* Rates (`banks.py:214-325`, `interest_rates.py`): pass-through/error-correction to the policy rate; t0 rates
  converted annual→quarterly (`3d2be8e`). Policy rate: `ConstantPolicyRate` (default) → constant;
  `RegionalAggregator.sync_central_banks` imposes one national rate (`regional_aggregator.py:14-31`).
* Bank profit: `Π_b = int_loans + r_CB·R^+ + r_OD·overdrafts − r_CB·R^− − r_D·deposits` (`banks.py:327-365`).
  No dividends; taxes deducted from equity.
* Household credit screens (`credit_market/func/clearing.py:568-600, 690-745`) [institutional]:
  consumption loans ≤ `0.05·avg(Y_t−1,Y_t) − Debt_h`; mortgages ≤ min(`0.05·avg(Y) − Debt_h`,
  `0.05/0.95·FA_h`, `0.05·Y·annuity(r,120)`) and **only granted if the full amount is available**
  (`:734`). Parameter values are the package defaults (`bank_configuration.py:36-47`), confirmed on the
  instantiated model.
* Installments: principal + interest per loan schedule (`credit_market.py:395-404`); household write-off on
  insolvency removes loans without a bank loss entry (`credit_market.py:557-572`).

### 3.5 Central government and government entities

```
Taxes (central_government.py:245-325), all booked after private settlement:
  T_prod = Σ_f τ_g(f)·p_f·Q_f;   VAT = τ_vat·Σ_h C_h;   T_cf = τ_cf·Σ_h I_h^+;   T_X = τ_X·X
  T_π   = τ_π·(Σ Π_f^+ + Σ Π_b^+)
  PIT   = τ_inc(1−τ_ee)·Σ_{emp} w_i + τ_inc·RENTPAID + τ_inc·Σ_h FAI_h
  SSC_ee = τ_ee·Σ_{emp} w_i ;  SSC_er = τ_er·Σ_{emp} w_i
REV = T_prod + VAT + T_cf + T_π + T_X + PIT + SSC_ee + SSC_er + social-housing rent      (:356-381)
DEF = n_unemp·UB + Σ_h TR_h + Σ G_nominal + ITC + r_policy·B − REV                       (:394-437)
UB_t = max(1, 1/(1+g^e))·UB_t−1;   TOT_OTHER_t = (1+g^e)·TOT_OTHER_t−1    (GrowthSocialBenefitsSetter, social_benefits.py:188, 209)
G*_g,t = (1+π^e)·(p_g,t/p_g,0)·Ĝ_t·share_g, Ĝ from a log-AR forecast of own history (government_entities/func/consumption.py:133-218)
```

* **A2.** Labour-tax bases are the **net real** wage `Σw`, while firms pay `cpi·Θ·Σw`. At cpi=1:
  firm cost − (household receipt + PIT + SSC_ee + SSC_er) = `Σw·[Θ − 1 − τ_inc(1−τ_ee) − τ_ee − τ_er] > 0`;
  the gap grows with `cpi`.
* **A1/A5.** VAT and PIT on FA/rent income are booked as revenue but are not debited from any household
  (rental PIT is withheld from landlords, so only VAT and FA-income PIT are unfunded).
* **A3.** UB is expenditure in DEF but never credited to households (E2).
* **A11.** `r_policy·B` is paid to nobody.

### 3.6 Rest of the world and goods market

* ROW demand for exports grows exogenously (`GrowthRoWExportsSetter`); ROW supplies any unmet domestic demand
  (`InfinityExcessDemandSetter`), so imports are a residual of domestic supply shortfalls; ROW prices follow
  inflation (`InflationRoWPriceSetter`). No ROW balance sheet (**A12**).
* Goods market (`WaterBucketGoodsMarketClearer`): global, at seller prices, with trade-proportion priorities and
  minimum-fill rules; buyers pay nominal amounts from deposits; no taxes on products at the point of sale.

### 3.7 Housing market

* Values: `V_t = (1+ε)V_t−1`, ε~N(0,0) → **constant nominal house prices** (`value.py`).
* Rents: `ConstantRentSetter` for existing leases (constant nominal); new leases priced from observed
  rent/value fractions (`property.py:398-435`).
* Demand (`property.py:224-319`): renters `status==0`, owners `status==1` re-decide with prob. 0.5; buy vs rent
  by a logistic comparison of annualised costs; max price `5·Y^e`·lognormal noise.
* Clearing `AutomaticHousingMarketClearer` (Hungarian matching, `clearing.py:271-320`); transfer of title and
  occupancy (`housing_market.py:417-500`). **A8:** the buyer is debited `P` (`households.py:896-900`,
  `wealth.py:417`) for every "Sell" match, including matches the transfer code rejects
  (`housing_market.py:471-475`); the seller is never credited.

### 3.8 National accounts in the model (`economy.py:993-1290`)

```
GDP_output  = Σp·Q − Σ used_int − T_prod + T_products + RENTPAID + RENTIMP
GDP_income  = GOS + WB + T_products + RENTREC + rent_to_gov + RENTIMP
GDP_exp     = ΔINV + GFCF + C(1+τ_vat) + G + X − M + RENTPAID + RENTIMP
```

**A9.** In the 2022 provincial-IO path the household consumption vector still contains sector-L output
(≈ paid + imputed rent, Stage 2), and `RENTIMP`/`RENTPAID` are added again in all three measures.

---

## 4. Household equations in the selected baseline (classification)

| # | Equation | Code | Class | Status |
|---|---|---|---|---|
| H1 | `C*_h,g = w_g/(1+τ_vat)·max(1.0·(1−s_h)·BEN_h, (1−s_h)·Y^e_h, 0·smooth)`, `BEN_h = n_adults·UB + TR^e_h` | `consumption.py:184-237`, `households.py:661-695` | behaviour | active |
| H2 | `s_h = s̄_r` (unweighted mean of t0 household saving rates in the region) | `saving_rates.py:62-89`, `households.py:217` | calibration | active |
| H3 | `I*_h,g = w^I_g/(1+τ_cf)·ι_h·Y^e_h` | `investment.py:148` | behaviour (fixed rate) | active |
| H4 | `TR_h = cpi·TOT_OTHER/N_h` | `social_transfers.py:89` | institutional | active |
| H5 | `FAI_h = c_FA·OFA_h` | `financial_assets.py:111, 134-145` | calibration (exogenous yield) | active |
| H6 | `φ_h` deposit share of new saving (linear model on normalised Income, Debt) | `wealth.py:286-316` | behaviour (fitted) | active |
| H7 | dissaving draws OFA first, then deposits; deposits may go negative (overdraft) | `wealth.py:318-342` | behaviour | active |
| H8 | `L^c*_h = max(0, ΣC* − (Y^e − rent) − FA)` | `target_credit.py:124-127` | behaviour | active (screen ≈ closed) |
| H9 | `M*_h = max(0, P − 1.0·max(0, FA − (ΣC* − (Y^e − rent))))` | `target_credit.py:155-163` | behaviour | active (screen ≈ closed) |
| H10 | rent for renters = lease rent; imputed rent for owners = dwelling's imputed rent; social-housing rent = 0.25·UB·n_adults | `households.py:902-965`, `social_housing.py` | institutional | active |
| H11 | move/buy/rent decision (H-demand) | `property.py:224-319` | behaviour | active; tenure codes inconsistent (S-H5) |
| H12 | insolvency: `NW<0 ∧ D<0` → loans written off | `insolvency.py:88-111` | institutional | active |
| H13 | `DisposableIncomeHouseholdConsumption` (H1 on after-tax income) | `consumption.py:240-285` | behaviour | optional |
| H14 | `CESHouseholdConsumption`, `ExogenousHouseholdConsumption` | `consumption.py:288-570` | behaviour | optional |

---

## 5. Nominal/real conventions

* Goods are traded in real quantities at nominal seller prices; household C, I, G are booked nominal at basic
  prices; `total_consumption = (1+τ_vat)·C` is a reporting variable only.
* Wages are stored **real and net**; firm wage bills are nominal gross (×cpi×Θ). Social transfers are real
  shares × cpi. UB per person is nominal in DEF but treated as real in expected income.
* House prices and rents are nominal and constant; financial-asset yield `c_FA` is a nominal constant.
* No asset revaluation of financial assets; firm equity and capital are revalued at current prices.
  Hence `Closing = Opening + Transactions` holds only for deposits/loans/OFA; dwellings change by transfer
  at transaction prices; firm equity is a revaluation residual.

## 6. What the model omits (household-relevant)

Mixed income and self-employment income; property income from corporations (dividends, withdrawals) and
interest on non-deposit assets; pension entitlements (D.8) and pension contributions; current transfers to/from
corporations and NPISH; non-life insurance; capital transfers; holding gains on dwellings and financial assets;
household formation, ageing and migration (`NoAging`); provincial differentiation of household behaviour except
via calibration residuals.
