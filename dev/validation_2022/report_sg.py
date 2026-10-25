"""SG review report: preserve failures, independent diagnostics and source scope."""
import json
import numpy as np,pandas as pd
from report_ih import table
from prepare_sg import HERE,OUT

def main():
    gates=json.loads((OUT/'step1_gates.json').read_text());source=json.loads((OUT/'source_audit.json').read_text());tax=pd.read_csv(OUT/'CIS_summary.csv');housing=pd.read_csv(OUT/'housing_summary.csv');house=pd.read_csv(OUT/'housing_by_decile_tenure.csv');concept=pd.read_csv(OUT/'CIS_concepts.csv');payout=pd.read_csv(OUT/'PIT_counterfactual_national.csv');rates=pd.read_csv(OUT/'CIS_effective_PIT.csv');compare=pd.read_csv(OUT/'compatibility_before_after.csv');region=pd.read_csv(OUT/'t0_by_region_annual_B.csv');industry=pd.read_csv(OUT/'t0_by_industry_annual_B.csv');prior=pd.read_csv(OUT/'prior_loss_industries_t0_change.csv');history=pd.read_csv(OUT/'IH_reference_only.csv');f=pd.read_csv(OUT/'FS_T_firm_bridge.csv')
    tf=OUT/'verification/full_test_execution.json';tests=json.loads(tf.read_text()) if tf.exists() else None
    testtext=f"{tests['passed']} passed, {len(tests['failures'])} failures, {tests['tests']} cases; sampler one worker" if tests else 'PENDING FULL SUITE'
    acfile=OUT/'short_accounting_execution.json';ac=json.loads(acfile.read_text()) if acfile.exists() else None
    actext=table(pd.DataFrame(ac)[['arm','exit_code','passed','max_accounting_error','seconds']]) if ac else 'PENDING SHORT ACCOUNTING DIAGNOSTICS'
    gateframe=pd.DataFrame([dict(arm=arm,**{k:g[k] for k in ['regional_initialization','independent_income','margin_exceptions','max_margin_gap_pp','above_price_exceptions','inherited_floor_exceptions','passed']}) for arm,g in gates.items()])
    gateframe['accounting_passed']=[gates[arm].get('accounting_passed',False) for arm in gateframe.arm]
    tiny=f[(f.margin_gap_pp.abs()>1)&~f.inherited_floor][['region','industry','new_output','margin_gap_pp']]
    housing_display=housing.copy();money=['C','DI','gap','imputed_memo','owner_L','memo_proxy','gap_after_memo_proxy','gap_after_all_owner_L_removed'];housing_display[money]/=1e9
    for k in ['C_dissaver_share','C_memo_proxy_dissaver_share','C_all_owner_L_removed_dissaver_share']:housing_display[k]*=100
    h=house.copy();h['gap']=h.C-h.DI;h['dissaver_pct']=100*h.C_dissavers/h.households;h['proxy_dissaver_pct']=100*h.C_memo_proxy_dissavers/h.households
    moneyh=['C','DI','gap','planned_L','imputed_memo','memo_proxy_removed'];h[moneyh]/=1e9
    sourcegdp=pd.concat([pd.read_csv(OUT/arm/'gfcf_GDP_initialization.csv').assign(arm=arm) for arm in ['FS','FS_T']]);sourcegdp[['output','expenditure','income']]/=1e9
    small=pd.DataFrame([dict(arm=arm,source_pickle=json.loads((OUT/f'{arm}_build_provenance.json').read_text())['new_pickle'].split('\\')[-1],sha256=json.loads((OUT/f'{arm}_build_provenance.json').read_text())['new_pickle_sha256']) for arm in ['FS','FS_T']])
    text=f'''# Closure SG review - 2026-10-25 UTC

Base `2cdf4d6`, branch `feature/validation-2022`. **Neither FS nor FS_T passes every gate: both also fail the short accounting attempt before Q1 completes. Do not promote either input. F_CFC remains the accepted diagnostic baseline.** All independent source, housing and income-concept checks are completed. Step 2 and all dependent twelve-quarter runs are skipped. No gate threshold or behavioural parameter was changed to obtain a pass. No push, Phase B, C_dp_005, investment expansion or new household allocation build.

## Steps, commits and gates

| Step | Commit / verification | Finding / decision |
|---|---|---|
| Independent GDP income assertion | `2ef7a32`; two focused regressions | Fixes the duplicated output/expenditure assertion. Same np.isclose tolerance; genuinely checks output against income. |
| FS / FS_T source build | `1eadde5`; four source-unit/net-surplus regressions; frozen git inputs | Canonical SUT balances independently. Both arms pass all13 regional GDP identities. FS fails cost gate; FS_T removes above-price exceptions but retains floor/tiny-output margin exceptions. |
| Source bookkeeping audit | `dc68b37`; four focused regressions plus exact build assertions | Explicit VA6 stays unchanged; reader-implied VA falls. ROW import counterpart follows the export removal. Only v3 candidates are retained for gates; earlier v1/v2 pickles remain untouched and excluded. |
| Step2 FSG | No build / no run | Depends on a passing Step1 arm. Neither passes the full gate; no scope rescale or GFCF substitution attempted. |
| Step3 housing | Read-only t0 F_CFC and existing CIS candidate | SNA housing services enter cash goods demand; imputed income remains a noncash memo. Exact imputed-purchase attribution is unavailable in mixed sector L; bounds/proxy below. No closure change. |
| Step4 income concept | Read-only CIS PUMF, existing inputs | Candidate max error13.265% before tax,21.153% after tax; empirical progressive-tax diagnostic12.064%. Allocation and PIT both remain specification issues. |
| Step5 | Full suite / source-stock audit / report | {testtext}. Stop for review. |

Gate results by arm (max margin deviation is percentage points):

{table(gateframe)}

The unchanged output/expenditure assertion and the corrected income assertion are both exercised in each region. Cost failures are recorded even where they arise in numerically tiny sectors. No exclusion or tolerance change is used to pass an arm. Accounting is an independent short diagnostic, reported below; its success alone cannot override a cost failure.

New inputs, with SHA256 (accepted pickles unchanged):

{table(small)}

## 1. Source verification and t0 bridge

All IO reads use `git show feature/sut-balance:<file>` at **d847fb2e22fee298c7af31803d3ab6543126dda4**, not the working tree. Old comparison blobs are from479dcb4. Both handoff documents, source schema and all input hashes are cached in benchmarks/SG. The requested compatibility hash **41590fdb19d9eb79758169b51afc0751e6d5c19ce88183bb8fbe330889e689aa** is the CRLF byte representation. Git's LF blob has SHA256 **f0004ad3d40e465cceba3d9735d6dda5b00658fe6ca88af5ffed944917a8adb9**; converting only LF to CRLF reproduces the requested hash exactly. Both are recorded; no economic content changed.

Independent CSV identities, not copied pass flags:

- Imported re-exports excluded48.431914B/year, exactly matching the international-export reduction within1.1e-13B. Domestic margin services remain exported (0.661880B including CE; the handoff's approximately0.65B is the13-region scope). Imports in use do not change.
- The canonical output_basic correction is **+26.545927B**, exactly its previously omitted net product taxes on intermediate inputs. The new column already includes these taxes; applying the older FB helper's additional product-tax addend would count them twice. This build uses the reader/source IO sales, not that stale helper.
- Every Canadian region-industry canonical row equals its column: maximum error **{source['canonical_row_column_max_M']:.9f}M**. Production/income/expenditure GDP at basic prices agree regionally, maximum error **{source['canonical_GDP_max_gap_M']:.9f}M**. Recomputed from Z, FD and VA primitives, including CE.
- Observed VA components are byte-equivalent numerically;13-region basic-price GDP remains **2674.182570B**. Compatibility-view reader-implied VA is still **0.122411B below VA6**, the CE boundary; it is reported, not filled.

Compatibility before/after, annual B:

{table(compare)}

The explicit industry-vector VA6 field and the firm's residual implied VA are distinct. The former is unchanged, apart from preserved inherited empty-sector floors. The latter falls48.431914B as the fictitious sales disappear. This removes an inflated starting level; it is not evidence of a dynamic no-shock contraction improving. Canonical GDP staying unchanged and model reader-implied GDP falling are consistent statements about different starting accounts.

The new DataWrapper instances clone F_CFC to retain exactly its household/member/job records, employer payroll, deposits, loans, bank capital, installed capital, initial purchases and observed CFC. IO output/export deltas are applied through the50-code concordance, preserving the existing empty-sector floor amounts. Input-productivity and depreciation coefficients are re-expressed in the new output units so physical inputs and CFC amounts stay fixed. International sourcing weights and ROW import counterparts use the new source flow. No population is resampled, new household income created or financial stock rebuilt. Zero-source producers remain contract holders, not forgiven debtors.

FS retains producer-tax amounts. FS_T adds signed D29/D39, **100.503564B/year**, with corresponding government production-tax receipts, the legacy GDP valuation aggregate and corporate-tax/revenue changes. Corporate tax changes follow initial profits; they are not offset with a revenue plug. Exact fiscal deltas are in FS_T_fiscal_bridge.csv.

Province t0 accounts, annual B (explicit VA6 and residual implied VA shown separately):

{table(region[['arm','region','output_change','old_VA','new_VA','old_implied_VA','new_implied_VA','old_GOS','new_GOS','export_change']])}

Largest affected industries, FS_T annual B; full50-industry and650 region-industry tables are retained:

{table(industry[industry.arm=='FS_T'].sort_values('output_change').head(12)[['industry','output_change','old_implied_VA','new_implied_VA','old_GOS','new_GOS','export_change']])}

Earlier F_CFC loss industries, **historical seeds0-2 mean over12 quarters**, alongside FS_T t0 changes (B; not new loss outcomes):

{table(prior.head(12)[['industry_code','historic_loss_B','output_change','old_GOS','new_GOS']])}

The export correction most strongly reduces C29/C28/C26/C302T309/C21, whereas historical losses are concentrated in G/F and several manufacturing/services sectors. G/F output hardly changes; FS_T's signed producer taxes still change their margins. Utilities and other previously flagged revaluation losses cannot be declared cured from this static bridge.

### Unchanged regional GDP checks and net-surplus failures

GDP levels B/quarter; residuals CAD/quarter:

{table(sourcegdp[['arm','region','passed','output','expenditure','income','expenditure_gap','income_gap']])}

FS has244 margin exceptions and6 above-price/nonnegative-observed-NOS exceptions. FS_T has33 margin exceptions and **zero** above-price exceptions. Of its33,29 are inherited1M/year empty-sector floors with zero observed GOS. The other four are source-zero cells carrying only floating-point remnants (CAD/quarter):

{table(tiny)}

These are not economically large margin errors, but the stated universal gate still fails. On non-floor cells with more than1M/quarter output, FS_T's maximum error is {f[(~f.inherited_floor)&(f.new_output>1e6)].margin_gap_pp.abs().max():.6f}pp. That is an additional diagnostic, **not a replacement threshold**. A future decision must specify the accounting/holding treatment of source-zero producer records and their inherited floor output. No new basket, fictitious buyer, deleted debt, zero-sector override or threshold adjustment was introduced here.

The old FB expenditure bridge's74.883B/year imbalance is removed at the model initialization level: IO sales and exports now change together, and both regional GDP tests pass. Observed/source income still differs at the documented CE/floor boundaries. Thus the broad GDP bridge is repaired, but the full adoption gate is not passed.

### Short accounting gate

Two-quarter seed0 diagnostics only, run after the one-worker suite, one at a time. These do not authorize twelve-quarter runs:

{actext}

**Both fail before Q1 completes**, with `Household cash budget requires finite settled cash and senior payments`; the1e-8 accounting battery is not reached. These failures are separate from the30 known full-suite test failures. Two additional seed0 read-only failure replays preserve the same failure and do not change economic values.

The completed first-failure probe identifies **CAN_NL C21** (industry14): balanced-SUT output is zero after removal of6.694M/year of imported re-export sales. Its initial labour-productivity baseline becomes zero while the legacy job/contract holder remains. Runtime labour_productivity_factor, labour_productivity, labour_inputs and production become nonfinite; current employee income is nonfinite for one model individual at that firm, and the wages component of settled receipts is nonfinite for one model household. Other stored household income components and D2 plans remain finite. `labour_productivity.py:149` divides the production target by raw labour input times industry productivity without a zero-denominator branch; `firms.py:780-794` propagates that factor into labour and production. This is a zero-activity runtime boundary exposed by the data correction, not evidence that the household budget needs a higher limit. Exact aggregate traces are in first_nonfinite_budget_probe_complete.json. No cash replacement, positive productivity floor or producer restructuring is applied after failure. A defined zero-activity holder path/zero-over-zero convention, regression-tested with contracts preserved, is needed before another adoption attempt.

Exact traces and attempted commands are preserved. No failed run is labelled an accounting pass. Neither an accounting failure nor a cost failure is repaired by parameter tuning.

## 2. GFCF dependency

No FSG pickle or twelve-quarter run was created. A passing Step1 input is required. The future split must preserve the balanced IO product column and distinguish business, government, NPISH and residential/household GFCF;36-10-0096 supplies investing-industry shares, not a second incompatible regional total. The legacy reader also folds inventory change into fixed capital formation, which must be kept separate from a concept-matched gross-fixed-investment target. No full IO GFCF total is silently relabelled business investment here. Lambda/gamma and the expansion rule are unchanged.

## 3. Housing cash/SNA consistency - read-only

Code trace:

| Link | File:line | Consequence |
|---|---|---|
| Provincial L HFCE not reduced for imputed housing | macro_data/readers/default_readers.py:515 | Unlike the global ICIO path, paid and imputed housing services remain in L household IO demand. |
| Imputed-rent total and owner allocation | macro_data/processing/synthetic_country.py:314; macro_data/configuration/can_2022_constants.py:3 | Initial memo235.938B/year comes from36-10-0124 imputed housing; owners receive the memo, not a cash receipt. |
| SNA HFCE consumption calibration | macromodel/country/household_closure.py:378; macromodel/configurations/household_closure_configuration.py:50 | Consumption target1511.382B/year is36-10-0112 v62305982 and includes noncash services. |
| Goods demand, all sectors including L | macromodel/agents/households/households.py:673; macromodel/agents/households/func/consumption.py:184 | Income/propensity generates a goods basket without a separate owner-imputed-rent exclusion. D caps this basket as cash spending. |
| D1 narrow rent offset | macromodel/country/household_closure.py:12 | Removes only renters' L demand up to actual household-landlord rent, without removing all L or owner imputed housing. |
| Cash income and landlord receipts | macromodel/agents/households/households.py:532 and619 | Rental cash income is actual non-owner-occupied rent after PIT. Owner-imputed memo is absent from cash income. |
| Memo calculation | macromodel/agents/households/households.py:977 | Owners' rent_imputed tracked separately; no self-payment. |
| Cash debit on realized goods purchases | macromodel/agents/households/households.py:1241 and1330 | Realized L purchases join nominal_amount_spent_in_lcu and reduce financial resources; imputed memo itself is not an additional debit. |
| IH GDP scope | macromodel/economy/economy_ts.py:201 and282; macromodel/country/country.py:431 | Prevents re-adding paid/imputed memo rents on top of IO housing in initial GDP. It does not repair the household cash basket. |

Goods-market L purchases are cash sales to sector L firms; those firms bear their usual inputs/costs. Actual private rent is a separate household-to-household cash flow. Imputed rent is neither paid to landlords nor booked as an owner cash income. Planned and realized L quantities have no subcategory identifying housing versus other real-estate services, nor an owner-specific noncash purchase. Consequently **the exact imputed rent inside any household's L purchase is not identifiable** from current model state.

[StatCan's income-account guide](https://www150.statcan.gc.ca/n1/pub/13-606-g/2016001/article/14620-eng.htm) includes implicit owner housing income in the rental component of mixed income; its [rental-income methodology](https://www150.statcan.gc.ca/n1/pub/13-017-x/2008001/themes/ch05/5213352-eng.htm) distinguishes gross rental output and net rental income. This supports a missing noncash counterpart, but does not establish that the full127.6B mixed-income gap equals gross imputed rent. Operating expenses, CFC and housing scope must be bridged. No235.938B cash receipt is invented to close that gap.

Annual B and percentage shares at t0:

{table(housing_display[['arm']+money+['C_dissaver_share','C_memo_proxy_dissaver_share','C_all_owner_L_removed_dissaver_share']])}

The88B figure belongs to the unaccepted CIS candidate (gap87.519B,70.10% planned dissavers); accepted F_CFC has95.884B and71.94%. The gross235.938B imputed memo is larger than either gap, but is not a measured amount charged to these households as cash. Owner L demand provides an upper bound. The explicit attribution proxy removes **min(owner L planned cash, owner imputed memo)**; it is a read-only bound/proxy, not a fitted allocation or implemented closure. In the candidate it removes162.121B, changes the aggregate gap to **-74.602B**, and reduces planned dissavers to **38.56%** (31.54pp reduction). Even the extreme removal of all owner L leaves34.35% as planned dissavers. A substantial non-housing income/spending issue therefore remains. Renters also buy the mixed L bundle; these diagnostics do not identify imputed housing inside their purchases.

Tenure and after-tax CIS-income decile detail, annual B and percentages:

{table(h[['arm','decile','tenure','households','C','DI','gap','planned_L','imputed_memo','memo_proxy_removed','dissaver_pct','proxy_dissaver_pct']])}

The model currently has tenure1 for owners,3 for renters and-1 for other/social households; the probe follows the runtime owner category. Planned dissaving holds t0 income and the rule fixed; it is not a longitudinal insolvency estimate. Realized consumption is rationed/market-cleared; no new realized path is inferred from this static exercise.

The exact accepted imputed-rent vintage is independently recovered from cached36-10-0124 DBnomics series1.1.1.18:2022 quarterly values57441/58553/59397/60547M sum to235938M. The cache was indexed2026-09-30; source/extract hashes and dimensions are frozen. This series ID is not a native StatCan v-number. The native vector is absent from the legacy cache; attempts to retrieve the official bulk file failed (closed connection / timeout), so native-vector provenance remains explicitly unavailable. No number or identifier was guessed, and no later vintage substituted.

Options, for approval only:

1. **Cash-consistent closure (recommended for the declared cash model).** Identify the housing-service part of L and allocate own-use services to actual owners. Remove that component from both the cash purchase basket and the cash consumption benchmark; retain matched noncash income/use memos and the correct producer/input/CFC accounts. Simple national scope arithmetic gives1511.382-235.938=1275.444B/year before further cash/VAT/rent-boundary reconciliation; that is not a new calibrated target. Paid rent and other L services stay cash. Do not delete the whole L sector or add a costless housing producer.
2. **Matched noncash SNA layer.** Separate owner own-use production/consumption and its income counterpart with net cash zero. Keep it outside deposit budgets, bank receipts, credit screens, PIT and the cash-saving statistic. Record intermediate costs/CFC and ownership consistently. Merely adding cash income or a memo to the current cash goods purchases would not solve the problem.

Neither option is implemented. The housing specification should precede a buffer-stock spending rule or a claim that the propensity itself is the main error.

## 4. CIS before-tax comparison and progressive PIT - read-only

Same CIS2022 PUMF household units as HI: unique EFID family income summed once into PUMFID, household FWEIGHT, unequivalised households, nominal2022 CAD. Before-tax total income is EFATINC+EFINCTX, ranked anew by before-tax income. After-tax ranks are separate; the frozen HI after-tax benchmark is retained exactly to avoid floating-point tied-record differences at decile cutoffs. These custom tabulations have no published vector IDs; source PUMF SHA is in household_provenance.json. Territory/coverage and model income-concept limitations remain.

Model before-tax income adds actual public transfers to reconstructed gross wages and grossed-up funded mixed/property/private-pension/corporate receipts. Employee CPP/EI is separately added back for the CIS after-tax bridge, as in HI; loan interest is excluded from the CIS comparison. Public transfers are not all subject to the model's flat PIT. **Flat PIT therefore does not make model before- and after-tax shares identical**, even though it lacks the observed progressive compression. No receipts are changed.

[StatCan's2022 CIS release](https://www150.statcan.gc.ca/n1/daily-quotidien/240426/dq240426a-eng.htm) defines after-tax income from market income and public transfers less income tax. The [CIS PUMF catalogue](https://www150.statcan.gc.ca/n1/en/catalogue/72M0003X) is the primary source. The empirical diagnostic uses its observed combined income taxes EFINCTX divided by total household income within each gross-income decile. This captures combined federal/provincial incidence, not statutory brackets or a provincial tax-return microsimulation. Applying those rates by model gross-income rank is an explicit descriptive assumption, not a fitted schedule. It includes the source population's credits/composition; this uncertainty is material.

Summary (share gaps are relative%, not differences in dollar levels):

{table(tax)}

Effective rates applied, fractions:

{table(rates[['decile','effective_PIT']])}

For the CIS candidate, comparing before tax reduces the maximum discrepancy from21.153% to13.265%, but still fails10%. Empirical progression reduces the after-tax maximum to12.064% (9.089 percentage points, about43% of the original maximum); the top-share error falls from21.153% to11.965%. It does not pass the unchanged HI gate or cure the remaining household/member/employer support mismatch. For F_CFC, maximum error remains37.250% after the counterfactual. The diagnostic is not a new accepted tax rule.

Counterfactual national annual flows, B; no rescale to preserve taxes or DI:

{table(payout.assign(**{k:payout[k]/1e9 for k in ['flat_PIT','counterfactual_PIT','before_tax_income','counterfactual_after_tax_income']}))}

All decile raw annual levels and shares, separately ranked, are in CIS_concepts.csv. No new household build or progressive PIT implementation. A proper proposal must specify federal and provincial schedules, taxable components, credits/refunds, benefit interactions and fiscal counterparties using household/member records; income-decile rates alone are not such a specification.

## 5. Dynamic comparison, tests and next priorities

No arm passed all Step1 gates, hence no new seeds0-2 twelve-quarter results or FSG comparison exist. Demand spiral, constrained-share paths, investment, losses and recapitalisations cannot be declared improved. Historical IH F_CFC numbers below are **references only**, not new runs:

{table(history)}

Full suite through run_pre_D3_tests.py: **{testtext}**. Exact failure IDs match HI's known30 NaN cases; additional failures **zero**. Four source/cost regressions and two independent GDP regressions pass focused checks; the strengthened explicit-VA assertion is separately rerun after source bookkeeping completion. Accepted input hashes, final v3 build stock/flow checks, source git blobs and run ordering are audited. Earlier v1/v2 data builds are excluded (ROW counterpart / explicit VA6 bookkeeping), retained under their original names, and never iterated.

Recommended order for the next decision: specify a cash/noncash housing split first; finish a traceable household rebuild retaining original household/member/donor IDs; specify progressive PIT alongside that rebuild and test both gross and net concepts; resolve the tiny/source-zero producer holding convention before adopting FS_T. Only after these account boundaries pass should an investment expansion specification be selected. A future desired-capital term must confront the capacity-censored demand signal, not simply raise an accelerator weight. Buffer-stock consumption remains deferred; it cannot substitute for correctly identified cash resources. Phase B remains on hold. Stop for review.
'''
    (HERE/'CLOSURE_SG_2026-10-25.md').write_text(text,encoding='utf-8');print('SG report written; full tests',bool(tests),'short accounting',bool(ac))
if __name__=='__main__':main()
