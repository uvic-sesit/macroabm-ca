# Final Policy-Experiment Closure

Branch: `feature/itc-monetary-diagnostic`

This note freezes the policy-experiment closure for the ITC paper. The previously
validated C0 configuration remains the historical-validation reference only. The
policy experiments use the richer closure consistently from initialization and are
interpreted as projection experiments, not historical backcasts.

## Final Baseline

- Household consumption: `DisposableIncomeHouseholdConsumption`; endogenous from disposable income.
- Household investment: `ExogenousHouseholdInvestment`; unchanged exogenous path.
- Government target consumption: `ExogenousGovernmentConsumptionSetter`; unchanged exogenous target.
- Government realized purchases: goods-market realization/rationing remains active.
- Benefits/transfers: OECD SOCX public cash benefits; unemployment plus other cash benefits.
- Taxes: existing modeled tax instruments only; no residual general-government revenue closure.
- ITC refunds: dormant in control; when active, refunds equal the statutory rate times realized eligible C27/C28 purchases.
- Prices: demand-pull pricing on with `price_setting_speed_dp = 0.05`; cost-push off with `cp = 0`.
- Interest rates: annual quoted policy/bank rates are converted once to quarterly effective model rates.
- Monetary policy: `ConstantPolicyRate` is the main specification.
- Monetary robustness: stylized Taylor rule only; not calibrated Bank of Canada policy.
- Bank rates/credit: existing pass-through and credit allocation unchanged.
- Firm expectations: existing adaptive demand/growth/profit expectations unchanged.
- Firm investment: existing baseline investment rule; treatment uses UC Design B pre-stock.
- External demand and labour force: validated CAN-2022 projection assumptions unchanged.

## Treatment

Main UC treatment:

```text
K*_{ij,t,ITC} = K*_{ij,t,base} * (1 - tau * s_{i,t-1})^(-eta)
```

where `s` is the lagged value-based eligible C27/C28 share of the planned capital
bundle. The final main run uses `tau = 0.30`, `eta = 0.50`, policy window
2026-2030, and `design_b_pre_stock`.

The ITC does not directly multiply target production, TFP, credit, labour force,
or prices. It directly affects desired capital; production and demand effects then
propagate through the normal model sequence.

## Final Constant-Rate Results

Richer closure from initialization, `ConstantPolicyRate`, UC Design B pre-stock.

| Window | d investment | d capital stock end | d production | d GVA | d employment agents end | d unemployment pp end | d HH consumption | d imports | CPI gap pp | gross ITC | d modeled taxes | d benefits | d G purchases | d interest | d deficit diagnostic |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-2030 | 38.000 | 31.005 | 69.413 | 32.987 | 214 | -0.451 | 4.624 | 23.621 | 0.013 | 57.048 | -2.776 | -1.480 | 39.722 | 3.166 | 101.232 |
| 2026-2035 | 83.905 | 39.721 | 287.468 | 136.127 | 254 | -0.669 | 35.877 | 74.676 | -0.001 | 60.256 | 26.554 | -12.966 | 45.732 | 10.683 | 77.153 |

Deficit and debt are diagnostic only. Absolute values are not Canadian fiscal
forecasts because the fiscal architecture is a synthetic regional consolidated
government with incomplete represented revenues and mixed debt perimeter.

## Monetary Robustness

The stylized Taylor robustness does not materially change the real UC result under
the same richer closure:

- 2026-2030: investment response about 37.36B and GVA response about 31.34B.
- 2026-2035: investment response about 81.26B and GVA response about 128.56B.

This supports using `ConstantPolicyRate` as the main specification and the Taylor
rule only as a robustness closure.

## Discarded Splice Diagnostic

The historical-C0 to 2026 richer-closure splice is not used. It is numerically
stable, but it creates a visible benefit/household-consumption break in 2026 when
the transfer concept switches from broad SOCX-style benefits to public cash SOCX.

## Interpretation

Use the validated C0 only to document historical fit. Use the richer closure from
initialization for all policy experiments. Gross ITC refunds and treatment-control
fiscal-flow changes are interpretable; absolute deficit/debt paths are diagnostic.
