# Macrocosm's Macromodel Documentation

Welcome to the documentation for Macrocosm's Macromodel, a comprehensive economic modeling framework. The project is organized into three main packages, each with its own specific functionality and documentation:

## Core Packages

### 1. macro_data

The data preprocessing and management package that handles:

- Creation of synthetic economic data
- Data preprocessing and validation
- Input-output table processing
- Trade flow calculations
- Exchange rate management
- Emissions data processing

[View macro_data documentation →](macro_data/index.md)

### 2. macromodel

The core modeling package that implements:

- Economic agent behaviors
- Market mechanisms
- Policy implementations
- Simulation engine
- Results processing

[View macromodel documentation →](macromodel/index.md)

### 3. macrocalib

The calibration package that provides:

- Model calibration tools
- Parameter estimation
- Validation methods
- Performance metrics
- Optimization algorithms

[View macrocalib documentation →](macrocalib/index.md)

## Getting Started

- [Installation Guide](getting_started/installation.md)
- [Quick Start Tutorial](getting_started/quickstart.md)
- [Basic Usage Examples](examples/basic_usage.md)
- [Canada Provincial IO Development Note](canada_provincial_io_development.md)

## Documentation Structure

Each package's documentation is organized into the following sections:

1. **Overview**: Package purpose and key features
2. **Core Components**: Main classes and their relationships
3. **Data Processing**: Data handling and transformation
4. **API Reference**: Detailed API documentation
5. **Examples**: Usage examples and tutorials
6. **Best Practices**: Guidelines and recommendations

## Contributing

New to the project? Start with our comprehensive contribution guides:

### Getting Started with Contributing
- [Project Structure Guide](contributing/project_structure.md) - **Start here** to understand where to contribute
- [Development Guide](contributing/development.md) - Development workflow and repository guidelines
- [Code Style Guide](contributing/style_guide.md) - Formatting, naming, and documentation standards
- [Testing Guidelines](contributing/testing.md) - Testing requirements and sample data

### Package-Specific Guides
- [Contributing to macro_data](contributing/macro_data.md) - Adding new data sources and readers
- [Contributing to macromodel](contributing/macromodel.md) - Adding agents, functions, and simulation features

The project is designed for use by multiple teams. Please read our [repository guidelines](contributing/development.md#repository-guidelines) to keep the codebase generic and maintainable.

## Canada (MacroABM-CA)

Documentation specific to the Canadian provincial adaptation, as used for the
*Powering Canada's Growth* analysis:

- [Overview](canada/index.md) - What MacroABM-CA is, the configuration used for the analysis, and how to reproduce a run
- [Onboarding Guide](canada/onboarding_guide.md) - Repository layout, where raw data enters, model components, team workflow
- [Data Build](canada/data_build.md) - How the pinned 2022 provincial population pickle was built
- [Raw Data Reference](canada/raw_data_reference.md) - Every raw-data input of the 2022 provincial build and how it is used

## Support

- For the Canadian adaptation, open an issue on [uvic-sesit/macroabm-ca](https://github.com/uvic-sesit/macroabm-ca). For the shared framework, open an issue on the [INET](https://github.com/inet-complexity/macro-main) or [macrocosm](https://github.com/macro-cosm/macro-main/) repositories.
