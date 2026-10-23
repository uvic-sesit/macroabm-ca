"""Build a new, auditable bank-capital input; never overwrite accepted inputs."""
import hashlib
import json
from pathlib import Path

import pandas as pd
from macro_data import DataWrapper
from macro_data.processing.synthetic_banks.canadian_book_capital import allocate_canadian_book_capital

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'dev/pkl_files/io2022_household_agreed.pkl'
TARGET = ROOT / 'dev/pkl_files/io2022_household_agreed_bankcap.pkl'
OUT = ROOT / 'dev/validation_2022/outputs/ABCD'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if TARGET.exists():
        raise FileExistsError(f'Refusing to overwrite {TARGET}')
    before = sha(SOURCE)
    data = DataWrapper.init_from_pickle(SOURCE)
    rows = pd.DataFrame(allocate_canadian_book_capital(data.synthetic_countries))
    rows['resolution_threshold'] = .05
    OUT.mkdir(parents=True, exist_ok=True)
    rows.to_csv(OUT / 'initial_bank_capital.csv', index=False)
    if (rows.resolution_ratio <= rows.resolution_threshold).any():
        raise RuntimeError('At least one bank starts at/below the resolution threshold; stop before running')
    data.save(TARGET)
    assert sha(SOURCE) == before
    provenance = json.loads((ROOT / 'dev/validation_2022/benchmarks/pre_D3_checks/bank_equity_provenance.json').read_text())
    provenance.update(source_pickle_sha256=before, new_pickle_sha256=sha(TARGET),
                      source_pickle=str(SOURCE.relative_to(ROOT)), new_pickle=str(TARGET.relative_to(ROOT)),
                      allocation='Initial loans to firms plus households; all 13 regions normalized jointly',
                      vectors={'v62696428': 405572e6, 'v62696533': 50649e6})
    (OUT / 'bankcap_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(rows.to_string(index=False))
    print('National equity:', rows.equity.sum(), 'New input SHA256:', sha(TARGET))


if __name__ == '__main__':
    main()
