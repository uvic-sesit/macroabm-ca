"""Full one-worker suite after HI candidate gates; no dependent 12-quarter runs."""
from pathlib import Path
import run_be_full_tests as t
HERE=Path(__file__).resolve().parent;t.OUT=HERE/'outputs/HI/verification';t.OUT.mkdir(parents=True,exist_ok=True)
t.main()
