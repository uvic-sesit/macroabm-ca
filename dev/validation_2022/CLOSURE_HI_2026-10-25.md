# Household closure HI round - 2026-10-25 UTC

Base `3fe9c17`, branch `feature/validation-2022`. **Neither new input passes adoption. F_CFC remains the accepted diagnostic baseline.** No parameter was tuned after failure. All independent steps were completed; the dependent six 12-quarter runs were not started. No push, original-repository write, ITC change, accepted-pickle overwrite, investment expansion rule, Phase B run or C_dp_005 port.

## Gates and commits

| Step | Result | Commit / evidence | Decision |
|---|---|---|---|
| 1 / HI-G1 | First divergence identified in the adapter's source distribution; subsequent population and payroll processing widen it | `ab8676a`; actual source and retained snapshots, source-code trace, CIS household-unit regression | Diagnostic gate passes. Historical intermediate fit inputs were not archived; incomplete reconstruction is disclosed below. |
| 2 / HI-G2 | Candidate improves concentration, but max relative decile-share error remains 21.153%; national model DI changes 0.000% | `fc70bf5`; donor/payroll/transfer/reset regressions; new input, seed-0 two-quarter accounting | Fails +/-10%; do not adopt or tune. |
| 2 / HI-G3 | Recipient incidence is close (max gap1.131pp), but transfer-amount shares miss by28.793% | CIS component/recipient comparison | Amount distribution fails; no benefit top-up added. |
| 2 / HI-G4 | Existing household/bank/firm financial stocks and all regional component totals preserved; accounting error4.99e-15 | Exact per-field build checks and 2Q battery | Marginal balance checks pass. Income-ranked wealth distribution moves and is reported, not silently refitted to SFS. |
| 3 / HI-G5 | National GFCF412.998B/year vs411.341B, +0.403%; four mapped source groups exceed2%; all13 GDP initialization checks fail | `d9102ec`; acquisition-value regression, independent new build, GDP checks unchanged | Fails. No unsupported capital bundle, cash, trade or inventory plug invented. |
| 4 | No passing input to carry forward | `gates.json` | Combined build and F_CFC/E2 seeds0-2 reruns gated off; no claim of improved Q12 dynamics or a new E2 gate. |
| 5 | Report and source/stock audit completed | Full suite below; `audit.json` | Stop for review. |

New, unaccepted inputs: `io2022_household_f_cfc_cisallocation_hi_2026_10_25.pkl` and `io2022_household_f_cfc_gfcf_hi_2026_10_25.pkl`. Their full hashes, source hashes and derivation are in the build provenance JSONs. Accepted files are unchanged.

## Primary CIS target and cash/SNA definitions

The primary target is a **CIS2022 PUMF household custom tabulation**, catalogue72M0003X: deduplicate economic families using EFID, sum family income components once into household PUMFID, then use the common household FWEIGHT. The unit is an unequivalised household, ranked by its annual nominal2022 after-tax cash income. The PUMF represents15.454537M households, versus15.497320M in the model. No survey or model weights were changed. PUMFID/EFID/EFATINC/EFWGSAL/EFSEMP/EFINVA/EFGTR/EFINCTX/EFPRPEN and FWEIGHT are recorded in `benchmarks/HI/cash_concept.json`; the PUMF and adapter source have SHA256 provenance. Microdata remain uncommitted.

[StatCan11-10-0192-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110019201) publishes economic-family/unattached-person deciles; [11-10-0193-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110019301) publishes adjusted-person income deciles. Neither is an unadjusted household-decile table. Both2022 extracts, metadata, exact vectors and retrieval hashes are frozen; the applicable published after-tax share vectors are listed in `published_CIS_crosscheck_vectors.csv`. **There are no StatCan vector IDs for the custom household tabulation**; none is invented. It is used to match model household units, while the published tables remain separate checks. Their dollar levels are in2024 constant dollars; they are not silently compared with nominal2022 dollars. The PUMF is its original2022 vintage; the current published tables include later population-weight revisions. National/territory coverage and household-versus-family differences remain explicit.

CIS after-tax income deducts income tax but not loan interest or CPP/EI employee deductions. For comparison only, the model bridge uses funded receipts before net loan/deposit interest and adds back the unchanged employee contribution deduction. This is **not additional spendable cash** and changes no payment. The model cash DI after net interest remains1468.386B/year. Its existing DHEA reference is1502.343B; that inherited2.26% concept/level gap is not filled. The CIS-comparable model income is1523.778B/year, unchanged by the candidate. Model national component budgets remain fixed even where they differ from CIS or SNA concepts.

Inherited national cash/SNA bridge (B/year, unchanged; model gross wages exclude employer contributions, property receipts net deposit interest into the paid line, mixed income omits imputed dwelling income, and deductions omit noncash pension entries):

| model_line | model_annual_B | DHEA_annual_B | gap_B |
| --- | --- | --- | --- |
| DI | 1468.386 | 1502.343 | -33.957 |
| current_transfers_gross | 377.824 | 422.524 | -44.700 |
| mixed_gross | 97.274 | 224.839 | -127.565 |
| net_interest | 36.395 | 84.211 | -47.816 |
| property_gross_ex_deposit_interest | 108.554 | 246.590 | -138.036 |
| taxes_contributions | 281.276 | 685.930 | -404.654 |
| wages_gross | 1202.404 | 1378.529 | -176.125 |

STiK belongs to adjusted DI and is not added as cash. DHEA remains a reference, not the household distribution target.

## 1. Stage-by-stage allocation audit

Actual source/retained snapshots (shares in%, per-household nominal CAD/year):

| stage | decile | share | per_HH |
| --- | --- | --- | --- |
| actual_adapter_source | 1 | 1.569 | 15248.450 |
| actual_adapter_source | 2 | 2.983 | 29012.846 |
| actual_adapter_source | 3 | 4.266 | 41453.376 |
| actual_adapter_source | 4 | 5.518 | 53628.239 |
| actual_adapter_source | 5 | 6.878 | 66851.961 |
| actual_adapter_source | 6 | 8.492 | 82551.856 |
| actual_adapter_source | 7 | 10.432 | 101409.571 |
| actual_adapter_source | 8 | 12.744 | 123877.504 |
| actual_adapter_source | 9 | 16.431 | 160248.304 |
| actual_adapter_source | 10 | 30.687 | 297326.731 |
| retained_synthetic_population_post_matching | 1 | 1.422 | 12259.600 |
| retained_synthetic_population_post_matching | 2 | 1.990 | 17142.395 |
| retained_synthetic_population_post_matching | 3 | 2.797 | 24098.410 |
| retained_synthetic_population_post_matching | 4 | 3.976 | 34264.579 |
| retained_synthetic_population_post_matching | 5 | 5.588 | 48142.396 |
| retained_synthetic_population_post_matching | 6 | 7.544 | 64987.836 |
| retained_synthetic_population_post_matching | 7 | 9.907 | 85377.848 |
| retained_synthetic_population_post_matching | 8 | 13.193 | 113630.727 |
| retained_synthetic_population_post_matching | 9 | 18.146 | 156365.495 |
| retained_synthetic_population_post_matching | 10 | 35.435 | 305129.456 |
| retained_validated_income_before_rescale | 1 | 1.552 | 15240.594 |
| retained_validated_income_before_rescale | 2 | 2.973 | 29187.684 |
| retained_validated_income_before_rescale | 3 | 4.241 | 41639.574 |
| retained_validated_income_before_rescale | 4 | 5.469 | 53685.221 |
| retained_validated_income_before_rescale | 5 | 6.796 | 66698.540 |
| retained_validated_income_before_rescale | 6 | 8.419 | 82680.449 |
| retained_validated_income_before_rescale | 7 | 10.390 | 101974.483 |
| retained_validated_income_before_rescale | 8 | 12.769 | 125413.746 |
| retained_validated_income_before_rescale | 9 | 16.542 | 162393.427 |
| retained_validated_income_before_rescale | 10 | 30.849 | 302691.134 |

The source household income vector is transplanted from SFS donors and nationally calibrated to DHEA, not calibrated to a CIS household-income distribution. The adapter's baked CIS shares are **economic-family component ratios** applied to those source household incomes; they do not turn SFS income ranks/levels into CIS household ranks/levels. Source top-decile share30.687% already exceeds CIS26.210% by17.08%; retained validated records have30.849%, and the post-matching population has35.435%. Thus HI-G1 does not depend on guessing an unobserved intermediate state.

| Stage | Mechanism and what can be measured |
|---|---|
| CIS ratios in adapter | `canadianized_household_adapter.py:96-106`: investment/private-pension/public-transfer ratios indexed by original income-decile labels. Residual market income is not a separately observed wage/self-employment split. Source income and components are retained in stage_deciles.csv; source-only taxes are unknown, not assumed zero. |
| Synthetic population | Retained Validated Income gives the sampled pre-reconciliation target. Sampling/count rounding produces a small distribution change, not the large final tail. |
| Pension/transfer fit | `hfcs_synthetic_population.py:705-723` merges private pensions into public-transfer weights, zeros the separate pension line, regresses normalized shares on Income/Debt, truncates and rescales to the public budget. This replaces the source joint pattern and conflates funding concepts. The retained output is measurable; pre-fit source IDs/normalized inputs were not retained. |
| Job matching and payroll | Initial jobs are on the retained European member/industry skeleton. Option-B residual reconciliation can assign wages to non-employed members; per-employer renormalization subsequently removes those wages and pins each firm's bill. `reconcile_labour_income` and `renormalise_labour_income_to_firms` are the relevant methods. Existing industry/household support can prevent a desired national income allocation even when aggregate payroll is exact. |
| Financial-income proxy / D2 | The initial proxy is proportional to financial assets. D2 replaces it with funded mixed/dividend/corporate transfers, formerly allocated by business/equity/pension **stocks**, not CIS receipt incidence. Exact instantiated pre/post-D2 snapshots are in t0_stage_probe.csv. |
| Final t0 / subsequent regular benefits | Model wage cash is after PIT/employee SSC; compare with CIS through the bridge above. The accepted baseline's EqualSocialTransfersSetter also flattens expected regular benefits from Q1; the candidate preserves its source-defined initial transfer weights. |

A controlled reconstruction checked whether original adapter decile labels could be recovered from the retained Validated Income. Only34-46% of records have an unambiguous source label (`stage_reconstruction_coverage.csv`); no complete region can be exactly replayed from those labels. **No historical intermediate tax/wage/transfer distributions are fabricated.** The requested first-break diagnostic is identified, but a complete numerical historical pipeline decomposition requires a fresh traceable build retaining original household/member/donor IDs. Source and retained endpoint tables should not be mistaken for such an archive. The proposed forward repair must retain that provenance.

## 2. One allocation candidate, then stop at failure

The candidate uses CIS household donors within employment/business-support cells, regionally where available, with a stable income-rank match and documented fallbacks. It uses wages, self-employment, investment, public transfers and private pensions as **allocation weights**, never as extra household cash. Each existing employer's net wage bill is conserved, and the sum of labour inputs within each firm is conserved. Regional public-transfer and initial financial-income totals remain exact. D2 receipt weights are source-based rather than wealth-based; funded totals and counterparties remain unchanged. No per-decile top-up, residual income payment or tuned multiplier is used. It preserves current jobs/support rather than inventing new jobs or changing balance sheets. Unsupported donor/payroll fallbacks are recorded.

The source-defined public-transfer shares are stored in the new input, used at initialization and from Q1, and survive reset. Source inputs lacking those columns retain their old functions. The data-specific code is an unaccepted candidate path; defaults and F_CFC accepted inputs are unchanged.

HI-G2 decile shares and relative deviations, all in%:

| decile | HI_baseline_audit | HI_cis_gate | CIS | baseline_gap_pct | candidate_gap_pct |
| --- | --- | --- | --- | --- | --- |
| 1 | 1.322 | 1.505 | 1.735 | -23.802 | -13.285 |
| 2 | 2.078 | 2.891 | 3.552 | -41.486 | -18.606 |
| 3 | 3.007 | 4.058 | 4.882 | -38.406 | -16.882 |
| 4 | 4.154 | 5.230 | 6.188 | -32.871 | -15.486 |
| 5 | 5.603 | 6.566 | 7.615 | -26.415 | -13.772 |
| 6 | 7.422 | 8.106 | 9.172 | -19.084 | -11.630 |
| 7 | 9.744 | 10.075 | 10.942 | -10.949 | -7.922 |
| 8 | 12.975 | 12.759 | 13.237 | -1.982 | -3.611 |
| 9 | 18.064 | 17.056 | 16.466 | 9.708 | 3.583 |
| 10 | 35.630 | 31.754 | 26.210 | 35.939 | 21.153 |

Per-household levels, CAD/year (national model budgets are fixed, so this is a reported comparison, not a second fitted target):

| arm | decile | per_HH | CIS_per_HH |
| --- | --- | --- | --- |
| HI_baseline_audit | 1 | 13005.654 | 16246.698 |
| HI_baseline_audit | 2 | 20435.159 | 33239.195 |
| HI_baseline_audit | 3 | 29574.786 | 45702.749 |
| HI_baseline_audit | 4 | 40818.233 | 57920.504 |
| HI_baseline_audit | 5 | 55126.647 | 71299.708 |
| HI_baseline_audit | 6 | 72947.378 | 85829.552 |
| HI_baseline_audit | 7 | 95816.538 | 102492.973 |
| HI_baseline_audit | 8 | 127609.562 | 123836.989 |
| HI_baseline_audit | 9 | 177527.497 | 154254.901 |
| HI_baseline_audit | 10 | 350324.495 | 245113.724 |
| HI_cis_gate | 1 | 14801.639 | 16246.698 |
| HI_cis_gate | 2 | 28415.674 | 33239.195 |
| HI_cis_gate | 3 | 39910.346 | 45702.749 |
| HI_cis_gate | 4 | 51408.332 | 57920.504 |
| HI_cis_gate | 5 | 64582.539 | 71299.708 |
| HI_cis_gate | 6 | 79714.730 | 85829.552 |
| HI_cis_gate | 7 | 99036.451 | 102492.973 |
| HI_cis_gate | 8 | 125477.146 | 123836.989 |
| HI_cis_gate | 9 | 167703.039 | 154254.901 |
| HI_cis_gate | 10 | 312066.141 | 245113.724 |

HI-G3 public transfer comparison (% and percentage points):

| decile | model_gov_share | CIS_gov_share | gov_share_gap | model_recipient_share | CIS_recipient_share |
| --- | --- | --- | --- | --- | --- |
| 1 | 5.922 | 8.316 | -28.793 | 95.533 | 95.388 |
| 2 | 9.802 | 10.989 | -10.804 | 98.320 | 98.092 |
| 3 | 11.598 | 11.603 | -0.043 | 98.190 | 97.152 |
| 4 | 11.525 | 11.188 | 3.016 | 97.546 | 96.415 |
| 5 | 11.939 | 11.202 | 6.583 | 97.155 | 96.802 |
| 6 | 11.477 | 11.005 | 4.291 | 96.251 | 95.974 |
| 7 | 11.447 | 10.926 | 4.769 | 97.221 | 96.642 |
| 8 | 10.305 | 9.391 | 9.725 | 96.635 | 96.006 |
| 9 | 8.803 | 8.430 | 4.424 | 95.409 | 96.283 |
| 10 | 7.183 | 6.950 | 3.344 | 93.965 | 94.129 |

Using HI-G2's10% relative share tolerance for component amounts, the bottom transfer share fails by28.793%. Recipient incidence is within1.131pp. Gross-source reallocation under a flat model PIT and the old household/member/job/industry support does not reproduce CIS after-tax household shares. National budget conservation is necessary but not sufficient. No weights, taxes, household data or parameters were adjusted after this gate measurement.

The original2Q output's taxes column is wage PIT only. `CIS_t0_gate_comparison.csv` additionally reports expected PIT on net mixed, investment/rental and corporate/private-pension receipts at the unchanged model rate. It is a benchmark decomposition, not a new booked tax. CIS private pension income is kept separate from public transfers; employer/pension/SNA imputations are not paid as cash.

HI-G4: all existing household balance-sheet columns, bank data and firm financial stocks remain exact in the candidate build; deposit/mortgage/net-worth totals and per-record LTVs do not move. Two-quarter accounting max relative errors are4.07e-15 baseline and4.99e-15 candidate, below1e-8. New income ranks can change joint income/wealth shares; these are reported below rather than reweighting SFS assets or claiming that unchanged marginal stocks guarantee a new joint fit. SFS/DHEA income-quintile wealth benchmarks have their own income-ranking scope; compare after matching that scope, not by relabeling CIS ranks.

| quintile | deposits | mortgages | net_worth | net_worth_share | arm |
| --- | --- | --- | --- | --- | --- |
| 1 | 189698533275.490 | 77574068193.126 | 1226143079585.119 | 0.080 | HI_baseline_audit |
| 2 | 330860216765.236 | 215440451157.590 | 2201777042512.612 | 0.144 | HI_baseline_audit |
| 3 | 367916762574.404 | 307017693394.995 | 2403072051728.126 | 0.157 | HI_baseline_audit |
| 4 | 440337998989.959 | 547480206636.877 | 3253180060732.312 | 0.212 | HI_baseline_audit |
| 5 | 706954943986.211 | 992716133551.212 | 6240945537563.613 | 0.407 | HI_baseline_audit |
| 1 | 289787787374.907 | 113046274352.279 | 1608468883534.633 | 0.105 | HI_cis_gate |
| 2 | 329650112419.896 | 213859783135.433 | 2130264637893.104 | 0.139 | HI_cis_gate |
| 3 | 394876562895.617 | 335432576107.559 | 2676600107517.230 | 0.175 | HI_cis_gate |
| 4 | 430662227601.411 | 524101783287.455 | 3302717387426.127 | 0.216 | HI_cis_gate |
| 5 | 590791765299.469 | 953788136051.074 | 5607066755750.688 | 0.366 | HI_cis_gate |

Read-only F_CFC **planned** consumption at t0 (VAT and actual rent, narrow D1 offset; before D rationing/market clearing), persistent planned C>cash DI and initial inability to cover senior service from deposits/receipts/liquid non-pension assets:

| arm | persistent_planned_dissaver_pct | unable_t0_pct | income | cash_DI | planned_C |
| --- | --- | --- | --- | --- | --- |
| CIS_candidate | 70.100 | 0.349 | 1523.778 | 1468.386 | 1555.905 |
| F_CFC | 71.941 | 0.349 | 1523.778 | 1468.386 | 1564.269 |

| arm | scheme | quintile | planned_share | historical_share |
| --- | --- | --- | --- | --- |
| F_CFC | DHEA | 1 | 6.548 | 4.109 |
| F_CFC | DHEA | 2 | 8.460 | 7.550 |
| F_CFC | DHEA | 3 | 13.488 | 13.008 |
| F_CFC | DHEA | 4 | 22.629 | 21.719 |
| F_CFC | DHEA | 5 | 48.876 | 53.614 |
| F_CFC | SHS | 1 | 5.759 | 3.527 |
| F_CFC | SHS | 2 | 7.905 | 6.706 |
| F_CFC | SHS | 3 | 12.815 | 12.349 |
| F_CFC | SHS | 4 | 22.067 | 21.294 |
| F_CFC | SHS | 5 | 51.454 | 56.124 |
| CIS_candidate | DHEA | 1 | 7.219 | 5.314 |
| CIS_candidate | DHEA | 2 | 11.021 | 9.176 |
| CIS_candidate | DHEA | 3 | 15.445 | 13.640 |
| CIS_candidate | DHEA | 4 | 22.438 | 20.962 |
| CIS_candidate | DHEA | 5 | 43.878 | 50.908 |
| CIS_candidate | SHS | 1 | 6.340 | 4.076 |
| CIS_candidate | SHS | 2 | 9.925 | 7.415 |
| CIS_candidate | SHS | 3 | 14.566 | 12.430 |
| CIS_candidate | SHS | 4 | 22.258 | 20.892 |
| CIS_candidate | SHS | 5 | 46.911 | 55.187 |

DHEA ranking uses household-weighted OECD-modified equivalised cash DI, with the existing cash/SNA limitation; SHS uses unequivalised gross household-income quintiles. Planned shares are distinct from the inherited historical t0 consumption field, which predates propensity recalibration. The persistent-planned-dissaver measure holds initial income and the rule fixed; it is not a longitudinal observation. The unable-at-t0 measure includes scheduled principal, interest and rent, and draws on liquid non-pension assets. Owner-imputed housing cannot be separately removed from the model's L bundle; it tends to raise upper-quintile national-account consumption shares relative to SHS. No buffer-stock rule or consumption-propensity distribution was fitted here.

## 3. Independent observed GFCF allocation

Source StatCan36-10-0096-01, nominal2022 non-residential Investment. Direct Canada vector **v90968052**,411.341B/year. Government investment/CFC **v90970252/v90970282**, NPISH **v90970012/v90970042**, all-industry CFC **v90968082**. Scope totals are government98.480B, NPISH1.519B, business residual311.342B, with observed total CFC377.319B and net investment34.022B. Existing CFC source concordance and fixed within-industry output shares are used; no lambda/gamma or investment dynamics change.

The raw concordance yields412.999B/year. Eight small model-industry cells have no purchase bundle or capital stock supporting a capital-good composition. They are explicitly unallocated rather than inventing a basket; total missing **1.284M/year**. The resulting unaccepted input purchases412.998B/year, **0.403%** above the direct Canada total (national0.5% gate passes). Financial stocks, banks, household data and installed capital are unchanged. All initial purchases are flows only, not a new stock or executed transfer.

For the requested mapped-source-group criterion, actual model allocations are attributed back to their source contributors using the fixed concordance proportions. Four source groups fail2%; maximum error7.931%. The100% error of an unsupported tiny individual model-industry cell is a separate support diagnostic, not a substituted definition of the source-group gate.

Mapped source-group failures, amounts in M/quarter and error in%:

| region | source_group | allocated_observed_investment | actual_group_component | relative_error |
| --- | --- | --- | --- | --- |
| CAN_NB | Chemical manufacturing | 2.250 | 2.138 | -4.986 |
| CAN_NL | Chemical manufacturing | 2.000 | 1.841 | -7.931 |
| CAN_PE | Primary metal manufacturing | 0.019 | 0.017 | -6.346 |
| CAN_SK | Transportation equipment manufacturing | 0.750 | 0.721 | -3.893 |

Before/after initial firm purchases and net investment, B/year, by industry (province detail and all vectors/fallbacks retained in the companion files):

| industry | old_investment | new_investment | observed_allocation | unallocated | CFC | old_net | new_net | change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | 12.820 | 9.480 | 9.480 | 0.000 | 9.080 | 3.740 | 0.400 | -3.340 |
| A02 | 4.702 | 0.668 | 0.668 | 0.000 | 0.559 | 4.143 | 0.109 | -4.034 |
| A03 | 1.491 | 0.167 | 0.167 | 0.000 | 0.203 | 1.288 | -0.036 | -1.324 |
| B05 | 3.266 | 1.442 | 1.442 | 0.000 | 1.258 | 2.008 | 0.184 | -1.825 |
| B06 | 8.434 | 39.688 | 39.688 | 0.000 | 50.053 | -41.619 | -10.365 | 31.254 |
| B07 | 9.951 | 10.212 | 10.212 | 0.000 | 7.669 | 2.282 | 2.543 | 0.261 |
| B08 | 4.021 | 4.004 | 4.004 | 0.000 | 4.561 | -0.540 | -0.557 | -0.016 |
| B09 | 5.102 | 4.559 | 4.559 | 0.000 | 4.042 | 1.060 | 0.517 | -0.543 |
| C10T12 | 11.240 | 4.729 | 4.729 | 0.000 | 4.347 | 6.893 | 0.382 | -6.511 |
| C13T15 | 2.545 | 0.232 | 0.232 | 0.000 | 0.278 | 2.267 | -0.046 | -2.313 |
| C16 | 6.360 | 1.549 | 1.549 | 0.000 | 1.495 | 4.865 | 0.054 | -4.811 |
| C17_18 | 5.824 | 1.580 | 1.580 | 0.000 | 1.985 | 3.839 | -0.405 | -4.244 |
| C19 | 7.551 | 2.251 | 2.251 | 0.000 | 2.134 | 5.417 | 0.117 | -5.300 |
| C20 | 6.717 | 4.278 | 4.278 | 0.000 | 3.546 | 3.171 | 0.732 | -2.439 |
| C21 | 3.648 | 1.079 | 1.080 | 0.001 | 1.096 | 2.553 | -0.017 | -2.570 |
| C22 | 4.731 | 1.360 | 1.360 | 0.000 | 1.215 | 3.516 | 0.145 | -3.371 |
| C23 | 5.251 | 0.789 | 0.789 | 0.000 | 0.962 | 4.289 | -0.173 | -4.462 |
| C24A | 1.775 | 0.858 | 0.858 | 0.000 | 0.746 | 1.029 | 0.112 | -0.917 |
| C24B | 3.431 | 2.578 | 2.578 | 0.000 | 2.527 | 0.904 | 0.050 | -0.854 |
| C25 | 4.705 | 1.391 | 1.391 | 0.000 | 1.348 | 3.357 | 0.043 | -3.314 |
| C26 | 3.831 | 1.355 | 1.355 | 0.000 | 1.485 | 2.346 | -0.130 | -2.476 |
| C27 | 3.373 | 1.129 | 1.129 | 0.000 | 0.692 | 2.681 | 0.437 | -2.244 |
| C28 | 4.304 | 1.657 | 1.657 | 0.000 | 1.592 | 2.712 | 0.065 | -2.647 |
| C29 | 3.098 | 4.104 | 4.104 | 0.000 | 4.044 | -0.946 | 0.060 | 1.006 |
| C301 | 1.069 | 0.114 | 0.114 | 0.000 | 0.126 | 0.943 | -0.011 | -0.955 |
| C302T309 | 3.034 | 1.959 | 1.959 | 0.000 | 1.817 | 1.217 | 0.141 | -1.076 |
| C31T33 | 3.938 | 1.045 | 1.045 | 0.000 | 0.925 | 3.013 | 0.120 | -2.893 |
| D | 22.439 | 24.456 | 24.456 | 0.000 | 23.792 | -1.353 | 0.664 | 2.017 |
| E | 7.637 | 7.344 | 7.344 | 0.000 | 6.660 | 0.977 | 0.684 | -0.293 |
| F | 4.518 | 10.095 | 10.095 | 0.000 | 8.390 | -3.872 | 1.705 | 5.577 |
| G | 9.951 | 23.267 | 23.267 | 0.000 | 21.690 | -11.739 | 1.577 | 13.316 |
| H49 | 7.740 | 29.786 | 29.786 | 0.000 | 19.228 | -11.488 | 10.558 | 22.046 |
| H50 | 2.125 | 1.352 | 1.352 | 0.000 | 0.748 | 1.377 | 0.604 | -0.773 |
| H51 | 7.956 | 5.854 | 5.854 | 0.000 | 3.655 | 4.302 | 2.200 | -2.102 |
| H52 | 6.001 | 12.983 | 12.983 | 0.000 | 7.751 | -1.750 | 5.232 | 6.982 |
| H53 | 13.181 | 5.194 | 5.194 | 0.000 | 3.420 | 9.760 | 1.773 | -7.987 |
| I | 49.391 | 4.360 | 4.360 | 0.000 | 4.877 | 44.514 | -0.517 | -45.031 |
| J58T60 | 4.609 | 5.829 | 5.829 | 0.000 | 4.929 | -0.320 | 0.900 | 1.220 |
| J61 | 15.492 | 7.867 | 7.867 | 0.000 | 6.771 | 8.721 | 1.097 | -7.625 |
| J62_63 | 4.542 | 18.697 | 18.697 | 0.000 | 15.698 | -11.156 | 2.999 | 14.155 |
| K | 9.872 | 12.159 | 12.159 | 0.000 | 12.586 | -2.714 | -0.427 | 2.287 |
| L | 7.162 | 13.067 | 13.067 | 0.000 | 12.101 | -4.940 | 0.966 | 5.905 |
| M | 5.465 | 9.192 | 9.192 | 0.000 | 7.547 | -2.082 | 1.646 | 3.727 |
| N | 23.373 | 7.844 | 7.844 | 0.000 | 7.281 | 16.092 | 0.563 | -15.529 |
| O | 7.065 | 59.277 | 59.277 | 0.000 | 57.248 | -50.183 | 2.029 | 52.212 |
| P | 5.042 | 28.286 | 28.286 | 0.000 | 25.508 | -20.466 | 2.778 | 23.244 |
| Q | 16.976 | 16.151 | 16.151 | 0.000 | 12.792 | 4.185 | 3.359 | -0.826 |
| R | 17.500 | 4.103 | 4.103 | 0.000 | 3.221 | 14.279 | 0.883 | -13.397 |
| S | 12.029 | 1.577 | 1.577 | 0.000 | 1.567 | 10.463 | 0.010 | -10.453 |
| T | 2.606 | 0.000 | 0.000 | 0.000 | 0.000 | 2.606 | 0.000 | -2.606 |

**All13 unchanged GDP initialization checks fail**. Production/income stocks were preserved, but changing the final-demand investment flow alone changes expenditure GDP. Regional gaps do not cancel into a valid SUT. National expenditure exceeds output by3.527960B/quarter. No trade, inventory, taxes, household cash or government plug was added. Since construction fails, the new GFCF input is not iterated and has no simulated accounting-battery pass claim.

| region | passed | expenditure_gap | income_gap |
| --- | --- | --- | --- |
| CAN_NL | False | 538412535.500 | 0.000 |
| CAN_PE | False | -11394781.494 | 0.000 |
| CAN_NS | False | -83415973.016 | 0.000 |
| CAN_NB | False | 82987373.445 | -0.000 |
| CAN_QC | False | 273846304.945 | -0.000 |
| CAN_ON | False | -2699070705.763 | 0.000 |
| CAN_MB | False | -105714224.524 | 0.000 |
| CAN_SK | False | 351952839.218 | 0.000 |
| CAN_AB | False | 4078150324.797 | -0.000 |
| CAN_BC | False | 852721547.958 | 0.000 |
| CAN_YT | False | 59316372.246 | 0.000 |
| CAN_NT | False | 77539307.778 | 0.000 |
| CAN_NU | False | 112629459.516 | 0.000 |

A balanced-SUT handoff was announced by the user during this round: `feature/sut-balance`, compatibility/compat_icio_2022_can_provinces.csv, hash prefix41590fdb, HANDOFF_TO_VALIDATION_2026-10-25.md. It was **not read, verified or adopted** here. The user reports imported re-exports and intermediate-product-tax valuation corrections. Its full hash, accounts and interaction with observed GFCF must be checked in the separately named later build step; this round remains on F_CFC. No change to macroabm-io2022 was made.

## 4. Dependent remeasurement is gated off

Neither household nor GFCF input passes adoption. Therefore there is no combined build, no corrected-start12Q F_CFC or E2 simulation, and no new E2 benchmark gate. This follows the dependency rule and does not abandon independent work. No parameter was tuned to obtain a run.

Only the seed-0 two-quarter gate diagnostics exist; B/quarter and percentages:

| arm | quarter | gdp | consumption | cash_DI | cash_saving_rate | constrained_share | investment | household_writeoffs | firm_loan_losses | overdraft_losses | bank_losses | recapitalisation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HI_baseline_audit | 1 | 700.259 | 378.377 | 371.908 | -1.739 | 18.631 | 51.518 | 76.936 | 0.000 | 0.000 | 76.936 | 0.693 |
| HI_baseline_audit | 2 | 692.427 | 370.049 | 366.528 | -0.961 | 24.758 | 46.267 | 50.451 | 0.000 | 0.000 | 50.451 | 0.000 |
| HI_cis_gate | 1 | 700.327 | 379.692 | 371.909 | -2.093 | 18.417 | 51.681 | 81.503 | 0.000 | 0.000 | 81.503 | 0.000 |
| HI_cis_gate | 2 | 692.372 | 369.508 | 366.429 | -0.840 | 24.743 | 46.570 | 56.993 | 0.000 | 0.000 | 56.993 | 0.679 |

These are short unaccepted diagnostics, **not** evidence that the12-quarter demand spiral eases. Existing IH all-seed contractions remain the historical reference, not rerun results:

| arm | seed | Q0_Q12_pct | Q1_Q12_pct |
| --- | --- | --- | --- |
| E2 | 0 | -4.452 | -3.384 |
| E2 | 1 | -1.411 | -2.370 |
| E2 | 2 | -10.130 | -8.687 |
| F_CFC | 0 | -7.594 | -6.562 |
| F_CFC | 1 | -8.907 | -9.794 |
| F_CFC | 2 | -17.400 | -16.074 |

Historical IH E2 gate (unchanged comparison bands and scope caveats; not retested on a new start):

| seed | annual_HH_writeoff_pct | Q12_60plus_pct | Q12_90plus_pct | passed |
| --- | --- | --- | --- | --- |
| 0 | 1.051 | 1.304 | 1.286 | False |
| 1 | 0.998 | 1.270 | 1.251 | False |
| 2 | 1.074 | 1.523 | 1.505 | False |

The historical GDP decomposition, constrained-share paths, employment, firm/household investment and bank-loss components remain in outputs/IH. New2Q equivalents are in this round's raw headline/outcomes/investment ledgers; there is no extrapolation to Q12. Neither a new employment trajectory, new SHS/DHEA Q12 shares, nor a reduction in recapitalisations is claimed without a passing start and all three seeds.

## 5. Tests, remaining decisions and recommendation

Full tests via run_pre_D3_tests.py: **488 passed, 30 known failures, 518 cases; 1376.5s; sampler one worker**. The audit compares exact failure IDs with IH's known30 Nan in transactor_total_real_supply cases; extras must be reported if present. No simulations overlap: baseline2Q, candidate2Q, then one-worker sampler; later t0 plan probes do not iterate. Input/benchmark/stock hashes, stage limitations and exclusions are in audit.json and provenance files. Report date is UTC.

Do not promote either candidate. Income support, matching and tax/benefit allocation must be reconciled jointly using CIS household/member source records; reconstructing cash receipts from wealth stocks or relying on a residual wage reconciliation is insufficient. A subsequent candidate should retain donor/member IDs and intermediate stage snapshots and reconcile source after-tax allocation with per-employer budgets/structural zeros. Flat-tax compression and the difference between public benefits and private pensions need explicit treatment; they are not to be concealed with decile payments.

Adopt the balanced SUT later in its dedicated build and retest GFCF scope, capital-good support and all regional GDP checks. Only then choose an expansion specification. A growth/expectations-consistent desired-capital term must use an uncensored demand signal and confront F-S1/F-S3's fully utilised/capacity-capped signal; merely raising an accelerator weight under that lock is not a demonstrated solution. No expansion term was added.

Keep the buffer-stock option deferred: it may change heterogeneity in dissaving, but it cannot validate an incorrect income allocation or balance the SUT. Phase B and C_dp_005 remain on hold. Stop for review.
