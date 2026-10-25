# 2022 start validation — stock-take (2026-10-25)

Branch `feature/validation-2022`, as of round ZA `9b556cb`. IO pipeline: `esizadi/macroabm-io2022`, branches `feature/sut-balance` (d847fb2) and `feature/ooh-split` (eb40128). Phase B and C_dp_005 remain on hold.

## Diagnostic baseline

**FS_T v4** is recommended, subject to review: `dev/pkl_files/io2022_fs_t_za_v4_2026_10_25.pkl`, SHA256 `0ef644b3…cc2a6`. It combines:
- F_CFC: the agreed household, bank-capital and firm-debt build with observed CFC (36-10-0096);
- the balanced 2022 SUT (re-exports excluded, output including product taxes on inputs);
- 100.5B of signed production taxes charged to firms, with the government counterpart;
- the zero-activity convention: 68 source-zero cells on the 1M floor path, plus an effort guard.

F_CFC (`io2022_household_agreed_bankcap_firmdebt_cfc_v2.pkl`) is kept as the historical comparator. Pickles are local only: they are untracked and hold synthetic household records.

## Solved, with gates passing

| Area | What was wrong | Fix / round |
|---|---|---|
| Stock-flow accounting | Money leaks; unnamed flows | Every flow has a counterparty; battery error about 1e-14. Named boundaries: A11 interest on public debt with no holder; A12 no ROW financial account (Phase A to QE) |
| Household and bank balance sheets | Bank capital 14× too large; write-off wave | Agreed household build; bank capital 456B observed |
| Firm depreciation | Proxy | Observed CFC from 36-10-0096 (F_CFC) |
| GDP reporting | 64B housing double count; income check duplicated the expenditure check | IH (`c1712b7`, `3557989`); SG (`2ef7a32`) |
| IO table | 74.9B row/column imbalance: 48.4B imported re-exports plus 26.5B output valuation | Balanced SUT in the pipeline; hard row = column and three-approach GDP controls |
| Production taxes (F-A1) | 100.5B not charged to firms | FS_T |
| Zero-output sectors | NaN abort (CAN_NL C21) | ZA `1ffdc06` |
| Defaults | Wealth-based defaults | E/E2 payment-based default (opt-in) |

## Open problems, by importance

1. **No-shock contraction.** Real GDP falls 7.6–9.3% over 12 quarters (FS_T, seeds 0–2). Household losses of about 234B are invariant across arms and seeds and front-loaded (about 85B in Q1). The constrained share rises steadily from 19% to 50%. Diagnosis: the household cash position at start, not behaviour.
2. **Housing cash/noncash.** Owners' imputed rent (235.9B) is bought for cash from L firms, and L firms book OOH income as corporate surplus (204.7B, including property tax). The exact split (eb40128) moves the planned gap from +96B to −73B and planned dissavers from 72% to 37%. It must be built at household level, by dwelling value, with the basket on market L only; post-hoc subtraction creates negative residuals. The cash income/saving benchmark must be restated as well. Dwelling CFC (36-10-0099) is pending.
3. **Household income allocation.** Too concentrated at start. The CIS candidate's error is 13.3% before tax and 12.1% with a progressive-tax diagnostic, against a 10% gate. Needs a traceable household rebuild (donor and member IDs) plus a progressive PIT calibrated to the observed tax total.
4. **Investment start (FSG).** The inherited allocation is badly wrong (for example I: 49.4B against 4.4B observed). FSG is blocked by 3.5B/yr of negative GFCF uses: SNA disposals of used assets (scrap metals C24A/B, used vehicles via G), all in business M&E. Needs a signed disposal account.
5. **Defaults about 8× too high.** Mostly downstream of problems 2 and 3.
6. **Later.** Government debt holder (A11) and banking audit; firm behaviour (pricing, capacity, investment expansion, deferred); Phase B with 20–50-seed Monte Carlo; Bayesian estimation.

## Next round

- **IO pipeline:** dwelling CFC from 36-10-0099; a market-L compatibility variant (OOH out of L firms, imputed rent as noncash memo, owner cash costs as household purchases and taxes); a note on the negative GFCF entries.
- **Validation:** household-level housing closure on FS_T; restated cash benchmark; seeds 0–2; check whether the constrained-share drift flattens.

## Repository hygiene

- The pushed branch is a slimmed copy: `dev/validation_2022/outputs/` is removed from history, and the commit map is in `COMMIT_MAP_slim.md`.
- Full evidence outputs are archived locally in `SESIT/local_archives/`, with a SHA256 manifest.
- The local branch keeps the original history, which is what the reports' commit hashes refer to.
