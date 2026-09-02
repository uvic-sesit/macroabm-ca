"""Import shim for dev.io2022.save_baseline_2022.

The closure diagnostics only import build_config from save_baseline_2022.
The HDF5 extraction helpers are used by that script's CLI verification path,
not by the baseline model builder exercised here.
"""


def open_run(*args, **kwargs):
    raise RuntimeError("h5_extract.open_run is not available in closure diagnostics.")


def load_matrix(*args, **kwargs):
    raise RuntimeError("h5_extract.load_matrix is not available in closure diagnostics.")


def load_series(*args, **kwargs):
    raise RuntimeError("h5_extract.load_series is not available in closure diagnostics.")
