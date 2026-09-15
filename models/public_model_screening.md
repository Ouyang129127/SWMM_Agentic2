# Public SWMM Model Screening for SWMM Agentic2

## Purpose

This inventory separates three uses of public SWMM material:

1. **Benchmark model projects**: independent SWMM systems used to test model discovery, scenario preparation, simulation, extraction, diagnosis, verification, and reporting.
2. **CA2D construction references**: cases containing GIS or terrain information that can support a reproducible surface-model construction workflow.
3. **Scenario and output references**: cases useful for batch execution, event management, and result summarisation, but not sufficient on their own to establish a new spatially consistent CA2D model.

The public repositories are not treated as physical validation data by default. Unless a source provides documented terrain, land cover, drainage geometry, calibration information, and observations, the resulting project is a **benchmark or synthetic/semi-real test case**, not a validated representation of a real city.

## Initial screening

| Source | Example or unit | SWMM content | GIS/CA2D readiness | Recommended role | Priority |
|---|---|---|---|---|---|
| [SWMMEnablement/1729-SWMM5-Models](https://github.com/SWMMEnablement/1729-SWMM5-Models) | Greenville | 30 subcatchments, 149 junctions, 223 conduits, 17 storage units, 5 pumps, coordinates and rainfall/time-series data | No general GIS surface package identified; coordinates are not equivalent to DEM/land-use/flow-direction data | Benchmark project for hydraulic structures and model-scale diversity | P1 |
| [SWMMEnablement/1729-SWMM5-Models](https://github.com/SWMMEnablement/1729-SWMM5-Models) | WestCampusWatershed | 30 subcatchments, 47 junctions, 47 conduits, 5 outfalls, one-year example run | No independent terrain package identified | Small benchmark project for workflow debugging and reproducibility | P1 |
| [SWMMEnablement/1729-SWMM5-Models](https://github.com/SWMMEnablement/1729-SWMM5-Models) | Semi_Real 1045 | 56 subcatchments, 500 junctions, 486 conduits, 22 outfalls, 4 pumps | No general GIS surface package identified | Medium-scale benchmark; stress diagnosis and extraction | P1 |
| [SWMMEnablement/1729-SWMM5-Models](https://github.com/SWMMEnablement/1729-SWMM5-Models) | Simon EPA sessions | Many focused examples for LID, pumps, storage, controls, routing, and unusual hydraulic cases | Usually a test/regression model rather than a spatially complete case | Targeted benchmark task families, not necessarily separate model projects | P1 |
| [AaltoUrbanWater/GisToSWMM5](https://github.com/AaltoUrbanWater/GisToSWMM5) | demo_catchment | GIS inputs, network shapefiles, DEM, flow direction, land-use rasters, rainfall data, generated SWMM inputs and GIS outputs | Strongest of the three sources; supports reproducible GIS-to-subcatchment construction | CA2D model-building skill and end-to-end spatial workflow reference | P1 |
| [marmargarida/UrbanDrainage](https://github.com/marmargarida/UrbanDrainage) | cenario_01–cenario_11 | Same approximately 218-subcatchment/97-junction network across 11 simulation scenarios, with INP, RPT, OUT, CSV, Parquet, and PDF outputs | No DEM, land-use, surface grid, or node-to-cell package identified | Batch scenario and result-extraction reference; not 11 independent networks | P2 |

## What this means for the paper

The `songhua_swmm_2d` project remains the current large coupled demonstration. The public cases should be added to test whether the Agentic workflow generalises across model structures and scenario types:

- **Model information tasks**: identify objects, sections, events, and existing runs.
- **Simulation tasks**: prepare an event and execute a deterministic SWMM/CA2D pipeline where a CA2D package exists.
- **Extraction tasks**: retrieve flooding, link loading, surface depth, duration, and event metadata.
- **Diagnosis tasks**: generate rule-bound claims from the evidence table.
- **Verification/report tasks**: check claim–evidence links and produce a traceable report.

The `1729` cases can therefore enlarge the benchmark even when they do not contain a defensible CA2D surface. A CA2D layer must not be silently invented and then described as observed terrain. If a synthetic surface is constructed, the project metadata must say so explicitly and the case must be analysed as a synthetic or semi-real benchmark.

## Proposed first import set

The first import set should be deliberately small:

1. `WestCampusWatershed` — minimal workflow/debugging case.
2. `Greenville` — pumps, storage, dynamic-wave routing, and richer time-series content.
3. `Semi_Real_1045` — medium-scale extraction and diagnosis stress case.
4. `GisToSWMM5/demo_catchment` — spatial/CA2D construction reference. This has now been imported as `gisto_swmm_demo` with its source GIS inputs preserved under `raw/`.
5. One `UrbanDrainage` scenario family — batch-event/output reference, represented as one model project with multiple scenarios. This has now been imported as `urban_drainage` with `cenario_01`–`cenario_11` and reference outputs preserved under `raw/repository`.

## Required metadata before import

Every imported project must provide:

```text
model.yaml
raw/                         original downloaded or supplied files
swmm/scenarios/<name>/model.inp
events/                      rainfall files used by the project
static/                      CA2D static files, or an explicit missing/synthetic note
mapping/                     node-to-cell mapping, or an explicit missing note
provenance.md                source URL, commit/date, license, and transformations
```

The importer should record at least:

- object counts by SWMM section;
- routing method and simulation period;
- rainfall/event availability;
- coordinates and GIS availability;
- CA2D status: `complete`, `reference_only`, `synthetic`, or `missing`;
- whether the case is suitable for numerical execution, evidence extraction, and diagnosis benchmarking.

## Evidence boundary

Results based only on SWMM outputs support claims about model execution and model-derived hydraulic indicators. They do not, by themselves, support claims of real-world flood prediction accuracy. Spatial accuracy claims require independent terrain/land-cover information and, ideally, observations or a documented reference solution.
