# Household correction benchmarks — retrieved 23 October 2026 UTC

Amounts below are current CAD, not fitted model outcomes. Full-table download
hashes and selection rules are in the adjacent `*_provenance.json` files.
The selected CSVs retain StatCan vectors, coordinates, units and statuses.

| Use | Official source, reference period and selection | Value / interpretation |
|---|---|---|
| D2 dividends | [36-10-0482-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610048201), annual 2022, Canada, `Dividends`, v80013659, coordinate 1.12; provincial equivalents determine geographical allocation | 92,052 million gross household receipts, before PIT. This is the identified domestic distribution target; do not add the entire property-income receipt of 246,588 million as dividends. |
| D2 other receipts | [36-10-0224-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610022401), annual 2022, Canada; existing cached `../raw/dbn_36100224.json`, series 1.2 minus 1.5 and 1.13 | Nonrental mixed income 224,841 − 127,567 = 97,274 million; current transfers from corporations 121,500 million. Cache retrieved 13 October, indexed 30 September 2026. |
| Saving comparison | [36-10-0112-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610011201), Canada, four 2022 seasonally adjusted annual-rate quarters, equal-weight mean of flow levels | DI 1,502,340; HFCE 1,511,382; pension adjustment D.8 40,585 million. Net saving 31,543 / DI = 2.0996%; excluding D.8, −0.6019%. Average flows before computing the annual ratio. |
| H7 total real estate and mortgages | [36-10-0580-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610058001), households, market value, 2022 Q4 | Dwellings 3,622,290 + underlying land 4,167,482 = 7,789,772 million; mortgage liabilities 2,126,996 million. Inherited `dev/io2022/household_prototype/controls_2022.json`; raw source is shared read-only. |
| H7 mortgage split and underwater fractions | [SFS 2023 economic-family PUMF, 13M0006X](https://www150.statcan.gc.ca/n1/en/catalogue/13M0006X), PWEIGHT × PWDPRMOR/PWDSTOMR; compare with PWAPRVAL/PWASTRST among positive mortgage holders | Main / other mortgage balances 1,556.804 / 467.615 billion; shares 76.901 / 23.099%; underwater 0.8249 / 9.1440%. These are survey families in 2023, not a second 2022 NBSA control. |
| H7 wealth distribution | [36-10-0660-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610066001), Canada, 2022-10, `Distribution of value`, `Net worth (wealth)`, income quintiles | 11.5 / 11.1 / 14.9 / 22.3 / 40.2%. Model income ranking is mapped gross income; DHEA uses equivalized disposable income. Diagnostic, not an exact like-for-like distributional target. |
| D4 effective amortization | [11-10-0065-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110006501), inherited 2022 principal-payment benchmark, mean of four SAAR quarters | Nonmortgage principal 60,172 and mortgage principal 58,695 million annually. Initial loan stocks divided by quarterly flows give 49 / 145 quarters. Original audit read the table viewer; no downloaded snapshot exists for this inherited benchmark. This provenance limitation is retained explicitly. |

`h7_diagnostics.py` saves hashes of the exact SFS and 36-10-0660 source files.
`benchmark_manifest.json` additionally hashes the inherited controls and cached
income source. Repeated-source mirrors and vintages can differ from later revisions.

D2 uses the observed **household receipts** rather than all corporate dividends
paid, which include payments to other corporations, government and nonresidents.
The corporate 36-10-0116 download is a cross-check only and is not a payout target.
The published detailed household table labels the receipt `Dividends`; no separate
unverified corporate-withdrawal residual is added. Within each province, total financial
wealth (including the synthetic aggregate's deposits and pensions) plus
self-employment business value proxy distribution recipients; this is
an allocation assumption, not an estimate of individual dividend entitlements.
Pension assets allocate current transfers from corporations, which include pension
benefits/withdrawals; paying them through representative firms remains a funded
proxy for the absent pension-institution accounts.

The D4 single 80% origination limit deliberately models uninsured loans only.
There is no insurer premium, guarantee asset or insurer balance sheet. Existing
insured loans up to 95% LTV remain in H7. An insured origination channel needs those
counterparties before it can be called a Canadian insurance specification.
[OSFI's loan-to-income threshold](https://www.osfi-bsif.gc.ca/en/supervision/financial-institutions/banks/loan-income-limits-uninsured-mortgage-portfolios)
is a portfolio supervisory measure from fiscal 2025, not a 2022 individual cap.
The 4.5-times disposable-income and 40% service screens are scenario assumptions.
