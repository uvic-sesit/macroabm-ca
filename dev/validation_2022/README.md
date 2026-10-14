# MacroABM-CA 2022 validation — Stage 1 (whole model), Stages 2–3 (households)

Working copy `SESIT/macroabm-ca-validation`, branch `feature/validation-2022` off `feature/itc-user-cost`
(`ab87ee2`). Nothing in `feature/itc-user-cost`, `SESIT/macroabm-ca`, or the ITC artefacts was modified. No
simulation step was run; only pickle builds and t0 instantiation.

| File | Content |
|---|---|
| `STAGE1_MODEL_EQUATIONS.md` | code-grounded timing, balance-sheet and flow structure, equations (whole model) |
| `STAGE2_HOUSEHOLD_RECONCILIATION.md` | 2022 household reconciliation vs StatCan, with attribution |
| `STAGE3_HOUSEHOLD_SPECIFICATION.md` | household specification assessment, priority ranking, decision points |
| `ISSUE_REGISTER.md` | single register (accounting, data, specification; firm/gov items noted) |
| `benchmarks/BENCHMARKS.md` | benchmark provenance (series IDs, periods, concepts, retrieval) |
| `scripts/` | reproducible extraction (t0 only) |
| `outputs/` | CSV/JSON extracts; `rebuild_pickle.log` |

Local artefacts (git-ignored): `dev/pkl_files/io2022_13prov_2022_canadianized.pkl` (byte copy of the canonical
pickle), `dev/pkl_files/io2022_13prov_2022_canadianized_branchab87ee2.pkl` (rebuilt with branch code;
`MACROABM_RAW_DATA` → `SESIT/macroabm-ca/dev/raw_data`, read-only), and
`dev/io2022/household_prototype/prototype_household_consumption.csv` (copy).
