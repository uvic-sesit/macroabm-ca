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

### Added 2026-10-14 (write-off and firm audits)

| Benchmark | Table | Series | Ref. period | Concept / coverage | Value | File |
|---|---|---|---|---|---:|---|
| Household obligated principal payments: non-mortgage / mortgage | 11-10-0065-01 | — | 2022, mean of 4 SAAR quarters | households, NBSA debt service indicators | 60,172 / 58,695 | read from StatCan table viewer (no file download) |
| Debt service ratio (total / mortgage / non-mortgage) | 11-10-0065-01 | — | 2022 Q1–Q4 | % of disposable income before interest | 13.81–14.62 / 7.18–7.84 / 6.63–6.80 | 〃 |
| Income-based GDP, Canada | 36-10-0221 | 1.1 CoE / 1.4 GOS / 1.5 NOS corp. / 1.6 CFC corp. / 1.7 CFC gov+NPISH / 1.8 gross mixed / 1.10 CFC unincorp. / 1.11 TLS on production / 1.12 TLS on products / 1.14 GDP | 2022 annual | | 1,387,017 / 874,554 / 503,658 / 278,541 / 92,355 / 312,829 / 87,988 / 100,505 / 189,200 / 2,864,159 | `raw/dbn_36100221.json` |
| Expenditure-based GDP | 36-10-0104 | 1.2.1.11 business GFCF / 1.2.1.10 GFCF / 1.2.1.18 gov GFCF / 1.2.1.19 inventories / 1.2.1.20 business inventories | 2022, mean of 4 SAAR quarters | | 556,433 / 661,124 / 101,425 / 55,687 / 54,603 | `raw/dbn_36100104.json` |
| Balance sheet, non-financial private corporations | 36-10-0580 | 1.8.1.x (market value) | 2022-Q4 | deposits 1.8.1.16 = 873,676 (Canadian 1.8.1.17 = 683,786); loans (liab.) 1.8.1.67 = 2,448,640 (non-mortgage 1.8.1.69 = 925,316; mortgages 1.8.1.70 = 356,299; intercompany 1.8.1.71 = 1,164,071); debt securities 1.8.1.55 = 644,168; inventories 1.8.1.9 = 398,821; fixed assets 1.8.1.107 = 2,223,423; equity 1.8.1.73 = 5,427,400 | | `raw/dbn_36100580_nfc.json` |
