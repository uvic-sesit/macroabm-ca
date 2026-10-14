# External benchmarks — provenance

Retrieved 2026-10-13. DBnomics mirror of StatCan (`indexed_at` 2026-09-30T02:23Z). Raw responses are in `raw/`.
Units: $M CAD current prices unless stated. "Concept" notes the SNA definition used.

| Benchmark | Table | Series | Ref. period | Concept / coverage | Value | File |
|---|---|---|---|---|---:|---|
| Compensation of employees | 36-10-0224 | 1.1 | 2022 annual | Households (excl. NPISH), current accounts | 1,378,529 | `raw/dbn_36100224.json` |
| Net mixed income | 36-10-0224 | 1.2 | 2022 | incl. rental income of households (1.5) | 224,841 | 〃 |
| Rental income of households | 36-10-0224 | 1.5 | 2022 | net, incl. owner-occupied | 127,567 | 〃 |
| Net property income / received / paid | 36-10-0224 | 1.6 / 1.7 / 1.8 | 2022 | | 162,377 / 246,588 / 84,211 | 〃 |
| Primary income | 36-10-0224 | 1.9 | 2022 | | 1,765,747 | 〃 |
| Transfers received / from gov / EI / social security / other | 36-10-0224 | 1.11 / 1.14 / 1.15 / 1.16 / 1.17 | 2022 | | 422,524 / 286,670 / 20,631 / 81,282 / 184,757 | 〃 |
| Transfers from corporations / NPISH / non-residents | 36-10-0224 | 1.13 / 1.12 / 1.18 | 2022 | | 121,500 / 11,021 / 3,333 | 〃 |
| Transfers paid / PIT / social contributions | 36-10-0224 | 1.19 / 1.23 / 1.25 | 2022 | | 685,931 / 348,148 / 131,280 | 〃 |
| Disposable income | 36-10-0224 | 1.27 | 2022 | B.6n | 1,502,340 | 〃 |
| HFCE | 36-10-0224 | 1.29 | 2022 | P.3 | 1,511,382 | 〃 |
| Net saving | 36-10-0224 | 1.30 | 2022 | B.8n = B.6n − P.3 + D.8 | 31,543 | 〃 |
| Saving rate | 36-10-0224 | 1.31 | 2022 | B.8n / B.6n, % | 2.1 | 〃 |
| Change in pension entitlements | 36-10-0224 | 1.32 | 2022 | D.8 | 40,585 | 〃 |
| HFCE: paid rent | 36-10-0124 | 1.1.1.17 | 2022 (Σ of 4 SAQR quarters) | | 81,506 | `raw/dbn_36100124.json` |
| HFCE: imputed rent | 36-10-0124 | 1.1.1.18 | 2022 (Σ SAQR) | | 235,938 | 〃 |
| HFCE total (cross-check) | 36-10-0124 | 1.1.1.1 | 2022 (Σ SAQR) | equals 36-10-0224 v1.29 | 1,511,382 | 〃 |
| Balance sheet, households only | 36-10-0580 | 1.4.1.x | 2022-Q4 | market value; assets 1.4.1.1 = 18,298,593; NW 1.4.1.84 = 15,404,785; deposits 1.4.1.16 = 2,034,716; FA 1.4.1.14 = 9,190,499; dwellings 1.4.1.4 = 3,622,290; land under dwellings 1.4.1.114 = 4,167,482; durables 1.4.1.8 = 878,804; liabilities 1.4.1.50 = 2,893,808; mortgages 1.4.1.70 = 2,126,996; consumer credit 1.4.1.68 = 597,597; non-mortgage loans 1.4.1.69 = 132,335 | | `raw/dbn_36100580_q.json` |
| Balance sheet, HH + NPISH (handoff figures) | 36-10-0580 | 1.3.1.x | 2022-Q4 | assets 18,560,868; NW 15,602,290; deposits 2,092,422; residential mortgages 1.3.1.105 = 2,118,372 | | 〃 |
| Households by tenure | 46-10-0083 (CHS) | provincial, "Total, household type", Number of households | 2022 | private households, provinces only (excl. territories) | Canada 15,455,000; owners 10,109,100 | `raw/statcan_46100083/` (WDS full-table CSV) |

Not yet retrieved (needed before confirming suspected items): Bank of Canada effective household interest
rates for 2022 (I-11); provincial household DI (36-10-0229 or DHEA by province); 2022 government sector
accounts (36-10-0477 / 36-10-0118) for the government audit.
