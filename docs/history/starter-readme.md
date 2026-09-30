# Automotive Production Planning & Supply Shortage Management

## Current status

**Version 0.1: project definition and validated data foundation.**
The production baseline, optimizer, scenario engine and Streamlit app are future stages.
There are no optimization gains, financial savings or feasible-plan claims in this version.

## Business question

How should a vehicle manufacturer schedule orders and component flows over 14 days
to fulfil demand under material availability, supplier schedules, capacity and lead-time constraints?
Which intervention reduces the most delivery disruption?

## Start here

1. Read `docs/project_framework.md` for the build stages and decisions.
2. Read `docs/model_rules.md` for established rules and open interpretations.
3. Review `docs/data_dictionary.md` for all source-to-clean column mappings.
4. Open `reports/data_summary.json` and `reports/validation_checks.csv`.
5. Inspect `data/processed/planning.sqlite` using a SQLite client, or open the CSV files.

## Run the completed stage

Python 3.10 or newer. The preparation pipeline and tests use the standard library only.
From the extracted project folder:

```bash
python src/prepare_data.py
python -m unittest discover -s tests -v
```

The pipeline validates source hashes, types, keys, references and capacity coverage;
builds stable configuration IDs; reconciles demand and direct component requirements;
computes the arrival periods of previously initiated flows; and writes CSVs and SQLite.
It deliberately does not fill missing supplier schedule entries.

## Optional re-extraction

The original XLSB and twelve source CSV exports are included. The delivered pipeline
does not require Excel or a binary-workbook reader. Initial extraction used a temporary
LibreOffice XLSX conversion and openpyxl; the original binary workbook was not edited.

`src/extract_workbook.py` can separately read XLSB with pandas/pyxlsb or XLSX with openpyxl.
Those are optional extraction dependencies, not dependencies of the completed pipeline.
Re-extract to a different folder first and compare parsed values. Do not overwrite source
files or refresh their manifest without reviewing any changes.

```bash
python src/extract_workbook.py data/raw/2020_dataset_OfAutomotiveProductionNetwork.xlsb --out reextracted_source
```

## Layout

- `config/`: explicit project rules, including unresolved interpretations.
- `data/raw/`: unchanged uploaded workbook.
- `data/source/`: source column names and values, one CSV per worksheet.
- `data/processed/`: normalized tables, derived mappings and SQLite database.
- `docs/`: project framework, model rules, data dictionary and source attribution.
- `reports/`: generated validation results and data summary.
- `src/`: executable preparation and optional extraction code.
- `sql/`: descriptive exploration queries.
- `tests/`: conservation, timing and invalid-input tests.

## Attribution and limitations

Data: Andre Moetz, Mathias Quetschlich and Boris Otto (2020),
*Data for: Optimisation model for multi-item multi-echelon supply chains with nested multi-level products*,
Mendeley Data, V1, https://doi.org/10.17632/pr3sdy5vp3.1, CC BY 4.0.
Derived CSVs normalize column/group labels and add calculations; all changes are documented.
The dataset is a research planning case supported by simulation and industrial information,
not a current operational feed. See `docs/sources.md`.

This project is an independent learning implementation, not work performed for Volkswagen.
Forecasting, profit optimization, supplier reliability scoring and realized savings are outside v0.1.
