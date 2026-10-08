# Exposure-Response Co-Alignment in Cybersecurity Maturity

> **Anonymous Repository for Double-Blind Review**
> This repository contains the reproduction code and materials for the manuscript: *Exposure-Response Co-Alignment in Cybersecurity Maturity for UK SMEs: A Prespecified Criterion-Validity Study*.

## Overview

Cybersecurity maturity assessments often evaluate capability without referencing the organization's underlying digital exposure. This study evaluates the empirical criterion validity of **Exposure-Response Co-Alignment (ERCA)** - the principle that cybersecurity response capacity should be measured relative to digital exposure demand. 

Using harmonized microdata from the UK Cyber Security Breaches Survey (CSBS) and the Cyber Security Longitudinal Survey (CSLS), we conduct a prespecified polynomial logistic analysis to test whether a higher response capacity at a given level of exposure yields the protective pattern implied by an adequacy interpretation.

## Repository Structure

```text
├── README.md                 # Overview and citation
├── DATA.md                   # Instructions for accessing the synthetic and official data
├── REPRODUCIBILITY.md        # Exact end-to-end reproduction steps
├── requirements.txt          # Python dependencies
├── src/                      # Helper modules and reusable functions
├── experiments/              # Analytical models and criterion tests
│   ├── run_primary_analysis.py
│   └── run_temporal_analysis.py
├── scripts/                  # Data preparation and output formatting
│   ├── harmonize_weights.py
│   ├── build_model_input.py
│   ├── build_prefit_assets.py
│   └── build_figures.py
```

## Reproducibility

This repository provides all the code required to run the primary analyses, generate statistical models, and reproduce the figures used in the manuscript.

Please refer to [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for step-by-step instructions on setting up the environment, preparing the input files, and executing the analytical pipeline.

## Data Availability

To preserve respondent anonymity and comply with data governance regulations, the raw microdata cannot be shared directly. We provide access instructions for the official datasets and details on the synthetic data used for the public test suite in [DATA.md](DATA.md).

## License

Code is provided under the MIT License.
