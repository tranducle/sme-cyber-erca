# Data Availability

## Official Dataset Access

The raw datasets analyzed in this study—the UK Cyber Security Breaches Survey (CSBS) and the Cyber Security Longitudinal Survey (CSLS)—are subject to usage conditions set by the Department for Science, Innovation and Technology (DSIT) and the UK Data Service (UKDS). To protect respondent confidentiality, raw microdata containing demographic and geographic identifiers cannot be redistributed.

Researchers may request access to the data directly from the UK Data Service (UKDS):
- **CSBS (2019-2022)**: [UK Data Service - Study 8971](https://beta.ukdataservice.ac.uk/datacatalogue/studies/study?id=8971)

## Data Preparation

To reproduce the study's models using authorized data extracts, the raw SPSS/Stata files from UKDS must be placed in the `data/raw/` directory (created locally). 
The data pipeline script (`scripts/build_model_input.py`) will automatically harmonize the retrospective weights and filter the sample boundaries.
