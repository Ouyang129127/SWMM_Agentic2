==========================================================
README – Global Hydrological Simulation Dataset
==========================================================

1. Context
----------
This repository contains output files generated from hydrological
simulations using the SWMM model and the Python script
"scenarios_global_peak_analysis.py". The simulations cover a set of
urban drainage scenarios (01 to 11).

2. Included files
-----------------
For each scenario (01 to 11), the following files are provided:

- scenarioXX_peak_statistics.csv
  Descriptive statistics of simulated water depths (m) in the nodes
  of scenario XX. Includes maximum peak, minimum peak, mean peak,
  and standard deviation.

- scenarioXX.pdf
  Time series plot of water depth (m) in selected nodes of scenario XX.
  Five nodes were chosen: the one with the highest peak, the one with
  the lowest peak, and three intermediate nodes.

Additionally, two consolidated files are available:

- all_scenarios_peak_statistics.csv
  Combined table containing peak depth statistics for all scenarios.

- all_scenarios_max_curves.pdf
  Comparative plot showing the maximum depth curves across all scenarios.

3. Generation script
--------------------
File: scenarios_global_peak_analysis.py

Description: Runs SWMM simulations for all scenarios, extracts the time
series of water depth, calculates peak depth statistics, saves
individual scenario files (CSV and PDF), and generates consolidated
outputs.

4. Folder structure
-------------------
- /scenarios
   |-- scenario01_peak_statistics.csv
   |-- scenario01.pdf
   |-- scenario02_peak_statistics.csv
   |-- scenario02.pdf
   ...
   |-- scenario11_peak_statistics.csv
   |-- scenario11.pdf

- all_scenarios_peak_statistics.csv
- all_scenarios_max_curves.pdf
- scenarios_global_peak_analysis.py
- README_global_drainage_scenarios.txt

5. Notes
--------
- Depth units are expressed in meters (m).
- Time axis in plots is expressed in hours and minutes (hh:mm).
- The dataset can be cited in scientific works as supporting data
  for urban drainage studies.

==========================================================
