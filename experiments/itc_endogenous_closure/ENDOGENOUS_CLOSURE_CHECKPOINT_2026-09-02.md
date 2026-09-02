# Endogenous-Closure ITC Checkpoint

Branch: `feature/itc-endogenous-closure`
Base commit: `a3b6353efd567162a3142694884393292b3767b4`

Purpose: preserve the reusable macro-closure layer before monetary-policy diagnostics. This branch is separate from `feature/wp-itc` and `feature/itc-user-cost`.

## Closure Ladder

| Label | Household consumption | Household investment | Government target consumption | Prices | Fiscal ITC | Status |
|---|---|---|---|---|---|---|
| `A_original_c0` | `ExogenousHouseholdConsumption` | `ExogenousHouseholdInvestment` | `ExogenousGovernmentConsumptionSetter` | `DefaultPriceSetter`, `dp=0`, `cp=0`, general factor/noise active | off | validated baseline comparison |
| `C_dp_005` | `DisposableIncomeHouseholdConsumption` | `ExogenousHouseholdInvestment` | `ExogenousGovernmentConsumptionSetter` | demand-pull `dp=.05`, `cp=0`; general factor/noise preserved | dormant unless activated | preferred current endogenous control |
| `D_dp005_hhinv_default` | `DisposableIncomeHouseholdConsumption` | `DefaultHouseholdInvestment` | `ExogenousGovernmentConsumptionSetter` | demand-pull `dp=.05`, `cp=0` | dormant unless activated | exploratory; stable but changes baseline materially |
| `E_dp005_hhinv_default_govar` | `DisposableIncomeHouseholdConsumption` | `DefaultHouseholdInvestment` | `AutoregressiveGovernmentConsumptionSetter` | demand-pull `dp=.05`, `cp=0` | dormant unless activated | exploratory; large government rationing wedge |

Rows 3 and 4 are sequential additions to row 2. Row 3 frees household investment; row 4 additionally frees government target consumption.

## Preferred Current Control

Use `C_dp_005` for the next UC comparisons:

- endogenous household consumption through disposable income;
- endogenous ordinary fiscal feedback: taxes, benefits/transfers, deficit, debt, debt interest;
- household investment remains exogenous;
- government target consumption remains exogenous, with realized purchases still goods-market-cleared;
- demand-pull pricing on with `price_dp=.05`;
- cost-push pricing off with `price_cp=0`;
- central bank remains `ConstantPolicyRate`;
- credit settings unchanged.

`price_dp=.05` is diagnostic and uncalibrated.

## UC Pre-Stock Results

UC setup: `design_b_pre_stock`, `eta=.5`, `tau=.30`, policy window 2026-2030, realized ITC refunds booked fiscally. The UC mechanism is present for comparison runs but the closure branch is not yet claiming a final ITC specification.

### HH endogenous only

| Window | d investment | d target production | d realized production | d GVA | d HH consumption | d imports | gross ITC refunds | d tax revenue | d benefits/transfers | d realized G | d deficit | eligible additionality |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-30 | 42.743B | 73.081B | 91.823B | 44.028B | 21.160B | 25.282B | 52.059B | 7.301B | -0.249B | -11.398B | 36.163B | 1.499% |
| 2031-35 | 74.188B | 257.000B | 268.817B | 129.318B | 47.907B | 59.164B | 2.938B | 38.985B | -3.084B | -15.157B | -47.545B | 2.041% |
| 2026-35 | 116.931B | 330.080B | 360.641B | 173.347B | 69.067B | 84.446B | 54.997B | 46.287B | -3.333B | -26.555B | -11.381B | 1.791% |

2030 effects: capital stock +22.279B, employment +149 model agents, unemployment -0.722 pp, CPI inflation -0.039 pp.

### HH endogenous + demand-pull `dp=.05`

| Window | d investment | d target production | d realized production | d GVA | d HH consumption | d imports | gross ITC refunds | d tax revenue | d benefits/transfers | d realized G | d deficit | eligible additionality |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-30 | 41.839B | 75.414B | 100.415B | 48.471B | 26.027B | 27.336B | 52.807B | 8.938B | -5.199B | -7.871B | 39.239B | 1.633% |
| 2031-35 | 62.048B | 269.305B | 293.581B | 141.869B | 83.377B | 59.520B | 3.127B | 38.657B | -8.566B | -21.689B | -63.418B | 1.934% |
| 2026-35 | 103.887B | 344.719B | 393.995B | 190.341B | 109.404B | 86.855B | 55.934B | 47.595B | -13.765B | -29.560B | -24.179B | 1.795% |

2030 effects: capital stock +27.175B, employment +187 model agents, unemployment -0.719 pp, CPI inflation -0.049 pp. 2035 effects: capital stock +43.506B, employment +112 model agents, unemployment -0.313 pp, CPI inflation +0.085 pp.

Annual GVA growth gaps for HH+`dp=.05`: 2027 +0.149 pp, 2028 +0.152 pp, 2029 +0.214 pp, 2030 +0.114 pp, 2031 +0.188 pp, 2032 +0.081 pp, 2033 +0.035 pp, 2034 +0.005 pp, 2035 -0.037 pp. Average gap: 2027-30 +0.157 pp, 2031-35 +0.055 pp, 2027-35 +0.100 pp.

CPI inflation gaps for HH+`dp=.05`: 2026 +0.023 pp, 2027 -0.060 pp, 2028 +0.010 pp, 2029 +0.064 pp, 2030 -0.049 pp, 2031 +0.034 pp, 2032 -0.093 pp, 2033 -0.046 pp, 2034 +0.056 pp, 2035 +0.085 pp.

Fiscal sense check: gross ITC refunds are based on total treatment eligible C27/C28 realized purchases, not incremental purchases. Tax offsets come from production, VAT, capital-formation, corporate, income, and social-insurance bases. Lower realized government purchases are reported separately and must not be described as the ITC paying for itself.

Persistence: post-policy effects persist mainly through higher capital stock, production capacity, sales/demand feedback, household consumption, tax bases, and lower benefits. Refunds after 2030 are small residual timing/capture values and should be monitored in future runs.

## Invalid Or Diagnostic Experiments

- Protected-government-purchases overwrite is invalid for economic interpretation. It overwrites government realized purchases after goods-market clearing, before macro/fiscal reporting, without reallocating seller-side supply or sales. A valid version must alter goods-market priority/allocation before realization.
- `dp=.10`, `.25`, `.50` are demand-pull sensitivity diagnostics only. They showed finite runs, but treatment-control CPI gaps remained small because treatment and control demand-pull signals are similar.
- `D_dp005_hhinv_default` is exploratory. `DefaultHouseholdInvestment` runs cleanly after initialization but materially changes the baseline path: faster GVA, much higher household consumption/investment, lower unemployment, and higher debt.
- `E_dp005_hhinv_default_govar` is exploratory. Autoregressive government target consumption is technically runnable but creates a large desired-vs-realized government-purchase wedge.

## Architecture Caveats

- Government debt has no explicit asset-holder/bond-market counterpart in the current branch.
- Monetary reaction remains off: central bank is still `ConstantPolicyRate`.
- Credit transmission is unchanged and weak/inactive for these diagnostics.
- Household macro-expectations are narrower than Poledna-style adaptive macro expectation systems.
- Historical 2022-25 behavior under the reopened closure still needs a final consistency check before freezing a clean 2026-forward policy switch.

## Reproducibility Files

- `closure_feedback_exp.py`: closure builder and generic dormant fiscal ITC/refund switches.
- `validate_closure_baseline.py`: no-ITC closure ladder validation.
- `run_uc_closure_comparison.py`: matched UC closure comparison and demand-pull diagnostics.
- `h5_extract.py`: small HDF5 extraction helper.

Generated `results/`, `*.csv`, `*.npz`, and `__pycache__/` are intentionally ignored.
