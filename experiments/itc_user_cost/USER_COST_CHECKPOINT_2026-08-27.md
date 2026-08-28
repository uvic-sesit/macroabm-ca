# User-Cost ITC Checkpoint

Date: 2026-08-27

Branch: `feature/itc-user-cost`

Base commit: `a3b6353efd567162a3142694884393292b3767b4`

## Motivation

This branch preserves an alternative ITC mechanism to compare against the working-paper `Q*` scale bridge. The aim is to represent an investment-tax-credit response through desired capital demand, while leaving target production initially unchanged.

## Current Preferred Design B

For firm `i` and capital good `j`:

```text
K*_ij,ITC = K*_ij,base * (1 - tau * s_i)^(-eta_I)
```

where `s_i` is the lagged value-based eligible capital share:

```text
s_i,t-1 =
  sum_{j in E} p_j,t-1 * K*_{ij,t-1}
  / sum_j p_j,t-1 * K*_{ij,t-1}
```

with `E = {C27, C28}`. The benchmark policy uses `tau = 0.30`, active over 2026-2030. `eta_I` is an externally supplied user-cost/project-investment elasticity.

Interpretation: the ITC lowers the effective user cost of the firm's broader investment project in proportion to its eligible C27/C28 exposure, raising desired gross capital while preserving baseline capital composition.

## Timing And Insertion Point

The mechanism enters in `FinancialTargetCapitalInputsSetter.compute_unconstrained_target_capital_inputs`, after the baseline stock-adjusted capital target is computed and before it is returned to the firm. The lagged planned bundle is passed from `Firms.compute_unconstrained_demand_for_capital_inputs`; at that point the current-period target has not yet been appended, so `current("unconstrained_target_capital_inputs")` is the prior planned bundle.

Sequence:

```text
baseline investment plan
-> lagged eligible share
-> ITC desired-capital multiplier during 2026-2030
-> goods-market purchases
-> capital-stock installation/update
-> later production-capacity and expectation feedbacks
```

The mechanism does not directly change `Q*`, TFP, credit, `extra_taxes`, production taxes, or government accounts.

## Design A Diagnostic

Pure Design A is kept as a separable diagnostic/lower-bound asset-only case:

```text
K*_ij,ITC = K*_ij,base * (1 - tau)^(-eta_I) for j in {C27, C28}
K*_ij,ITC = K*_ij,base otherwise
```

It directly raises only desired C27/C28 capital demand and does not intentionally scale complementary non-eligible capital.

Main Design A result, `eta_I = 1.00`, cumulative 2026-2030:

| Measure | Treatment-control delta |
| --- | ---: |
| Desired/realized investment | 89.7244 B |
| Eligible C27/C28 investment | 88.0793 B |
| Non-eligible capital investment | 1.6451 B |
| Realized production | 8.7262 B |
| GVA | 4.0232 B |
| Gross ITC fiscal cost | 88.5281 B |
| Eligible-purchase additionality | 0.2985 |

## Design B Results

Design B cumulative 2026-2030:

| eta_I | Delta investment | Delta GVA | Delta target production | Delta realized production | Gross ITC fiscal cost | Eligible-purchase additionality |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50 | 57.6773 B | 57.6403 B | 86.5490 B | 120.7140 B | 63.2381 B | 0.0179 |
| 0.75 | 83.0653 B | 82.3830 B | 123.2890 B | 171.4149 B | 63.7296 B | 0.0255 |
| 1.00 | 105.9296 B | 103.9992 B | 153.9069 B | 215.4617 B | 64.1707 B | 0.0322 |

Design B cumulative 2026-2035:

| eta_I | Delta GVA | Delta realized production |
| ---: | ---: | ---: |
| 0.50 | 208.2571 B | 432.4696 B |
| 0.75 | 298.5122 B | 618.2861 B |
| 1.00 | 378.8416 B | 783.8579 B |

Direct multiplier diagnostics for Design B:

| eta_I | 2026 median | 2026 mean | 2026 p90 | 2030 median | 2030 mean | 2030 p90 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50 | 1.0092 | 1.0113 | 1.0162 | 1.0094 | 1.0108 | 1.0166 |
| 0.75 | 1.0139 | 1.0169 | 1.0243 | 1.0142 | 1.0163 | 1.0250 |
| 1.00 | 1.0185 | 1.0227 | 1.0326 | 1.0189 | 1.0218 | 1.0335 |

Scaling checks show near-linearity with mild endogenous amplification. Relative to proportional fractions of the `eta_I = 1.00` case, 2026-2030 actual ratios were:

| eta_I | Investment | GVA | Target production | Realized production |
| ---: | ---: | ---: | ---: | ---: |
| 0.50 | 1.0890 | 1.1085 | 1.1247 | 1.1205 |
| 0.75 | 1.0455 | 1.0562 | 1.0681 | 1.0608 |

## Artifact Audit Conclusions

The current audit found:

- no accidental second application of the user-cost multiplier;
- the share used in quarter `t` is based on the intended lagged planned bundle;
- policy is off after 2030;
- `Q*` is not directly multiplied by the ITC;
- direct Design B wedges are small, with median multipliers around 1-2 percent depending on `eta_I`;
- fiscal cost is gross treatment cost during 2026-2030 only, computed as `tau * treatment realized eligible C27/C28 purchases`;
- desired and realized investment matched in aggregate in these runs, indicating no aggregate capital-order rationing in the saved results.

Cell-level capital-binding diagnostics were limited to PROV10 / available captures. In the 2030 diagnostic for Design B `eta_I = 1.00`, capital-binding cells were rare: control 4/500 and treatment 3/500.

## Unresolved

The main unresolved question is why the project-wide user-cost design produces much stronger production and GVA responses than the working-paper scale bridge at similar fiscal cost and, for `eta_I = 0.50`, similar cumulative investment. This checkpoint does not claim Design B is the preferred final specification; it preserves the mechanism, diagnostics, and results for review.

## Reproducibility

Tracked harness:

```text
experiments/itc_user_cost/itc_user_cost_exp.py
```

Example commands:

```powershell
.\.venv\Scripts\python.exe experiments\itc_user_cost\itc_user_cost_exp.py design_b_long 0.50
.\.venv\Scripts\python.exe experiments\itc_user_cost\itc_user_cost_exp.py design_b_long 0.75
.\.venv\Scripts\python.exe experiments\itc_user_cost\itc_user_cost_exp.py design_b_long 1.00
.\.venv\Scripts\python.exe experiments\itc_user_cost\itc_user_cost_exp.py design_a_long 1.00
```

Generated CSV/NPZ outputs remain untracked under `dev/validation/prov_2022`.
