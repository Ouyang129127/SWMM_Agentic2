# Site_Drainage_Model

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

- Grid cell size: 3 m (150 rows × 145 columns).
- Terrain: IDW interpolation from SWMM node elevations plus contour labels visible on `Site-Post.jpg`.
- Streets: six road centre lines traced from `swmm/Site-Post.jpg`, registered to SWMM `[BACKDROP]` dimensions. Roads are 8–10 m wide and depressed by 0.10 m. The park's drainage conduits are not used as road centre lines.
- Buildings: 56 varied, rotated synthetic footprints placed in inferred residential/commercial parcels, raised by 15 m above the original ground and excluded from the flow mask. The backdrop shows parcels rather than surveyed building outlines; footprint sizes and roof heights are modelling assumptions.
- Buildings avoid road buffers by 3 m and SWMM nodes by 6 m. The central park remains open terrain.
- The solver's `resistance.npy` multiplies surface flux; coefficients are 0.90 on roads and 0.62 on other flow cells, with zero on buildings and outside the domain.
- `terrain.npy` stores unmodified ground; `elevation.npy` stores ground with road and building offsets applied.
- Node coupling: each SWMM node is attached to the nearest valid, non-building flow cell.

## Current Baseline

- SWMM input: `swmm/scenarios/baseline/model.inp`
- 2-year SWMM input: `swmm/scenarios/two_year_design/model.inp`
- CA2D static model: `static/`
- Node-cell mapping: `static/node_to_cell_mapping.csv`

## Simulation timing

New rainfall runs use `simulation_timing.json`: native SWMM reports every minute,
five-minute interval-mean overflow input to CA2D, five-minute surface snapshots,
and three hours of simulation after rainfall ends. Rainfall timestamps mark
interval starts. Internal solver time steps retain their existing settings.
The project requires this file before starting a rainfall run; it no longer
exports SWMM results by sampling during simulation. Existing runs retain their
original time coverage and outputs; adding this policy does not update them.

## Rebuild and review


Run from the repository root:

```powershell
.venv\Scripts\python.exe models\Site_Drainage_Model\scripts\build_site_ca2d.py
```

Edit `raw/references/site_layout_reference.json` to adjust traced roads, developable parcels, heights, widths, and clearances. Reference coordinates are image pixels (X rightward, Y downward); the script converts the backdrop's feet to metres. Grid bounds include partial-cell padding beyond the backdrop bounds.

The build updates only CA2D static files and node mapping, with checks for elevation offsets, road/building overlap, valid flow cells and node mapping consistency. It preserves SWMM scenarios, rainfall files and historical runs. Historical CA2D results must be rerun to reflect the new layout.

- `static/ca2d_static_preview.png`: backdrop overlay alongside the new model.
- `static/backdrop_layout_reference.png`: road traces and developable parcels over the source image.
- `static/ca2d_elevation_3d.png`: raised buildings in the actual solver elevation grid.
- `static/build_summary.md`: assumptions and cell counts.
- `static/layout_validation.json`: array checks and a 10-minute artificial-inflow solver test (not a design-storm result). Repeat with `.venv\Scripts\python.exe models\Site_Drainage_Model\scripts\verify_site_ca2d.py`.

The previous static model and build script are backed up at `E:\SWMM_Agentic\backups\Site_Drainage_Model_ca2d_20261011`.
