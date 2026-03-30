# Quantum Chemistry AI Template

This template focuses on accelerating quantum chemistry computations using AI. The MACE package, which implements neural network potentials, is used to calculate energies and forces in molecular simulations.

While MACE-type neural networks are strong at predicting energies and forces, their use in molecular dynamics simulations also exposes meaningful links between architecture choices and simulation behavior. This template is a starting point for exploring that relationship.

## Datasets

Download the required datasets from this GitHub repository:
- <https://github.com/karsar/molecular_data/archive/refs/heads/main.zip>

After downloading, place the folder named after each molecule into `templates/MACE/`.

## Example Paper

An example generated paper is available here:
- <https://drive.google.com/file/d/1G_0QDmuBCVzbUGPTvWCSXWEVql9A8MSX/view?usp=sharing>

## Installation

Install the additional packages required for this template:

```bash
pip install mace-torch
pip install MDAnalysis
pip install statsmodels
```

Depending on your hardware, you may need to increase the timeout used in `run_experiment(folder_name, run_num, timeout=7200)`.
