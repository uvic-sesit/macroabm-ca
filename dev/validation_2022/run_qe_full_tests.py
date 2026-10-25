"""Final full suite, serial sampler, preserving all previous verification files."""
from pathlib import Path
import run_be_full_tests as runner

if __name__=='__main__':
    runner.OUT=Path(__file__).resolve().parent/'outputs/QE/verification'
    runner.OUT.mkdir(parents=True,exist_ok=True)
    runner.main()
