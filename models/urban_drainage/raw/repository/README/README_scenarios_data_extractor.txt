==========================================================
README – SWMM Scenario Data Extraction and Validation
==========================================================

1. Context
----------
This repository contains structured datasets generated from SWMM input
(.inp) and report (.rpt) files for a series of urban drainage scenarios.
The files were processed using the Python script
"scenarios_data_extractor.py", which performs parsing, consolidation,
and validation of hydrological and hydraulic variables.

2. Included files
-----------------
For each scenario (01 to 11), the following files are provided:

- scenarioXX.csv
  Structured dataset with hydrological and hydraulic variables extracted
  from both .inp and .rpt files. Includes subcatchment parameters,
  node-level metrics, infiltration, runoff, flow, and storage values.

- scenarioXX.parquet
  Same dataset as scenarioXX.csv but saved in Apache Parquet format for
  optimized performance in large-scale data analysis.

- scenarioXX_audit_report.txt
  Audit report of scenarioXX.csv. Provides an overview of the dataset
  including:
  * First value for each variable
  * Number of non-empty values
  * Number of empty cells
  * Measurement unit

3. Generation script
--------------------
File: scenarios_data_extractor.py

Description: Iterates through all scenarios, parses SWMM input (.inp)
and report (.rpt) files, extracts hydrological and hydraulic variables,
constructs structural mappings (B → P → G), calculates derived indicators
(e.g., RAZA, CLBO, PSUP, PINF), and saves results in multiple formats.

4. Variables included
---------------------
Key variables stored in the datasets:

- AREA: Subcatchment area (m²)
- DECL: Slope (%)
- DURC: Rainfall duration (min)
- VCHU: Total precipitation (mm)
- IMPV: Imperviousness (%)
- TIPO: Subcatchment type (lot or street)
- DIAM: Conduit diameter (m)
- LESC: Subcatchment width (m)
- PMAX: Maximum depth (m)
- VAZT: Maximum total inflow (m³/s)
- VTOT: Total inflow volume (10^6 L)
- RAZA: Ratio PMAX/ALTC
- CLBO: Classification ("Normal", "Overloaded", "Overflow")
- KSAT: Saturated hydraulic conductivity (mm/h)
- ALTC: Junction height (m)
- VSUP: Surface runoff volume (m³)
- VINF: Infiltrated volume (m³)
- VGER: Total generated volume (m³)
- PSUP: Surface runoff ratio
- PINF: Infiltration ratio
- VINI: Initial volume (mm)
- VEVA: Evaporation (mm)
- VRET: Retention (mm)
- VSTO: Final storage (mm)
- ERRO: Mass balance error (%)

5. Folder structure
-------------------
- /scenarios
   |-- scenario01.csv
   |-- scenario01.parquet
   |-- scenario01_audit_report.txt
   |-- scenario02.csv
   |-- scenario02.parquet
   |-- scenario02_audit_report.txt
   ...
   |-- scenario11.csv
   |-- scenario11.parquet
   |-- scenario11_audit_report.txt

- scenarios_data_extractor.py
- README_scenarios_data_extractor.txt

6. Notes
--------
- Depths are expressed in meters (m).
- Precipitation totals and rainfall durations are mapped from scenario
  IDs to their respective time series.
- The audit reports ensure data transparency and traceability.
- This dataset provides comprehensive input-output variables for
  advanced modeling and analysis in urban drainage studies.

==========================================================
