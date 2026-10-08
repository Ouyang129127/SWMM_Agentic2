"""Build a reproducible 3 m CA2D model for the UrbanDrainage SWMM case.

The active domain is the union of SWMM subcatchment polygons.  The road
centre lines are taken from the user's registered orange road markup.  Ground
control elevations are SWMM manhole cover elevations (invert + max depth).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import pandas as pd


PROJECT = Path(__file__).resolve().parents[1]
INP = PROJECT / "swmm" / "scenarios" / "baseline" / "model.inp"
STATIC = PROJECT / "static"
MAPPING = PROJECT / "mapping"
REFERENCES = PROJECT / "raw" / "references"

CELL_SIZE = 3.0
ROAD_WIDTH = 8.0
ROAD_LOWERING = 0.10
BUILDING_RAISE = 15.0
BUILDING_CLEARANCE = 1.5
NODE_CLEARANCE = 6.0


def parse_sections(path: Path) -> dict[str, list[list[str]]]:
    sections: dict[str, list[list[str]]] = {}
    current = ""
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].upper()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line.split())
    return sections


def read_nodes(sections: dict[str, list[list[str]]]) -> dict[str, dict[str, float | str]]:
    nodes: dict[str, dict[str, float | str]] = {}
    for row in sections.get("JUNCTIONS", []):
        if len(row) >= 3:
            invert, max_depth = float(row[1]), float(row[2])
            nodes[row[0]] = {
                "node_type": "JUNCTION", "invert": invert, "max_depth": max_depth,
                "surface": invert + max_depth,
            }
    for row in sections.get("OUTFALLS", []):
        if len(row) >= 2:
            invert = float(row[1])
            nodes[row[0]] = {
                "node_type": "OUTFALL", "invert": invert, "max_depth": 0.0,
                "surface": invert,
            }
    for row in sections.get("COORDINATES", []):
        if len(row) >= 3 and row[0] in nodes:
            nodes[row[0]]["x"] = float(row[1])
            nodes[row[0]]["y"] = float(row[2])
    return {key: value for key, value in nodes.items() if "x" in value}


def read_polygons(sections: dict[str, list[list[str]]]) -> dict[str, list[tuple[float, float]]]:
    polygons: dict[str, list[tuple[float, float]]] = {}
    for row in sections.get("POLYGONS", []):
        if len(row) >= 3:
            polygons.setdefault(row[0], []).append((float(row[1]), float(row[2])))
    return {key: points for key, points in polygons.items() if len(points) >= 3}


def polygon_domain_mask(polygons, minx, maxy, shape):
    mask = np.zeros(shape, dtype=np.uint8)
    for points in polygons.values():
        pixels = np.asarray([
            [(x - minx) / CELL_SIZE - 0.5, (maxy - y) / CELL_SIZE - 0.5]
            for x, y in points
        ], dtype=np.float64)
        cv2.fillPoly(mask, [np.rint(pixels).astype(np.int32)], 1)
    # Close one-cell seams caused by independently rasterising adjacent polygons.
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool)


def orange_mask(image_path: Path) -> np.ndarray:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(image_path)
    b, g, r = cv2.split(image)
    return ((r > 190) & (g > 25) & (g < 190) & (b < 120)).astype(np.uint8)


def registered_road_mask(xx, yy):
    registration = json.loads((REFERENCES / "reference_registration.json").read_text(encoding="utf-8"))
    affine = np.asarray(registration["roads"]["world_to_pixel_affine"], dtype=float)
    source = orange_mask(REFERENCES / "road_distribution_reference.png")
    # Distance to an orange reference stroke.  Pixel/world scale is obtained
    # from the registered affine transform, preserving an 8 m total road width.
    distance_px = cv2.distanceTransform(1 - source, cv2.DIST_L2, 5)
    px = affine[0, 0] * xx + affine[0, 1] * yy + affine[0, 2]
    py = affine[1, 0] * xx + affine[1, 1] * yy + affine[1, 2]
    ix = np.rint(px).astype(int)
    iy = np.rint(py).astype(int)
    inside = (ix >= 0) & (ix < source.shape[1]) & (iy >= 0) & (iy < source.shape[0])
    sampled = np.full(xx.shape, np.inf, dtype=float)
    sampled[inside] = distance_px[iy[inside], ix[inside]]
    metres_per_pixel = 1.0 / math.sqrt(abs(np.linalg.det(affine[:, :2])))
    return sampled * metres_per_pixel <= ROAD_WIDTH / 2.0


def registered_domain_mask(xx, yy):
    """Rasterise the interior of the user's orange modelling boundary."""
    registration = json.loads((REFERENCES / "reference_registration.json").read_text(encoding="utf-8"))
    affine = np.asarray(registration["domain"]["world_to_pixel_affine"], dtype=float)
    boundary = orange_mask(REFERENCES / "model_domain_reference.png")
    boundary = cv2.morphologyEx(boundary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(boundary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise RuntimeError("No closed orange modelling boundary found in the domain reference")
    interior = np.zeros_like(boundary)
    cv2.drawContours(interior, [max(contours, key=cv2.contourArea)], -1, 1, thickness=cv2.FILLED)
    px = affine[0, 0] * xx + affine[0, 1] * yy + affine[0, 2]
    py = affine[1, 0] * xx + affine[1, 1] * yy + affine[1, 2]
    ix = np.rint(px).astype(int)
    iy = np.rint(py).astype(int)
    inside_image = (ix >= 0) & (ix < interior.shape[1]) & (iy >= 0) & (iy < interior.shape[0])
    result = np.zeros(xx.shape, dtype=bool)
    result[inside_image] = interior[iy[inside_image], ix[inside_image]].astype(bool)
    return result


def idw_surface(xx, yy, nodes):
    controls = np.asarray([
        (float(item["x"]), float(item["y"]), float(item["surface"]))
        for item in nodes.values()
    ])
    dx = xx[..., None] - controls[:, 0]
    dy = yy[..., None] - controls[:, 1]
    d2 = dx * dx + dy * dy
    weights = 1.0 / np.maximum(d2, 1.0)
    return (weights * controls[:, 2]).sum(axis=2) / weights.sum(axis=2)


def make_buildings(valid_mask, road_mask, xx, yy, nodes):
    road_buffer_cells = max(1, math.ceil(BUILDING_CLEARANCE / CELL_SIZE))
    forbidden = cv2.dilate(road_mask.astype(np.uint8), np.ones((2 * road_buffer_cells + 1,) * 2, np.uint8)).astype(bool)
    for item in nodes.values():
        forbidden |= (xx - float(item["x"])) ** 2 + (yy - float(item["y"])) ** 2 <= NODE_CLEARANCE ** 2
    available = valid_mask & ~forbidden
    components, labels, stats, _ = cv2.connectedComponentsWithStats(available.astype(np.uint8), 8)
    building = np.zeros_like(valid_mask)
    records = []
    # Deliberately varied footprints, all exact multiples of the 3 m grid.
    sizes = [(3, 3), (4, 3), (5, 4), (4, 5), (6, 4), (5, 5), (7, 5), (6, 6)]
    building_id = 1
    for label in range(1, components):
        area_cells = int(stats[label, cv2.CC_STAT_AREA])
        if area_cells < 25:
            continue
        component = labels == label
        # A few buildings per road-cut block; small slivers receive one.
        target = min(6, max(1, round(area_cells * CELL_SIZE ** 2 / 1800.0)))
        clearance = cv2.distanceTransform(component.astype(np.uint8), cv2.DIST_L2, 5)
        for local_idx in range(target):
            w, h = sizes[(building_id * 3 + label + local_idx) % len(sizes)]
            placed = False
            # Prefer deep interior cells and spread later buildings away from existing ones.
            score = clearance.copy()
            if building.any():
                score = np.minimum(score, cv2.distanceTransform((~building).astype(np.uint8), cv2.DIST_L2, 5))
            for flat in np.argsort(score.ravel())[::-1][:300]:
                row, col = np.unravel_index(int(flat), score.shape)
                r0, c0 = row - h // 2, col - w // 2
                r1, c1 = r0 + h, c0 + w
                if r0 < 0 or c0 < 0 or r1 > building.shape[0] or c1 > building.shape[1]:
                    continue
                footprint = component[r0:r1, c0:c1] & ~forbidden[r0:r1, c0:c1] & ~building[r0:r1, c0:c1]
                if footprint.shape == (h, w) and footprint.all():
                    building[r0:r1, c0:c1] = True
                    records.append({
                        "building_id": f"B{building_id:03d}", "component_id": label,
                        "row_min": r0, "row_max": r1 - 1, "col_min": c0, "col_max": c1 - 1,
                        "width_m": w * CELL_SIZE, "depth_m": h * CELL_SIZE,
                        "raise_m": BUILDING_RAISE,
                    })
                    building_id += 1
                    placed = True
                    break
            if not placed:
                break
    return building, records, components - 1


def map_nodes(nodes, flow_mask, xx, yy, elevation, cell_id_grid, smid_grid):
    flow_rows, flow_cols = np.where(flow_mask)
    fx, fy = xx[flow_mask], yy[flow_mask]
    records = []
    for node_smid, (node_id, item) in enumerate(nodes.items(), start=1):
        distance2 = (fx - float(item["x"])) ** 2 + (fy - float(item["y"])) ** 2
        idx = int(np.argmin(distance2))
        row, col = int(flow_rows[idx]), int(flow_cols[idx])
        records.append({
            "node_smid": node_smid, "node_id": node_id, "node_type": item["node_type"],
            "node_x": item["x"], "node_y": item["y"], "invert_elevation": item["invert"],
            "max_depth": item["max_depth"], "surface_elevation": item["surface"],
            "cell_id": int(cell_id_grid[row, col]), "smid": int(smid_grid[row, col]),
            "cell_row": row, "cell_col": col, "cell_x": float(xx[row, col]),
            "cell_y": float(yy[row, col]), "cell_elevation": float(elevation[row, col]),
            "distance_m": float(math.sqrt(distance2[idx])), "weight": 1.0,
        })
    return records


def render_preview(elevation, valid_mask, road_mask, building_mask, nodes, bounds):
    minx, miny, maxx, maxy = bounds
    terrain = np.ma.masked_where(~valid_mask, elevation)
    fig, ax = plt.subplots(figsize=(8.5, 11), constrained_layout=True)
    image = ax.imshow(terrain, extent=[minx, maxx, miny, maxy], origin="upper", cmap="terrain")
    ax.imshow(np.ma.masked_where(~road_mask, road_mask), extent=[minx, maxx, miny, maxy],
              origin="upper", cmap=ListedColormap(["#f28e2b"]), alpha=0.88, interpolation="nearest")
    ax.imshow(np.ma.masked_where(~building_mask, building_mask), extent=[minx, maxx, miny, maxy],
              origin="upper", cmap=ListedColormap(["#4d4d4d"]), alpha=0.98, interpolation="nearest")
    ax.contour(valid_mask.astype(float), levels=[0.5], extent=[minx, maxx, miny, maxy],
               origin="upper", colors="#d95f02", linewidths=1.2)
    ax.scatter([float(v["x"]) for v in nodes.values()], [float(v["y"]) for v in nodes.values()],
               s=8, c="#1565c0", edgecolors="white", linewidths=0.25, label="SWMM nodes")
    ax.set_aspect("equal")
    ax.set_title("UrbanDrainage CA2D layout (3 m grid)")
    ax.set_xlabel("Source X coordinate (m)")
    ax.set_ylabel("Source Y coordinate (m)")
    ax.legend(loc="lower left", fontsize=8)
    fig.colorbar(image, ax=ax, shrink=0.65, label="Elevation (m)")
    fig.savefig(STATIC / "ca2d_layout_preview.png", dpi=180)
    plt.close(fig)


def main():
    STATIC.mkdir(parents=True, exist_ok=True)
    MAPPING.mkdir(parents=True, exist_ok=True)
    sections = parse_sections(INP)
    nodes = read_nodes(sections)
    polygons = read_polygons(sections)
    vertices = np.asarray([point for points in polygons.values() for point in points])
    minx = math.floor((vertices[:, 0].min() - CELL_SIZE) / CELL_SIZE) * CELL_SIZE
    miny = math.floor((vertices[:, 1].min() - CELL_SIZE) / CELL_SIZE) * CELL_SIZE
    maxx = math.ceil((vertices[:, 0].max() + CELL_SIZE) / CELL_SIZE) * CELL_SIZE
    maxy = math.ceil((vertices[:, 1].max() + CELL_SIZE) / CELL_SIZE) * CELL_SIZE
    nx, ny = round((maxx - minx) / CELL_SIZE), round((maxy - miny) / CELL_SIZE)
    x = minx + (np.arange(nx) + 0.5) * CELL_SIZE
    y = maxy - (np.arange(ny) + 0.5) * CELL_SIZE
    xx, yy = np.meshgrid(x, y)

    polygon_mask = polygon_domain_mask(polygons, minx, maxy, (ny, nx))
    valid_mask = registered_domain_mask(xx, yy)
    road_mask = registered_road_mask(xx, yy) & valid_mask
    building_mask, buildings, road_cut_components = make_buildings(valid_mask, road_mask, xx, yy, nodes)
    flow_mask = valid_mask & ~building_mask
    terrain = idw_surface(xx, yy, nodes)
    elevation = terrain.copy()
    elevation[road_mask] -= ROAD_LOWERING
    elevation[building_mask] += BUILDING_RAISE
    elevation[~valid_mask] = 0.0
    resistance = np.zeros((ny, nx), dtype=np.float32)
    resistance[flow_mask] = 0.75
    resistance[road_mask] = 0.55
    smid_grid = np.arange(1, nx * ny + 1, dtype=np.int32).reshape(ny, nx)
    cell_id_grid = smid_grid - 1

    arrays = {
        "elevation.npy": elevation.astype(np.float32), "terrain.npy": terrain.astype(np.float32), "smid_grid.npy": smid_grid,
        "flow_mask.npy": flow_mask, "building_mask.npy": building_mask,
        "resistance.npy": resistance, "valid_mask.npy": valid_mask,
        "cell_id_grid.npy": cell_id_grid, "road_mask.npy": road_mask,
        "domain_mask.npy": valid_mask,
    }
    for name, data in arrays.items():
        np.save(STATIC / name, data)

    render_preview(elevation, valid_mask, road_mask, building_mask, nodes, [minx, miny, maxx, maxy])

    mapped = map_nodes(nodes, flow_mask, xx, yy, elevation, cell_id_grid, smid_grid)
    pd.DataFrame(mapped).to_csv(STATIC / "node_to_cell_mapping.csv", index=False)
    pd.DataFrame(mapped).to_csv(MAPPING / "node_to_cell_mapping.csv", index=False)
    pd.DataFrame(buildings).to_csv(STATIC / "synthetic_buildings.csv", index=False)
    pd.DataFrame([{
        "source": "registered user road reference", "road_width_m": ROAD_WIDTH,
        "lowering_m": ROAD_LOWERING, "road_cells": int(road_mask.sum()),
    }]).to_csv(STATIC / "synthetic_streets.csv", index=False)

    cells = pd.DataFrame({
        "cell_id": cell_id_grid.ravel(), "smid": smid_grid.ravel(),
        "row": np.repeat(np.arange(ny), nx), "col": np.tile(np.arange(nx), ny),
        "x": xx.ravel(), "y": yy.ravel(), "area_m2": CELL_SIZE ** 2,
        "elevation": elevation.ravel(), "is_valid": valid_mask.ravel(),
        "is_building": building_mask.ravel(), "is_road": road_mask.ravel(),
        "is_flow": flow_mask.ravel(),
    })
    cells.to_csv(STATIC / "cells.csv", index=False)

    distances = np.asarray([row["distance_m"] for row in mapped])
    config = {
        "cell_size": CELL_SIZE, "bounds": [minx, miny, maxx, maxy],
        "crs": "unknown; source coordinates retained", "grid_shape": [ny, nx],
        "n_cells": int(nx * ny), "n_valid_cells": int(valid_mask.sum()),
        "n_flow_cells": int(flow_mask.sum()), "n_building_cells": int(building_mask.sum()),
        "n_buildings": len(buildings), "n_road_cells": int(road_mask.sum()),
        "n_road_cut_components": road_cut_components, "n_subcatchment_polygons": len(polygons),
        "n_nodes": len(nodes), "n_mapped_nodes": len(mapped),
        "node_mapping_distance_median": float(np.median(distances)),
        "node_mapping_distance_95p": float(np.quantile(distances, 0.95)),
        "node_mapping_distance_max": float(np.max(distances)),
        "terrain_method": "IDW from SWMM cover elevations: junction invert + max depth; outfall invert",
        "domain_method": "interior of the registered orange modelling-region boundary, cross-checked against 218 SWMM [POLYGONS] subcatchments",
        "road_method": "registered orange road reference expanded to 8 m width and lowered by 0.10 m",
        "building_method": "1-6 varied 9-21 m by 9-18 m footprints per suitable road-cut component, raised by 15 m",
        "assumption_status": "synthetic_surface_from_SWMM_elevations_and_user_reference_maps",
    }
    (STATIC / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (STATIC / "build_summary.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(config, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
