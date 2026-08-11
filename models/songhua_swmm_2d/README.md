# songhua_swmm_2d

This is the first migrated SWMM-2D model project for SWMM-2D Agentic.

## Structure

- `raw/`: original source data reserved for DEM, tile/grid, building, road, and node-coordinate inputs.
- `static/`: reusable CA2D static model files copied from `E:\ModelCoupling2\experiments\ca2d_tile_demo\ca2d_model`.
- `swmm/`: SWMM baseline and future scenario input files.
- `mapping/`: stable mapping tables used by SWMM-2D coupling.
- `events/`: rainfall-event definitions and event input files.
- `runs/`: one folder per event-scenario simulation run.

## Current Baseline

- SWMM input: `swmm/scenarios/baseline/model.inp`
- CA2D static model: `static/`
- Node-cell mapping: `static/node_to_cell_mapping.csv`

The current prototype intentionally does not include zoning or database writes.
