==========================================================
README – Hydrological Simulation Dataset
==========================================================

1. Context
----------
This repository contains output files generated from hydrological
simulations using the SWMM model and the Python script
"scenarios_peak_depth_analysis.py". The simulations represent
different urban drainage scenarios.

2. Included files
-----------------
For each scenario (01 to 11), the following files are provided:

- scenarioXX_peak_statistics.csv
  Descriptive statistics of simulated water depths (m) in the nodes
  of scenario XX. Includes maximum peak, minimum peak, mean peak,
  and standard deviation.

- scenarioXX_depth_timeseries.png
  Time series plot of water depth (m) in selected nodes of scenario XX.
  Five nodes were chosen: the one with the highest peak, the one with
  the lowest peak, and three intermediate nodes.

3. Generation script
--------------------
File: scenarios_peak_depth_analysis.py

Description: Runs the SWMM simulation for each scenario, extracts the
time series of water depth at all nodes, calculates peak depth
statistics, generates tables in CSV format, and produces comparative
time series plots in PNG format.

4. Folder structure
-------------------
- /scenarios
   |-- scenario01_peak_statistics.csv
   |-- scenario01_depth_timeseries.png
   |-- scenario02_peak_statistics.csv
   |-- scenario02_depth_timeseries.png
   ...
   |-- scenario11_peak_statistics.csv
   |-- scenario11_depth_timeseries.png

- scenarios_peak_depth_analysis.py
- README_drainage_scenarios.txt

5. Notes
--------
- Depth units are expressed in meters (m).
- Time axis in plots is expressed in hours and minutes (hh:mm).
- The dataset can be cited in scientific works as supporting data
  for urban drainage studies.

==========================================================
