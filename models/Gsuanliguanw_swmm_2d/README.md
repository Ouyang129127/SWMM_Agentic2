# suanliguanw_swmm_2d

This project packages the EPA SWMM `Site_Drainage_Model.inp` sample with a synthetic CA2D static surface.

## Structure

- `raw/`: original SWMM sample input and backdrop image.
- `swmm/scenarios/baseline/model.inp`: standard baseline SWMM entry point.
- `swmm/scenarios/two_year_design/model.inp`: same model with the rain gage switched to the 2-year storm.
- `static/`: reusable CA2D grids, masks, resistance field, cells table, and node-cell mapping.
- `mapping/`: copy of stable node-to-cell mapping table.
- `events/`: rainfall time series extracted from the INP; `rain1.txt` mirrors the 2-year event.
- `runs/`: reserved for simulation outputs.

## CA2D Build Assumptions

- Grid cell size: 25 ft / 7.62 m.
- Terrain: IDW interpolation from SWMM node elevations plus contour labels visible on `Site-Post.jpg`.
- Streets: buffered SWMM conduit polylines, depressed by up to 0.25 ft and assigned higher conveyance.
- Buildings: six synthetic polygon blocks digitized from the visible residential/commercial parcels on the backdrop.
- Node coupling: each SWMM node is attached to the nearest valid, non-building flow cell.

## Current Baseline

- SWMM input: `swmm/scenarios/baseline/model.inp`
- 2-year SWMM input: `swmm/scenarios/two_year_design/model.inp`
- CA2D static model: `static/`
- Node-cell mapping: `static/node_to_cell_mapping.csv`
