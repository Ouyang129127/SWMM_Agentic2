UrbanDrainage event status
The repository stores rainfall/time-series definitions inside each scenario INP. The 11 scenarios share a common network structure but may differ in scenario-specific input sections.
Standalone timestamp/value files have now been extracted from the active rain-gage time series of cenario_01 through cenario_11. The mapping is recorded in manifest.json.
cenario_01 has one original rainfall point; the extractor adds a zero-intensity start point so the event satisfies the ScenarioAgent two-timestamp contract. The original SWMM INPs remain unchanged under raw/repository and swmm/scenarios.
