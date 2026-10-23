"""Run requested pytest checks with the sampler constrained to one worker.

Pytest itself is serial, but the sampler fixture defaults to cpu_count()/2.
This hook changes only that execution parameter, without skipping any test.
"""
import sys

import pytest


class SerialSampler:
    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_call(self,item):
        if item.nodeid.endswith('test_sampler.py::test_sampler'):
            item.funcargs['sampler'].n_cores=1
            item.user_properties.append(('sampler_n_cores',1))


if __name__=='__main__':
    raise SystemExit(pytest.main(sys.argv[1:] or ['tests/','-q'],plugins=[SerialSampler()]))
