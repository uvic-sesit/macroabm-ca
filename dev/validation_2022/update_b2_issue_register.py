"""Append the B2 review state, without changing historical entries."""
from pathlib import Path
import json
import pandas as pd
from report_b2 import table
HERE=Path(__file__).resolve().parent
MARK='<!-- B2-2026-10-24 -->'

def main():
    p=HERE/'ISSUE_REGISTER.md';old=p.read_text(encoding='utf8').split(MARK)[0].rstrip()
    out=HERE/'outputs/B2';g=pd.read_csv(out/'gates.csv').query("variant=='base'")
    parts=[MARK,'## B2 and independent firm-data reconciliation — 2026-10-24\n',
        'B2 fails. E, Phase B and C_dp_005 remain on hold. Per clarification, independent Step 2 was completed on accepted FE arm F (e386f4e lineage), with P off. No parameter tuning or push.\n',
        '| Item | Evidence / commit | Status |\n|---|---|---|\n'
        '| B2 form | c2c3eb8, ea3485a; 6 regressions | One c0 rescale .961350238407, no additive intercept; zero-goods gate passes; base G2–G4 fail every seed |\n'
        '| G3 clarification | DHEA 36-10-0587 primary, SHS 11-10-0223 secondary | Gate uses quintile shares, not dollar levels. Source-specific equivalence/ranking applied; full DHEA income remains a cash proxy, housing scope caveat disclosed |\n'
        '| Regional rank scaling | d40e353; scale-invariance regression | Corrected national per-household income ranks; 15 diagnostic replays require identical original macro paths. Original misranked tables retained but superseded |\n'
        '| Initial acquisitions vs CFC | 2237cb1; 1 regression | Clear mechanical separation; new CFC does not overwrite accepted initial purchases; default legacy fallback unchanged |\n'
        '| Observed CFC | c3df2d9; 2 allocation regressions | New cfc_v2 pickle; 377.244B/year allocated versus 377.319B source; missing-stock boundary explicit. I/H53/A02 national costs below price |\n'
        '| F-A1 / F-D1 | 55fb64a, b3227ea; 5 regressions | 100.504B/year missing signed taxes and 48.338B/year row–column discrepancy confirmed. Experimental correction not promoted: fails GDP initialisation. CFC-only retains unresolved bridge |\n'
        '| Step 2 gate | 409 gross-margin exceptions >1 pp; 87 above-price cells with nonnegative IO GOS | Fails; neither data boundary nor remaining losses declared validated |\n'
        '| E | no implementation | Step 1 gate prevents dependent work |\n',
        table(g[['seed','constrained_slope_pp','Q12_saving_pct','max_zero_positive_pct','G1','G2','G3','G4']]),
        table(pd.read_csv(out/'F_CFC_seed_comparison.csv')),
        'Firm losses fall 48–60% under observed CFC; household write-offs stay about 233B over 12 quarters. Remaining firm losses mix data/concept limitations with price, demand and default behaviour; initial-condition diagnostics are not a causal behavioural decomposition. Bank recapitalisations remain large.\n']
    tpath=out/'verification/full_test_execution.json'
    if tpath.exists():
        t=json.loads(tpath.read_text());parts.append(f'Full tests: {t["passed"]} passed / {len(t["failures"])} known failures / {t["tests"]} cases; sampler one worker. Exact failure IDs checked against BE baseline in the final audit.\n')
    parts.append('[CLOSURE_B2_2026-10-24.md](CLOSURE_B2_2026-10-24.md) contains every gate, quarterly losses, resolutions, seed comparisons, quintile raw levels and shares, source definitions/hashes, and remaining limitations. Stop for review; not ready for Phase B.\n')
    p.write_text(old+'\n\n'+'\n'.join(parts),encoding='utf8')

if __name__=='__main__':main()
