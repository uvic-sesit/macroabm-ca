<!--
MacroABM-CA pull request. Keep it short — the fields below are the minimum a
reviewer needs. Delete any guidance comments before submitting.
Contribution rules live in docs/contributing/ (shared with INET-Complexity/macro-main).
-->

## Linked issue
<!-- e.g. "Closes #123". Open an issue first if one doesn't exist. -->

## Classification
<!-- Tick exactly one. This decides review depth and whether the change is upstreamed. -->
- [ ] **CA-specific** — Canadian model logic, calibration, or data; stays on this fork
- [ ] **Upstream candidate** — generic `macromodel`/`macro_data` change with no Canada specificity (SESIT will re-file on INET after merge)
- [ ] **Docs / validation only** — no runtime behaviour change

## Summary of changes
<!-- What changed and why, in a few lines. Modelling justification where relevant. -->

## Default & backward-compatibility impact
<!-- Does this change shipped-default behaviour? New mechanisms should be opt-in and
     reproduce prior results when not enabled. State "no default change" if so. -->
- [ ] No change to shipped defaults (legacy runs reproduce exactly)
- [ ] Changes default behaviour — described above, with justification

## Mechanisms / outputs affected
<!-- Which agents, functions, or output series move as a result. -->

## Tests & results
<!-- What you added/ran, and the outcome. For behavioural changes, include
     before/after evidence (numbers, not just "looks right"). -->

## Checklist
- [ ] Tests added/updated and passing locally (`uv run pytest`)
- [ ] Style passes (`ruff`)
- [ ] No local paths, temporary outputs, credentials, or restricted/large data included
- [ ] Docs / data dependencies updated if needed
