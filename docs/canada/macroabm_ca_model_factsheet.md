# MacroABM-CA — Model Factsheet

> **Snapshot date:** 2026-07-22 · **Round:** GMMI questionnaire (first draft) · **Status:** provisional / experimental beta model
>
> This factsheet characterizes MacroABM-CA using the prespecified choices of the GMMI
> Model Description Questionnaire. It is a **point-in-time snapshot** of the model's design.
> Where a mechanism is implemented but not active in the baseline, it is marked
> *available (opt-in)*. Answers describe the model version used for the current provincial
> beta runs. Re-timestamp and revise when the model's capabilities change.

**Respondent:** Esmaeil Izadi (SESIT, University of Victoria)
**Model:** MacroABM-CA (MacroABM-Canada) — Canadian provincial adaptation of the
INET-Complexity MacroABM framework.
**Model type:** Agent-based, stock-flow-consistent macro-financial model; multi-regional
(10 Canadian provinces + rest-of-world); 43 ISIC sectors; 2014 base year; quarterly.

---

## At a glance

| Dimension | MacroABM-CA |
|---|---|
| Paradigm | Agent-based, stock-flow-consistent, macro-financial |
| Geography | 10 provinces (Admin 1) + simplified ROW; open economy |
| Sectors | 43 ISIC sectors, provincial IO trade network |
| Time | Quarterly, ~10-year horizon (2014 base) |
| Agents | Households, non-financial firms, private banks, central bank, government |
| Prices | Heuristic adaptive (cost-push + demand-pull + inflation pass-through) |
| Expectations | Backward-looking / adaptive |
| Monetary policy | Endogenous Taylor-type policy rule (constant-rate variant available) |
| Growth (baseline) | Exogenous labour productivity + demand-led transmission |
| Growth (available) | Endogenous / sector-specific TFP growth (opt-in); energy-model coupling (CIMS, experimental) |
| Objective | What-if policy scenarios (e.g. clean-investment tax-credit incidence) |

**Reading the boxes:** ✅ = represented in the beta model · ☑️ *available (opt-in)* =
implemented but off in the baseline · ☐ = not represented.

---

## A. Scope and aggregation

**1. Spatial scope** — Country model (open): Canada as 10 interacting provincial economies
plus a simplified rest-of-world sector.

**2. Economic disaggregation**
- ✅ Sector-level (>5 sectors) — 43 ISIC sectors
- ✅ Multiple agents (not a single representative agent)
- ✅ Agent-based model

**3. Spatial aggregation** — ✅ Subnational (Admin 1): provinces.

**4. Demographics** — ✅ Exogenous (default fixed labour force; optional exogenous
observed labour-force path).

**5. Time horizon** — ~10 years (2014 base, validated to ~2024).

**6. Time step** — Quarterly.

**7. Objective** — ✅ Production of what-if scenarios (exogenous policy inputs).

---

## B. Economic mechanisms

**9. Actors** — ✅ Households · ✅ Non-financial firms · ✅ Private banks ·
✅ Central bank · ✅ Government. ☐ Other financial corporations (pension funds, etc.).

**10. Real vs monetary** — Monetary model with an explicit financial sector (banks, credit
market, central bank), two-way real–financial interaction.

**11. Inflation and relative prices** — ✅ Aggregate inflation (sectoral relative prices
also present).

**12. Price modeling** — Heuristic adaptive price-setting: cost-push (unit costs) +
demand-pull (excess demand / inventories) + inflation pass-through + noise, with adjustment
speeds < 1. (Closest prespecified choice: endogenous markups.)

**13. Price and wage stickiness** — ✅ Price stickiness · ✅ Wage stickiness.

**14. Macroeconomic (dis)equilibrium** — Supply/demand disequilibrium over the long term
(rationing and inventories).

**15. Labour-market frictions** — Explicit, agent-based search-and-matching labour market
(with reservation-wage floors).

**16. Private debt** — ✅ Households (consumption loans, mortgages) · ✅ Non-financial firms.

**17. Unemployment** — Involuntary unemployment emerging from matching-market
disequilibrium (not Phillips-curve-based; reservation-wage floors present).

**18. Financial frictions** — ✅ Endogenous risk premia (banks set product-specific rates as
spreads over the central-bank policy rate) · ✅ Borrowing constraints (credit rationing).

**19. Capital-stock inertia** — ✅ Investment / capital adjustment costs (rolling capital
reference) · ✅ Firm-specific assets with reallocation frictions.

**20. Public debt** — ✅ Aggregated: government debt stock with deficit dynamics
(`debt_{t+1} = debt_t + deficit_t`) and interest servicing.

**21. Taxes and expenditures** — ✅ Disaggregated (income tax, social-insurance/labour tax,
rental-income tax, corporate).

**22. Behaviors** — Heuristics and behavioural rules (household demand has an optional CES
static-optimization variant).

**23. Expectations** — Backward-looking (adaptive expectations for demand and inflation).

**24. Balance-of-payments closure** — Through external flows: a ROW block provides trade
closure and consistent global accounting (exports demand-driven, imports tracked).

**25. Exchange-rate modeling** — Exogenous exchange-rate path (USD ↔ local-currency
conversion in the ROW trade block). (Closest prespecified choice: fixed exchange rate.)

**26. Sources of long-term growth**
- ✅ Exogenous labour productivity growth *(baseline)*
- ✅ Demand-led *(baseline transmission: demand → investment → capacity → employment → output)*
- ☑️ *available* Endogenous labour productivity growth (investment-driven TFP)
- ☑️ *available* Endogenous technology-specific productivity gains (sector-specific TFP)

**27. Goods market and inventories** — ✅ Temporary disequilibrium · ✅ Explicit inventories
and rationing.

**28. Policy credibility / commitment** — Not explicitly modeled: policies enter as
exogenous scenario paths and agents respond adaptively (no forward-commitment or
time-inconsistency mechanism).

---

## C. Technology, energy, transport, industry, land-use

**30. Natural capital** — ☐ Not included.

**31. Land-use** — ☐ No representation.

**32. Energy system** — ☑️ *emerging* Coupled with an external energy/power-sector model:
the first **CIMS** linkage is released and under experimentation. In the macro core,
emissions are tracked via sectoral emission intensities (fixed coefficients).

**33. Other non-energy technologies** — ☐ Not represented as discrete technologies
(production uses IO/Leontief intermediates plus labour and capital).

**34. Technological change**
- ✅ Baseline: fixed / exogenously evolving productivity
- ☑️ *available* Endogenously evolving productivity (multiple methods)
- ☑️ *available* Sector-specific dynamic technological change (endogenous, via sectoral TFP,
  productivity investment, and evolving technical coefficients)

---

## D. Climate-change impacts, environment, co-benefits

**36. Ecosystem services** — ☐ None (the macro core tracks emissions but no ecosystem-service
channels).

**37a–c. Climate-change impacts** (temperature / other climate / extreme events) — ☐ None:
no climate-damage feedback into productivity, agriculture, or capital in the macro core.
These are candidates for the energy/impact model couplings under development.

**38. Economic benefits of decarbonization** — ☐ Not modeled explicitly in the macro core.

---

## Context and caveats

- **Modular by design.** MacroABM-CA is a macro-financial ABM being **coupled to
  energy-system models** (CIMS is the first linkage, in testing), moving toward broader
  IAM-style coverage rather than being an integrated assessment model itself.
- **Baseline vs capability.** Several richer channels — endogenous/sectoral TFP growth,
  the observed labour-force path — are **implemented but opt-in**; the current beta baseline
  runs exogenous productivity with demand-led transmission.
- **Experimental status.** Outputs are beta-run evidence for diagnosis and scenario
  prototyping, not a finalized production baseline. See the
  [onboarding guide](canada_beta_model_onboarding_guide.md) for how to run the model and
  report findings.
- **First-draft questionnaire.** The GMMI questionnaire is itself a first draft; some
  prespecified choices fit MacroABM-CA only approximately (noted inline above).
