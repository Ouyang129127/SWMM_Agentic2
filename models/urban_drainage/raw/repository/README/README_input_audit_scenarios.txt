==========================================================
README – Input Data Audit for Drainage Scenarios
==========================================================

1. Context
----------
This repository contains audit reports generated for the input data
of urban drainage scenarios. The reports were produced using the
Python script "scenarios_input_audit.py", which performs a quick
integrity and quality check on the scenario input CSV files.

2. Included files
-----------------
For each scenario (01 to 11), the following files are provided:

- scenarioXX.csv
  Input dataset of scenario XX. Contains the values for hydrological
  and hydraulic parameters required for simulation.

- scenarioXX_audit_report.txt
  Report generated from scenarioXX.csv. Summarizes the following
  information for each variable:
  * First value in the column
  * Number of non-empty values
  * Number of empty cells
  * Measurement unit

3. Generation script
--------------------
File: scenarios_input_audit.py

Description: Iterates through the input CSV files, extracts basic
statistics and integrity checks for each variable, and generates
an audit report in TXT format.

4. Folder structure
-------------------
- /scenarios
   |-- scenario01.csv
   |-- scenario01_audit_report.txt
   |-- scenario02.csv
   |-- scenario02_audit_report.txt
   ...
   |-- scenario11.csv
   |-- scenario11_audit_report.txt

- scenarios_input_audit.py
- README_input_audit_scenarios.txt

5. Notes
--------
- Units for each variable are predefined in the script and included
  in the audit reports.
- Empty cells are explicitly counted for quality control.
- This dataset ensures transparency and traceability of the input
  data used for hydrological simulations.

==========================================================
