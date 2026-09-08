import csv
import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE_INP = Path(r"C:\Users\ouyang\Documents\EPA SWMM Projects\Samples\Site_Drainage_Model.inp")
SOURCE_BACKDROP = SOURCE_INP.with_name("Site-Post.jpg")

FT_TO_M = 0.3048
CELL_SIZE_M = 3.0
CELL_SIZE_FT = CELL_SIZE_M / FT_TO_M


def parse_inp(path: Path) -> dict:
    sections: dict[str, list[list[str]]] = {}
    current = None
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                current = line.strip("[]").upper()
                sections.setdefault(current, [])
                continue
            if current is None or line.startswith(";;") or line.startswith(";"):
                continue
            sections[current].append(line.split())
    return sections


def read_named_points(sections: dict) -> dict[str, tuple[float, float]]:
    points = {}
    for row in sections.get("COORDINATES", []):
        if len(row) >= 3:
            points[row[0]] = (float(row[1]), float(row[2]))
    return points


def read_nodes(sections: dict) -> dict[str, dict]:
    nodes = {}
    for row in sections.get("JUNCTIONS", []):
        if len(row) >= 3:
            invert = float(row[1])
            max_depth = float(row[2])
            surface = invert + max_depth if max_depth > 0 else invert
            nodes[row[0]] = {
                "type": "JUNCTION",
                "invert_ft": invert,
                "max_depth_ft": max_depth,
                "surface_ft": surface,
            }
    for row in sections.get("OUTFALLS", []):
        if len(row) >= 2:
            invert = float(row[1])
            nodes[row[0]] = {
                "type": "OUTFALL",
                "invert_ft": invert,
                "max_depth_ft": 0.0,
                "surface_ft": invert,
            }
    return nodes


def read_conduit_polylines(sections: dict, coords: dict[str, tuple[float, float]]) -> dict[str, list[tuple[float, float]]]:
    vertices: dict[str, list[tuple[float, float]]] = {}
    for row in sections.get("VERTICES", []):
        if len(row) >= 3:
            vertices.setdefault(row[0], []).append((float(row[1]), float(row[2])))

    lines = {}
    for row in sections.get("CONDUITS", []):
        if len(row) >= 3 and row[1] in coords and row[2] in coords:
            lines[row[0]] = [coords[row[1]], *vertices.get(row[0], []), coords[row[2]]]
    return lines


def read_polygons(sections: dict) -> dict[str, list[tuple[float, float]]]:
    polygons: dict[str, list[tuple[float, float]]] = {}
    for row in sections.get("POLYGONS", []):
        if len(row) >= 3:
            polygons.setdefault(row[0], []).append((float(row[1]), float(row[2])))
    return polygons


def point_segment_distance(px, py, ax, ay, bx, by):
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    denom = vx * vx + vy * vy
    if denom == 0:
        return np.hypot(px - ax, py - ay)
    t = np.clip((wx * vx + wy * vy) / denom, 0.0, 1.0)
    proj_x = ax + t * vx
    proj_y = ay + t * vy
    return np.hypot(px - proj_x, py - proj_y)


def distance_to_polylines(x_grid, y_grid, polylines):
    dist = np.full(x_grid.shape, np.inf, dtype=np.float32)
    for points in polylines:
        for a, b in zip(points[:-1], points[1:]):
            seg_dist = point_segment_distance(x_grid, y_grid, a[0], a[1], b[0], b[1])
            dist = np.minimum(dist, seg_dist.astype(np.float32))
    return dist


def idw_surface(x_grid, y_grid, controls):
    values = np.zeros(x_grid.shape, dtype=np.float64)
    weights = np.zeros(x_grid.shape, dtype=np.float64)
    for x, y, z in controls:
        dist2 = (x_grid - x) ** 2 + (y_grid - y) ** 2
        w = 1.0 / np.maximum(dist2, 36.0)
        values += w * z
        weights += w
    return values / weights


def polygon_mask(x_grid, y_grid, polygon):
    points = np.column_stack([x_grid.ravel(), y_grid.ravel()])
    mask = MplPath(polygon).contains_points(points)
    return mask.reshape(x_grid.shape)


def build_static_model():
    sections = parse_inp(SOURCE_INP)
    coords = read_named_points(sections)
    nodes = read_nodes(sections)
    conduit_lines = read_conduit_polylines(sections, coords)
    subcatchment_polygons = read_polygons(sections)

    backdrop = {row[0].upper(): row[1:] for row in sections.get("BACKDROP", [])}
    if "DIMENSIONS" in backdrop:
        minx_ft, miny_ft, maxx_ft, maxy_ft = map(float, backdrop["DIMENSIONS"][:4])
    else:
        minx_ft, miny_ft, maxx_ft, maxy_ft = 0.0, 0.0, 1423.0, 1475.0

    nx = int(math.ceil((maxx_ft - minx_ft) / CELL_SIZE_FT))
    ny = int(math.ceil((maxy_ft - miny_ft) / CELL_SIZE_FT))
    x_centers_ft = minx_ft + (np.arange(nx) + 0.5) * CELL_SIZE_FT
    y_centers_ft = maxy_ft - (np.arange(ny) + 0.5) * CELL_SIZE_FT
    x_grid_ft, y_grid_ft = np.meshgrid(x_centers_ft, y_centers_ft)

    domain_mask = np.zeros((ny, nx), dtype=bool)
    for polygon in subcatchment_polygons.values():
        domain_mask |= polygon_mask(x_grid_ft, y_grid_ft, polygon)

    manual_controls = [
        (80, 1280, 4975.0),
        (360, 1420, 4975.0),
        (690, 1320, 4974.0),
        (1110, 1320, 4973.0),
        (1310, 1110, 4971.0),
        (1345, 930, 4969.0),
        (1380, 700, 4967.0),
        (1280, 150, 4970.0),
        (780, 70, 4970.0),
        (430, 760, 4970.3),
        (800, 820, 4968.8),
        (1150, 745, 4968.4),
        (1410, 477, 4962.0),
    ]
    node_controls = []
    for node_id, node in nodes.items():
        if node_id in coords:
            x, y = coords[node_id]
            node_controls.append((x, y, node["surface_ft"]))

    elevation_ft = idw_surface(x_grid_ft, y_grid_ft, node_controls + manual_controls)
    network_dist_ft = distance_to_polylines(x_grid_ft, y_grid_ft, conduit_lines.values())
    road_mask = (network_dist_ft <= 32.0) & domain_mask
    elevation_ft = elevation_ft - np.where(road_mask, np.clip((32.0 - network_dist_ft) / 32.0, 0, 1) * 0.25, 0.0)

    building_polygons = {
        "B_NorthWest_Commercial": [(350, 1130), (560, 1090), (585, 1240), (430, 1300)],
        "B_NorthCentral_Block": [(760, 1050), (985, 1010), (1060, 1160), (820, 1225)],
        "B_EastCommercial_Block": [(1020, 785), (1230, 730), (1275, 930), (1080, 980)],
        "B_SouthResidential_Block": [(570, 315), (790, 175), (920, 385), (685, 535)],
        "B_SouthEast_RowHomes": [(870, 330), (1160, 155), (1300, 390), (1005, 570)],
        "B_SouthCentral_Small": [(465, 505), (620, 395), (700, 555), (545, 665)],
    }
    building_mask = np.zeros((ny, nx), dtype=bool)
    for polygon in building_polygons.values():
        building_mask |= polygon_mask(x_grid_ft, y_grid_ft, polygon)
    building_mask &= domain_mask & (network_dist_ft > 45.0)

    valid_mask = domain_mask
    flow_mask = valid_mask & (~building_mask)
    elevation_ft = np.where(valid_mask, elevation_ft, np.nan)
    elevation_ft = np.where(building_mask, elevation_ft + 8.0, elevation_ft)

    smid_grid = np.zeros((ny, nx), dtype=np.int32)
    cell_id_grid = np.full((ny, nx), -1, dtype=np.int32)
    valid_indices = np.argwhere(valid_mask)
    for cell_id, (row, col) in enumerate(valid_indices):
        cell_id_grid[row, col] = cell_id
        smid_grid[row, col] = cell_id + 1

    resistance = np.zeros((ny, nx), dtype=np.float32)
    resistance[flow_mask] = 0.62
    resistance[road_mask & flow_mask] = 0.90
    resistance[building_mask] = 0.0

    elevation_m = np.nan_to_num(elevation_ft * FT_TO_M, nan=0.0).astype(np.float32)
    x_grid_m = x_grid_ft * FT_TO_M
    y_grid_m = y_grid_ft * FT_TO_M

    static_dir = PROJECT_DIR / "static"
    swmm_dir = PROJECT_DIR / "swmm"
    baseline_dir = swmm_dir / "scenarios" / "baseline"
    two_year_dir = swmm_dir / "scenarios" / "two_year_design"
    mapping_dir = PROJECT_DIR / "mapping"
    raw_dir = PROJECT_DIR / "raw"
    events_dir = PROJECT_DIR / "events"
    for directory in [static_dir, swmm_dir, baseline_dir, two_year_dir, mapping_dir, raw_dir, events_dir, PROJECT_DIR / "runs"]:
        directory.mkdir(parents=True, exist_ok=True)

    shutil.copy2(SOURCE_INP, raw_dir / SOURCE_INP.name)
    shutil.copy2(SOURCE_INP, swmm_dir / "Model.inp")
    shutil.copy2(SOURCE_INP, baseline_dir / "model.inp")
    make_two_year_inp(SOURCE_INP, two_year_dir / "model.inp")
    if SOURCE_BACKDROP.exists():
        for target_dir in [raw_dir, swmm_dir, baseline_dir, two_year_dir]:
            shutil.copy2(SOURCE_BACKDROP, target_dir / SOURCE_BACKDROP.name)

    np.save(static_dir / "elevation.npy", elevation_m)
    np.save(static_dir / "smid_grid.npy", smid_grid)
    np.save(static_dir / "flow_mask.npy", flow_mask)
    np.save(static_dir / "building_mask.npy", building_mask)
    np.save(static_dir / "resistance.npy", resistance)
    np.save(static_dir / "valid_mask.npy", valid_mask)
    np.save(static_dir / "cell_id_grid.npy", cell_id_grid)
    np.save(static_dir / "road_mask.npy", road_mask)

    flow_cells = np.argwhere(flow_mask)
    flow_xy = np.column_stack([x_grid_m[flow_mask], y_grid_m[flow_mask]])
    node_rows = []
    for idx, (node_id, node) in enumerate(nodes.items(), start=1):
        if node_id not in coords:
            continue
        node_x_ft, node_y_ft = coords[node_id]
        node_x_m, node_y_m = node_x_ft * FT_TO_M, node_y_ft * FT_TO_M
        distances = np.hypot(flow_xy[:, 0] - node_x_m, flow_xy[:, 1] - node_y_m)
        nearest = int(np.argmin(distances))
        row, col = map(int, flow_cells[nearest])
        node_rows.append(
            {
                "node_smid": idx,
                "node_id": node_id,
                "node_type": node["type"],
                "node_x": node_x_m,
                "node_y": node_y_m,
                "node_x_ft": node_x_ft,
                "node_y_ft": node_y_ft,
                "invert_elevation_m": node["invert_ft"] * FT_TO_M,
                "max_depth_m": node["max_depth_ft"] * FT_TO_M,
                "surface_elevation_m": node["surface_ft"] * FT_TO_M,
                "cell_id": int(cell_id_grid[row, col]),
                "smid": int(smid_grid[row, col]),
                "cell_row": row,
                "cell_col": col,
                "cell_x": float(x_grid_m[row, col]),
                "cell_y": float(y_grid_m[row, col]),
                "cell_elevation": float(elevation_m[row, col]),
                "distance_m": float(distances[nearest]),
                "weight": 1.0,
            }
        )
    node_mapping = pd.DataFrame(node_rows)
    node_mapping.to_csv(static_dir / "node_to_cell_mapping.csv", index=False, encoding="utf-8")
    node_mapping.to_csv(mapping_dir / "node_to_cell_mapping.csv", index=False, encoding="utf-8")

    cell_rows = []
    for cell_id, (row, col) in enumerate(valid_indices):
        cell_rows.append(
            {
                "cell_id": cell_id,
                "smid": int(smid_grid[row, col]),
                "row": int(row),
                "col": int(col),
                "x": float(x_grid_m[row, col]),
                "y": float(y_grid_m[row, col]),
                "x_ft": float(x_grid_ft[row, col]),
                "y_ft": float(y_grid_ft[row, col]),
                "area_m2": CELL_SIZE_M * CELL_SIZE_M,
                "elevation": float(elevation_m[row, col]),
                "is_valid": bool(valid_mask[row, col]),
                "is_building": bool(building_mask[row, col]),
                "is_road": bool(road_mask[row, col]),
                "is_flow": bool(flow_mask[row, col]),
            }
        )
    cells = pd.DataFrame(cell_rows)
    cells.to_csv(static_dir / "cells.csv", index=False, encoding="utf-8")

    building_df = pd.DataFrame(
        [{"building_id": name, "vertices_ft": json.dumps(poly), "assumption": "digitized from SWMM sample backdrop"} for name, poly in building_polygons.items()]
    )
    building_df.to_csv(static_dir / "synthetic_buildings.csv", index=False, encoding="utf-8")

    street_rows = []
    for link_id, points in conduit_lines.items():
        street_rows.append(
            {
                "street_id": link_id,
                "source": "SWMM conduit polyline",
                "buffer_width_ft": 64.0,
                "vertices_ft": json.dumps(points),
            }
        )
    pd.DataFrame(street_rows).to_csv(static_dir / "synthetic_streets.csv", index=False, encoding="utf-8")

    write_event_files(sections, events_dir)
    write_project_files(static_dir, node_mapping, cells, building_df, street_rows, nx, ny, minx_ft, miny_ft, maxx_ft, maxy_ft)
    render_preview(static_dir, elevation_m, valid_mask, flow_mask, road_mask, building_mask, node_mapping)


def write_event_files(sections: dict, events_dir: Path):
    series: dict[str, list[tuple[str, float]]] = {}
    for row in sections.get("TIMESERIES", []):
        if len(row) >= 3:
            name, time, value = row[0], row[1], row[2]
            series.setdefault(name, []).append((time, float(value)))
    for name, rows in series.items():
        out = events_dir / f"{name.replace('-', '_')}.txt"
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "intensity_in_per_hr"])
            writer.writerows(rows)
    if "2-yr" in series:
        shutil.copy2(events_dir / "2_yr.txt", events_dir / "rain1.txt")


def make_two_year_inp(source: Path, target: Path):
    text = source.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("TIMESERIES 100-yr", "TIMESERIES 2-yr  ")
    target.write_text(text, encoding="utf-8")


def write_project_files(static_dir, node_mapping, cells, buildings, street_rows, nx, ny, minx_ft, miny_ft, maxx_ft, maxy_ft):
    config = {
        "source_inp": str(SOURCE_INP),
        "source_backdrop": str(SOURCE_BACKDROP),
        "spatial_units": "metre",
        "source_map_units": "feet",
        "source_elevation_units": "feet",
        "coordinate_conversion": "source feet multiplied by 0.3048",
        "bounds": [minx_ft * FT_TO_M, miny_ft * FT_TO_M, maxx_ft * FT_TO_M, maxy_ft * FT_TO_M],
        "source_bounds_ft": [minx_ft, miny_ft, maxx_ft, maxy_ft],
        "crs": None,
        "cell_size": CELL_SIZE_M,
        "cell_size_ft": CELL_SIZE_FT,
        "grid_shape": [ny, nx],
        "n_cells": int(nx * ny),
        "n_valid_cells": int(len(cells)),
        "n_flow_cells": int(cells["is_flow"].sum()),
        "n_building_cells": int(cells["is_building"].sum()),
        "n_road_cells": int(cells["is_road"].sum()),
        "n_nodes": int(len(node_mapping)),
        "n_mapped_nodes": int(len(node_mapping)),
        "node_mapping_distance_median": float(node_mapping["distance_m"].median()),
        "node_mapping_distance_95p": float(node_mapping["distance_m"].quantile(0.95)),
        "node_mapping_distance_max": float(node_mapping["distance_m"].max()),
        "terrain_method": "IDW interpolation from SWMM node elevations plus backdrop contour control points; conduit buffers depressed as streets",
        "building_method": "manual synthetic polygons digitized from visible blocks on SWMM sample backdrop",
    }
    (static_dir / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    (PROJECT_DIR / "model.yaml").write_text(
        "\n".join(
            [
                "name: suanliguanw_swmm_2d",
                "type: swmm_2d",
                "description: Synthetic CA2D companion model for EPA SWMM Site Drainage Model sample.",
                "",
                "paths:",
                "  raw: raw",
                "  static: static",
                "  swmm: swmm",
                "  mapping: mapping",
                "  events: events",
                "  runs: runs",
                "",
                "default_scenario: baseline",
                "scenarios:",
                "  baseline:",
                "    swmm_inp: swmm/scenarios/baseline/model.inp",
                "  two_year_design:",
                "    swmm_inp: swmm/scenarios/two_year_design/model.inp",
                "",
                "ca2d:",
                "  static_model: static",
                "  node_to_cell_mapping: static/node_to_cell_mapping.csv",
                "  source_config: static/config.json",
                "  default_dt_seconds: 10.0",
                "  default_boundary_interval_minutes: 5.0",
                "  default_save_interval_minutes: 30.0",
                "",
                "notes:",
                "  - The CA2D surface is synthetic and inferred from SWMM node elevations and the sample backdrop.",
                "  - Coordinates and elevations from the SWMM sample are converted from feet to metres for CA2D.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = [
        "# suanliguanw_swmm_2d",
        "",
        "This project packages the EPA SWMM `Site_Drainage_Model.inp` sample with a synthetic CA2D static surface.",
        "",
        "## Structure",
        "",
        "- `raw/`: original SWMM sample input and backdrop image.",
        "- `swmm/scenarios/baseline/model.inp`: standard baseline SWMM entry point.",
        "- `swmm/scenarios/two_year_design/model.inp`: same model with the rain gage switched to the 2-year storm.",
        "- `static/`: reusable CA2D grids, masks, resistance field, cells table, and node-cell mapping.",
        "- `mapping/`: copy of stable node-to-cell mapping table.",
        "- `events/`: rainfall time series extracted from the INP; `rain1.txt` mirrors the 2-year event.",
        "- `runs/`: reserved for simulation outputs.",
        "",
        "## CA2D Build Assumptions",
        "",
        "- Grid cell size: 25 ft / 7.62 m.",
        "- Terrain: IDW interpolation from SWMM node elevations plus contour labels visible on `Site-Post.jpg`.",
        "- Streets: buffered SWMM conduit polylines, depressed by up to 0.25 ft and assigned higher conveyance.",
        "- Buildings: six synthetic polygon blocks digitized from the visible residential/commercial parcels on the backdrop.",
        "- Node coupling: each SWMM node is attached to the nearest valid, non-building flow cell.",
        "",
        "## Current Baseline",
        "",
        "- SWMM input: `swmm/scenarios/baseline/model.inp`",
        "- 2-year SWMM input: `swmm/scenarios/two_year_design/model.inp`",
        "- CA2D static model: `static/`",
        "- Node-cell mapping: `static/node_to_cell_mapping.csv`",
    ]
    (PROJECT_DIR / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    build_summary = [
        "# CA2D Static Build Summary",
        "",
        f"- Source INP: `{SOURCE_INP}`",
        f"- Source backdrop: `{SOURCE_BACKDROP}`",
        f"- Grid shape: {ny} rows x {nx} columns",
        f"- Cell size: {CELL_SIZE_M:.2f} m ({CELL_SIZE_FT:.1f} ft)",
        f"- Valid cells: {len(cells)}",
        f"- Flow cells: {int(cells['is_flow'].sum())}",
        f"- Building cells: {int(cells['is_building'].sum())}",
        f"- Road cells: {int(cells['is_road'].sum())}",
        f"- Buildings: {len(buildings)}",
        f"- Street buffers: {len(street_rows)}",
        f"- Mapped SWMM nodes: {len(node_mapping)}",
        f"- Node mapping max distance: {node_mapping['distance_m'].max():.2f} m",
        "",
        "The source model has zero MaxDepth values at junctions, so surface elevations use the listed node elevations directly; outfall elevation is retained as a low outlet control.",
    ]
    (static_dir / "build_summary.md").write_text("\n".join(build_summary) + "\n", encoding="utf-8")


def render_preview(static_dir, elevation_m, valid_mask, flow_mask, road_mask, building_mask, node_mapping):
    masked = np.ma.masked_where(~valid_mask, elevation_m)
    fig, ax = plt.subplots(figsize=(10, 8), dpi=160)
    image = ax.imshow(masked, cmap="terrain")
    ax.imshow(np.ma.masked_where(~road_mask, road_mask), cmap="Greys", alpha=0.45)
    ax.imshow(np.ma.masked_where(~building_mask, building_mask), cmap="binary", alpha=0.70)
    ax.scatter(node_mapping["cell_col"], node_mapping["cell_row"], s=18, c="#1b9e77", edgecolors="black", linewidths=0.3)
    for _, row in node_mapping.iterrows():
        ax.text(row["cell_col"] + 0.6, row["cell_row"] + 0.4, row["node_id"], fontsize=6, color="black")
    ax.set_title("Synthetic CA2D terrain, streets, buildings, and SWMM node-cell links")
    ax.set_xticks([])
    ax.set_yticks([])
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Elevation (m)")
    fig.tight_layout()
    fig.savefig(static_dir / "ca2d_static_preview.png")
    plt.close(fig)


if __name__ == "__main__":
    build_static_model()
