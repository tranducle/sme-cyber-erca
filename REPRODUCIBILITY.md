# Reproducibility Guide

## 1. Environment Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Data Preparation
After obtaining the official dataset extract from UKDS and placing it in `data/raw/`, run the harmonization pipeline:
```bash
python scripts/harmonize_weights.py
python scripts/build_model_input.py
python scripts/build_prefit_assets.py
```

## 3. Statistical Analysis
To run the primary criterion-validity analysis:
```bash
python experiments/run_primary_analysis.py
```

To run the longitudinal/temporal robustness tests:
```bash
python experiments/run_temporal_analysis.py
```

## 4. Figures and Visualization
To rebuild the exposure-response surface response curves and margin plots:
```bash
python scripts/build_figures.py
```
