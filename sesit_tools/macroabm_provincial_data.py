RAW_DATA_PATH = "C:/Users/deven/University of Victoria/SESIT (O) - Documents/SESIT Shared Team/Individual storage/Deven Azevedo/projects/macroABM/raw_data" # @param {"type":"string","placeholder":"data"}
PKL_PATH = "C:/gitlab/projects/macroabm/pkl_files/disagg_sectorprovs_260124.pkl" # @param {"type":"string", "placeholder":"data.pkl"}


import macro_data
from macro_data import configuration_utils
from macro_data.configuration.countries import Country as CountryCode
from macro_data.configuration.region import Region
from macro_data import configuration_utils
from macro_data import DataWrapper
from pathlib import Path
from macromodel.configurations import SimulationConfiguration, CountryConfiguration
from macromodel.simulation import Simulation


data_config = configuration_utils.default_data_configuration(
            countries=["CAN"],
            aggregate_industries=False,
            proxy_country_dict={"CAN": "FRA"},
        )

data_config.year = 2014

data_config.can_disaggregation = True
data_config.aggregate_industries = False
data_config.prune_date = None
data_config.seed = 0

base_config = data_config.country_configs[CountryCode("CAN")]
base_config.single_firm_per_industry = True
base_config.single_bank = True
base_config.single_government_entity = True

base_config.firms_configuration.constructor = "Default"

base_config.scale = 1000

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

for province in provinces:
    data_config.country_configs[province] = base_config
    data_config.country_configs[province].eu_proxy_country = CountryCode("FRA")

data_config.aggregation_structure = {CountryCode("CAN"): provinces}


# Create DataWrapper instance
creator = DataWrapper.from_config(
    configuration=data_config,
    raw_data_path=RAW_DATA_PATH,
    single_hfcs_survey=True  # Use single survey for household finance data
)

creator.save(PKL_PATH)
