UrbanDrainage event status

## Current synthetic rainfall inputs (updated 2026-10-09)

All six files use timestamp,value, intensity in mm/h, 5-minute interval-start values, a 4-hour span, and a terminal zero at 04:00. These are Chicago-like synthetic events, not locally calibrated design storms; no return period is assigned.

- chicago_like_single_4h_60mm_5min.txt — added; existing single-peak 80 mm values scaled by 0.75.
- chicago_like_single_4h_80mm_5min.txt — existing, unchanged.
- chicago_like_single_4h_120mm_5min.txt — added; existing single-peak 80 mm values scaled by 1.5.
- chicago_like_double_4h_80mm_5min.txt — existing, unchanged.
- chicago_like_double_4h_160mm_5min.txt — added; existing double-peak 80 mm values scaled by 2.
- chicago_like_triple_4h_80mm_5min.txt — existing, unchanged.

Generation metadata, validation, and comparison plots for the three additions are in ../rainfall_generation/20261009/. The application discovers event files directly from this directory. manifest.json below is a historical scenario-extraction mapping, not the current synthetic-event inventory; the mapped cenario_* files are not currently present here.

## Historical scenario-extraction notes (preserved)

The repository stores rainfall/time-series definitions inside each scenario INP. The 11 scenarios share a common network structure but may differ in scenario-specific input sections.
Standalone timestamp/value files have now been extracted from the active rain-gage time series of cenario_01 through cenario_11. The mapping is recorded in manifest.json.
cenario_01 has one original rainfall point; the extractor adds a zero-intensity start point so the event satisfies the ScenarioAgent two-timestamp contract. The original SWMM INPs remain unchanged under raw/repository and swmm/scenarios.
