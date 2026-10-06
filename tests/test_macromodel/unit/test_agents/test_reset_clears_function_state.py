"""Unit tests for the function state a reset has to clear.

update_functions patches the configured parameters onto the live function instance
unless the caller names it in force_reset, so a function carrying state of its own
survives a reset with that state intact.
"""

import numpy as np

from macromodel.configurations import FirmsConfiguration, IndividualsConfiguration

NEW_SEED = 987654321


def _exogenous_labour_force_configuration(seed):
    """A configuration selecting the demography that carries state, at the given seed."""
    configuration = IndividualsConfiguration()
    configuration.functions.demography.name = "ExogenousLabourForcePath"
    configuration.functions.demography.parameters = {"seed": seed}

    return configuration


class TestResetClearsFunctionState:
    def test_the_demand_estimator_loses_its_smoothed_demand(self, test_firms):
        test_firms.functions["demand_estimator"]._smoothed_demand = np.ones(len(test_firms.states))

        test_firms.reset(FirmsConfiguration())

        assert test_firms.functions["demand_estimator"]._smoothed_demand is None

    def test_the_demography_generator_follows_a_new_seed(self, test_individuals):
        # The first reset installs the stateful demography; the second is the one under test,
        # since a reset naming a different class reinstantiates whatever force_reset says.
        test_individuals.reset(_exogenous_labour_force_configuration(0))
        test_individuals.functions["demography"]._rng.random()

        test_individuals.reset(_exogenous_labour_force_configuration(NEW_SEED))

        demography = test_individuals.functions["demography"]
        assert demography.seed == NEW_SEED
        assert demography._rng.random() == np.random.default_rng(NEW_SEED).random()

    def test_the_demography_step_counter_is_cleared(self, test_individuals):
        test_individuals.reset(_exogenous_labour_force_configuration(0))
        test_individuals.functions["demography"]._t = 7

        test_individuals.reset(_exogenous_labour_force_configuration(0))

        assert test_individuals.functions["demography"]._t == -1
