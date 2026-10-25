"""Full tests after serial measurements, using the one-worker sampler wrapper."""
from pathlib import Path
import run_be_full_tests as runner

if __name__=='__main__':
    runner.OUT=Path(__file__).resolve().parent/'outputs/B2/verification'
    runner.OUT.mkdir(parents=True,exist_ok=True)
    # The inherited runner uses an exclusive temp path and records the exact command.
    runner.main()
