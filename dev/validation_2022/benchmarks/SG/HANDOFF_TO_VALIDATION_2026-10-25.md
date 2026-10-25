# Handoff: balanced 2022 SUT for macroabm-ca-validation (2026-10-25)

From `macroabm-io2022`, branch `feature/sut-balance`; nothing pushed. Full report: `SUT_BALANCE_2026-10-25.md`.
Nothing in `macroabm-ca-validation` was touched. This is an input for a dedicated adoption step; it doesn't block current work.

## What changed

- **The 48.3B row/column adjustment came from imported re-exports** that had been booked as Canadian producer sales. They're now excluded from the Canada→ROW blocks and kept in a satellite file. Canadian margins on re-exports (0.65B, in G/H49/H52) stay as exports.
- **The 26.5B "input-product valuation" was an `output_basic` bug.** That column now includes net product taxes on intermediates.
- **In the new canonical table, every region × industry balances**, sales = costs, to about 1e-5 M. The three GDP approaches agree in every region. Both are now hard build checks.

## Effect on the model input

- **Reader-implied VA falls by 48.4B, to observed VA6.** In the compatibility file it goes from 2,722.5B to 2,674.1B, against VA6 of 2,674.2B. The legacy reader derives VA as row output − inputs, so the overstatement disappears without any reader change.
- **International exports in the table fall by 48.4B**, from 965.8B to 917.4B. Imports in use are unchanged at 902.5B. GDP at basic prices is unchanged.
- **Expect firm GOS and profits at t0 to fall by about 48B a year nationally.** Most of the fall is in goods-exporting industries in ON, QC and AB (C29, C28, C26, C302T309, C21, C20).
- **Not in this file: the 100.504B of other production taxes less subsidies (F-A1).** They are inside VA6, but the model doesn't charge them. That stays a model-side step.

## How to adopt (validation session, dedicated step)

1. Point a **new, separately named** 2022 datawrapper build at `macroabm-io2022` @ `feature/sut-balance`, file `compatibility/compat_icio_2022_can_provinces.csv` (SHA-256 `41590fdb19d9eb79758169b51afc0751e6d5c19ce88183bb8fbe330889e689aa`). Keep the accepted pickles unchanged.
2. Re-run the FB GDP-initialisation checks for all 13 regions, plus the net-surplus cost gate. The 74.883B expenditure excess should be gone, apart from the documented 0.122B CE residual in the compatibility view.
3. Re-check t0 firm margins and the industries flagged earlier; I, H53 and A02 are not directly affected.
4. Only then combine with F_CFC, the CIS income fix and the investment reallocation, one at a time, with seeds 0–2.
