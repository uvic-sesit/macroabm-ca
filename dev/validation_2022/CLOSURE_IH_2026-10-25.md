# Household closure IH review — 2026-10-25 (UTC)

Review baseline: `51f0615`; accepted configuration remains **F_CFC**. Q and E/E2 are opt-in. No investment or household-income rule was changed. No accepted pickle, original model repository, ITC experiment, or IO pipeline was modified; no push. Phase B and C_dp_005 remain on hold.

## Decisions and gates

| Step | Change / finding | Commit / validation | Gate / decision |
|---|---|---|---|
| 1 Housing GDP | Remove duplicate IO-contained real/imputed rent at t0; scope public rental income and debug addends consistently; retain cash rent memos | `c1712b7`, `3557989`; two housing regression tests; three F_CFC and three E exact-path comparisons | H-G1/H-G2 pass on all applicable seeds. Initial GDP decreases 64.131664B. |
| 2 Investment | Read-only ledger identifies replacement-only dynamics **and an inherited investment allocation proxy**, rather than an observed-GFCF initial anchor | `04fb61e`, `57f16c9`; per-industry/province investment ledger and exact decomposition | Specification decision required; no rule change. Independent steps completed. |
| 3 Income distribution | Cash DI is substantially more concentrated than DHEA, with income concepts and allocation both contributing | `04fb61e`, `57f16c9`; exact income reconstruction, benchmark vectors in companion CSV | No fix; decide the income bridge and allocation before fitting consumption shares. |
| 4 E2 cure | Full cure already existed; partial catch-up now freezes the bucket and distress clock when current service is covered and old arrears shrink | `15fcb37`; two cure regressions, 2Q then 12Q seeds 0–2, N=3 and discount=20% unchanged | E-G1 fails every seed; E-G2 and accounting pass. E2 remains opt-in and unvalidated. |
| 5 Net-surplus cost gate | F_CFC fails; unaccepted FB passes the revised cost criterion | `04fb61e`; net-surplus regression, exception CSVs | FB's separate GDP/SUT failure remains; do not promote it. |
| 6 Review | All independent work completed; no tuning | Full one-worker suite below; protected hashes and run manifests audited | Stop for review. |

Diagnostic scripts and gates live in `ih_diagnostics.py`, `prepare_ih.py`, `ih_observed_investment.py`, `summarise_ih.py`; measurement implementation was committed separately from model changes. The subsequent arrears-attribution correction is read-only, regression tested, and replayed against the original E economic paths.

## 1. Housing scope and corrected contraction

IO-contained housing contributes **zero additional rent** to each GDP approach at t0 and dynamically. Rent paid, imputed rent and rent received remain intact in cash/market ledgers. Paid and imputed rents have explicitly named report memo columns. No trade, inventory or cash entry was introduced. The residual in expenditure component changes is below one dollar nationally; the Q0 to Q12 decomposition contains no `initial_housing_scope_change` term.

A code search found no agent behaviour reading the GDP, national C or national I reporting series. Growth expectations use historic **gross-output growth** and exogenous observations (`economy/economy.py:439–448`), rather than GDP; firm targets use firm-specific demand/production histories. Household propensity calibration uses household incomes and its explicit benchmark, rather than economy-level t0 C. Initial economy C/I continue to precede closure reanchoring; that surviving timing distinction is documented, not silently reanchored. Exact `outcomes.csv`, non-GDP headline series and Q1–Q12 GDP match the previous F_CFC/E runs on every seed (`behaviour_comparison.csv`). The changes in GDP growth reporting denominators are intentional reporting effects.

Nominal levels in B; PPI-deflated GDP is an indicative proxy, **not** SNA chained real GDP:

| arm | seed | Q0 | Q1 | Q12 | Q0_Q12_pct | Q1_Q12_pct | PPI_proxy_Q0_Q12_pct | PPI_proxy_Q1_Q12_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E2 | 0 | 708.084 | 700.259 | 676.562 | -4.452 | -3.384 | -7.930 | -7.512 |
| E2 | 1 | 708.084 | 715.043 | 698.093 | -1.411 | -2.370 | -11.577 | -11.263 |
| E2 | 2 | 708.084 | 696.897 | 636.358 | -10.130 | -8.687 | -13.154 | -12.943 |
| E | 0 | 708.084 | 700.259 | 673.723 | -4.853 | -3.790 | -7.024 | -6.602 |
| E | 1 | 708.084 | 715.043 | 663.913 | -6.238 | -7.151 | -8.722 | -8.398 |
| E | 2 | 708.084 | 696.897 | 573.661 | -18.984 | -17.684 | -10.835 | -10.618 |
| F_CFC | 0 | 708.084 | 700.259 | 654.309 | -7.594 | -6.562 | -7.321 | -6.901 |
| F_CFC | 1 | 708.084 | 715.043 | 645.013 | -8.907 | -9.794 | -9.216 | -8.893 |
| F_CFC | 2 | 708.084 | 696.897 | 584.880 | -17.400 | -16.074 | -13.062 | -12.851 |

The reporting correction removes an exaggerated initial contraction. It does not eliminate the model's no-shock contraction or explain seed divergence.

## 2. Investment diagnosis — no rule change

For firm i and capital input j, the active rule is:

- Expected demand extrapolates smoothed previous demand with macro and firm growth expectations (`agents/firms/func/demand_estimator.py:120` onward). Desired output adds inventory-buffer adjustments (`func/target_production.py:267`).
- Capital-plan reference output q^K is clamped toward available labour, intermediate inputs and capital capacity (`firms.py:709–738`; `func/target_production.py:364–379`). The shipped capital-capacity weight is 1; fully utilised initial capacity and capacity-capped excess demand are the previously documented F-S1/F-S3 lock.
- Raw replacement R_ij = q^K_i × delta_ji (`func/target_capital_inputs.py:339`). Unconstrained purchases U_ij = max(0, R_ij - lambda × (K_ij - Kref_ij)) (`:371–386`). The accepted lambda is **0**, so there is no independent expansion or positive net-investment term. The default base-year reference is K0 × q_previous/q0; forward-looking and rolling alternatives exist but are off (`:104–207`). ITC/user-cost switches are inactive and untouched.
- Finance-adjusted plan T_ij = max(0, U_ij - gamma × (credit_target - credit_received)/[(1+expected_inflation) × lagged_price_j]) (`:438–444`). Gamma is **0** in the accepted configuration. This particular financing cut is zero, even where requested credit is unmet; financing can still affect other targets and payment distress. The ledger keeps requested/received long credit separately.
- Actual capital goods are allocated from executed goods purchases (`firms.py:1369–1377`), then valued and assigned actual nominal expenditure (`:1390–1434`). Therefore plan less nominal actual is a **clearing/price residual**, not all credit rationing. Realised CFC is valued on actual output; replacement planning uses reference output and lagged prices.

**Correction to the starting hypothesis:** initial firm purchases were explicitly frozen from the previous used-capital/depreciation proxy by `build_firm_cfc_b2.py:83–86`. They are not an independently observed 2022 GFCF series. Their annual total is **398.886B**, while the observed-CFC charge is **377.244B**. The resulting t0 model net investment of **21.642B/year** cannot be treated as an observed growth target.

Observed annual 2022 current-price non-residential capital flows, StatCan **36-10-0096-01**, including the business residual that excludes government and NPISH:

| Industry | Geometric depreciation | Investment | net_investment |
| --- | --- | --- | --- |
| Government sector | 90.815 | 98.480 | 7.665 |
| Non-profit institutions serving households | 1.539 | 1.519 | -0.020 |
| Total all industries | 377.319 | 411.341 | 34.022 |
| Business residual excluding government and NPISH | 284.965 | 311.342 | 26.377 |

Direct Canada vectors: total investment/CFC **v90968052/v90968082**; government **v90970252/v90970282**; NPISH **v90970012/v90970042**. The business residual is derived from those three source series, with no independent invented vector.

The national model includes O/P/Q and financial/other producers, so it is not a private-business-only GFCF series. Its t0 O/P/Q purchases are only **29.084B/year**, versus CFC **95.548B/year**; other model industries purchase **369.802B/year**, versus CFC **281.696B/year**. Those groupings do not exactly equal institutional government/business sectors. They show that a close national aggregate conceals a large allocation discrepancy. No part of this discrepancy was repaired or rescaled.

The read-only provincial/industry concordance reuses the accepted CFC source grouping and fixed output shares. It maps investment to **412.999B/year**, **1.658B above** the direct Canada total; provincial/national fallback and concordance differences remain visible. This diagnostic mapping is not a balanced new investment calibration. Its row-level vectors and fallback labels are in `observed_investment_concordance.csv`; the direct Canada totals above are the primary benchmark. Mapped observed net investment uses mapped **source CFC**, separately from CFC actually charged by the model. Before/after concept comparisons are in `initial_investment_observed_comparison.csv` (industry × province) and `initial_investment_industry_annual_B.csv`.

Seed 0, B/quarter. At Q0 the “stock adjustment” column is the inherited acquisition-minus-CFC difference, not an executed behavioural expansion calculation:

| quarter | replacement_planned | stock_adjustment_and_clipping | credit_cut | realised | CFC | net_investment | hold_initial_net_accounting |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 94.311 | 5.411 | 0.000 | 99.721 | 94.311 | 5.411 | 99.721 |
| 1 | 94.311 | 0.000 | 0.000 | 94.775 | 94.754 | 0.021 | 100.164 |
| 2 | 94.473 | 0.000 | 0.000 | 94.698 | 94.827 | -0.129 | 100.237 |
| 3 | 94.422 | 0.000 | 0.000 | 93.103 | 93.190 | -0.087 | 98.601 |
| 4 | 92.771 | 0.000 | 0.000 | 93.697 | 93.719 | -0.022 | 99.129 |
| 5 | 92.908 | 0.000 | 0.000 | 92.071 | 92.027 | 0.044 | 97.438 |
| 6 | 91.395 | 0.000 | 0.000 | 91.859 | 91.809 | 0.050 | 97.220 |
| 7 | 91.110 | 0.000 | 0.000 | 89.675 | 89.618 | 0.057 | 95.028 |
| 8 | 89.840 | 0.000 | 0.000 | 90.993 | 90.861 | 0.132 | 96.271 |
| 9 | 90.008 | 0.000 | 0.000 | 89.131 | 88.989 | 0.141 | 94.400 |
| 10 | 88.852 | 0.000 | 0.000 | 88.609 | 88.416 | 0.193 | 93.826 |
| 11 | 87.801 | 0.000 | 0.000 | 87.948 | 87.749 | 0.199 | 93.159 |
| 12 | 86.998 | 0.000 | 0.000 | 88.881 | 88.585 | 0.296 | 93.996 |

All seeds have zero active stock-gap expansion and zero direct credit-plan cut. Their Q12 firm purchases are **88.881/85.133/72.144B**, compared with 99.721B at t0. Household investment falls as well and must not be folded into the firm-rule attribution. All industry × province × quarter observations, prices/clearing residuals and financing quantities are retained in `investment_industry_province.csv`.

The counterfactual column holds **each cell's initial nominal net investment**, including negative values: I_accounting(t)=CFC_actual(t)+(I0-CFC0). This is an accounting replacement of one line; actual output, prices, wages, financing and clearing are held at their observed run values. It is **not** a feasible investment policy, causal GDP simulation, or forecast; negative cell values are not clipped to conceal scope problems.

### Consumption and descriptive GDP attribution

Household-account C includes VAT and actual rent; GDP's IO C has its own housing scope. At Q1/Q12, B/quarter and percentages:

| seed | quarter | consumption | cash_DI | cash_saving_rate | constrained_share | investment | asset_liquidation | investment_cut | consumption_cut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 378.377 | 371.908 | -1.739 | 18.631 | 51.518 | 11.080 | 8.494 | 5.404 |
| 0 | 12 | 325.442 | 339.069 | 4.019 | 50.374 | 29.219 | 22.279 | 25.832 | 29.055 |
| 1 | 1 | 382.889 | 371.141 | -3.165 | 18.762 | 52.174 | 11.976 | 8.661 | 5.579 |
| 1 | 12 | 334.172 | 348.461 | 4.100 | 50.072 | 32.133 | 23.375 | 24.692 | 23.428 |
| 2 | 1 | 379.227 | 370.753 | -2.286 | 18.561 | 50.407 | 11.677 | 8.339 | 5.390 |
| 2 | 12 | 304.621 | 315.942 | 3.583 | 49.647 | 27.313 | 22.216 | 23.893 | 27.872 |

The wage/price bridge (compensation and contributions in B; employment in millions):

| seed | quarter | firm_compensation | employment | workers_effect | wage_composition_effect | GDP_C_price_effect | GDP_C_quantity_effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 346.584 | 19.202 | 0.000 | 0.000 | 0.000 | 0.000 |
| 0 | 12 | 317.798 | 18.207 | -17.954 | -10.832 | -11.616 | -34.864 |
| 1 | 0 | 346.584 | 19.202 | 0.000 | 0.000 | 0.000 | 0.000 |
| 1 | 12 | 319.599 | 17.840 | -24.578 | -2.407 | -5.961 | -31.736 |
| 2 | 0 | 346.584 | 19.202 | 0.000 | 0.000 | 0.000 | 0.000 |
| 2 | 12 | 284.679 | 16.947 | -40.702 | -21.204 | -16.071 | -51.298 |

The wage-bill change splits exactly into a worker-count term at the initial average bill and a wage/composition term at current workers. The nominal GDP-C change splits into its CPI-deflated quantity change and price term at the regional indices; these are diagnostic index calculations. `consumption_cash_bridge.csv` gives every quarter's exact identity C = net wages + mixed income + property receipts + transfers - net interest - cash saving. It separates the transfer and saving contributions without treating them as an identified investment multiplier.

`income_quintiles.csv` contains every quarter's wage income, transfers, mixed/property receipts, taxes, net interest, C and financial assets. Together with `headline.csv` employment and CPI and `quarterly.csv` spending cuts, it decomposes nominal income/spending changes without claiming an identified causal multiplier. Planned consumption can exceed receipts while assets run down; binding budgets and falling earned income then reduce realised C. CPI-deflated C and employment are in `changes.csv`; prices are separated from nominal expenditure. Transfers include automatic benefits and firm-funded D2 receipts, so they cannot all be interpreted as exogenous stabilisers.

Signed contribution to Q0 to Q12 nominal GDP change, B and percent of that change (negative percentages offset the contraction):

| seed | component | delta_CAD | share_GDP_change |
| --- | --- | --- | --- |
| 0 | C | -46.480 | 86.435 |
| 0 | G | 22.756 | -42.318 |
| 0 | I | -37.806 | 70.305 |
| 0 | inventories | 9.412 | -17.503 |
| 0 | X | -13.953 | 25.947 |
| 0 | M | 12.296 | -22.866 |
| 1 | C | -37.697 | 59.769 |
| 1 | G | 3.259 | -5.167 |
| 1 | I | -38.641 | 61.266 |
| 1 | inventories | 12.211 | -19.360 |
| 1 | X | -15.560 | 24.671 |
| 1 | M | 13.357 | -21.178 |
| 2 | C | -67.369 | 54.681 |
| 2 | G | -21.284 | 17.276 |
| 2 | I | -56.449 | 45.818 |
| 2 | inventories | 23.932 | -19.425 |
| 2 | X | -50.570 | 41.046 |
| 2 | M | 48.536 | -39.395 |

Direct total investment decline accounts descriptively for **70.3%, 61.3%, 45.8%** of the GDP decline; C accounts for **86.4%, 59.8%, 54.7%**, with the other components offsetting or adding to them. These shares are not an estimate that investment *caused* the consumption fall. Establishing that feedback requires an approved structural counterfactual. The legacy GDP routine balances reported X/M to output GDP; those trade entries are not independently identified feedback effects.

**Investment options for decision (none implemented):** (1) reconcile observed GFCF by industry/province and institution, explicitly distinguishing source CFC from net additions, then decide a transitional or exogenous net-additions path; this fixes the data anchor but does not create an endogenous expansion mechanism. (2) introduce a growth/expectations-consistent desired-capital term, tied to *unclamped* demand and a defensible utilisation target, alongside correcting the F-S1/F-S3 censored-demand lock. Merely raising a stock-gap weight with capacity-clamped demand cannot reliably unlock growth; the existing forward-looking/rolling-reference options must be tested jointly with the signal. (3) use a stock-adjustment plan around desired capacity with explicit order/backlog expectations and financing, replacing the output-proportional replacement shortcut. Options 2/3 need stability and shock-response checks; no parameters should be chosen to make these gates pass.

## 3. Household income distribution vs DHEA — no fix

Rank is national, household-weighted cash DI per actual household divided by OECD-modified units (1 for first adult, .5 additional age 14+, .3 under 14), exactly the G3 ranking. Quintile totals and shares are **unequivalised household DI** after ranking, and per-household annual amounts use expanded household counts. This is a cash proxy, whereas DHEA allocates SNA DI, including noncash concepts. It is not the SHS before-tax-income ranking.

DHEA table **36-10-0587-01**, 2022 DI vectors **v116884005/028/051/074/097**. Seed 0 initial levels (shares in %, per-HH in CAD/year):

| quintile | model_DI_share | DHEA_DI_share | model_per_HH | DHEA_per_HH | nonpositive_DI_share | negative_DI_share |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3.834 | 6.805 | 18169.386 | 31485.000 | 0.387 | 0.387 |
| 2 | 7.860 | 12.473 | 37230.809 | 57709.000 | 0.000 | 0.000 |
| 3 | 13.686 | 16.673 | 64853.963 | 77139.000 | 0.000 | 0.000 |
| 4 | 23.259 | 23.880 | 110188.356 | 110484.000 | 0.000 | 0.000 |
| 5 | 51.360 | 40.168 | 243263.310 | 185843.000 | 0.000 | 0.000 |

Other seeds and Q12 are in `DHEA_DI_comparison.csv`. The model represents **15.49732M households**, while DHEA's published totals/per-household means imply about **16.24M** (rounded source means). That denominator gap matters for levels; it cannot explain the large share differences. Only about **0.387% of bottom-quintile households** have nonpositive initial cash DI; the rest of the initial quintiles have none. The bottom shortfall is broader than zero-income records. The optional weighted mean of per-household equivalised DI is retained only as a model statistic; it is **not** compared to DHEA “value per consumption unit,” which divides the aggregate by aggregate units (metadata footnote 10).

Bottom-quintile component bridge, B/year. Gross wages exclude employer contributions; property receipts exclude deposit interest, which is netted in the interest-paid line. Taxes/contributions are the model PIT and employee SSC. Those scope differences are explicit:

| model_line | model_annual_B | DHEA_annual_B | gap_B | vector |
| --- | --- | --- | --- | --- |
| wages_gross | 13.983 | 38.194 | -24.211 | v116884006 |
| mixed_gross | 0.591 | 16.828 | -16.237 | v116884007 |
| property_gross_ex_deposit_interest | 4.926 | 7.997 | -3.071 | v116884008 |
| current_transfers_gross | 45.685 | 83.095 | -37.410 | v116884010 |
| taxes_contributions | 4.538 | 31.585 | -27.047 | v116884011 |
| net_interest | 4.342 | 12.290 | -7.948 | v116884009 |
| DI | 56.305 | 102.239 | -45.934 | v116884005 |

The model lines reconstruct DI exactly (rounding residual under one cent at quintile level). Current transfers combine government benefits/pensions and grossed-up corporate transfers, with the benchmark counted once. Separate government transfers are **40.099B**, against DHEA's broader current receipts **83.095B**; corporate receipts add **5.586B**. Thus combined transfers have the largest negative bottom-quintile line gap (**37.410B**), followed by labour (**24.211B**) and mixed income (**16.237B**). Lower model taxes/contributions and net interest offset part of those gaps. This is a concept-aware decomposition, not proof that every gap is an error to be filled with cash.

National component totals, B/year:

| model_line | model_annual_B | DHEA_annual_B | gap_B |
| --- | --- | --- | --- |
| DI | 1468.386 | 1502.343 | -33.957 |
| current_transfers_gross | 377.824 | 422.524 | -44.700 |
| mixed_gross | 97.274 | 224.839 | -127.565 |
| net_interest | 36.395 | 84.211 | -47.816 |
| property_gross_ex_deposit_interest | 108.554 | 246.590 | -138.036 |
| taxes_contributions | 281.276 | 685.930 | -404.654 |
| wages_gross | 1202.404 | 1378.529 | -176.125 |

Bottom quintile's shares of each national component:

| model_line | model_bottom_share_pct | DHEA_bottom_share_pct |
| --- | --- | --- |
| wages_gross | 1.163 | 2.771 |
| mixed_gross | 0.607 | 7.484 |
| property_gross_ex_deposit_interest | 4.538 | 3.243 |
| current_transfers_gross | 12.092 | 19.666 |
| taxes_contributions | 1.613 | 4.605 |
| net_interest | 11.931 | 14.594 |
| DI | 3.834 | 6.805 |

National cash DI is 1,468.386B versus DHEA 1,502.343B, a 2.26% shortfall, while bottom DI is 45% short. Large gross receipt and deduction concept gaps offset nationally; the disproportionate bottom gaps in wages, mixed income and transfers establish an allocation problem in addition to missing concepts. Adding the national gross-income gaps as cash while omitting their pension/tax/noncash counterparts would be an unjustified closure change.

Mapping: model gross wages correspond to part of DHEA compensation, without employer pension/social contributions; nonrental mixed income corresponds to only part of DHEA net mixed income, which includes owner-occupied dwelling services; cash dividends/rent and net deposit interest correspond to portions of DHEA property receipts/payments, without the full pension/insurance/imputed attribution; government and corporate transfers correspond to current transfers, with different pension and institutional coverage. DHEA taxes/social contributions include noncash and employer-related entries absent from the model's cash deduction. STiK is **not** added to DI (it belongs to adjusted DI). The initial financial-asset-income proxy is removed in favour of funded D2 receipts, as in the accepted configuration.

Source allocation is also material: the adapter first uses CIS-decile income shares (`macro_data/readers/population_data/canadianized_household_adapter.py:96–106`); pension/social-transfer weights are subsequently fitted and nationally rescaled (`synthetic_population/hfcs_synthetic_population.py:705–723`); matched individual jobs determine wages; D2 distributions depend on its allocation weights. None is a DHEA component-by-component allocation. Since the mismatch exists at t0, it cannot be attributed to subsequent firm failures alone. The gross wage/transfer gaps require an allocation/data-boundary audit; missing imputed housing and pension concepts require a conceptual bridge, not an invented payment.

**Income options:** build matched cash/SNA accounts first, including employer/pension contributions and imputed housing as noncash memo counterparts; then audit CIS/benefit/job allocation against a consistent after-tax household-income distribution. Alternatively retain a deliberately cash-only household model and use cash-comparable distribution targets after documented exclusions. Do not infer spending propensities from unmatched DHEA C/DI ratios or add transfers just to reproduce consumption shares. No income or spending specification was changed here.

## 4. E2 cure and remaining defaults

E already returned a household to current when the entire scheduled service plus old arrears was paid. The premise that cure was impossible was therefore incorrect. E2 adds one opt-in assumption: when the current schedule is fully covered and outstanding old arrears decline, preserve the current bucket and consecutive-distress clock; full settlement resets both; otherwise age as before. There is no forgiveness, no new term extension, and **zero restructurings**. Full current payment without positive catch-up does not freeze ageing. N=3 and the 20% foreclosure discount are unchanged. Household overdraft relief keeps its existing negative-deposit distress rule; the added 30/60/90 catch-up treatment concerns formal loan arrears.

Canadian [CMHC mortgage guidance](https://www.cmhc-schl.gc.ca/professionals/industry-innovation-and-leadership/industry-expertise/resources-for-mortgage-professionals/i-cant-pay-my-mortgage) discusses alternative payment arrangements; [FCAC debt guidance](https://www.canada.ca/en/financial-consumer-agency/services/debt/paying-debt.html) discusses repayment schedules and past-due accounts. These support considering cure/workouts, **not** the numerical quarterly bucket-freeze assumption. Source dates, factual-extract hashes and the direct CMHC 403 limitation are recorded in `benchmarks/IH/cure_assumption.json`; no full-webpage hash is claimed. The rule is a labelled diagnostic assumption, not a fitted Canadian cure estimate.

The initial entrant classification incorrectly treated a rising stock interest/principal ratio as a rate reset. Amortisation can raise that ratio with no reset; the current loan implementation does not reset existing contracts. That diagnostic was rejected and replaced with a tested classification and exact-path E replays (`entrant_replay_proof.json`). Main entrant counts use those corrected replays. No model payment rule changed for this correction. Trigger labels are a descriptive priority hierarchy: unable to cover initial senior service from initial deposits/receipts/liquid assets; then current DI below initial DI; then initially planned C above DI; then other. Separate overlapping flags are retained. An income decline flag does not prove that the decline alone caused failure; any-decline classification is stated explicitly. Confirmed existing-contract reset entrants are zero; changing new-loan mix is not a reset.

`arrears_entrants_corrected.csv` reports entrants by seed, quarter, formal debt type, initial equivalised-DI decile and tenure; these are loan-type entry events, **not unique people over 12 quarters**. Mortgage/consumer co-entry can count a household twice. Initial-data inability, persistent planned dissaving and income losses must therefore not be compared as independent causal experiments.

Corrected entrant events over 12 quarters (expanded household counts):

| seed | income_loss | other | persistent_dissaver | unable_from_t0 | confirmed_rate_reset |
| --- | --- | --- | --- | --- | --- |
| 0 | 232260 | 42060 | 138040 | 68070 | 0 |
| 1 | 259220 | 40030 | 122060 | 79070 | 0 |
| 2 | 339340 | 38040 | 120060 | 74070 | 0 |

Seed 0 mortgage entrants by initial equivalised-income decile and tenure code (1 owner, 3 renter; other codes retained as observed housing states). Other seeds and debt types are in the companion CSV:

| decile | -1 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| 1 | 1000 | 61040 | 1000 | 9000 |
| 2 | 0 | 17000 | 0 | 0 |
| 3 | 0 | 10020 | 1000 | 1000 |
| 4 | 0 | 9010 | 3000 | 4000 |
| 5 | 0 | 7000 | 10 | 2000 |
| 6 | 0 | 10020 | 2000 | 2010 |
| 7 | 0 | 13010 | 3000 | 5010 |
| 8 | 0 | 8000 | 2000 | 0 |
| 9 | 0 | 24030 | 5010 | 3000 |
| 10 | 0 | 19030 | 4000 | 0 |

Arrears/write-off benchmark gate:

| arm | seed | annual_HH_writeoff_pct | Q12_60plus_pct | Q12_90plus_pct | passed |
| --- | --- | --- | --- | --- | --- |
| E2 | 0 | 1.051 | 1.304 | 1.286 | False |
| E2 | 1 | 0.998 | 1.270 | 1.251 | False |
| E2 | 2 | 1.074 | 1.523 | 1.505 | False |
| E | 0 | 1.034 | 1.269 | 1.269 | False |
| E | 1 | 1.048 | 1.377 | 1.377 | False |
| E | 2 | 1.172 | 1.993 | 1.993 | False |

Frozen benchmark sources: [RBC Annual Report 2023](https://www.rbc.com/investor-relations/_assets-custom/pdf/ar_2023_e.pdf), [TransUnion Q3 2024](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q3_24_ciir_report.pdf), and [CBA monthly arrears table](https://cba.ca/Assets/CanadianBankersAssociation/Documents/Articles/Statistics/stat-mortgages-arrears-november-2025-en.pdf).

The annual household net-write-off diagnostic divides total 12-quarter household losses by three and by average formal debt plus household overdrafts (13 stock dates). RBC's 0.10–0.14% is **all consolidated bank loans**, not household-only Canadian losses; its factor-two band is .05–.28%. [TransUnion Q3 2024](https://www.transunion.ca/content/dam/transunion/ca/business/collateral/report/q3_24_ciir_report.pdf)'s mortgage account 60+ Q3 2024 benchmark is .25% (band .125–.50%); [CBA December 2022](https://cba.ca/Assets/CanadianBankersAssociation/Documents/Articles/Statistics/stat-mortgages-arrears-november-2025-en.pdf) 90+ is .15% (band .075–.30%). These different dates and scopes remain limitations, not calibration targets. E-G1 applies the inherited quarterly arrears bounds and annual loss band; all seeds fail. Initial arrears start at zero, so Q1 has no write-off by construction under N=3; passing E-G2 is not validation of initial arrears prevalence.

Cash cures and mortgage roll rates, summed event exposures over 12 quarters:

| arm | seed | mortgage_cure_pct | consumer_cure_pct | roll_30_60_pct | roll_60_90_pct | partial_catchup_household_quarters | restructurings |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E | 0 | 18.604 | 2.871 | 98.335 | 100.000 | 0.000 | 0 |
| E | 1 | 17.723 | 2.180 | 97.852 | 100.000 | 0.000 | 0 |
| E | 2 | 15.420 | 1.611 | 99.355 | 100.000 | 0.000 | 0 |
| E2 | 0 | 16.525 | 3.853 | 96.717 | 95.456 | 97090.000 | 0 |
| E2 | 1 | 17.757 | 4.582 | 92.179 | 95.239 | 100130.000 | 0 |
| E2 | 2 | 17.073 | 3.149 | 98.534 | 95.653 | 115110.000 | 0 |

Cure numerators are captured immediately after servicing, **before** default/foreclosure can zero an arrears record. Thus write-off is not miscounted as cure. The buckets infer monthly due dates from quarterly cash and can jump directly beyond 90; 30 to 60 and 60 to 90 report crossing of the threshold at the next quarterly observation, not a monthly transition probability. Partial-catch-up counts are household × loan-type × quarter events.

### Household and bank loss composition

B over 12 quarters; household losses include formal unsecured, mortgage shortfalls and household overdrafts. The separate firm-overdraft column is **not** an extra household loss:

| arm | seed | household_writeoffs | firm_loan_losses | firm_overdraft_losses | bank_losses | recapitalisation |
| --- | --- | --- | --- | --- | --- | --- |
| E | 0 | 83.044 | 43.006 | 32.027 | 158.077 | 7.694 |
| E | 1 | 84.062 | 50.142 | 34.067 | 168.271 | 12.983 |
| E | 2 | 94.028 | 32.425 | 23.381 | 149.834 | 5.611 |
| E2 | 0 | 84.357 | 47.313 | 27.399 | 159.069 | 7.204 |
| E2 | 1 | 80.184 | 51.007 | 38.567 | 169.758 | 39.406 |
| E2 | 2 | 86.107 | 51.578 | 18.216 | 155.901 | 9.231 |
| F_CFC | 0 | 233.541 | 54.106 | 30.266 | 317.913 | 165.205 |
| F_CFC | 1 | 233.594 | 102.062 | 36.791 | 372.446 | 199.720 |
| F_CFC | 2 | 233.240 | 66.091 | 25.289 | 324.620 | 99.958 |

E2 quarterly composition, B (the `overdraft_losses` column below is firm OD; household OD is separate):

| seed | quarter | mortgage_writeoffs | formal_unsecured_writeoffs | household_overdraft_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation | min_capital_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.109 |
| 0 | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.111 |
| 0 | 3 | 0.000 | 18.741 | 0.004 | 0.005 | 0.003 | 18.754 | 0.000 | 0.074 |
| 0 | 4 | 0.031 | 14.366 | 0.000 | 0.030 | 0.006 | 14.433 | 0.000 | 0.074 |
| 0 | 5 | 0.147 | 9.854 | 0.000 | 0.146 | 0.232 | 10.379 | 0.000 | 0.073 |
| 0 | 6 | 0.020 | 7.943 | 0.080 | 1.008 | 0.546 | 9.596 | 0.000 | 0.065 |
| 0 | 7 | 0.282 | 8.521 | 0.866 | 5.453 | 1.378 | 16.500 | 5.399 | 0.072 |
| 0 | 8 | 0.184 | 5.628 | 0.455 | 3.496 | 3.281 | 13.043 | 0.000 | 0.072 |
| 0 | 9 | 0.018 | 5.821 | 0.781 | 2.783 | 1.159 | 10.562 | 0.000 | 0.063 |
| 0 | 10 | 0.028 | 4.797 | 0.087 | 6.781 | 5.891 | 17.585 | 0.000 | 0.058 |
| 0 | 11 | 0.000 | 2.195 | 1.033 | 17.946 | 10.762 | 31.936 | 1.805 | 0.052 |
| 0 | 12 | 0.000 | 2.302 | 0.173 | 9.665 | 4.141 | 16.281 | 0.000 | 0.050 |
| 1 | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.109 |
| 1 | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.111 |
| 1 | 3 | 0.000 | 18.887 | 0.000 | 0.004 | 0.003 | 18.895 | 0.000 | 0.073 |
| 1 | 4 | 0.058 | 14.421 | 0.000 | 0.001 | 0.000 | 14.480 | 0.000 | 0.074 |
| 1 | 5 | 0.029 | 10.321 | 0.000 | 1.340 | 0.359 | 12.049 | 0.000 | 0.070 |
| 1 | 6 | 0.107 | 7.741 | 0.157 | 0.639 | 0.706 | 9.351 | 0.000 | 0.062 |
| 1 | 7 | 0.094 | 8.424 | 0.560 | 5.592 | 1.441 | 16.110 | 6.719 | 0.084 |
| 1 | 8 | 0.000 | 5.877 | 0.137 | 10.323 | 2.588 | 18.926 | 0.000 | 0.079 |
| 1 | 9 | 0.056 | 5.731 | 0.540 | 19.804 | 9.428 | 35.558 | 0.199 | 0.067 |
| 1 | 10 | 0.023 | 2.597 | 0.500 | 3.077 | 1.520 | 7.717 | 0.000 | 0.065 |
| 1 | 11 | 0.000 | 0.515 | 1.412 | 4.114 | 3.596 | 9.637 | 0.041 | 0.062 |
| 1 | 12 | 0.321 | 0.754 | 0.922 | 6.115 | 18.925 | 27.036 | 32.446 | 0.073 |
| 2 | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.109 |
| 2 | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.111 |
| 2 | 3 | 0.000 | 18.928 | 0.157 | 0.005 | 0.003 | 19.093 | 0.000 | 0.074 |
| 2 | 4 | 0.103 | 14.528 | 0.000 | 0.098 | 0.013 | 14.743 | 0.000 | 0.074 |
| 2 | 5 | 0.069 | 10.067 | 0.000 | 1.032 | 0.377 | 11.545 | 0.000 | 0.072 |
| 2 | 6 | 0.237 | 8.304 | 0.231 | 1.451 | 0.694 | 10.916 | 0.000 | 0.055 |
| 2 | 7 | 0.172 | 8.826 | 1.480 | 6.841 | 2.111 | 19.430 | 5.778 | 0.066 |
| 2 | 8 | 0.000 | 9.173 | 0.000 | 3.349 | 1.204 | 13.726 | 0.000 | 0.065 |
| 2 | 9 | 0.018 | 5.882 | 0.364 | 16.690 | 2.652 | 25.606 | 0.000 | 0.062 |
| 2 | 10 | 0.031 | 3.022 | 0.524 | 6.154 | 4.884 | 14.615 | 2.910 | 0.059 |
| 2 | 11 | 0.281 | 1.430 | 0.240 | 13.726 | 4.376 | 20.054 | 0.387 | 0.067 |
| 2 | 12 | 0.000 | 1.755 | 0.283 | 2.231 | 1.902 | 6.172 | 0.156 | 0.053 |

`E2_loss_quarterly.csv` contains every quarter and seed's mortgage loss, formal unsecured loss, household OD relief, firm loan/OD loss, bank total, recapitalisation, recoveries, defaults and foreclosure sales. `resolution_log.csv` retains each bank/quarter event and recapitalisation; `quarterly.csv` and raw bank files retain minimum capital ratios. Household unsecured figures in the raw headline include OD relief; the derived file subtracts it to report formal unsecured losses separately. No loan-vintage loss-share result is claimed: the inherited vintage hook observes the automatic-servicing path and is not validated for E/E2.

The cure amendment changes timing and some macro paths but does not bring loss levels close to the comparison bands. It produces small differences between 60+ and 90+ at Q12; it does not solve the distribution/spending problem or the remaining firm losses. No further cure/default parameter was tuned after failure.

## 5. Net-surplus gate and IO handoff

The corrected comparison is 100 × [(p-unit_cost_including_CFC)/p - (IO GOS-observed CFC)/output], with tolerance 1 pp. An above-price cost is permitted when observed NOS is negative. Zero-output rows are reported separately and are not divided by zero; IO comparison uses the mapped source GOS, rather than mistaking gross for net surplus.

| arm | active_cells | margin_failures | above_price_exceptions | max_gap_pp | passed |
| --- | --- | --- | --- | --- | --- |
| F_CFC | 648 | 409 | 6 | 100.000 | False |
| FB_unaccepted | 582 | 0 | 0 | 0.001 | True |

Every exception, including its industry/province, price, cost, output, source GOS/CFC and signed margin gap, is in `F_CFC_net_margin_gate.csv` and `FB_unaccepted_net_margin_gate.csv`. The FB cost criterion now passes; its **74.883B/year expenditure imbalance and failed regional GDP construction checks remain unresolved**. This does not promote or modify FB. See `IO_HANDOFF_2026-10-25.md` for the independent pipeline handoff; the pipeline was not changed.

## Provenance, verification and recommendation

Benchmarks: `benchmarks/IH/provenance.json`, exact selected source rows and vectors in `DHEA_components_2022.csv` and `nonres_investment_CFC_2022.csv`; inherited raw retrieval dates and full-file hashes are retained. The DHEA source was retrieved 2026-10-24; investment/CFC source was retrieved 2026-10-24. Canadian credit benchmark URLs, dates, account-versus-balance definitions and hashes remain frozen in `benchmarks/QE/credit_benchmarks.json`. Inputs and accepted pickle hashes are checked in `outputs/IH/audit.json`. Monetary tables use B CAD unless stated; runs and report date use UTC, rather than implying the user's local calendar date.

Full suite via `run_pre_D3_tests.py`, sampler **one worker**: **482 passed, 30 failures, 512 cases**, 835.3s. Every failure is a known `Nan in transactor_total_real_supply` case; zero additional failures. Final results are in `verification_final/full_test_execution.json`. All primary runs pass the 1e-8 accounting battery. Rejected diagnostic classifications and superseded extracts remain identified rather than silently overwritten.

Recommendation: retain the housing reporting fix. Keep F_CFC as the accepted **diagnostic baseline**, not a validated equilibrium. Do not promote E2 or FB and do not start Phase B. Prioritise the observed-GFCF allocation and expansion specification jointly with the cash/SNA income bridge. The buffer-stock household rule remains an option for an explicit user decision after that reconciliation. Cure alone does not make household losses, firm losses or recapitalisations plausible. Stop here for review; no investment or income change, Phase B run, or C_dp_005 port has been started.
