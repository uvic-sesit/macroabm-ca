"""Short accounting smoke run (Phase A test): shipped-default 2022 configuration, N quarters, accounting
battery as a post-hook. Writes per-region records and the national residual summary.

    .venv/Scripts/python.exe dev/validation_2022/battery/run_accounting_smoke.py PICKLE TAG [QUARTERS]
"""
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[3]
# Optional: run against another code tree (e.g. the pre-correction worktree) without installing it.
CODE_ROOT = os.environ.get("MACROABM_CODE_ROOT")
if CODE_ROOT:
    sys.path.insert(0, CODE_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounting import AccountingBattery, summarise  # noqa: E402
from macro_data import DataWrapper  # noqa: E402
from macromodel.configurations import CountryConfiguration, SimulationConfiguration  # noqa: E402
from macromodel.simulation import Simulation  # noqa: E402
import macromodel  # noqa: E402

print("macromodel code:", macromodel.__file__)


def build_config(d, seed, quarters):
    """Identical to dev/io2022/save_baseline_2022.build_config (shipped default, all CAN_* regions)."""
    provs = [c for c in d.all_country_names if str(c).startswith("CAN_")]
    cfg = SimulationConfiguration(
        seed=seed,
        country_configurations={c: CountryConfiguration.n_industry_default(n_industries=d.n_industries) for c in provs},
        t_max=quarters,
    )
    return provs, cfg

pkl, tag = Path(sys.argv[1]), sys.argv[2]
quarters = int(sys.argv[3]) if len(sys.argv) > 3 else 2
out = REPO / "dev" / "validation_2022" / "outputs"
d = DataWrapper.init_from_pickle(pkl)
provs, cfg = build_config(d, 0, quarters)
m = Simulation.from_datawrapper(datawrapper=d, simulation_configuration=cfg)
battery = AccountingBattery()
m.posthooks.append(battery)
m.posthooks.append(lambda sim, t, y, mo: print(f"t={t} goods settlement (USD):",
                                               getattr(sim.goods_market, "states", {}).get("settlement")))
for t in range(quarters):
    m.iterate(t)
df = battery.frame()
df.to_csv(out / f"accounting_smoke_{tag}_by_region.csv", index=False)
nat = summarise(df)
nat.to_csv(out / f"accounting_smoke_{tag}_national.csv")
with np.printoptions(suppress=True):
    print((nat / 1e9).round(4).T.to_string())
