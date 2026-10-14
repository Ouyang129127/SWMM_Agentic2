"""Validate the rebuilt site and exercise actual CA2D injection/diffusion.

The injected flow is a numerical smoke test, not a design-storm result.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from build_site_ca2d import PROJECT_DIR, parse_inp, SOURCE_INP, validate_arrays

sys.path.insert(0, str(PROJECT_DIR.parents[1]))
from ca2d import add_inflow, diffuse_one_step, load_model, render_depth


def main():
    static = PROJECT_DIR / "static"
    model = load_model(static)
    config = model["config"]
    arrays = {path.stem: np.load(path) for path in static.glob("*.npy")}
    mapping = model["node_mapping"]
    validate_arrays(arrays, config, mapping)
    cells = pd.read_csv(static / "cells.csv")
    buildings = pd.read_csv(static / "synthetic_buildings.csv")
    assert len(cells) == arrays["valid_mask"].sum() == config["n_valid_cells"]
    assert len(buildings) == config["n_buildings"]
    assert buildings.n_cells.sum() == arrays["building_mask"].sum()
    assert np.array_equal(arrays["valid_mask"], arrays["domain_mask"])
    assert np.array_equal(arrays["smid_grid"][arrays["valid_mask"]], np.arange(1, len(cells) + 1))
    assert np.array_equal(arrays["cell_id_grid"][arrays["valid_mask"]], np.arange(len(cells)))
    assert np.allclose(cells.elevation, arrays["elevation"][arrays["valid_mask"]])
    assert np.allclose(cells.terrain, arrays["terrain"][arrays["valid_mask"]])
    assert np.allclose(np.asarray(config["bounds"])[[2, 3]] - np.asarray(config["bounds"])[[0, 1]],
                       np.asarray(config["grid_shape"])[::-1] * config["cell_size"])
    duplicate_mapping = pd.read_csv(PROJECT_DIR / "mapping" / "node_to_cell_mapping.csv")
    pd.testing.assert_frame_equal(mapping, duplicate_mapping)

    # Independently check registration against original SWMM node coordinates.
    coords = {row[0]: np.asarray(row[1:3], dtype=float) * .3048
              for row in parse_inp(SOURCE_INP)["COORDINATES"]}
    bx = config["bounds"][0] + (np.arange(arrays["elevation"].shape[1]) + .5) * config["cell_size"]
    by = config["bounds"][3] - (np.arange(arrays["elevation"].shape[0]) + .5) * config["cell_size"]
    xx, yy = np.meshgrid(bx, by)
    min_building_node_distance = np.inf
    for record in mapping.itertuples():
        assert np.allclose([record.node_x, record.node_y], coords[record.node_id])
        assert np.allclose([record.cell_x, record.cell_y], [xx[record.cell_row, record.cell_col], yy[record.cell_row, record.cell_col]])
        x, y = coords[record.node_id]
        min_building_node_distance = min(min_building_node_distance,
            float(np.hypot(xx[arrays["building_mask"]] - x, yy[arrays["building_mask"]] - y).min()))
    assert min_building_node_distance > config["building_node_clearance_m"]

    depth = np.zeros_like(model["elevation"], dtype=np.float32)
    rows = mapping.cell_row.to_numpy(dtype=int)
    cols = mapping.cell_col.to_numpy(dtype=int)
    flows = np.full(len(mapping), .01)  # 10 L/s per node, for 10 minutes.
    dt, steps, input_volume = 5.0, 120, 0.0
    for _ in range(steps):
        input_volume += add_inflow(depth, rows, cols, flows, dt, config["cell_size"])
        diffuse_one_step(depth, model["elevation"], model["resistance"], model["flow_mask"], dt, config["cell_size"])
    assert np.isfinite(depth).all() and (depth >= 0).all()
    assert not depth[arrays["building_mask"]].any()
    assert not depth[~arrays["flow_mask"]].any()
    assert np.count_nonzero(depth > 1e-6) > len(mapping), "Injected water did not diffuse"
    stored_volume = float(depth.sum(dtype=np.float64) * config["cell_size"] ** 2)
    relative_error = abs(stored_volume - input_volume) / input_volume
    assert relative_error < 1e-5, f"Smoke test water-volume error: {relative_error}"
    report = {"status": "PASS", "test_type": "synthetic injection, not a rainfall-event simulation",
              "duration_seconds": steps * dt, "internal_dt_seconds": dt,
              "injected_flow_lps_per_node": 10.0, "mapped_nodes": len(mapping),
              "n_buildings": len(buildings), "n_road_cells": int(arrays["road_mask"].sum()),
              "min_building_node_distance_m": min_building_node_distance,
              "input_volume_m3": input_volume, "stored_volume_m3": stored_volume,
              "relative_mass_error": relative_error, "water_in_buildings_m3": 0.0,
              "wet_cells": int(np.count_nonzero(depth > 1e-6)), "max_depth_m": float(depth.max()),
              "checks": ["elevation offsets", "disjoint roads and buildings", "flow/valid/domain masks",
                         "cell identifiers and CSVs", "grid extent", "node coordinates and clearance",
                         "mapping copy", "solver loading and display layers", "diffusion and mass conservation"]}
    (static / "layout_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_depth(depth, model["elevation"], model["flow_mask"], model["building_mask"],
                 static / "ca2d_smoke_test.png", "数值验收：人工注水 10 分钟（非设计暴雨）", **model["display_layers"])
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
