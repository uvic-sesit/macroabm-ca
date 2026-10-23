from pathlib import Path
import json
import pandas as pd

root=Path(__file__).resolve().parents[2];here=root/'dev/validation_2022';out=here/'outputs/pre_D3_checks'
parts=[]
def add(s):parts.append(s.strip()+'\n')
def table(df):
    def cell(x):
        if pd.isna(x):return '—'
        if isinstance(x,float):return f'{x:,.3f}'
        return str(x).replace('|','/')
    cols=list(df.columns)
    return '| '+' | '.join(cols)+' |\n|'+'|'.join(['---']*len(cols))+'|\n'+'\n'.join('| '+' | '.join(cell(x) for x in row)+' |' for row in df.itertuples(index=False,name=None))+'\n'
def panel(s):
    add(table(s))

add('''# Four checks before D3 — 22 October 2026, local time

D3 is **on hold**. Substantial write-offs survive the mechanical fixes, but the
diagnostics do not establish that D3 is the appropriate remedy. The initial
consumption/income mismatch, automatic overdrafts, collateral treatment in the
old insolvency rule and invalid bank-capital initialization need separate review.
Phase B and C_dp_005 have not started. Work remains on `feature/validation-2022`;
no push, original-repository edit, ITC/user-cost edit or pickle change.

This report supersedes the earlier recommendation to retain D3 merely because
arm iv had large write-offs. Dollar amounts are CAD billions unless stated.
`b1` denotes the original b1b2960 behaviour with read-only instrumentation;
`fixed` adds the obligation-screen correction only; **`final` adds the liability
bookkeeping correction as well**. The bank reader correction protects future
builds; it does not change the serialized input used in any of these runs.

## Findings and decisions

| Check | Finding | Fix commit | Decision needed |
|---|---|---|---|
| 1: starting income and Q1 cohort | Q1 saving gap is predominantly consumption; most cancelled debt belongs to households already having negative net worth at t0, though nonnegative deposits | No residual income plug; 37cf590 synchronizes household liabilities after cancellation | Consistent initial income/consumption closure and treatment of recoverable collateral |
| 2: new D4 loans | Existing overdraft principal/interest and consumer debt-service capacity were incompletely screened; automatic overdrafts remain outside origination limits | d7a2110, regression tests | Explicit overdraft facility, limit and arrears policy; no blanket prohibition imposed |
| 3: firm payouts and bank capital | Q9 spike is mostly utilities and accommodation/food failures; payout cash cap works; every region starts with a national bank-capital amount, from the wrong financial-account concept | 59a37ef fixes omitted regional multiplier only | Canadian book-equity benchmark/bank boundary and fresh validation input; retained-profit/cash-reserve payout policy |
| 4: sector L | Final seed 0: sales -0.7%, essentially fixed quantity/employment. Final D1 seeds 1/2 fail bank-resolution accounting; original-path decomposition below | Diagnostic instrumentation only | Cross-seed acceptance blocked; keep narrow D1 opt-in, no wider producer boundary |

## Commits and reproducibility

| Commit | Change | Focused validation tests |
|---|---|---:|
| 5ea5807 | Read-only cohort, lending-vintage, firm and bank instrumentation | Exact two-quarter replay of earlier arm iv |
| d7a2110 | Include overdraft principal/interest and consumer service in D4 screens | 49 |
| 59a37ef | Apply regional share to both bank-equity reader return paths | 51 |
| 37cf590 | Refresh household debt and net worth when the old rule cancels loans; trigger unchanged | 52 |
| 94a956b | Domestic L buyer panels, summary/audit tools and isolated baseline replay | Read-only artifact checks |

All household diagnostic simulations were serial, with 13 Canadian regions. Two-quarter iv/v accounting
checks precede the final 12-quarter runs. No calibration or new behavioural cap
was introduced. Each run manifest records source hashes, seed, HEAD, input hash
and accounting error. Exact input SHA256 is
`3b48c0dba90c2d3c837f92bc0477e4b242ba0afa78275b095e26cc52b4fcb313`.
Read-only baseline instrumentation replayed the prior two-quarter GDP/write-offs
to less than one cent. Baseline labels reflect model behaviour, not the manifest
HEAD, which also contains instrumentation.

Individual borrower/cohort records remain local in ignored `micro/` directories.
Their hashes and the aggregate panels appear in
[result_manifest.json](outputs/pre_D3_checks/result_manifest.json). These are
synthetic model records. The panel files, rather than rounded tables, are the
numerical record.

Raw run CSV stocks/flows are CAD for the represented model agents; aggregate
columns ending `_B` are billions. The origination audit's `_per_household_CAD`
columns divide by the regional representation factor. Report tables use billions
unless a per-household or employment unit is stated.

## 1. Household income, spending and the starting cohort

Comparison uses annualized model Q1 cash flows against the mean of the four 2022
seasonally adjusted annual-rate observations in
[36-10-0112](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201),
with property detail from annual
[36-10-0482](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610048201).
The retained extracts/provenance are under `benchmarks/household_corrections/`.
That downloaded vintage is dated 23 October UTC, which was 22 October locally.
The line bridge is an accounting/concept comparison, not a seasonally fitted
simulation or a claim that noncash SNA receipts are available for spending.
Rental income belongs to mixed income in SNA; it is separated here for clarity.
Gaps are model minus benchmark, in $B/year; expense gaps are not sign-reversed.
The following initial snapshot and Q1 use original arm iv as requested.
''')
bridge=pd.read_csv(out/'income_bridge.csv')
b0=bridge[bridge.quarter.eq(0)].set_index('line')
b1=bridge[bridge.quarter.eq(1)].copy()
b1['t0']=b1.line.map(b0.model_B_per_year)
panel(b1[['line','t0','model_B_per_year','benchmark_B_per_year','gap_B_per_year','table','vector']].rename(columns={'model_B_per_year':'Q1 annualized','benchmark_B_per_year':'2022 benchmark','gap_B_per_year':'Q1 gap'}))
inc=json.loads((out/'income_summary.json').read_text())
add('**Recorded saving-rate bridge (SNA comparison, percentage points; cash-restatement caveat below)**')
panel(pd.DataFrame({'component':['2022 D.8-free rate','Disposable-income gap','Consumption gap','Model Q1 cash rate'],
                    'rate_or_change_pp':[inc['observed_D8_free_saving_pct'],inc['income_gap_effect_pp'],inc['spending_gap_effect_pp'],inc['model_Q1_saving_pct']]}))
add(f'''At t0, booked income is {inc['initial_booked_income']:.3f}B/year and consumption
is {inc['initial_C']:.3f}B/year. The booked income includes an unfunded financial-asset
proxy of {inc['initial_FA_proxy']:.3f}B/year; realized D2 mixed income, dividends
and corporate-transfer series are initially zero, although planned D2 payments
are available for subsequent decisions. Initial interest-paid series are NaN
placeholders, so a measured initial cash-DI/saving rate is unavailable. Initial
deposit interest in the table is stock × rate, not a booked cash receipt; initial
taxes are reconstructed from the configured wage/rent rates. This is an
inconsistent initial closure, not evidence for adding every missing SNA line
as a cash transfer.

The source paths also explain why observed aggregates need not be hit: public
benefits are built by `DefaultDataReaders.get_total_benefits_lcu` from OECD public
cash social-expenditure share × World Bank scaled GDP, not directly from the
household-account transfer vector. Coverage/reference-year reconciliation is
needed before replacing that target. Canadian PIT uses 348,148/2,005,348 from
an SNA income base (`macro_data/processing/country_data/tax_data.py`), whereas
the model taxes a smaller/different set of wage/rent/distribution flows. An
observed average rate therefore does not reproduce observed PIT receipts.
Neither difference is repaired by adding an unsourced net-income residual.

Q1 cash disposable income is {inc['model_Q1_DI']:.3f} versus 1,502.340B/year;
consumption is {inc['model_Q1_C']:.3f} versus 1,511.382B/year. Cash saving is
{inc['model_Q1_saving_pct']:.3f}% versus {inc['observed_D8_free_saving_pct']:.3f}%
excluding D.8 (40.585B/year, v105775422). The exact ordered rate bridge is
{inc['income_gap_effect_pp']:.3f}pp from the disposable-income difference and
{inc['spending_gap_effect_pp']:.3f}pp from consumption. Thus 7.375 of the 9.020
percentage-point gap is spending. This is the residual after using D2 in arm iv;
it does not add the previous ordered D1/D2/deposit-saving effects a second time.

This is an arithmetic bridge to the cited SNA account, **not a fully restated
cash-only benchmark**. Removing D.8 alone does not remove imputed housing,
FISIM and other accruals. The model treats the owner L bundle as a cash market
purchase, while SNA imputed housing is noncash; simply deleting that benchmark
line from one side would be inconsistent. A complete cash restatement needs
the housing and pension/institutional boundary decisions. The rate decomposition
locates the recorded gap without claiming those concept differences are solved.

Large gross scope differences offset: imputed rental income and pension/insurance
investment income lack cash counterparts, while current taxes and transfers paid
are also incomplete. All model employer social contributions go to government;
the SNA government contribution benchmark is a narrower recipient boundary.
Other transfers paid include pension-related flows missing from the model's
institutional structure. Interest paid has a different FISIM/property-income
boundary. The inherited negative saving propensity was initialized on incomplete
income and remains unchanged when D2 raises expected income, increasing desired
consumption. A consistent initialization or revised consumption rule is an option
for approval; fitting a saving propensity or inventing an income residual is not
a mechanical correction and was not done.

The original Q1 pair makes the interaction visible: iii has annualized cash DI
1,308.008B and consumption 1,522.166B (saving -16.373%); iv has 1,478.170B and
1,620.402B (-9.622%). Adding funded D2 receipts raises DI by 170.162B/year and
realized consumption by 98.236B/year. It improves saving by 6.751pp while taking
consumption from 10.784B above the SNA benchmark to 109.020B above. This is a
paired simulation outcome with market rationing, not an estimated marginal
propensity or a calibrated household-account correction.

### Q1 write-off cohort under the old rule

The following is original arm iv. The old trigger is negative net worth **and**
negative deposits at the time of the check. Counts use regional population
scales, with unscaled simulated counts also reported in the CSV. Income deciles
use t0 income per represented household with national population weighting.
Age is the oldest member of the synthetic household, an explicit proxy rather
than the SFS reference person's age. Tenure -1 is assigned social housing,
1 owner, 2 part owner, 3 private renter.
''')
co=json.loads((out/'Q1_cohort_summary.json').read_text())
add(f'''There are {co['simulated_count']:,} simulated households, representing
{co['represented_count']:,.0f}, with {co['writeoff_B']:.3f}B of term debt cancelled.
None met both old-rule conditions at t0. However, {co['negative_NW_at_t0_pct']:.2f}%
of the cohort already had negative net worth; those households account for
93.88% of cancelled debt. A further 29.39% of households had nonnegative net worth
below one quarter's income. The saving/settlement gap pushes this fragile
starting cohort into overdraft; it does not create all of its balance-sheet
insolvency from scratch. Initial deposits are {co['initial_deposits_B']:.3f}B,
falling to {co['final_deposits_B']:.3f}B; net worth moves from {co['t0_NW_B']:.3f}
to {co['Q1_NW_B']:.3f}B. Real assets rise {co['real_asset_change_B']:.3f}B in
aggregate, so an aggregate house-price collapse does not explain the cohort.
The old rule cancels all term debt rather than just the uncovered recovery loss.
''')
g=pd.read_csv(out/'Q1_cohort_groups.csv')
for dim in ['decile','tenure','age_band','deposit_band','net_worth_band','main_cause','t0_state']:
    add('**'+dim.replace('_',' ')+'**')
    panel(g[g.dimension.eq(dim)][['group','simulated_count','represented_count','count_share_pct','group_incidence_pct','debt_B','debt_share_pct']])
add('''Cause attribution uses a three-block Shapley decomposition of the observed
overdraft: goods/investment spending plus VAT, debt service (principal, loan and
overdraft interest), and actual rent. Resources are the exact residual of these
blocks and closing deposits; no arbitrary sequencing chooses the winner.
Classification uses the largest block per household. Aggregate overdraft
attribution is 2.788B spending, 1.395B debt service and 0.368B rent, with zero
other-resource residual. These are cash pressures, not legal insolvency causes.
All group counts, incidence and debt shares are in
[Q1_cohort_groups.csv](outputs/pre_D3_checks/Q1_cohort_groups.csv).

## 2. New lending and the mechanical screen fixes

The original D4 screen omitted overdraft principal from its LTI debt total and
overdraft interest from existing debt service; consumer originations also lacked
the mortgage-style service-cap check. d7a2110 counts these obligations in both
allocators and both loan categories, including same-quarter consumer service
before granting mortgages. Existing scheduled principal is capped by remaining
principal. Overdraft principal enters total debt, while its interest enters
service; no fictional overdraft amortization schedule was added.

37cf590 separately synchronizes household debt/net worth to surviving credit
books immediately after cancellation. Previously the household could carry
forgiven liabilities into later decisions. The old trigger and cancellation
amount for an already selected cohort are unchanged.

Loan tracking follows new principal through contractual amortization and actual
per-bank/per-household cancellations. The loss fraction below is principal
written off divided by new principal originated within this 12-quarter window.
The second measure is original value of vintages with any write-off; neither is
an annual default rate. Later vintages are right-censored.
''')
r=pd.read_csv(out/'run_summary.csv')
names=['b1_iii_q12_s0','b1_iv_q12_s0','final_iii_q12_s0','final_iv_q12_s0','final_v_q12_s0']
panel(r[r.run.isin(names)][['run','new_lending_B','new_principal_written_B','loss_pct','orig_value_eventually_written_pct','lent_to_overdrawn_pct','lent_to_negative_NW_pct']])
add('After both fixes, arm iv still loses 40.60% of newly originated principal within the window, and 97.76% of lending goes to borrowers already overdrawn. Its negative-net-worth share falls to 1.26% once forgiven liabilities are synchronized; the original recorded negative-net-worth measure was materially distorted by stale debt. In v, which preserves more collateral-backed liabilities, 45.98% of lending goes to recorded negative-net-worth borrowers. D4 screens income, service and property collateral; it does not impose a separate positive-net-worth or no-overdraft eligibility condition.')
add('''Each origination's bank, household, quarter, principal, deposits, overdraft,
net worth, total installment debt and existing service are retained in each
run's `micro/originations.csv`. `micro/origination_audit.csv` joins the population
scale and supplies each amount in CAD per represented household. Original
`b1` net worth is the state actually seen by the decision, which can contain
the now-fixed stale liabilities; it must not be read as independently recomputed
economic net worth. The final runs use synchronized balances.

Automatic settlement overdrafts remain possible even if new installment credit
is denied. Passing these screens does not mean a household has enough cash to
cover its consumption plan or all future obligations. An approved overdraft
facility with a limit and arrears treatment is a separate architectural choice;
no such limit has been silently imposed.

## Revised iv/v write-offs after both model fixes

Arm iv = H7 + D4 + D2, old insolvency. Arm v adds D3 only. D1 and deposit-only
saving are off in both. Bank losses include firm term debt and cancelled firm
overdrafts as well as household term debt. The following seed-0 table is the
final comparison, not the intermediate `fixed` run.
''')
w=pd.read_csv(out/'writeoffs_quarterly.csv');ww=w[w.run.isin(['final_iv_q12_s0','final_v_q12_s0'])]
p=ww.pivot(index='quarter',columns='run',values=['HH_writeoffs_B','bank_losses_B'])
p.columns=[('iv' if 'final_iv' in run else 'v')+' '+('HH' if metric=='HH_writeoffs_B' else 'bank') for metric,run in p.columns]
p=p[['iv HH','v HH','iv bank','v bank']];p.loc['Total']=p.sum();panel(p.reset_index())
add('Two-quarter accounting runs:')
panel(r[r.run.isin(['final_iv_q2_s0','final_v_q2_s0'])][['run','total_HH_writeoffs_B','total_bank_losses_B','accounting_error']])

add('''## 3. D2 firm payouts, the Q9 spike and bank capital

Original arms iii/iv are preserved to diagnose the reported 701B versus 648B
Q12 GDP and Q9 spike, rather than attributing a changed path to the old event.
Each quarterly row below includes failed-firm loan principal and cancelled
overdraft; industry counts and all firm observations are in
[firm_quarterly.csv](outputs/pre_D3_checks/firm_quarterly.csv) and the run's
`firms.csv`. Firm IDs are model industry-region representatives, not identified
Canadian companies. The industry mapping is retained in `industry_mapping.json`.
''')
fq=pd.read_csv(out/'firm_quarterly.csv')
for name in ['b1_iii_q12_s0','b1_iv_q12_s0','final_iii_q12_s0','final_iv_q12_s0']:
    add('**'+name+'**')
    panel(fq[fq.run.eq(name)][['quarter','insolvencies','firm_debt_B','overdraft_loss_B','requested_dividends_B','paid_dividends_B','cash_before_payout_B','cash_after_payout_B']])
f=pd.read_csv(out/'b1_iv_q12_s0/firms.csv');spike=f[f.quarter.eq(9)&f.failed].copy()
mapping=json.loads((out/'industry_mapping.json').read_text());spike['industry_name']=spike.industry.astype(str).map(mapping)
for key in ['loan_debt','overdraft_cancelled','equity','deposits','profits','paid_dividends','cash_before_payout','cash_after_payout']:spike[key]/=1e9
add('**All original arm-iv Q9 failures ($B)**')
panel(spike[['region','firm','industry_name','loan_debt','overdraft_cancelled','equity','deposits','profits','paid_dividends']])
add('Original arm iv: payouts to firms with negative current profit, summed over 12 quarters:')
neg=f[f.profits<0][['paid_mixed','paid_transfers','paid_dividends']].sum()/1e9
panel(neg.rename('paid_B').rename_axis('payment').reset_index())
add('''Original Q9 bank losses total 222.785B: 28.940B household loans, 133.399B firm
loans and 60.446B cancelled firm overdrafts. Utilities (D) in Ontario and British
Columbia account for 111.209B of failed loan principal; accommodation/food (I)
also contributes large overdrafts. Failure follows the model's balance-sheet
trigger, not simply negative current profit: Ontario utilities still has positive
current profit but negative equity and deposits. This identifies the spike's
balance-sheet source; it does not establish that dividends alone caused every
failure. Source-scope problems in firm debt and missing production taxes remain
in the prior firm audit.

Both utilities representatives were already overdrawn in Q7 and paid **zero**
mixed income, transfers or dividends in Q7–Q9. Ontario's Q8→Q9 equity moves
5.220→-3.494B: deposits -4.773→-6.077B, debt 83.777→82.165B, and the noncash
asset residual (equity + debt - deposits) 93.770→84.749B. The 9.022B decline in
that asset-value/stock residual dominates the equity deterioration; current
profit is +0.417B. BC's equivalent residual falls 38.276→37.107B and deposits
-7.400→-8.226B, taking equity 1.263→-0.163B while debt amortizes. These are
balance-sheet decompositions, not a claim that the entire residual change is
pure price revaluation: the saved panel does not split asset prices from
quantities/depreciation. Earlier D2 payments and general-equilibrium paths can
still affect later buffers. These six observations are retained in
`Q9_utilities_balance_bridge.csv`.

The payout algorithm uses lagged positive profit and two available-cash caps.
No observed payout turns nonnegative cash into overdraft, and cash-short firms
pay zero. Negative cash after payout occurs when cash was already negative.
Payouts may nevertheless be made while current-quarter profits are negative,
and consume cash buffers needed in future periods. The retained panel includes
requested versus actual mixed-income/corporate-transfer payments as well as
dividends; current-loss-maker dividends, cash-short payouts and overdraft-created
counts are explicit columns. A possible rule is dividends bounded by positive
current retained earnings and cash after near-term obligations plus a liquidity
reserve. This changes behaviour and needs approval. Mixed income and pension
transfers need their own institutional treatment rather than blindly adopting
the corporate-dividend restriction.

### Bank capital is not validated

Every provincial bank starts with **506.210B**, giving 6,580.730B nationally.
No recorded bank equity turns negative in the original or final runs; this is partly a
consequence of excessive starting capital, not evidence that Canadian banks
could absorb these losses. The quarterly bank-level panel includes initial,
before-rescue and end-of-quarter observations, equity and equity/loan ratio:
`b1_iii_q12_s0/banks.csv`, `b1_iv_q12_s0/banks.csv` and final equivalents.
''')
panel(r[r.run.isin(names)][['run','total_bank_losses_B','min_bank_equity_B','negative_bank_observations']])
add('''**Failed diagnostic: final D1, seed 1.** Ontario reaches a bank-resolution
trigger in Q11 while book equity is still positive (50.139B; equity/loans 3.796%).
`DefaultBankDemography` uses equity/(loans + bank deposits), not the equity/loans
ratio reported in the bank panel. Resolution calls `remove_loans_by_bank`,
cancelling 1,320.852B of loans. That call increments the aggregate write-off
counter without a by-bank loss attribution, after the quarter's ordinary bank
loss recognition and stock calculation. The bank stock is not refreshed until
Q12. The loan identity consequently has +1,320.852B in Q11 and -1,320.852B in Q12;
the run's maximum normalized accounting error is 2.939. It is retained as a
failed diagnostic, not an accepted accounting path. The cancelled bank portfolio
is outside the household-only write-off measure and the origination loss tracker
around household insolvency, so that run's loan-loss percentages understate
all cancellation routes. Its Q12 seed comparison is descriptive only.

Final D1 seed 2 also fails through this route: Ontario cancels a 1,356.011B
portfolio in Q10, with the opposite loan-stock residual in Q11 and another
14.131B cancellation in Q12. Its maximum normalized accounting error is 3.073.
Both requested D1 seed runs were completed and retained, but neither is an
accepted accounting path. The paired iv runs pass.

Repairing the full resolution transaction requires choosing whether loans
transfer, borrowers receive forgiveness, and which equity/deposit/fiscal claims
absorb the loss. That is an architectural decision, not an authorized choice
for this diagnostic. No resolution change or bailout was invented. No negative
*recorded* equity therefore does not imply solvency after recognizing all losses.

For review, the preferred resolution design is to preserve borrower contracts
and transfer the loan book to a successor/bridge bank while specifying the
equity/deposit/fiscal loss waterfall. An alternative is explicit debt forgiveness,
with simultaneous borrower liability cancellation, bank asset/loss recognition
and a funded recapitalization transaction. These are proposals only.
''')
add('''The reader computed a regional ratio and omitted it from both return paths;
59a37ef fixes that mechanical error, including own-observation and proxy-country
regressions. Separately, its selector uses **ASS/F5** for S122_S123, meaning banks'
holdings of equity assets, not their own book capital. Merely applying the ratio
does not resolve that concept error. The agreed pickle is unchanged, so all
results here retain the inherited bad capital stock.

This interpretation follows the selected asset-side instrument and
[Eurostat financial-account definitions](https://ec.europa.eu/eurostat/cache/metadata/en/nasq_10_f_esms.htm);
it is a source-concept diagnosis, not a newly estimated bank-capital target.

For a Canadian benchmark,
[36-10-0580](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058001)
2022 Q4 liability-side **Book value / Equity** reports chartered banks 405.572B
(v62696428), quasi-banks 50.649B (v62696533), total 456.221B (v62696323).
The model total is 14.4 times that combined benchmark. Sector coverage must be
chosen explicitly; neither regulatory CET1 nor banks' equity asset holdings is
the same concept. Model equity/loans is not a risk-weighted regulatory capital
ratio. Benchmark extract and raw-source SHA are in
`benchmarks/pre_D3_checks/36100580_bank_equity_2022Q4.csv` and
`bank_equity_provenance.json`, from the inherited 13 October controls snapshot.

**Decision:** choose Canadian bank sector/book-equity coverage, regional
allocation and balance-sheet counterpart, then authorize a new validation input
and reruns. No rescaling of existing pickles or automatic capital injection was
used to make losses appear sustainable.

## 4. Sector L: prices, quantities, buyers and seeds

Each paired run changes only narrow D1 relative to iv. Seeds 1 and 2 were run
for 12 quarters per arm, serially; seed 0 is also retained. This is a paired-seed
comparison, not a guarantee of identical later random draws: changed allocation
branches can consume different numbers of draws. National P is total L sales
divided by total L real sales. The exact symmetric decomposition is
Δsales = ΔP × mean(Q) + ΔQ × mean(P). Inventory is in base-value quantity units.
''')
effects=pd.read_csv(out/'L_price_quantity_effects.csv')
old=effects[effects.label.eq('b1')]
if len(old):
    add('**Original reported anomaly: exact b1b2960-source replay, seed 0**')
    panel(old[['quarter','base_sales_B','D1_sales_B','price_base','price_D1','price_effect_B','quantity_effect_B','inventory_base_B_units','inventory_D1_B_units']])
    q12=old[old.quarter.eq(12)].iloc[0]
    add(f"The reported Q12 increase of {q12.delta_sales_B:.3f}B decomposes into {q12.price_effect_B:.3f}B from the national unit-value price and {q12.quantity_effect_B:.3f}B from quantity. The national unit value includes regional mix. Summing province-level decompositions instead gives {q12.regional_price_effect_B:.3f}B price and {q12.regional_quantity_effect_B:.3f}B quantity, also price-led. Employment falls from 360,120 to 342,110; inventory accumulates to 3.321B base-value quantity units. Higher nominal sales therefore do not indicate a real L expansion.")
    add('The replay uses an isolated `git archive b1b2960 macromodel` source snapshot, read-only input and the same diagnostic wrappers. Its manifest records the native source commit and archive hash. No branch checkout or original-repository edit was performed. `replay_pre_D3_original.py` reproduces this operation. Buyer, inventory and employment observations are retained in `b1_d1_q12_s0/L.csv`.')
ef=effects[effects.label.eq('final')]
add('**Final Q12 pairs: seeds 1 and 2 have failed D1 accounting and are descriptive only**')
panel(ef[ef.quarter.eq(12)][['seed','base_sales_B','D1_sales_B','delta_sales_B','delta_pct','price_effect_B','quantity_effect_B','price_base','price_D1']])
add('**Intermediate obligation-screen-only pairs (before the stale-liability fix), all pass accounting**')
panel(effects[effects.label.eq('fixed')&effects.quarter.eq(12)][['seed','base_sales_B','D1_sales_B','delta_pct','price_effect_B','quantity_effect_B']])
add('The intermediate sign changes across seeds. The final seed-0 quantities and employment are essentially unchanged, with a small nominal sales decline; the final cross-seed comparison cannot be accepted until bank resolution is repaired. The reported original sales increase must therefore not be treated as a robust D1 response.')
add('**Quarterly price × quantity decomposition, seed 0**')
panel(ef[ef.seed.eq(0)][['quarter','base_sales_B','D1_sales_B','price_base','price_D1','price_effect_B','quantity_effect_B','inventory_base_B_units','inventory_D1_B_units']])
l=pd.read_csv(out/'L_quarterly.csv')
for name in ['final_iv_q12_s0','final_d1_q12_s0']:
    z=l[l.run.eq(name)].copy()
    for k in ['sales','quantity','HH_L_domestic','firms_L_domestic','government_L_domestic','ROW_L_sales','rent_offset']:z[k]/=1e9
    z['buyer_residual_B']=z.sales-z[['HH_L_domestic','firms_L_domestic','government_L_domestic','ROW_L_sales']].sum(axis=1)
    add('**'+name+': buyers of Canadian L output**')
    panel(z[['quarter','quantity','sales','HH_L_domestic','firms_L_domestic','government_L_domestic','ROW_L_sales','buyer_residual_B','employment','rent_offset']])
add('''National buyer flows reconcile to Canadian L sales; regional buyer expenditure
alone need not equal that region's seller revenue because purchases cross
provincial borders. `HH_L`/`firms_L` include imports; the `_domestic` columns above
exclude imports and include all Canadian origins. Buyer splits can shift despite
the reduced renter budget when supply constraints ration realized purchases.
The full L panel retains regional minimum/maximum prices, inventories, production,
employment and all quarters/seeds. These paths must be read with the inherited
noise-driven price rule documented in the firm audit.

## Recommendation and review boundary

Do not accept D3 yet. Its smaller write-off totals establish a scenario difference,
not a Canadian arrears, foreclosure or recovery mechanism. First resolve the
initial income/consumption boundary, automatic overdrafts and Canadian bank
capital; then choose a collateral/recovery specification with an explicit cash
and balance-sheet path. The old rule also remains unsuitable as a validated
Canadian default process. D2 and narrow D1 remain opt-in candidates. H7 and the
quota correction are unchanged. No Phase B or C_dp_005 work was started.
''')
errors=r[r.run.str.startswith('final_')][['run','accounting_error']]
failed=errors[errors.accounting_error.ge(1e-8)]
add(f'{len(errors)-len(failed)} of {len(errors)} final runs pass the 1e-8 accounting threshold; {len(failed)} fail and are retained explicitly. Focused tests: 52 passed.')
if len(failed):panel(failed)
audit=out/'audit.json'
if audit.exists():
    a=json.loads(audit.read_text())
    if 'full_suite' in a:
        suite=a['full_suite'];nf=len(suite['failures']);ne=len(suite['errors']);extra=sum(not x['known_NaN'] for x in suite['failures'])
        add(f"Full suite: {suite['cases']-nf-ne} passed, {nf} failures, {ne} setup/runtime errors. {nf-extra} failures match the known `Nan in transactor_total_real_supply` cases; {extra} additional failures. Raw XML/log and case classifications are retained.")
    if 'serial_sampler_rerun' in a:
        serial=a['serial_sampler_rerun']
        add(f"Sampler rerun: workers={serial['worker_count']}, failures={serial['failures']}, errors={serial['errors']}; all failures match the known NaN: {serial['known_NaN']}. Worker count is verified from the JUnit property.")
add('''Test-harness exception: pytest was serial, but its existing sampler test
internally defaults to cpu_count()/2 workers. This was discovered after that
test finished; its workers had exited. The household diagnostic runs remained
serial. The sampler is rerun with `run_pre_D3_tests.py`, which sets only its
worker count to one and records that setting in JUnit; no test is skipped.
Use this wrapper for future full suites under the one-simulation constraint.
The initial full-suite result and the serial sampler rerun are retained separately.
''')
(here/'HOUSEHOLD_CLOSURE_PRE_D3_2026-10-22.md').write_text('\n'.join(parts),encoding='utf-8')
print('Wrote report')
