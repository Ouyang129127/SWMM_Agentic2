# Urban Drainage – Simulations and Data Extraction with SWMM

## 1. Context
This repository contains the files, scripts, and reports generated from hydrological and hydraulic simulations using the **Storm Water Management Model (SWMM)**.  
The objective is to analyze the behavior of the urban drainage system under different rainfall, imperviousness, and soil parameter scenarios, as well as to consolidate datasets for use in **supervised machine learning models**.

---

## 2. Execution Plan

### (i) Simulation of urban scenarios in SWMM
A total of **8 distinct scenarios** were simulated, varying:  
- **Rainfall duration**: 5, 20, 60 minutes  
- **Imperviousness levels**: 75%, 87.5%  
- **Curve Number (CN)**: 85 (lots), 98 (streets)  

For each scenario, the following outputs were generated:  
- `.rpt` and `.out` files (raw SWMM outputs)  
- Individual plots of depth curves at selected nodes  
- `.csv` files containing hydrological statistics per subcatchment  
- Hydraulic classification of storm drains: **Normal, Overloaded, or Overflow**

---

### (ii) Construction of the consolidated database
From the simulations, a table was created where each row represents a **subcatchment**, containing:

**Geometric and hydrological explanatory variables (X):**
- Subcatchment area (m²)  
- Imperviousness (%)  
- Curve Number (CN)  
- Subcatchment type (lot or street)  
- Overland flow path length (m)  
- Average terrain slope (%)  
- Rainfall duration (min)  
- Total precipitation volume (mm)  
- Maximum depth (m)  
- Time to peak (min)  
- Depth/inspection chamber height ratio (dimensionless)  

**Soil-related explanatory variables (when simulated via Green-Ampt):**
- Saturated hydraulic conductivity (Ksat, mm/h)  
- Suction head at wetting front (Ψ, mm)  
- Initial soil moisture (θinit, fraction)  
- Effective soil layer depth (m)  
- Soil texture (categorical: sandy, loam, clay, etc.)  

**Target variable (y):**
- Operational class of storm drain: **Normal / Overloaded / Overflow**

The final consolidated dataset is stored in **`df_final.csv`**, including all explanatory variables and the corresponding target classification.

---

## 3. Scripts and Outputs

### Main scripts
- **`scenarios_peak_depth_analysis.py`** → analyzes depth in a single scenario  
- **`scenarios_global_peak_analysis.py`** → consolidates statistics and curves across scenarios  
- **`scenarios_input_audit.py`** → audits input `.csv` files  
- **`scenarios_data_extractor.py`** → extracts and organizes hydrological, hydraulic, and soil variables  

### Generated outputs
- `.csv` statistics (maximum, minimum, mean, standard deviation)  
- Time series plots in `.png` or `.pdf`  
- Audit reports in `.txt`  
- Structured datasets in `.csv` and `.parquet`  

---

## 4. Folder Structure
```
/scenarios
   ├── scenarioXX.rpt                # Original SWMM report files
   ├── scenarioXX_peak_statistics.csv
   ├── scenarioXX_depth_timeseries.png / .pdf
   ├── scenarioXX.csv                 # Structured datasets
   ├── scenarioXX.parquet
   ├── scenarioXX_audit_report.txt
   ...
/outputs
   ├── all_scenarios_peak_statistics.csv
   ├── all_scenarios_max_curves.pdf
scenarios_peak_depth_analysis.py
scenarios_global_peak_analysis.py
scenarios_input_audit.py
scenarios_data_extractor.py
```

---

## 5. Tools and Technologies
- **SWMM** for hydrological and hydraulic simulations  
- **Python (pandas, matplotlib, pySWMM)** for data extraction, analysis, and visualization  
- **Apache Parquet** for optimized data storage  
- Audit scripts to ensure **transparency and traceability** of the data  

---

## 6. Notes
- All depths are expressed in **meters (m)**  
- Rainfall duration in **minutes (min)**  
- Volumes in **m³** or **mm**, depending on the variable  
- Data are suitable for **scientific publications**, **reproducibility studies**, and **machine learning applications**  

---
