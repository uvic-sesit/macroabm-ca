# Commit map: local full-evidence history → pushed slim history

The pushed `feature/validation-2022` removes `dev/validation_2022/outputs/` from every commit (evidence outputs, about 835 MB). Content is otherwise identical. Reports cite the **original** hashes (left column) and link to `outputs/` paths, which exist only in the local branch and in `SESIT/local_archives/validation_2022_outputs_2026-10-25.tar.gz` (SHA256 manifest alongside). Base: ab87ee2 (feature/itc-user-cost).

| original | slim | subject |
|---|---|---|
| `25e0d62` | `e69bd7f` | docs(validation): Stage 1 equations, household Stage 2-3 reconciliation and issue register |
| `96f0abd` | `c575140` | fix(validation-2022): Phase A data and accounting corrections (WIP) |
| `a5f850d` | `80db40a` | fix(validation-2022): close bank-interest and rent leaks; Phase A report |
| `7bab49e` | `8883236` | fix(validation-2022): settle goods payments at sellers' prices; drop negative household investment weights |
| `4efc999` | `33ffe81` | fix(validation-2022): charge written-off loans to the lending bank's equity |
| `d14fa10` | `cdcd905` | fix(validation-2022): CAN-2022 initial household loan terms from observed principal payments |
| `e2cca22` | `658c1f7` | docs(validation-2022): battery goods/bank checks, write-off diagnosis, issue register |
| `4ecbac0` | `4db4d4b` | fix(validation-2022): CAD-native CAN-2022 build uses a CAD numeraire exchange rate |
| `8bc9244` | `c7cc805` | fix(validation-2022): allocate firm deposits by output when no firm-level data |
| `d999561` | `a980502` | fix(validation-2022): recognise cancelled overdrafts of insolvent firms as bank losses |
| `4bdef06` | `a24decb` | docs(validation-2022): firm-sector audit, benchmarks, diagnostics and issue register |
| `c4862de` | `123c3b9` | fix(credit): convert loan-category fractions to currency budgets by default |
| `4cea6e2` | `e6b19dd` | fix(households): preserve weights and survey LTVs in H7 mortgage calibration |
| `1fdedd2` | `4d5767e` | feat(credit): isolate D4 underwriting and reconcile amortization terms |
| `4e9ac88` | `1a8fd88` | feat(households): calibrate D2 distributions to observed 2022 receipts |
| `f549246` | `4775d5b` | fix(housing): offset private rent only against renters sector L purchases |
| `8fabeee` | `9d7b7d4` | feat(households): isolate D3 distress scenario and writeoff attribution |
| `b1b2960` | `1df85e0` | docs(validation): record household correction attribution and benchmark provenance |
| `5ea5807` | `368f944` | feat(validation): instrument pre-D3 household and firm diagnostics |
| `d7a2110` | `ccf578d` | fix(credit): count overdrafts and consumer service in D4 screens |
| `59a37ef` | `9f4c59a` | fix(data): preserve regional shares in bank equity reader returns |
| `37cf590` | `5ec71ae` | fix(accounting): refresh household liabilities after loan cancellation |
| `94a956b` | `e3ed4f3` | feat(validation): retain buyer panels and audit pre-D3 diagnostic artifacts |
| `448a6bb` | `78e8c64` | feat(validation): complete four pre-D3 checks and record unresolved bank resolution |
| `f8e9854` | `54040ad` | fix: initialize Canadian bank book equity from NBSA liabilities |
| `c977e16` | `7347d7c` | fix: preserve contracts through fiscally funded bridge-bank resolution |
| `c2c0120` | `a893fe3` | fix: include funded D2 receipts in initial saving calibration |
| `788f84f` | `3341105` | feat: cap discretionary goods budgets with zero unused overdraft capacity |
| `3054d2e` | `6c0172c` | chore: add serial ABCD accounting and loss attribution runner |
| `ddde9c2` | `d7ff045` | docs(validation): record ABCD diagnostics, seed comparisons and held default proposals |
| `1c1eb8a` | `5e0e57f` | docs(validation): distinguish full-source and snapshot benchmark hashes |
| `54709c9` | `30418ec` | fix: include declared current receipts in household cash budgets |
| `3d54d44` | `8459ee7` | feat(validation): enable narrow rent offset in both cashflow candidate arms |
| `ed02f71` | `7d1e077` | fix(validation): serialize household gate results and run paired serial measurements |
| `3248706` | `a2a36ae` | docs(validation): record corrected household timing and D1 gate results |
| `393bff8` | `03ac4f8` | feat: allow cash-first non-pension asset drawdown in household budgets |
| `f140ae2` | `d9e21b3` | fix(validation): reconcile household asset diagnosis to regional consumption |
| `e11ff6d` | `7c0a0ef` | docs(validation): record failed asset drawdown gate across three seeds |
| `de244bc` | `21c440f` | feat(validation): measure household capital purchases in an exact cash ledger |
| `f1e7b60` | `0dc353c` | fix: benchmark initial household investment to sector fixed capital formation |
| `b75d4a7` | `42ecf51` | feat: fund household consumption before discretionary investment under D |
| `f77f0f5` | `39aac5e` | docs(validation): record investment ledger and failed household capital gate |
| `12987e6` | `33930d2` | Correct Canadian firm external loan boundary and industry allocation |
| `923f107` | `8c074f3` | Add opt-in firm payment distress and partial secured restructuring |
| `bd72103` | `7c3a57b` | Instrument F losses and household constraint income counterfactuals |
| `9a26aeb` | `6c3bba9` | Record planned investment acceptance and F continuation checks |
| `43bd9f9` | `411ac99` | Include existing overdraft interest in firm payment distress |
| `980c8cd` | `1c25779` | Separate household employment and firm receipt changes in F diagnosis |
| `0e64a05` | `9ace30e` | Document F implementation and execution-blocked validation checkpoint |
| `a039998` | `57c2b07` | Include overdraft principal in firm collateral shortfalls |
| `e386f4e` | `c7741ee` | Report gated F results, household diagnosis and full validation suite |
| `2948b08` | `58e96d4` | Add opt-in SFS buffer-stock household consumption rule |
| `47e6002` | `f2ac616` | Initialize buffer income from scheduled debt service |
| `6a973a6` | `e653de1` | Add serial buffer measurements and read-only firm cost decomposition |
| `1e83c42` | `5f02194` | Record buffer gate boundaries and reproducible validation audits |
| `95cf3e6` | `0e694a6` | Restrict discretionary firm dividends to retained profit and reserved cash |
| `28c27ee` | `a2fafa4` | Report gated buffer-stock results, prudent payouts and full-suite audit |
| `c2c3eb8` | `4aad14d` | Add B2 multiplicative propensity anchor with fixed wealth responses |
| `ea3485a` | `5df7c25` | Freeze B2 gates and source-specific DHEA and SHS distribution diagnostics |
| `55fb64a` | `fdbc128` | Add tested data-only firm output, tax and observed CFC reconciliation helpers |
| `2237cb1` | `b71e0a5` | Separate initial firm capital acquisitions from depreciation with legacy fallback |
| `b3227ea` | `6198ffa` | Add signed IO tax and cost-side output diagnostic build with zero-output guards |
| `c3df2d9` | `13529e5` | Build observed CFC input and measure it serially on accepted household arm F |
| `d40e353` | `dc0a51e` | Normalise national quintile income ranks by regional household expansion factors |
| `7a1767e` | `372b3b9` | Record B2 gate failures and independent firm CFC reconciliation with audited evidence |
| `9cc1563` | `d64b5de` | Adopt observed firm CFC on accepted FE household baseline for QE diagnostics |
| `f0b6aee` | `b065bfb` | Add opt-in DHEA rank consumption propensities and QE construction diagnostics |
| `d23d31e` | `4609976` | Add opt-in cash payment arrears and executed-sale foreclosure accounting |
| `c89ea09` | `b810967` | Add tested GDP valuation bridge and freeze QE credit and deposits-only benchmarks |
| `f0fc613` | `227fa01` | Exclude public housing rent from household landlord income tax base |
| `4ef8b68` | `bb0bca2` | Keep third-party tenants linked until an executable move gives vacant possession |
| `367bc04` | `344d232` | Add QE share gates, direct payment-default regression and serial evidence audit |
| `a1d55a6` | `ccc20a7` | Complete E unsecured overdraft losses with exact deposit and bank accounting |
| `840a97d` | `2628162` | Correct secondary SHS gross-wage ranks using the model payroll identity |
| `51f0615` | `9551fe1` | Record QE gate failures and complete household default diagnostics with audited evidence |
| `c1712b7` | `77b88a0` | Align initial and reported GDP housing scope with household IO coverage |
| `15fcb37` | `aa3adbc` | Add opt-in partial arrears catch-up with full-payment cure preserved |
| `04fb61e` | `b32ddaf` | Add read-only IH investment, income and servicing diagnostics with net-surplus gate |
| `3557989` | `53a15e4` | Scope GDP component report rent addends while preserving cash memo columns |
| `57f16c9` | `c049add` | Correct arrears entrant attribution and distinguish cash-income benchmark scope |
| `3fe9c17` | `38ca590` | Record IH housing, investment, income and cure diagnostics with audited evidence |
| `ab8676a` | `d83f10e` | Audit CIS household units and freeze source distribution benchmarks |
| `fc70bf5` | `ca4bdf2` | Add input-scoped CIS income allocation candidate with conserved payroll and transfers |
| `d9102ec` | `29c6cc9` | Build independent observed GFCF start and expose unsupported allocations and GDP gaps |
| `2cdf4d6` | `736c24e` | Record HI income and investment gate failures with audited evidence |
| `2ef7a32` | `75b019c` | Check initial GDP income independently of expenditure |
| `1eadde5` | `6dcae91` | Build isolated balanced SUT and signed producer tax candidates with cost gates |
| `dc68b37` | `e7a56c7` | Preserve explicit VA6 and refresh the ROW import counterpart in SUT builds |
| `ca33da2` | `68d5d73` | Record SG SUT gates, zero-activity failure, housing and CIS tax diagnostics |
| `1ffdc06` | `73a20b3` | Define zero-activity work-effort guard and reuse the provincial source-zero floor convention |
| `a9fee55` | `f65d10d` | Apply the declared source-positive cost gate and build FS_T v4 with universal zero-source floors |
| `f599a9d` | `72d90f6` | Distinguish unset opening forecasts from defined floor state in ZA audits |
| `7f9789c` | `740b5e3` | Retain signed IO capital products and stop FSG before invalid purchase allocation |
| `41d4e68` | `acf16f9` | Record the exact read-only OOH cash split and unidentified dwelling depreciation |
| `9b556cb` | `b125c98` | Freeze ZA FS_T seed comparisons, FSG blockers and final validation evidence |
| `afced23` | `9c618ef` | Add 2022 validation stock-take after round ZA |
