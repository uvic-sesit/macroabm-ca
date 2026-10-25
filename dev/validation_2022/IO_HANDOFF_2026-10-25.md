# IO pipeline handoff — 2026-10-25 (UTC)

Read-only handoff from `macroabm-ca-validation/feature/validation-2022`. The `macroabm-io2022` pipeline, accepted input files and original model repository were not modified. FB remains an unaccepted experiment. Passing its revised **net**-surplus cost gate does not repair the independent GDP imbalance.

## Outstanding national 2022 valuation bridge

| Item | B CAD/year | Treatment needed |
|---|---:|---|
| Sales row/column adjustment | 48.337550 | Identify and reconcile actual product/industry supply-use transactions; do not invent buyers. |
| Input-product taxes less subsidies | 26.545927 | Reconcile purchaser/basic valuation and tax allocation across intermediate/final uses. They are not other taxes on production. |
| Expenditure excess | 74.883477 | The two preceding items sum, up to rounding, to this unresolved excess. No cash, trade or inventory plug is approved. |
| Other taxes less subsidies on production | 100.503564 | Preserve signed taxes/subsidies in the income/value-added bridge; do not confuse with product taxes or force positive NOS. |

Source: 2022 provincial detailed SUT, StatCan **36-10-0478**, mapped to OECD50. Canonical vectors PRM100000/200000/300000/400000/500000/600000/700000/800000; exact source metadata retained in `outputs/QE/bridge/provenance.json`, checked 2026-10-25T01:29:25.281015+00:00.

Source hashes (read-only):

- `VA_tax_output_basic.csv`: `20a066ee3190cad9b9217184646da73c7a3a1d550e647c1a1a6b2245f6faaa10`
- `SCHEMA.json`: `ce864fe7dcaf173338723da9ab59c92528feebd7140fb889e9ad9e4e8ec712ee`
- `concordance_statcan_to_oecd50.csv`: `b5b21b085d07734f760a9b971d8365c6271fa46b288140ec6aa1e0a6776108ca`

The accepted F_CFC pickle SHA256 is `a16386b64e0eeca5986dc1d4a3d94a4a7c0b33b178f76e1a8933e926948677ae`; unaccepted FB SHA256 `8d50412140c5483b06f6b5007dccaea84960299fa3f0ddc182c89f7556d3aa8d`. Source GOS is gross; the corrected cost test subtracts observed CFC. FB passes that revised criterion (maximum gap under .001 pp, zero above-price/nonnegative-NOS exceptions). F_CFC does not. Do not repeat the rejected gross-GOS criterion.

## A balanced SUT needs

1. A province/product/industry reconciliation of basic-price output and intermediate uses with final C, government consumption, GFCF, inventories, exports and imports, on a common annual reference and institutional/housing scope.
2. Explicit purchaser-to-basic-price bridges for trade/transport margins, product taxes/subsidies and import valuation, with taxes allocated to their actual uses. Preserve separate signed other-production taxes in GVA/income.
3. A documented treatment of the 48.338B row/column adjustment: reconcile its sources rather than moving it into fictional sales, profits, cash, inventory or trade.
4. Source-zero industries should not become operating producers through positive placeholders. Inactive holders retain outstanding financial obligations and capital; no debt forgiveness is implied by zero source output.
5. Initial investment must be benchmarked independently: current F_CFC t0 acquisitions retain a **depreciation proxy**, not observed GFCF. Reconcile private business, government, NPISH and household/dwelling scopes, and actual capital formation versus CFC. The IH read-only mapping residual of 1.658B/year must also remain visible.
6. Validate all 13 regional supply-use, production/income and expenditure identities independently, then the national sum. The legacy initializer's second output/income assertion repeats the output/expenditure operands; passing that repeated check is not independent income validation.

The IH housing correction removes the extra 64.132B/quarter t0 housing memo from GDP when sector L already contains housing services. It does not provide additional supply-use transactions or cure the 74.883B/year imbalance. Cash rent remains in household/landlord ledgers. No pipeline implementation or additional build is authorised by this handoff.
