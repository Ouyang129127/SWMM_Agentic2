==========================================================
README – Original SWMM Simulation Files
==========================================================

1. Context
----------
This folder contains the original report files (.rpt) produced by the
Storm Water Management Model (SWMM) after running hydrological and
hydraulic simulations for each scenario. These files serve as the raw
input for the Python scripts developed in this project.

2. Relation to Python scripts
-----------------------------
The following scripts read the .rpt files and generate post-processed
outputs:

- scenarios_peak_depth_analysis.py  
  Reads the .rpt file of a specific scenario, extracts node depth data,
  and produces:  
  * scenarioXX_peak_statistics.csv → peak depth statistics  
  * scenarioXX_depth_timeseries.png → time series of selected nodes  

- scenarios_global_peak_analysis.py  
  Reads all .rpt files, extracts maximum depth curves and node
  statistics across scenarios, and produces:  
  * scenarioXX_peak_statistics.csv → individual peak depth statistics  
  * scenarioXX.pdf → individual time series plots  
  * all_scenarios_peak_statistics.csv → combined statistics  
  * all_scenarios_max_curves.pdf → comparative maximum depth curves  

3. Content
----------
- scenarioXX.rpt  
  Report file of scenario XX, containing simulation results such as:  
  * Node Depth Summary  
  * Node Inflow Summary  
  * Subcatchment Runoff Summary  
  * Storage Volume Summary  

4. Usage
--------
- Each .rpt file is directly read by the Python scripts.  
- The scripts extract node depths, inflows, and runoff information to
  compute statistics and generate comparative plots.  
- Researchers may also inspect the .rpt files directly for raw details
  of the simulation.  

5. Notes
--------
- Report files are in plain text format.  
- Each file corresponds to one simulated scenario (01 to 11).  
- These files are not modified; they remain as raw simulation outputs
  used by post-processing scripts.  

==========================================================
