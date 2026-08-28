# User-Cost ITC Sequencing And Propagation Checkpoint

Date: 2026-08-27

Branch: `feature/itc-user-cost`

Previous checkpoint: `4e7ee865ed95a8657f12b72dac5bd8b0870803b5`

## Current Benchmark

The current user-cost benchmark remains Design B:

```text
K*_ij,ITC = K*_ij,base * (1 - tau * s_i,t-1)^(-eta_I)
```

where `s_i,t-1` is the lagged value-based C27/C28 share in the firm's planned capital bundle. The interpretation is project-wide desired gross investment: the ITC lowers the effective user cost of a broader investment project in proportion to eligible exposure.

The policy remains `tau = 0.30`, active only over 2026-2030. It does not directly change `Q*`, TFP, credit, `extra_taxes`, production taxes, or government accounts.

## Existing Diagnostics

Design A is retained as an asset-only diagnostic:

```text
K*_ij,ITC = K*_ij,base * (1 - tau)^(-eta_I) for j in {C27, C28}
K*_ij,ITC = K*_ij,base otherwise
```

It is treated as a lower-bound case because it raises desired C27/C28 demand without intentionally scaling complementary non-eligible capital.

Design B sensitivity results, cumulative 2026-2030:

| eta_I | Delta investment | Delta GVA | Delta target production | Delta realized production | Gross ITC fiscal cost | Eligible-purchase additionality |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50 | 57.6773 B | 57.6403 B | 86.5490 B | 120.7140 B | 63.2381 B | 0.0179 |
| 0.75 | 83.0653 B | 82.3830 B | 123.2890 B | 171.4149 B | 63.7296 B | 0.0255 |
| 1.00 | 105.9296 B | 103.9992 B | 153.9069 B | 215.4617 B | 64.1707 B | 0.0322 |

Gross fiscal cost remains around `63-64 B` across comparable Design B variants because it is computed on total treatment eligible purchases, not incremental eligible purchases. Eligible-purchase additionality remains low.

## Artifact And Mechanism Audit

Audits so far found:

- no double application of the user-cost multiplier;
- intended lagged planned-bundle timing for `s_i,t-1`;
- policy off after 2030;
- small direct Design B wedges, with eta `0.50` median multipliers near `1.009`;
- desired and realized capital purchases matching in aggregate in the saved runs;
- fiscal cost zero after 2030 in the reporting harness.

Some cell-level capital-binding diagnostics were limited to PROV10 or to lightweight captures, so they should be treated as diagnostics rather than definitive national microdata documentation.

## WP-Vs-UC Propagation Finding

Matched diagnostics comparing WP scale bridge `eps = 1` with user-cost Design B `eta_I = 0.50` showed that fairly similar 2026-2030 investment can generate very different realized production and GVA because the mechanisms enter different parts of the planning/state-transition sequence.

WP scale bridge:

```text
ITC exposure -> direct Q* increase -> feasibility/clamping -> labour/intermediate/capital plans -> realization
```

User-cost bridge:

```text
ITC exposure -> desired capital orders -> purchases/installation -> feasible capacity and input stocks -> realized sales/output -> future estimated demand and Q*
```

Matched 2026-2030 trace:

| Metric | WP eps=1 | UC Design B eta=.5 |
| --- | ---: | ---: |
| Direct policy delta Q* | 77.52 B | 0.00 B |
| Direct policy delta desired K | 0.00 B | 32.03 B |
| Total delta Q* | 125.40 B | 87.04 B |
| Delta desired/realized capital | 53.23 B | 58.15 B |
| Delta desired/realized intermediates | 35.66 B | 86.06 B |
| Delta capital stock, 2030 | 45.35 B | 34.39 B |
| Delta capital-limited capacity, 2030 | 6.72 B | 19.06 B |
| Delta realized production | 63.64 B | 121.37 B |

The central propagation result is that the K* shock changes a stock/input state first, while the Q* shock first asks for output that is then disciplined by feasibility and input planning. This is useful for an ABM paper because it shows timing and state dependence, not just different headline multipliers.

## Sequencing/Common-Sense Audit

Economically, the user-cost bridge is closer to an ITC decision because firms react through investment first. The concern is sequencing: applying the multiplier after the stock-adjusted gross order may subsidize the final order directly rather than the project-scale capital requirement that generated it.

The WP bridge is less natural as an ITC mechanism because it begins with desired output, but it is strongly disciplined by feasibility/clamping.

Current working verdict: sequencing needs attention before treating UC and WP as directly comparable.

## New Sequencing Variant

A new separable variant was added:

```text
design_b_pre_stock
```

Equation:

```text
K_req_base,ij = Q*_cap,i * delta_ij
K_req_ITC,ij = K_req_base,ij * (1 - tau * s_i,t-1)^(-eta_I)
K*_ij = max(0, K_req_ITC,ij - lambda * (K_prev,ij - K_ref,ij))
```

Difference from current UC:

- current UC applies the user-cost multiplier after stock adjustment;
- pre-stock UC applies the multiplier to the production-scale capital requirement before stock adjustment;
- the stock-gap term then attenuates gross orders when existing stocks already cover part of the requirement.

This keeps the current UC benchmark unchanged and adds only a separate mode.

## Pre-Stock Results

For `tau = 0.30`, `eta_I = 0.50`, active over 2026-2030:

| 2026-2030 cumulative | Current UC eta=.5 | Pre-stock UC eta=.5 | Ratio |
| --- | ---: | ---: | ---: |
| Investment | 57.6773 B | 52.9993 B | 0.9189 |
| Target production | 86.5490 B | 81.2184 B | 0.9384 |
| Realized production | 120.7140 B | 112.9425 B | 0.9356 |
| GVA | 57.6403 B | 53.2202 B | 0.9233 |
| Imports | 37.0685 B | 34.3034 B | 0.9254 |

Fiscal accounting:

| 2026-2030 fiscal metric | Current UC eta=.5 | Pre-stock UC eta=.5 |
| --- | ---: | ---: |
| Treatment eligible purchases | 210.7938 B | 210.4465 B |
| Control eligible purchases | 207.0145 B | 207.0145 B |
| Incremental eligible purchases | 3.7793 B | 3.4320 B |
| Gross fiscal cost | 63.2381 B | 63.1340 B |
| Eligible-purchase additionality | 0.0179 | 0.0163 |

The pre-stock variant reduces investment/GVA/production by roughly `6-8%` in the active window. Stock-adjustment sequencing matters, but it does not explain the large UC-vs-WP gap.

## Current Unresolved Questions

- Why does the K* shock generate much larger complementary intermediate demand than the Q* bridge after similar cumulative investment?
- How much of the UC response is a plausible project-wide user-cost effect versus an artifact of allowing capacity/input states to validate future demand?
- Should the preferred final specification apply the user-cost elasticity to the production-scale capital requirement before stock adjustment?
- Should Design B's project-wide complementarity be weakened, or is eta calibration sufficient?
- Should future diagnostics include a cleaner decomposition of 2028-2030 target growth into current direct wedge versus inherited endogenous demand feedback?

No claim has yet been made that UC is the final preferred specification.

## Local Outputs

Generated CSV/NPZ outputs remain ignored under:

```text
dev/validation/prov_2022
```

They are useful local audit artifacts but are not part of this checkpoint commit.
