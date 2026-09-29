#!/usr/bin/env python3
"""Shared configuration helpers for the Canada provincial MacroABM.

Exports the province list, the pinned-pickle loader guard and the provincial
simulation configuration used by ``scenarios/run_cims_linkage.py`` and by the
M3-linkages driver (``scripts/run_cer_linkage.py``).

The production data pickle (2022 OECD-50 IO base, 10 provinces, v2 PUMF households)
is built by ``dev/io2022/build_2022_datawrapper_10prov.py`` and pinned under
``dev/pkl_files/``; this module does not build data.
"""

from __future__ import annotations

from pathlib import Path

from macro_data.configuration.region import Region
from macromodel.configurations import CountryConfiguration, SimulationConfiguration

CANADIAN_PROVINCES = [
    Region.from_code("CAN_AB", "Alberta"),
    Region.from_code("CAN_BC", "British Columbia"),
    Region.from_code("CAN_MB", "Manitoba"),
    Region.from_code("CAN_NB", "New Brunswick"),
    Region.from_code("CAN_NL", "Newfoundland and Labrador"),
    Region.from_code("CAN_NS", "Nova Scotia"),
    Region.from_code("CAN_ON", "Ontario"),
    Region.from_code("CAN_PE", "Prince Edward Island"),
    Region.from_code("CAN_QC", "Quebec"),
    Region.from_code("CAN_SK", "Saskatchewan"),
]

PROVINCE_LABELS = {
    "CAN_AB": "Alberta",
    "CAN_BC": "British Columbia",
    "CAN_MB": "Manitoba",
    "CAN_NB": "New Brunswick",
    "CAN_NL": "Newfoundland",
    "CAN_NS": "Nova Scotia",
    "CAN_ON": "Ontario",
    "CAN_PE": "PEI",
    "CAN_QC": "Quebec",
    "CAN_SK": "Saskatchewan",
}

PICKLE_BUILDER = "dev/io2022/build_2022_datawrapper_10prov.py"


def create_data_pickle(
    input_path: Path,
    pkl_path: Path,
    *,
    force: bool = False,
) -> None:
    """Ensure the provincial data pickle exists at *pkl_path*.

    The pickle is a pinned build artefact (see ``PICKLE_BUILDER``), not something a
    run constructs on the fly.  A missing pickle -- or ``force=True`` -- raises with
    instructions rather than building anything here.
    """
    if pkl_path.exists() and not force:
        print(f"Using existing data pickle at {pkl_path}.")
        return
    reason = "was requested to be rebuilt (force=True)" if pkl_path.exists() else "does not exist"
    raise FileNotFoundError(
        f"Provincial data pickle {pkl_path} {reason}. The production pickle is built by "
        f"`{PICKLE_BUILDER}` from the raw data under {input_path} and pinned under "
        "dev/pkl_files/; build it there (or point --pkl-path at the pinned file)."
    )


def build_simulation_configuration(
    n_industries: int,
    *,
    timesteps: int,
    seed: int,
    firms_bundles: list[list[int]] | None = None,
    use_obps_reg: bool = False,
) -> SimulationConfiguration:
    """Build the provincial simulation configuration.

    Args:
        n_industries: Number of industries in the disaggregated model.
        timesteps: Total simulation timesteps.
        seed: Random seed.
        firms_bundles: Optional list of substitution bundles (each a list of
            industry indices).  When provided, firms use ``BundledLeontief``
            production with bundle-weighted input targets, so inputs within a
            bundle are substitutable and investment arbitrages toward the cheaper
            member.  Used by the CIMS linkage to make energy carriers
            substitutable between CIMS milestones.  ``None`` (default) keeps the
            ``PureLeontief`` behaviour with no substitution.
        use_obps_reg: Enable Canada's Output-Based Pricing System on every province.
    """
    tfp_base_growth_rate = 0.001
    tfp_investment_elasticity = 0.5
    # The investment-driven TFP term contributes about +0.6%/yr at 0.01, in line with
    # Canadian MFP growth of ~0-1%/yr.  Wages are indexed to the TFP multiplier, so this
    # parameter also paces real wage growth.
    productivity_growth_investment_effectiveness = 0.01
    technical_coefficients_investment_effectiveness = 0.3
    diminishing_returns_factor = 0.1
    hurdle_rate = 0.01
    investment_effectiveness = 0.3
    technical_investment_effectiveness = 0.3
    technical_diminishing_returns = 0.1
    tfp_investment_share = 0.5
    max_investment_fraction = 0.2

    config = SimulationConfiguration(
        seed=seed,
        country_configurations={
            province: CountryConfiguration.n_industry_default(
                n_industries=n_industries, firms_bundles=firms_bundles
            )
            for province in CANADIAN_PROVINCES
        },
        t_max=timesteps,
    )

    if use_obps_reg:
        # Canada's Output-Based Pricing System: covered sectors pay the carbon price on
        # emissions above an output-based benchmark and are rebated below it.  Requires
        # emissions tracking, which Country enables when the fossil-fuel industries are
        # present in the provincial model.
        for province in CANADIAN_PROVINCES:
            config.country_configurations[province].use_obps_reg = True

    for province in CANADIAN_PROVINCES:
        firms = config.country_configurations[province].firms

        firms.functions.productivity_investment_planner.name = "SimpleProductivityInvestmentPlanner"
        firms.functions.productivity_investment_planner.parameters.update(
            {
                "n_firms": n_industries,
                "tfp_investment_share": tfp_investment_share,
                "max_investment_fraction": max_investment_fraction,
                "investment_effectiveness": investment_effectiveness,
                "technical_investment_effectiveness": technical_investment_effectiveness,
                "technical_diminishing_returns": technical_diminishing_returns,
                "hurdle_rate": hurdle_rate,
            }
        )

        firms.functions.productivity_growth.name = "SimpleTFPGrowth"
        firms.functions.productivity_growth.parameters = {
            "investment_effectiveness": productivity_growth_investment_effectiveness,
        }
        firms.parameters.tfp_base_growth_rate = tfp_base_growth_rate
        firms.parameters.tfp_investment_elasticity = tfp_investment_elasticity

        firms.functions.technical_coefficients_growth.name = "SimpleTechnicalGrowth"
        firms.functions.technical_coefficients_growth.parameters = {
            "investment_effectiveness": technical_coefficients_investment_effectiveness,
            "diminishing_returns_factor": diminishing_returns_factor,
        }

    return config
