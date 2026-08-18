"""Single configurable raw-data root for the CAN-2022 household prep + 2022 build tooling.

The production model (`macro_data`) is already root-agnostic: `DataWrapper.from_config` /
`DataReaders.from_raw_data` take an injected `raw_data_path` and read `raw_data_path/{hfcs, can_2022,
icio}`. Only the standalone `dev/` tooling scripts used to hardcode `dev/raw_data`. This helper removes that
hardcode and resolves ONE root, so a cloned repo works against the canonical root-level `raw_data/` while
the current local `dev/raw_data/` layout keeps working unchanged.

Resolution order:
  1. `$MACROABM_RAW_DATA` environment variable, if set (explicit override);
  2. `<repo>/raw_data/`  -- the canonical root-level layout, if it exists (pushed-repo / clone convention);
  3. `<repo>/dev/raw_data/`  -- the legacy local layout (backward compatibility; current default here).

Logical layout under the resolved root (files are git-ignored; see SOURCE_MANIFEST.md):
  raw_data/
  |- can_2022/
  |   |- pumf/{sfs_2023, cis_2022, shs_2023, shs_archive}/
  |   |- controls/                      # StatCan control tables incl. CHS 46-10-0083
  |   `- *_oecd50_by_province_*.csv     # CoE / employment / capital (2022 integration)
  |- hfcs/                              # SHARED member skeleton (all countries) -- NOT duplicated
  `- icio/                             # SHARED IO tables -- NOT duplicated
"""
from __future__ import annotations

import os
from pathlib import Path


def raw_data_root(repo_root: Path) -> Path:
    """Resolve the raw-data root (see module docstring for the order)."""
    env = os.environ.get("MACROABM_RAW_DATA")
    if env:
        return Path(env).expanduser()
    canonical = repo_root / "raw_data"
    if canonical.exists():
        return canonical
    return repo_root / "dev" / "raw_data"
