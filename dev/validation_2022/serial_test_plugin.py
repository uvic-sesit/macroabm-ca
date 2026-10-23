"""Respect the review's one-simulation-at-a-time constraint in the full suite.

The sampler fixture otherwise defaults to half the machine's CPU count. Keep
its test and assertions, but execute its five draws through one worker.
"""


def pytest_runtest_call(item):
    sampler = item.funcargs.get("sampler")
    if sampler is not None and hasattr(sampler, "n_cores"):
        sampler.n_cores = 1
