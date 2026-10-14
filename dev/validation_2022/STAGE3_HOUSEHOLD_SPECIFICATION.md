# Stage 3 — Household specification assessment (no code changes)

This stage judges the household equations as economics, separately from whether the code runs or balances.
Equation numbers (H1–H14) refer to `STAGE1_MODEL_EQUATIONS.md` §4; data findings (I-x) to
`STAGE2_HOUSEHOLD_RECONCILIATION.md`; accounting items (A-x) to the issue register.

The benchmark is not a representative-agent Euler equation. A heterogeneous-agent ABM can legitimately use
rule-of-thumb, buffer-stock or norm-based consumption. The questions here are whether each rule is internally
coherent, uses information available at decision time, respects budget and credit constraints, and can
reproduce the regularities the policy applications rely on (for the ITC/fiscal work: the marginal
propensity to consume out of transitory income and transfers, the response to interest rates and debt
service, and distributional incidence).

Verdict classes: **E** confirmed specification error · **A** defensible but a material alternative exists ·
**S** deliberate simplification, acceptable if documented · **U** empirical uncertainty.

---

## S-H1 Consumption: `C* = (1−s̄_r)·Y^e/(1+τ_vat)` with benefit floor (H1, H2) — **E** (as configured)

* **Rationale.** A fixed average propensity applied to expected income: Keynesian/Godley-Lavoie
  `C = α₁·Y^e`, with no wealth term (α₂ = 0). The benefit floor `(1−s)·(n_adults·UB + TR)` is a subsistence
  device.
* **Information.** `Y^e` (H1) is computed before the goods market from current employment, the end-of-t−1
  CPI and expected inflation. Using it is legitimate in principle. In practice it is not the income
  households will receive (E1–E3: cpi-indexed wages and UB that never arrive). Households therefore
  systematically over-forecast, and the error grows with inflation.
* **Parameters.** `s̄_r` is a **regional unweighted mean of calibration residuals** (I-2, I-7). It is neither
  estimated nor taken from evidence. Its spread (−2% to 56%) is driven by the household-count error
  (corr 0.83). The national income-weighted value implied by t0 C (15.5%) is an artefact of I-1;
  count-adjusted it is 2.8%. The rule applies `s` to a hybrid income concept: net wages, gross transfers and
  FA income (I-5).
* **Constraints.** No liquidity constraint: the target does not depend on deposits or credit access, so
  households with zero deposits keep spending into overdraft. Only H8 links consumption to wealth, and H8 is
  screened shut (S-H6).
* **Empirical regularities.** MPC = APC = 1 − s̄ for every household. This contradicts the robust micro
  evidence that MPCs out of transitory income are heterogeneous and decline with liquid wealth: they are high
  for hand-to-mouth households and low for wealthy ones. Specific Canadian estimates should be attached when
  this is calibrated (not retrieved here). It cannot
  produce heterogeneous incidence of transfers or the debt-service channel of monetary policy, and it has no
  wealth effect from housing or financial assets. Because the APC = MPC uniformity is regional,
  regional fiscal multipliers are mechanically inherited from I-2.
* **Alternatives with material consequences.**
  (a) `DisposableIncomeHouseholdConsumption` (implemented, off): fixes the income concept but not the
  propensity problem.
  (b) Household-specific `s_h` (the `ConstantSavingRatesSetter` uses the fitted model, off) calibrated on
  correctly counted, SHS-based APC by income/wealth cell. This restores the APC gradient (1.77 → 0.56 by
  quintile in the prototype).
  (c) A buffer-stock / Godley-Lavoie rule `C = α₁·Y^d + α₂·W_{t−1}` with α₁ heterogeneous by liquid wealth.
  This adds a wealth channel and stabilises deposits, and is standard in SFC-ABMs (Caiani et al. 2016;
  Dosi et al. 2013 use income-based rules plus wealth).
  (d) A Carroll-style target liquid-wealth-to-income ratio.
  Choosing among these changes the household-demand multiplier, which matters directly for ITC/fiscal results.
* **Classification.** The functional form (a fixed propensity) is S. Its calibration (I-2, I-7) and its
  income concept (E1–E3, I-5) are **E**.

## S-H2 Expected income (E1–E3) — **E**

`Y^e` adds UB and cpi-indexed wages that realised income never contains. This is an internal inconsistency,
not a simple expectations assumption: households cannot learn from it, because nothing compares planned with
realised income. Fixing it is a prerequisite for interpreting any consumption parameter.

## S-H3 Income components and missing accounts — **E** (missing accounts) / **S** (merges)

| SNA component (2022, $B) | Model | Verdict |
|---|---|---|
| CoE 1,378.5 | net real wage `w`, uniform within firm, reset at t=1 | **E**: not cpi-indexed in household income (A2); t0 distribution discarded (I-6) |
| Net mixed income 224.8 (incl. rental 127.6) | absent; self-employment business value is a real asset with no income | **E** for a model meant to track household income; unincorporated income stays in firm GOS and is never distributed |
| Property income received 246.6 | `c_FA·OFA`, exogenous yield, no payer | **E** (accounting, A4) and **A** (should be linked to firm/bank profits and to interest rates) |
| Dividends (in 246.6) | computed for investor individuals, never paid; 0 investors in the pickle | **E**: firm and bank profits accumulate forever; there is no profit→household channel |
| Transfers from government 286.7 | equal per household (H4), grown at expected real growth, cpi-indexed | **A**: equal split removes the distribution that drives transfer incidence; fold-in of private pensions is a concept error (I-4) |
| UB / EI 20.6 | per unemployed individual; ratchets up when expected growth < 0 (`social_benefits.py:188`) | **E**: not received (A3). The ratchet never reverses, so the level is not a policy rule |
| Transfers from corporations 121.5; to corporations 162.1; NPISH | absent | **S** (document) |
| PIT 348.1; SSC 131.3 | flat 9% (I-3) on a net base; not charged to households for non-wage income | **E** (calibration and accounting) |
| D.8 pension entitlements 40.6 | absent; pension reserves are in OFA earning `c_FA` | **S** if documented: saving should be compared with DI − HFCE (Stage 2.1) |

## S-H4 Saving allocation and portfolio (H6, H7) — **E** (accounting) / **A** (behaviour)

`φ_h` is a linear model on `[Income, Debt]` **normalised by their cross-sectional sums each period**
(`wealth.py:302-311`). The prediction therefore depends on population size and on the aggregate, not on the
household's own ratios. That is a functional-form defect: a fitted share of normalised levels is not a
portfolio rule. Saving placed in OFA leaves the payments system with no issuer, and dissaving liquidates OFA
first with no buyer (A7). A defensible alternative is to hold OFA as a non-monetary claim on firms/banks
(equity) or on the government (bonds), with explicit issuers, or to keep all household saving in deposits
(`SimpleWealthSetter`, implemented) and treat OFA as exogenously revalued wealth with no cash flow. The
second is the minimal SFC-consistent choice.

## S-H5 Housing: values, rents, tenure, transactions (H10, H11) — **E** (implementation of spec) / **A**

* Constant nominal house prices (σ = 0) and constant nominal rents (`ConstantRentSetter`), while the CPI rises
  (about 15% over 13 quarters in the prior 2022 baseline), mean real rents and real housing wealth fall
  mechanically. That is **A**: defensible for a short validation horizon if documented, but not for
  multi-year projections. Alternatives: index rents to CPI (`partial_rent_inflation_indexation`,
  implemented), or an HPI forecast.
* Tenure codes: the demand rule tests renters as `status == 0` and owners as `status == 1`
  (`property.py:261, 266`). The data and every other module use 3 (renter), 1/2/4 (owner) and −1 (social).
  So renters never re-decide, owners with a mortgage (code 2) or with free use (code 4) never move, and about
  50% of outright owners (code 1, ≈63% of households) list their dwelling every quarter
  (`probability_stay_in_owned_property = 0.5`). This is **E** (coding inconsistency); see the earlier "#30
  tenure-encoding" work, which concerned the same codes.
* Transactions: the buyer is debited, the seller is never credited, and a buyer whose purchase is rejected is
  still debited (A8). **E**.
* Imputed rent: owner-occupiers pay for it in cash through L-sector purchases and do not receive it as income
  (I-13). **E** for any saving or housing-cost analysis. The SNA-consistent options are (i) remove imputed rent
  from the L consumption column (as the ICIO path does) and keep it as a memo item, or (ii) book it on both
  sides (income and consumption) of the household account.
* Actual rent: renters pay 13.3B as transfers to landlords, and the L column (≈81.5B paid rent inside 312.7B)
  is bought from firms as well. Rent is therefore represented twice, at the wrong level in each place (I-8).

## S-H6 Mortgages and consumer credit (H8, H9, credit screens) — **E** (calibration) / **A**

* Screens at package defaults: LTI ≤ 0.05 × *quarterly* income − existing debt; LTV ≤ 0.05/0.95 × financial
  assets; DSTI ≤ 0.05; and a mortgage is taken only if granted in full. With existing debt ≫ 5% of quarterly
  income, new household credit is effectively zero. The mortgage stock (2.4T) then only amortises (installments
  of 184B/yr), so the model contains forced, unmodelled household deleveraging. The values are not Canadian
  (OSFI B-20 and the GDS/TDS rules imply LTI of about 4.5× annual income, LTV ≤ 0.8 without insurance, and
  TDS ≤ 0.44).
* Down-payment rule `M* = P − 1.0·free FA` means every buyer exhausts all free financial assets before
  borrowing. **A**.
* Interest rates: mortgage 0.97%/yr at t0 (I-11, suspected data). **U** until benchmarked.
* Insolvency (H12): loans are written off with no bank loss entry and no asset seizure. **E** (accounting) as
  implemented.

## S-H7 Household investment (H3) — **A**

A fixed rate on expected income (calibrated to the IO household-capital column). The capital accumulates in
"other real assets" at δ = 5% per quarter (≈19% per year). It does not enter the dwelling stock, and it has no
return (no imputed rent, no mixed income). Residential investment is the dominant household GFCF in Canada,
so the stock it builds should be dwellings, with a residential depreciation rate (~1.5–2%/yr). Alternative:
tie investment to housing transactions or to a q-type housing-return rule.

## S-H8 Social transfers and UB (H4) — **A** / **E**

* Equal per household: **A**. This discards the CIS transfer gradient, which is the main determinant of
  low-income consumption and of transfer incidence. Alternative: `DefaultSocialTransfersSetter` (fitted on
  Income/Debt, implemented) or fixed t0 shares.
* `TOT_OTHER` grows with *expected real growth* and is indexed to CPI: a plausible automatic-stabiliser form,
  **S**.
* The UB ratchet (`max(1, 1/(1+g^e))`) is **E** as a policy rule: benefits can rise but never fall.

## S-H9 Mixed income and self-employment — **E** (missing account)

224.8B of net mixed income (rental 127.6B + farm 9.8B + non-farm 87.5B) has no counterpart in household
income. In the model the corresponding value added is firm GOS and is retained. This biases household income
down by about 15% of DI and raises firm cash. Remedies: distribute unincorporated GOS to owner households
(a withdrawal flow), or treat self-employed workers as receiving a wage-equivalent.

## S-H10 Heterogeneity and regional dimension — **A**

Every province samples the same national household file. Provincial behaviour differs only through
calibration residuals (I-2). This is defensible for a first national calibration, but provincial
consumption and saving outcomes should not be interpreted until counts and regional controls (CHS tenure,
provincial DI) are targeted.

---

## Priority ranking (households)

| Rank | Item | Why first |
|---|---|---|
| 1 | I-1 household count and provincial allocation | Contaminates every household aggregate, the regional saving rates and the first-step dynamics. It is a data fix and does not touch behaviour |
| 2 | A2 + E1/E2 (wage indexation, labour-tax base, UB receipt) | Planned and realised income diverge by construction and the gap grows with inflation, which drives deposit drift |
| 3 | A1, A5, A3, A4, A7, A8 household-side leaks | Without them the household budget constraint does not hold, so SFC drift cannot be attributed |
| 4 | I-6 + I-7 (labour-income residual, average-saving rule) | Initialisation is not a fixed point of the rules; first-step jumps are guaranteed |
| 5 | I-13 / S-H5 rent and imputed-rent treatment | About 230B/yr of mis-classified housing cost; affects saving and GDP |
| 6 | S-H1 propensity specification (heterogeneous MPC, wealth term) | Matters for multipliers, but cannot be calibrated until 1–5 are fixed |
| 7 | S-H6 credit screens, I-11 rates | Household credit is inactive, with forced deleveraging |
| 8 | S-H9, S-H3 missing accounts (mixed income, dividends, corporate transfers) | Model-wide; belongs with the firm and bank audits |
| 9 | S-H5 tenure-code bug, house-price/rent indexation | Behavioural but contained to the housing module |

## Recommended decision points (for the user)

1. **Reference pickle.** Adopt the branch-rebuilt pickle (SOCX transfers) as the validation reference, and
   flag that any `feature/itc-user-cost` run on the canonical pickle uses the superseded 516B transfer level.
2. **Fix order.** Fix data and accounting before behaviour: (i) household count and provincial allocation from
   CHS; (ii) the household budget-constraint leaks (A1–A5, A7, A8) one at a time, each with regression checks;
   (iii) only then re-calibrate `s`.
3. **Saving concept.** Calibrate the consumption rule against `DI − HFCE` (no D.8) and state this
   explicitly.
4. **Housing/rent treatment.** Choose between removing imputed rent from L consumption (memo item) and booking
   it on both sides. Replace the French "Rent Paid" with a Canadian rent source (SHS or CHS shelter cost).
5. **Consumption rule family.** Keep the fixed-propensity rule but with household-specific SHS-based `s`
   (minimal change), or move to an income-plus-liquid-wealth rule (recommended for policy multipliers).
6. **Credit screens.** Keep them closed and document it, or recalibrate to Canadian B-20/GDS/TDS-type limits
   before any interest-rate experiment.
