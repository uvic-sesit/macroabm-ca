import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import followup_e16 as fu, run_batch, run_historical_experiment as historical
ID = "ABL7_full_alpha040"
specs = {sid: s for sid, _, s in fu.ablation_specs()}
spec = dict(specs["ABL4_full_e16"]); spec["demand_smoothing"] = 0.40
spec["description"] = "alpha=0.40 + all four substantive changes (30-seed validation)"
data = historical.DataWrapper.init_from_pickle(historical.PKL)
for seed in range(30):
    p = historical.DEFAULT_OUT/ID/f"seed{seed:03d}"/"national_quarterly.csv"
    if not p.exists():
        print(f"RUN {ID} seed={seed}", flush=True); run_batch.run_seed(data, spec, ID, seed, fu.Q_HIST, historical.DEFAULT_OUT)
    else:
        print(f"SKIP {ID} seed={seed}", flush=True)
print("alpha040 30-seed: complete", flush=True)
