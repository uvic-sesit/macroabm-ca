# ITC working-paper scenario layer

Reproducible scenario/experiment code for the Investment Tax Credit (ITC) working
paper. This is a **scenario layer**, not a change to `macromodel/` core: every
policy effect is applied by runtime configuration and target-production wedges on
top of the frozen baseline. No core model files are modified.

> Scaffolding note: this commit adds the shared `projection.py`, this README, and
> the outputs `.gitignore`. The scenario runners and analysis scripts land in the
> following commits; the sections below document the intended interface.

## Baseline

- **Branch:** `feature/wp-itc`, branched from `feature/io-2022-integration` @ `a3b6353`.
- **Frozen C0 reference:** tag `pre-itc-validation-2026-08-22` (`c796755`).
- **Baseline definition (tracked in `dev/`):** `save_baseline_2022.build_config`
  and the candidate closure in `provincial_validation_2022.py`
  (`configure` / `post_build` / `install_external_demand`), plus its
  `labour_index_2022` dependency. Scenarios build on this unchanged.
- **Projection:** 2022Q1–2035Q4 (56 quarters); 2022–2025 historical block, then a
  common 2026+ growth path (see `projection.py`). Single seed (0).

## Scenarios

- **Broad C27/C28 ITC** — 30% credit, cell-level (sector×province) scale response.
  Per representative firm, `x = TAU * planned eligible C27+C28 investment / production cost`
  (previous-quarter unconstrained target capital), and target production is scaled
  by `(1 + eps * x)` during the policy window.
- **Stylized Clean Electricity ITC** — 15% credit, sector D only, treating *all*
  planned D capital as eligible (the model cannot split clean vs fossil within D).
  Stylized approximation, not a statutory replication.

Both are demand/scale-channel treatments; the acquisition, financing, and TFP
channels are out of scope here (financing and TFP were investigated and deferred).

## Parameters

| item | value | where defined |
|---|---|---|
| projection growth GC/GG/GI, GL, GX | 0.02, 0.01, 0.02 /yr | `projection.py` (shared) |
| horizon `Q_LR`, projection start `PROJ_START` | 55, 16 | `projection.py` (shared) |
| scale elasticity `eps_scale` | 1 central; 0.5 / 1.5 sensitivity | scenario arg |
| ITC rate `TAU` | 0.30 (broad) / 0.15 (Clean Electricity) | scenario file |
| policy window | 2026–2030 (quarters 16–35) | scenario file |
| eligible goods/sectors | C27+C28 (broad) / D (Clean Electricity) | scenario file |
| seed | 0 | scenario file |

## Run commands (intended interface)

```
uv run python experiments/itc/scenario_broad.py            run control
uv run python experiments/itc/scenario_broad.py            run treat        # eps=1
uv run python experiments/itc/scenario_broad.py            run treat 0.5    # eps sensitivity
uv run python experiments/itc/scenario_broad.py            run treat 1.5
uv run python experiments/itc/scenario_clean_electricity.py run control
uv run python experiments/itc/scenario_clean_electricity.py run treat
uv run python experiments/itc/trace_edges.py               run control|treat   # edge tensors
uv run python experiments/itc/analysis/consolidate.py                          # headline + heterogeneity
uv run python experiments/itc/analysis/report_eps.py
uv run python experiments/itc/analysis/report_clean_electricity.py
```

Set `PYTHONIOENCODING=utf-8` on Windows. Each 56-quarter run is long; run one at a time.

## Reporting conventions

- **Flow** variables (GVA, target/realized production, investment, imports, fiscal
  cost): calendar-year **sum** of 4 quarters.
- **Stock** variables (capital stock, inventories): **year-end** value.
- **Rate** variables (unemployment, realization ratio): annual **average**.
- **Employment:** native unit is **employed model agents** (not persons).
- **Fiscal cost:** the harness does not record the refund in government accounts;
  report it as **"implied realized ITC fiscal cost"** = ITC rate × realized
  eligible capital purchases.

## Outputs

Generated `.npz`/`.csv` are written to `experiments/itc/outputs/` and are
**git-ignored** (see `.gitignore`). They are fully regenerable from the runners.
