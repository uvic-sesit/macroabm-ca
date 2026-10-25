"""HI report: record failed adoption gates and complete independent evidence."""
from pathlib import Path
import json
import numpy as np,pandas as pd
from report_ih import table
HERE=Path(__file__).resolve().parent;OUT=HERE/'outputs/HI';DATE='2026-10-25'
def main():
    gates=json.loads((OUT/'gates.json').read_text());comparison=pd.read_csv(OUT/'CIS_t0_gate_comparison.csv');national=pd.read_csv(OUT/'CIS_national_comparison.csv');stages=pd.read_csv(OUT/'stage_deciles.csv');gdp=pd.read_csv(OUT/'gfcf_GDP_initialization.csv');inv=pd.read_csv(OUT/'investment_industry_annual_B.csv');groups=pd.read_csv(OUT/'gfcf_mapped_group_check.csv');q=pd.read_csv(OUT/'two_quarter_outcomes.csv');wealth=pd.read_csv(OUT/'balance_sheets_by_CIS_income_quintile.csv')
    pivot=comparison.pivot(index='decile',columns='arm',values='share').reset_index();pivot['CIS']=comparison[comparison.arm=='HI_cis_gate'].CIS_share.to_numpy();pivot['baseline_gap_pct']=100*(pivot.HI_baseline_audit/pivot.CIS-1);pivot['candidate_gap_pct']=100*(pivot.HI_cis_gate/pivot.CIS-1);pivot[['HI_baseline_audit','HI_cis_gate','CIS']]*=100
    levels=comparison[['arm','decile','per_HH','CIS_per_HH']]
    transfers=comparison[comparison.arm=='HI_cis_gate'][['decile','model_gov_share','CIS_gov_share','gov_share_gap','model_recipient_share','CIS_recipient_share']].copy();transfers.iloc[:,1:]*=100
    source=stages[['stage','decile','share','per_HH']].copy();source['share']*=100
    # Historical DHEA cash/SNA bridge remains an account reference, never a cash target.
    bridge=pd.read_csv(HERE/'outputs/IH/DHEA_national_cash_bridge_B.csv')
    outcomes=q[['arm','quarter','gdp','consumption','cash_DI','cash_saving_rate','constrained_share','investment','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation']].copy()
    for k in ['gdp','consumption','cash_DI','investment','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation']:outcomes[k]/=1e9
    outcomes[['cash_saving_rate','constrained_share']]*=100
    history=pd.read_csv(HERE/'outputs/IH/changes.csv');history=history[(history.metric=='gdp')&history.arm.isin(['F_CFC','E2'])][['arm','seed','Q0_Q12_pct','Q1_Q12_pct']]
    e2=pd.read_csv(HERE/'outputs/IH/gates.csv');e2=e2[(e2.arm=='E2')&(e2.gate=='E-G1')][['seed','value','Q12_60plus_pct','Q12_90plus_pct','passed']].rename(columns={'value':'annual_HH_writeoff_pct'})
    planned=OUT/'t0_stage_probe.csv';hasplan=planned.exists();plantext='Pending read-only t0 plan probe; final report must not retain this placeholder.'
    if hasplan:
        plan=pd.read_csv(planned);c=pd.read_csv(OUT/'t0_consumption_distribution.csv');a=plan[plan.stage=='after_D2_funded_plan'].groupby('arm')[['weight','persistent','unable','income','cash_DI','planned_C']].sum().reset_index();a['persistent_planned_dissaver_pct']=100*a.persistent/a.weight;a['unable_t0_pct']=100*a.unable/a.weight;a[['income','cash_DI','planned_C']]/=1e9
        cc=c[c.funded].copy();cc[['planned_share','historical_share']]*=100;plantext=table(a[['arm','persistent_planned_dissaver_pct','unable_t0_pct','income','cash_DI','planned_C']])+'\n\n'+table(cc[['arm','scheme','quintile','planned_share','historical_share']])
        a.to_csv(OUT/'t0_plan_summary.csv',index=False)
        post=plan[['arm','stage','decile','income','wages','self_employment','investment','private_pensions','government_transfers','financial_proxy','share','per_HH']].copy();post.to_csv(OUT/'instantiation_stage_components.csv',index=False)
    testfile=OUT/'verification/full_test_execution.json';tests=json.loads(testfile.read_text()) if testfile.exists() else None
    testtext=f"{tests['passed']} passed, {len(tests['failures'])} known failures, {tests['tests']} cases; {tests['seconds']:.1f}s; sampler one worker" if tests else 'Pending full suite; final report must not retain this placeholder.'
    failuregroups=groups[groups.relative_error.abs()>.02].copy();failuregroups[['allocated_observed_investment','actual_group_component']]/=1e6;failuregroups.relative_error*=100
    report=f'''# Household closure HI round - {DATE} UTC

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

{table(bridge)}

STiK belongs to adjusted DI and is not added as cash. DHEA remains a reference, not the household distribution target.

## 1. Stage-by-stage allocation audit

Actual source/retained snapshots (shares in%, per-household nominal CAD/year):

{table(source)}

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

{table(pivot)}

Per-household levels, CAD/year (national model budgets are fixed, so this is a reported comparison, not a second fitted target):

{table(levels)}

HI-G3 public transfer comparison (% and percentage points):

{table(transfers)}

Using HI-G2's10% relative share tolerance for component amounts, the bottom transfer share fails by28.793%. Recipient incidence is within1.131pp. Gross-source reallocation under a flat model PIT and the old household/member/job/industry support does not reproduce CIS after-tax household shares. National budget conservation is necessary but not sufficient. No weights, taxes, household data or parameters were adjusted after this gate measurement.

The original2Q output's taxes column is wage PIT only. `CIS_t0_gate_comparison.csv` additionally reports expected PIT on net mixed, investment/rental and corporate/private-pension receipts at the unchanged model rate. It is a benchmark decomposition, not a new booked tax. CIS private pension income is kept separate from public transfers; employer/pension/SNA imputations are not paid as cash.

HI-G4: all existing household balance-sheet columns, bank data and firm financial stocks remain exact in the candidate build; deposit/mortgage/net-worth totals and per-record LTVs do not move. Two-quarter accounting max relative errors are4.07e-15 baseline and4.99e-15 candidate, below1e-8. New income ranks can change joint income/wealth shares; these are reported below rather than reweighting SFS assets or claiming that unchanged marginal stocks guarantee a new joint fit. SFS/DHEA income-quintile wealth benchmarks have their own income-ranking scope; compare after matching that scope, not by relabeling CIS ranks.

{table(wealth)}

Read-only F_CFC **planned** consumption at t0 (VAT and actual rent, narrow D1 offset; before D rationing/market clearing), persistent planned C>cash DI and initial inability to cover senior service from deposits/receipts/liquid non-pension assets:

{plantext}

DHEA ranking uses household-weighted OECD-modified equivalised cash DI, with the existing cash/SNA limitation; SHS uses unequivalised gross household-income quintiles. Planned shares are distinct from the inherited historical t0 consumption field, which predates propensity recalibration. The persistent-planned-dissaver measure holds initial income and the rule fixed; it is not a longitudinal observation. The unable-at-t0 measure includes scheduled principal, interest and rent, and draws on liquid non-pension assets. Owner-imputed housing cannot be separately removed from the model's L bundle; it tends to raise upper-quintile national-account consumption shares relative to SHS. No buffer-stock rule or consumption-propensity distribution was fitted here.

## 3. Independent observed GFCF allocation

Source StatCan36-10-0096-01, nominal2022 non-residential Investment. Direct Canada vector **v90968052**,411.341B/year. Government investment/CFC **v90970252/v90970282**, NPISH **v90970012/v90970042**, all-industry CFC **v90968082**. Scope totals are government98.480B, NPISH1.519B, business residual311.342B, with observed total CFC377.319B and net investment34.022B. Existing CFC source concordance and fixed within-industry output shares are used; no lambda/gamma or investment dynamics change.

The raw concordance yields412.999B/year. Eight small model-industry cells have no purchase bundle or capital stock supporting a capital-good composition. They are explicitly unallocated rather than inventing a basket; total missing **1.284M/year**. The resulting unaccepted input purchases412.998B/year, **0.403%** above the direct Canada total (national0.5% gate passes). Financial stocks, banks, household data and installed capital are unchanged. All initial purchases are flows only, not a new stock or executed transfer.

For the requested mapped-source-group criterion, actual model allocations are attributed back to their source contributors using the fixed concordance proportions. Four source groups fail2%; maximum error7.931%. The100% error of an unsupported tiny individual model-industry cell is a separate support diagnostic, not a substituted definition of the source-group gate.

Mapped source-group failures, amounts in M/quarter and error in%:

{table(failuregroups)}

Before/after initial firm purchases and net investment, B/year, by industry (province detail and all vectors/fallbacks retained in the companion files):

{table(inv)}

**All13 unchanged GDP initialization checks fail**. Production/income stocks were preserved, but changing the final-demand investment flow alone changes expenditure GDP. Regional gaps do not cancel into a valid SUT. National expenditure exceeds output by3.527960B/quarter. No trade, inventory, taxes, household cash or government plug was added. Since construction fails, the new GFCF input is not iterated and has no simulated accounting-battery pass claim.

{table(gdp[['region','passed','expenditure_gap','income_gap']])}

A balanced-SUT handoff was announced by the user during this round: `feature/sut-balance`, compatibility/compat_icio_2022_can_provinces.csv, hash prefix41590fdb, HANDOFF_TO_VALIDATION_2026-10-25.md. It was **not read, verified or adopted** here. The user reports imported re-exports and intermediate-product-tax valuation corrections. Its full hash, accounts and interaction with observed GFCF must be checked in the separately named later build step; this round remains on F_CFC. No change to macroabm-io2022 was made.

## 4. Dependent remeasurement is gated off

Neither household nor GFCF input passes adoption. Therefore there is no combined build, no corrected-start12Q F_CFC or E2 simulation, and no new E2 benchmark gate. This follows the dependency rule and does not abandon independent work. No parameter was tuned to obtain a run.

Only the seed-0 two-quarter gate diagnostics exist; B/quarter and percentages:

{table(outcomes)}

These are short unaccepted diagnostics, **not** evidence that the12-quarter demand spiral eases. Existing IH all-seed contractions remain the historical reference, not rerun results:

{table(history)}

Historical IH E2 gate (unchanged comparison bands and scope caveats; not retested on a new start):

{table(e2)}

The historical GDP decomposition, constrained-share paths, employment, firm/household investment and bank-loss components remain in outputs/IH. New2Q equivalents are in this round's raw headline/outcomes/investment ledgers; there is no extrapolation to Q12. Neither a new employment trajectory, new SHS/DHEA Q12 shares, nor a reduction in recapitalisations is claimed without a passing start and all three seeds.

## 5. Tests, remaining decisions and recommendation

Full tests via run_pre_D3_tests.py: **{testtext}**. The audit compares exact failure IDs with IH's known30 Nan in transactor_total_real_supply cases; extras must be reported if present. No simulations overlap: baseline2Q, candidate2Q, then one-worker sampler; later t0 plan probes do not iterate. Input/benchmark/stock hashes, stage limitations and exclusions are in audit.json and provenance files. Report date is UTC.

Do not promote either candidate. Income support, matching and tax/benefit allocation must be reconciled jointly using CIS household/member source records; reconstructing cash receipts from wealth stocks or relying on a residual wage reconciliation is insufficient. A subsequent candidate should retain donor/member IDs and intermediate stage snapshots and reconcile source after-tax allocation with per-employer budgets/structural zeros. Flat-tax compression and the difference between public benefits and private pensions need explicit treatment; they are not to be concealed with decile payments.

Adopt the balanced SUT later in its dedicated build and retest GFCF scope, capital-good support and all regional GDP checks. Only then choose an expansion specification. A growth/expectations-consistent desired-capital term must use an uncensored demand signal and confront F-S1/F-S3's fully utilised/capacity-capped signal; merely raising an accelerator weight under that lock is not a demonstrated solution. No expansion term was added.

Keep the buffer-stock option deferred: it may change heterogeneity in dissaving, but it cannot validate an incorrect income allocation or balance the SUT. Phase B and C_dp_005 remain on hold. Stop for review.
'''
    (HERE/f'CLOSURE_HI_{DATE}.md').write_text(report,encoding='utf-8');print('HI report written; t0 probe:',hasplan,'full suite:',bool(tests))
if __name__=='__main__':main()
