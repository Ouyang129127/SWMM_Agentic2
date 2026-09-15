# CA2D static layer status

Status: synthetic_complete

The CA2D surface is generated from the SWMM model and the two user-provided
reference maps rather than an observed DEM. Junction surface elevation is
calculated as invert elevation plus JUNCTIONS maximum depth. Outfall surface
elevation uses the outfall invert elevation.

- Grid size: 3 m x 3 m
- Domain: interior of the orange modelling-region reference boundary,
  cross-checked against the 218 SWMM `[POLYGONS]` subcatchments
- Roads: orange roads extracted from the georegistered road reference, expanded
  to 8 m total width, clipped only at the outer modelling boundary, and lowered
  by 0.10 m; roads remain continuous across subcatchment gaps
- Buildings: 34 varied footprints distributed among the road-cut regions,
  raised by 15 m and excluded from flow
- Builder: scripts/build_ca2d.py

The generated files are suitable for benchmark execution, but spatial accuracy
must not be described as real-world validation.
