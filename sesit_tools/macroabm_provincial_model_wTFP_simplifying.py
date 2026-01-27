PKL_PATH = "C:/gitlab/projects/macroabm/pkl_files/disagg_sectorprovs_260124.pkl" # @param {"type":"string", "placeholder":"data.pkl"}


# Run Simulation
import macro_data
from macro_data import configuration_utils
from macro_data.configuration.countries import Country as CountryCode
from macro_data.configuration.region import Region
from macro_data import configuration_utils
from macro_data import DataWrapper
from macromodel.configurations import SimulationConfiguration, CountryConfiguration
from macromodel.simulation import Simulation

from macro_data.configuration.region import Region
import pickle as pkl

data = DataWrapper.init_from_pickle(PKL_PATH)

TimeSteps = 10
OUTPUT_Directory = "C:/gitlab/projects/macroabm/output/" 
OUTPUT_FileName = "results_provinces_260124_wTFP_simple3.h5" 

COUNTRIES = "CAN" 
# Define Canadian provinces
provinces = [
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

countries = provinces

n_industries = data.n_industries
config = SimulationConfiguration(
    seed =1,
    country_configurations={
        country: CountryConfiguration.n_industry_default(n_industries=n_industries)
        for country in countries
    },
    t_max=TimeSteps,
)

# Configure productivity investment (both TFP and technical coefficients)
for country in countries:
    firms_config = config.country_configurations[country].firms
    individuals_config = config.country_configurations[country].individuals

    # Enable productivity investment planner
    firms_config.functions.productivity_investment_planner.name = "SimpleProductivityInvestmentPlanner"
    firms_config.functions.productivity_investment_planner.parameters.update(
        {
            "tfp_investment_share": 0.5,  # 50% to TFP, 50% to technical coefficients
            "max_investment_fraction": 0.2,  # Allow up to 20% of available cash
            "investment_effectiveness": 0.3,  # Effectiveness for TFP
            "technical_investment_effectiveness": 0.3,  # Effectiveness for technical coefficients
            "technical_diminishing_returns": 0.1,  # Diminishing returns for technical
            "hurdle_rate": 0.01,  # Low hurdle rate
        }
    )

    # Enable TFP growth
    firms_config.functions.productivity_growth.name = "SimpleTFPGrowth"
    firms_config.functions.productivity_growth.parameters = {
        "investment_effectiveness": 0.3,
    }
    firms_config.parameters.tfp_base_growth_rate = 0.001  # 0.1% base growth
    firms_config.parameters.tfp_investment_elasticity = 0.5

    # Enable technical coefficient growth
    firms_config.functions.technical_coefficients_growth.name = "SimpleTechnicalGrowth"
    firms_config.functions.technical_coefficients_growth.parameters = {
        "investment_effectiveness": 0.3,
        "diminishing_returns_factor": 0.1,
    }

 
model = Simulation.from_datawrapper(
    datawrapper=data, simulation_configuration=config
)

model.run()
model.save(save_dir=OUTPUT_Directory, file_name=OUTPUT_FileName)
