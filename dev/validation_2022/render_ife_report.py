"""Render the investment-ledger gate report; F/E remain conditional."""
import json
from pathlib import Path
import pandas as pd
from render_afe_report import table
HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/IFE'


def main():
    q=pd.read_csv(OUT/'quarterly.csv').query('quarters==12')
    s=pd.read_csv(OUT/'summary.csv').query('quarters==12')
    gates=pd.DataFrame(json.loads((OUT/'gate1.json').read_text()))
    if gates.gate1_pass.all():raise RuntimeError('Gate 1 passed: proceed to F before final reporting')
    ledger=pd.read_csv(OUT/'cash_ledger_national.csv')
    dec=pd.read_csv(OUT/'cash_ledger_decile.csv');assets=pd.read_csv(OUT/'cash_ledger_assets.csv')
    base=ledger.query("arm=='iv-ACDpA' and quarters==12")
    cal=pd.read_csv(OUT/'iv-ACDpAI_q12_s0/investment_calibration.csv')
    source=json.loads((HERE/'benchmarks/IFE/provenance.json').read_text())
    tests=json.loads((OUT/'full_test_execution.json').read_text()) if (OUT/'full_test_execution.json').exists() else None
    parts=['''# Household investment, F and E — 23 October 2026

**Step 1 is implemented. Gate 1 fails: realized Q1 investment remains more
than 10% below the independent benchmark. F and E therefore did not start.**
Saving and constraint trends are reported, not used to stop this step. Phase B,
C_dp_005 and the heterogeneous buffer-stock rule remain on hold. Branch
feature/validation-2022, from e11ff6d; no push.

## Decisions, commits, tests and gates

| Step | Commit / tests | Result |
|---|---|---|
| 1a: read-only household cash ledger | de244bc; individual cash-identity regression passes | Seed-0 baseline reproduced within floating-point tolerance; directly measured Q12 investment 50.700811B including CF tax |
| 1b: initial GFCF level | f1e7b60; 3 focused checks including opt-in/relative propensity/initial-flow checks | One common multiplier, 0.95537 approximately; initial desired investment exactly 60.59825B/quarter, independently sourced |
| 1c: consumption priority | b75d4a7; 12 focused asset/budget/calibration/priority checks plus gate-boundary regression pass | Investment is cut first; no new spending parameter; stock/counterparty identities retained |
| 1d: link to dwellings | Proposal below | Not implemented |
| 2: F debt boundary/default | Not started | Gate 1 prevents entry; no new firm-debt pickle, allocation, N or recovery parameter |
| 3: E household payment default/foreclosure | Not started | No E or D3 rule in the candidate; old household rule retained |

Amounts are CAD billions; flows quarterly unless marked annual or 12Q totals.
Percentages are labelled; cuts are planned purchasers-price amounts before
market rationing. Constrained share means any D budget cut, including a cut
only to discretionary investment. The consumption-constrained share is also
retained separately in quarterly.csv; the definition is not changed to pass a gate.

## Gate 1 and seed comparison

The target is 60.59825B per quarter. Gate 1 requires accounting ≤1e-8 and
realized Q1 investment within ±10% of that level. It does not test saving or
the constraint trend. All three candidate seeds have their own 2Q accounting
run immediately before 12Q; runs are serial. F/E do not begin after a failure.
gate1.json is authoritative. The inherited manifest household_gate_passed
field is only the older Q1 consumption check, not this investment gate.
''']
    parts.append(table(gates,['seed','Q1_investment','quarterly_benchmark','gap_pct','gate1_pass'],money=['Q1_investment','quarterly_benchmark']))
    parts.append('''## Ledger first: what S-H7 actually does

The previous description “investment at 5% per quarter, not tied to income”
is incorrect. The 5% is depreciation, in households_configuration.py,
WealthFunction.other_real_assets_depreciation_rate. Desired investment is
DefaultHouseholdInvestment.compute_target_investment, investment.py:148:

I_basic[h,j] = weight[j] × investment_rate[h] × expected_income[h] / (1+CF tax).

households.py:732 calls it with current expected income, after income
expectations and before labour/housing/credit/goods clearing. The 13 regional
baseline rates are uniform within region, about 0.1364–0.2533. They originate
from the synthetic population's set_household_investment_rates (initial 0.2
seed, then rescaled to IO household capital inputs), not a 5% wealth rule.
All measured countries use assume_zero_growth=False; the fixed-initial-flow
branch is not active. Goods-market purchases are subsequently split into
consumption up to its target and residual investment. The realized basic
investment enters wealth_other_real_assets through update_wealth, with the
existing 5% quarterly depreciation. It does not add dwellings.

The read-only instrument captures every household before its insolvency
handler: paid consumption including VAT, investment including CF tax,
principal, interest, rent, new loans, OFA liquidation and deposit change.
It also records income, new OFA saving and property transactions, which are
necessary to close a household-level identity:

Δdeposits = income − C_with_VAT − I_with_CF − rent − interest − principal
            + new loans + OFA liquidation − new OFA saving
            − house purchases + house-sale proceeds.

Cash saving elsewhere in this report is income − interest − C_with_VAT − rent.
It excludes investment/principal. Liquidation is a stock conversion, not income.
Every individual identity closes to 1e-4 CAD absolute or better. Group ledgers
are available by quarter, decile, asset band and their cross-classification.
The household files remain locally under each run's micro/ledger_*.csv;
household_ledger_manifest.json records their hashes. Aggregates are committed.

### Baseline seed-0 paid spending, measured directly
''')
    parts.append(table(base,['quarter','consumption_VAT','investment_CF','principal','interest','rent'],money=['consumption_VAT','investment_CF','principal','interest','rent']))
    parts.append('### Baseline seed-0 financing and stock movement\n')
    cols=['quarter','income','new_loans','asset_liquidation','new_OFA_saving','house_purchases','house_sale_proceeds','deposit_change','cash_residual']
    parts.append(table(base,cols,money=cols[1:]))
    parts.append('''At Q12, direct investment is 50.700811B. It agrees with the old cash bridge's
implied value. This confirms the cash use, not excessive aggregate initial
investment: baseline Q1 paid I is 55.551B, already below the 60.598B quarterly
benchmark. Allocation, financing, stock destination and priority remain
separate questions. The earlier positive cash-saving figure was not accumulating
financial wealth. The new ledger distinguishes cash uses rather than
redefining saving to remove the overshoot.

### Q12 ledger by income decile and assets, baseline seed 0

Deciles are fixed national t0 income ranks with population weights. Asset bands
are t0 non-pension OFA per represented household: zero, 0–10k, 10–100k, >100k.
All quarters and all candidate seeds are in cash_ledger_decile.csv,
cash_ledger_assets.csv and cash_ledger_decile_assets.csv.
''')
    for frame,group in [(dec,'decile'),(assets,'asset_band')]:
        x=frame.query("arm=='iv-ACDpA' and quarter==12 and quarters==12")
        cols=[group,'consumption_VAT','investment_CF','principal','interest','rent','new_loans','asset_liquidation','deposit_change']
        parts.append(table(x,cols,money=cols[1:]))
    parts.append('''## Independent initial investment calibration

StatCan 36-10-0112, household sector Fixed capital, **v62305994**: 2022 quarterly
current-dollar SAAR values 269.468, 240.876, 225.284 and 233.944B/year. Mean
242.393B/year, or 60.59825B/quarter. Unadjusted v62306041 independently sums to
the same annual total. This is household-sector GFCF, including unincorporated
enterprises, not a consumer-durable allowance or net investment.

At initialization, one common propensity multiplier matches this purchasers'
price level using the existing expected-income base including funded D2.
Relative household/regional propensities, industry weights and dynamic
income dependence are retained. No realized outcome, saving rate, bank loss
or gate statistic enters calibration. Initial wealth/debt/housing stocks are
unchanged. Target investment is not reset to the benchmark every quarter.
''')
    levels=pd.DataFrame([dict(measure='Old initial recorded flow',quarterly=cal.old_initial.sum()),
        dict(measure='Old propensity on initial D2 expected income',quarterly=cal.old_desired.sum()),
        dict(measure='New initial desired / StatCan quarterly target',quarterly=cal.target.sum())])
    parts.append(table(levels,['measure','quarterly'],money=['quarterly']))
    parts.append(table(cal,['region','old_rate','new_rate','multiplier','target'],money=['target']))
    parts.append('### Retained initial goods basket (largest sectors)\n')
    basket=pd.read_csv(OUT/'investment_basket_national.csv').head(12)
    parts.append(table(basket,['industry_code','old_initial_purchasers','new_initial_purchasers','share'],
        money=['old_initial_purchasers','new_initial_purchasers'],percent=['share']))
    parts.append('Positive education/public-administration or other service weights cannot be verified as household fixed-capital uses from this industry vector alone. The asset-use mapping needs separate review; no claim that every such purchase matches SNA capital is made.\n')
    parts.append('''### Concept boundary and limitations

SNA household GFCF includes residential construction, renovations and
ownership-transfer costs plus unincorporated-enterprise fixed capital. Land,
within-sector existing-house purchase prices as such, ordinary repairs and private consumer
durables are not GFCF. The model retains its IO capital-input goods basket;
vehicles/equipment can be business capital, but industry alone does not
identify end use. No private car, furniture or training expense is newly
reclassified as investment to match the level.

The calibrated flow is an aggregate household-GFCF proxy. Existing purchases
still accumulate in a generic other-real-assets stock rather than distinct
dwellings/business capital. The IO basket does not separately identify new
houses, renovations and transfer fees, or verify each commodity's capital use;
a full asset-category concept reconciliation remains incomplete. Numerical
Gate 1 fails regardless, so no full concept-validation claim is needed to
permit a later step. The original S-H7 dwelling-stock concern remains open.

## Consumption priority under D

After senior obligations and available non-pension assets, allocate resources
to planned consumption first. Investment receives only resources left after
consumption, up to its plan. Cut investment within its existing sector mix;
reduce consumption within its own mix only after investment is zero. Existing
OFA liquidation books only actual cash need after clearing. The priority is
opt-in for this candidate; old controls/defaults remain reproducible. No new
numeric preference or gate-fitting parameter is introduced.

## Quarterly candidate results

Cash saving is compared with −0.601861%, the unchanged 2022 DI/C comparison
excluding D.8. Saving and constrained-share slopes are diagnostics only here.
The fixed investment comparison is 60.59825B/quarter, not a refitted path.
''')
    parts.append('### Budget versus consumption constraints at Q1/Q12\n')
    parts.append(table(q[q.quarter.isin([1,12])],['seed','quarter','constrained_share','consumption_constrained_share'],
        percent=['constrained_share','consumption_constrained_share']))
    for seed in range(3):
        parts.append(f'### Seed {seed}\n')
        cols=['quarter','constrained_share','investment_cut','consumption_cut','asset_liquidation','investment','consumption','cash_DI','cash_saving','cash_saving_rate','gdp']
        parts.append(table(q[q.seed==seed],cols,money=[c for c in cols if c not in ['quarter','constrained_share','cash_saving_rate']],percent=['constrained_share','cash_saving_rate']))
    parts.append('## Before/after realized household investment, seed 0\n')
    actual=q[q.seed==0][['quarter','investment','consumption']].merge(base[['quarter','investment_CF']],on='quarter')
    parts.append(table(actual,['quarter','investment_CF','investment','consumption'],money=['investment_CF','investment','consumption']))
    parts.append('## Household/firm losses and bank support\n\nThese retain both old default rules and the old firm-debt boundary; they are not F/E results.\n')
    cols=['seed','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation','resolution_events','min_capital_ratio']
    parts.append(table(s,cols,money=cols[1:6],percent=['min_capital_ratio']))
    parts.append('### Quarterly losses and recapitalisations\n')
    cols=['seed','quarter','household_writeoffs','firm_loan_losses','overdraft_losses','bank_losses','recapitalisation']
    parts.append(table(q,cols,money=cols[2:]))
    parts.append('''Full by-industry firm failures, by-bank capital ratios, resolution events
and new-loan vintages remain in their named CSV panels. Minimum ratios above
are model end-quarter equity/loans, not CET1/RWA. Support is not netted from losses.

### Firm debt before/after

| Item | Before | After |
|---|---:|---|
| Initial firm loan debt | 2,271.807B (accepted model audit) | Unchanged |
| Intercompany consolidation / external bank-credit boundary / O/P/Q | Legacy | F not entered; unchanged |
| Industry allocation and default trigger | Legacy | Unchanged |
| io2022_household_agreed_bankcap_firmdebt.pkl | Not built by this task | Not built |

F industry before/after tables and E foreclosure/recovery tables would imply
an implementation that did not occur. No provisional/final N or haircut is
chosen; E and D3 are not enabled.

## Deferred dwellings proposal (1d), not implemented

Separate the capital budget into new residential construction, renovations,
ownership-transfer costs and unincorporated-business capital using asset-use
data. Exclude personal consumer durables and non-produced land. Builders'
production/input costs, work in progress and completed units must reconcile
to purchaser finance before adding properties to the housing market.
Renovations should improve existing structures without automatically creating
units; transfer fees require separate capitalization and depreciation.
Allocate each completed dwelling to an owner/property ID, distinguish structure
from land, and link new mortgages, cash payments, occupancy and later rents.
Existing-house trades remain transfers, not newly produced dwellings.
Redirect each residential capital flow out of the generic other-real-assets
addition when recognized as a dwelling, so a purchase does not create both stocks. Replace
the generic stock/depreciation treatment only with independently sourced
residential/business capital stocks and service lives. Do not add a housing
producer without its costs or duplicate the existing F-sector output.

## Recommendation

Gate 1 fails on realized capital purchases despite a correct initial target.
Consumption priority reduces investment whenever household resources bind;
rescaling propensities to undo that cut would fit the gate and is not done.
The next unresolved investment issue is the allocation and funding of capital
projects, including their dwelling/business destination, rather than a proven
5%-of-wealth investment error. Firm feedback remains uncorrected because F is
gated. Review planned investment, affordability and the realized-investment
gate separately before changing the instruction sequence.

Household/firm losses and recapitalisations remain economically unvalidated;
legacy firm/default problems prevent a plausibility claim. The buffer-stock
rule stays deferred: these results do not establish that it is necessary or
sufficient, and it would not by itself identify/fund household capital projects.
The model is **not ready for Phase B**. Stop for review before F/E.

## Provenance and verification

Investment benchmark selection, exact vector/date/values, full upstream CSV/ZIP
hashes, local extract hashes and concept-source snapshot are in
benchmarks/IFE/provenance.json. Official sources:
[36-10-0112](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201),
[capital concepts](https://www150.statcan.gc.ca/n1/pub/13-017-x/2008001/themes/ch09/5213371-eng.htm),
[residential components](https://www150.statcan.gc.ca/n1/pub/13-017-x/2008001/themes/ch09/5213372-eng.htm).
The cached source retrieval date is 2026-10-23. The same table's v62305982
(1,511.382B annual C) and v62305981 (1,502.340B annual cash-comparison DI)
retain their accepted provenance for −0.601861% saving excluding D.8.
Prior RBC/TransUnion/OSB orders-of-magnitude sources remain under benchmarks/ABCD/;
no source level is fitted and F/E comparisons are not claimed.

Manifests retain head, exact input/source hashes, quarter count and seed.
The read-only baseline is frozen at de244bc; corrected pairs at b75d4a7.
Its numerical paths reproduce the accepted AFE seed-0 baseline, and the direct
ledger confirms the implied investment. Every short run reproduces its long
run's first two quarters. Household-level flows and aggregates reconcile;
OFA/pension bounds, D2 funding and accounting identities are checked. All
accepted input hashes are preserved. Historical source hashes are checked
against their git version, allowing Windows/Unix newline representations.
''')
    parts.append('### Full suite\n')
    if tests:parts.append(f"**{tests['passed']} passed; {len(tests['failures'])} known NaN failures, zero additional failures/errors.** run_pre_D3_tests.py; sampler n_cores=1. Failure identities are checked against AFE. JUnit, logs and audit are in outputs/IFE/.\n")
    else:parts.append('Pending; draft.\n')
    parts.append('Original macroabm-ca, ITC/user-cost files and accepted pickles unchanged. No new pickle built. Nothing pushed. Stop for review.\n')
    (HERE/'CLOSURE_IFE_2026-10-23.md').write_text('\n'.join(parts),encoding='utf-8')


if __name__=='__main__':main()
