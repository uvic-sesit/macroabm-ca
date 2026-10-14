# Phase A report — household starting point and transaction accounting (2022)

Branch `feature/validation-2022` (local, not pushed). Pre-correction reference: tag
`validation-2022-precorrection` (= `ab87ee2` + Stage 1–3 docs) with the branch-rebuilt pickle
`io2022_13prov_2022_canadianized_branchab87ee2.pkl`. Corrected pickle: `dev/pkl_files/io2022_phaseA.pkl`
(sha256 `a052868d…34ea`; previous Phase A build kept as `io2022_phaseA_v1.pkl`). Canonical ITC pickle untouched.
Units: $B CAD; flows quarterly (model) unless marked /yr.

## 1. What changed (dependency order)

| Batch | Change | Type |
|---|---|---|
| 1 Counts | household counts and owner rates per region: CHS 2022 (46-10-0083) for provinces, Census 2021 (98-10-0232) for territories; tenure-stratified sampling (owners = codes 1, 2, 4) | data |
| 2 Wages/UB | households receive cpi·Σw; PIT/SSC on the gross base; UB credited (no cpi/inflation factor); t0 wages renormalised to firm wage bills; effective PIT 0.1736 (36-10-0224) | accounting / data |
| 2 Cash | VAT debited from households; firms pay for purchases (cash) instead of inputs used; deposits debited for spending beyond deposits (A16); bank deposit interest = customers' individual payments + CB interest (A17) | accounting |
| 2 Loans | other-property mortgages (653B) on the loan book; explicit write-off counter | accounting / data |
| 3 Housing | t0 occupancy bug (`fillna(-1)` on all property fields) fixed; tenure codes in demand rule; feasible matching (WTP, no self-purchase); only executed sales paid, seller credited; seller must move; vacancy/listing logic; renter never matched to own unit (build); property counts consistent with SFS values; rental-income rescale on private renters only | accounting / data |
| 3 GDP | provincial IO keeps paid + imputed rent in household purchases of sector L; flag stops GDP adding rent again (−218B/yr double count); imputed rent from HFCE 36-10-0124 | accounting |
| 4 Saving/credit | income-weighted mean saving rate (reproduces t0 consumption); consumer credit (lines, cards) retained | data |

Not changed (per instructions): consumption functional form, behavioural parameters, credit screens,
insolvency rule, paid-rent level. The Canadian rent level was implemented and **reverted** (see D1).

## 2. Results

**t0 balance sheet vs 36-10-0580 (households):** deposits +0.1%, dwellings 0.0%, mortgages +0.6%,
liabilities −0.4%, net worth −0.5%; consumer credit 743B. Households 15.50M (+0.3% vs CHS+Census).

**First quarter (static) jumps:** labour income −22.2% → +0.001%; consumption −8.5% → +0.001%.

**Accounting battery** (national, $B/q, 2 quarters, shipped default, seed 0):

| Residual | Pre-correction Q1 / Q2 | Phase A Q1 / Q2 |
|---|---|---|
| wages (firm bill − receipts − labour taxes) | 44.1 / 48.6 | 0 / 0 |
| UB (paid − received) | 3.1 / 3.9 | 0 / 0 |
| house sales (paid − received) | 9.3 / 4.9 | 0 / 0 |
| rent (paid − received − PIT − social) | 3.0 / 3.0 | 0 / 0 |
| household cash identity | 1.9 / 28.6 | 0 / 0 |
| loan stock identity | −843.8 / −20.9 | 0 / 0 |
| bank snapshot / bank equity links | — | 0 / 0 |
| **reserves unexplained** | −24.6 / +1.2 | **−0.053 / −0.056** |
| of which goods-market pricing gap (D6) | — | −0.053 / −0.056 |

Every remaining reserve movement is now attributed to a named term. The named boundary terms (FA income without
payer, OFA without issuer, write-offs, firm-deposit zeroing) are reported separately, not concealed.

**Tests:** `tests/test_validation_2022` — 16 pass. Existing suite: see §5.

## 3. Decisions needed (escalated)

| ID | Issue | Evidence | Options |
|---|---|---|---|
| D1 | Paid rent / sector L boundary | 81.5B paid rent is already inside household purchases of L (L FD 312.7B ≈ paid 81.5 + imputed 235.9). No corporate landlords. With Canadian rent levels household landlords earn ≈10% gross yields and the build sends ≈10% of households to social housing | (a) housing services stay in sector L; household rent market is a transfer layer only (current); (b) move paid rent to the housing module and remove it from L FD; (c) add a corporate landlord sector |
| D2 | Missing household accounts | income 1,335B vs DI 1,502B: no mixed income (225B), dividends, transfers from corporations (121.5B). Calibrated mean saving rate −9.8% | add distribution flows (architecture) or accept and document |
| D3 | Insolvency write-offs | 268B (Q1) and 43B (Q2) written off: households with NW<0 and deposits<0 default immediately; previously hidden by A16 | change rule / grace period / write-offs hit bank equity (A14) |
| D4 | Credit screens | LTI/LTV/DSTI 0.05 shut household credit | Canadian B-20 type limits |
| D5 | Provincial income distribution | one national survey file for all provinces | provincial controls |
| D6 | Goods-market pricing | buyers pay the industry average price, sellers receive own price × quantity: −0.05B/q leak (0.005–0.07% of sales) | buyers pay the realised seller-weighted price (changes the market clearing code) |
| D7 | Housing mobility | high churn of owner-occupiers through the market | mobility parameter |
| D8 | Boundary terms A4, A7, A11, A12, A14 | FA income without payer; OFA without issuer; unpaid public-debt interest; no ROW financial account; write-offs without bank loss | architecture |
| D9 | Wage equalisation, interest rates (I-10, I-11) | data | after D1–D2 |

## 4. Provenance of previous ITC runs

All ITC/user-cost scripts load the canonical pickle `io2022_13prov_2022_canadianized.pkl` (sha `4e103fd5…0d67`,
19 Aug). `closure_feedback_exp.py` additionally replaces social transfers at run time with the SOCX cash-benefit
level (`_apply_public_cash_benefits`), so its runs differ from the others in transfer level. All ran on
pre-correction code: every property was unoccupied at t0 (no rent ever paid), and the wage, UB, VAT, sales and
firm-purchase leaks above were present.

## 5. Existing test suite

Full `tests/` on this branch: 354 passed, 31 failed (35 min). After updating
`test_property_probability.py` to the model's tenure codes (renter = 3; the test encoded the old 0/1 convention
that Phase A corrected): 30 failures, all `ValueError: Nan in transactor_total_real_supply` on the French test
datawrapper — the same 29 `test_simulation.py` failures as the pre-correction reference (29 failed, 210 passed in
`tests/test_macromodel`), plus `test_macrocalib/unit/test_sampler.py`, which fails identically on the
pre-correction worktree. No regressions.

## 6. Proposed Phase B (controlled short baseline)

| Setting | Value |
|---|---|
| Arms | (P) pre-correction: worktree `C:/vwt/precorr` (tag) + branch pickle; (A) Phase A: this branch + `io2022_phaseA.pkl` |
| Config | shipped default `CountryConfiguration.n_industry_default`, all 13 regions, identical `build_config` |
| Horizon | 12 quarters (2022Q1–2024Q4) |
| Seeds | 0 for the main comparison; seeds 1–4 for dispersion (Phase A arm only, then P if needed) |
| Battery | `AccountingBattery` post-hook every quarter; acceptance: all named identities < 1e-6 relative; reserves_unexplained = goods-market gap |
| Outputs | national and provincial GDP (3 measures), C, I, G, X, M, employment, CPI, household income, saving rate, deposits, debt, write-offs vs StatCan 2022–2024 quarterly |
| Execution | one simulation at a time; h5 outputs off or written outside OneDrive |
| Decision gate | D1, D3 and D4 change dynamics materially; run Phase B before and after the chosen options only if you want the attribution |
