"""Full suite serially, after SG pre-run gates and read-only household probes."""
from pathlib import Path
import run_be_full_tests as t
HERE=Path(__file__).resolve().parent;t.OUT=HERE/'outputs/SG/verification';t.OUT.mkdir(parents=True,exist_ok=True)
if __name__=='__main__':t.main()
