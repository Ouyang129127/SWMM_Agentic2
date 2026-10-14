"""Rebuild only the site's CA2D surface from local SWMM data and backdrop.

Roads are traced in backdrop pixel coordinates. Building footprints are
synthetic hypotheses placed within traced developable parcels, not surveys.
Existing SWMM scenarios, event files, project settings and runs are preserved.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.path import Path as MplPath
import numpy as np
import pandas as pd
from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE_INP = PROJECT_DIR / "swmm" / "scenarios" / "baseline" / "model.inp"
SOURCE_BACKDROP = PROJECT_DIR / "swmm" / "Site-Post.jpg"
LAYOUT = PROJECT_DIR / "raw" / "references" / "site_layout_reference.json"
FT_TO_M = 0.3048
CELL_SIZE_M = 3.0
CELL_SIZE_FT = CELL_SIZE_M / FT_TO_M


def parse_inp(path: Path) -> dict:
    sections = {}
    current = None
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line.strip("[]").upper()
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line.split())
    return sections


def read_named_points(sections):
    return {r[0]: (float(r[1]), float(r[2])) for r in sections.get("COORDINATES", []) if len(r) >= 3}


def read_nodes(sections):
    nodes = {}
    for section, kind in [("JUNCTIONS", "JUNCTION"), ("OUTFALLS", "OUTFALL")]:
        for row in sections.get(section, []):
            invert = float(row[1])
            depth = float(row[2]) if kind == "JUNCTION" else 0.0
            nodes[row[0]] = {"type": kind, "invert_ft": invert, "max_depth_ft": depth,
                             "surface_ft": invert + depth}
    return nodes


def read_polygons(sections):
    polygons = {}
    for row in sections.get("POLYGONS", []):
        polygons.setdefault(row[0], []).append((float(row[1]), float(row[2])))
    return {key: value for key, value in polygons.items() if len(value) >= 3}


def point_segment_distance(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    if denom == 0:
        return np.hypot(px - ax, py - ay)
    t = np.clip(((px - ax) * vx + (py - ay) * vy) / denom, 0.0, 1.0)
    return np.hypot(px - (ax + t * vx), py - (ay + t * vy))


def distance_to_polyline(xx, yy, points):
    result = np.full(xx.shape, np.inf)
    for a, b in zip(points[:-1], points[1:]):
        result = np.minimum(result, point_segment_distance(xx, yy, *a, *b))
    return result


def polygon_mask(xx, yy, polygon):
    return MplPath(polygon).contains_points(np.column_stack([xx.ravel(), yy.ravel()])).reshape(xx.shape)


def idw_surface(xx, yy, controls):
    values, weights = np.zeros(xx.shape), np.zeros(xx.shape)
    for x, y, z in controls:
        w = 1.0 / np.maximum((xx - x) ** 2 + (yy - y) ** 2, 36.0)
        values += w * z
        weights += w
    return values / weights


def pixel_to_world(points, image_size, source_bounds_ft):
    """Map image outer edges to BACKDROP bounds; invert the downward pixel Y."""
    width, height = image_size
    minx, miny, maxx, maxy = source_bounds_ft
    points = np.asarray(points, dtype=float)
    return np.column_stack([minx + points[:, 0] / width * (maxx - minx),
                            maxy - points[:, 1] / height * (maxy - miny)]) * FT_TO_M


def make_buildings(xx, yy, valid, road_margin, coords, layout, image_size, source_bounds_ft):
    forbidden = ~valid | road_margin
    for x_ft, y_ft in coords.values():
        forbidden |= np.hypot(xx - x_ft * FT_TO_M, yy - y_ft * FT_TO_M) <= layout["building_node_clearance_m"]
    building = np.zeros(xx.shape, dtype=bool)
    occupied = np.zeros(xx.shape, dtype=bool)
    records = []
    # Each type has fixed spacing and deterministically varied sizes, in metres.
    recipes = {
        "commercial": (27.0, 24.0, [(18, 15), (21, 15), (18, 18)]),
        "residential": (21.0, 21.0, [(12, 12), (15, 12), (12, 15)]),
        "terraced": (15.0, 18.0, [(9, 12), (6, 9), (9, 9)]),
    }
    for parcel_index, parcel in enumerate(layout["parcels"]):
        region = pixel_to_world(parcel["points_px"], image_size, source_bounds_ft)
        region_mask = polygon_mask(xx, yy, region)
        # The reference angle is clockwise on the image, counterclockwise on map Y.
        angle = math.radians(-parcel["angle_deg"])
        rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
        local = region @ rotation
        step_x, step_y, sizes = recipes[parcel["kind"]]
        x0, y0 = local.min(axis=0)
        x1, y1 = local.max(axis=0)
        # Start with a regular lattice; then try grid-centre candidates to
        # accommodate narrow/irregular parcels instead of leaving them empty.
        candidates = [(cx, cy) for cy in np.arange(y0 + step_y / 2, y1, step_y)
                      for cx in np.arange(x0 + step_x / 2, x1, step_x)]
        interior_distance = distance_to_polyline(xx, yy, np.vstack([region, region[0]]))
        rr, cc = np.where(region_mask & ~forbidden)
        order = np.argsort(-interior_distance[rr, cc], kind="stable")
        candidates.extend(np.column_stack([xx[rr[order], cc[order]], yy[rr[order], cc[order]]]) @ rotation)
        target = max(1, int(region_mask.sum() * CELL_SIZE_M ** 2 / (step_x * step_y)))
        count = 0
        for candidate_index, (cx, cy) in enumerate(candidates):
            if count >= target:
                break
            preferred = sizes[(parcel_index + candidate_index) % len(sizes)]
            for w, h in [preferred] + sorted(set(sizes), key=lambda s: s[0] * s[1]):
                corners = np.array([[-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]])
                footprint = (corners + [cx, cy]) @ rotation.T
                if not MplPath(region).contains_points(footprint).all():
                    continue
                mask = polygon_mask(xx, yy, footprint)
                if mask.sum() < 6 or (mask & (forbidden | occupied | ~region_mask)).any():
                    continue
                building |= mask
                expanded = (corners * [(w + 6) / w, (h + 6) / h] + [cx, cy]) @ rotation.T
                occupied |= polygon_mask(xx, yy, expanded)
                records.append({"building_id": f"B{len(records)+1:03d}", "parcel_id": parcel["id"],
                                "kind": parcel["kind"], "width_m": w, "depth_m": h,
                                "raise_m": layout["building_raise_m"], "n_cells": int(mask.sum()),
                                "vertices_m": json.dumps(footprint.tolist()),
                                "assumption": "synthetic footprint within backdrop-inferred parcel"})
                count += 1
                break
    if not records:
        raise ValueError("No building footprints fit the registered parcels")
    return building, pd.DataFrame(records)


def map_nodes(nodes, coords, flow, xx, yy, elevation, cell_ids, smids):
    rows, cols = np.where(flow)
    records = []
    for index, (name, node) in enumerate(nodes.items(), 1):
        if name not in coords:
            raise ValueError(f"Missing SWMM node coordinate: {name}")
        x_ft, y_ft = coords[name]
        x, y = x_ft * FT_TO_M, y_ft * FT_TO_M
        distances = np.hypot(xx[flow] - x, yy[flow] - y)
        nearest = int(np.argmin(distances))
        row, col = int(rows[nearest]), int(cols[nearest])
        records.append({"node_smid": index, "node_id": name, "node_type": node["type"],
                        "node_x": x, "node_y": y, "node_x_ft": x_ft, "node_y_ft": y_ft,
                        "invert_elevation_m": node["invert_ft"] * FT_TO_M,
                        "max_depth_m": node["max_depth_ft"] * FT_TO_M,
                        "surface_elevation_m": node["surface_ft"] * FT_TO_M,
                        "cell_id": int(cell_ids[row, col]), "smid": int(smids[row, col]),
                        "cell_row": row, "cell_col": col, "cell_x": float(xx[row, col]),
                        "cell_y": float(yy[row, col]), "cell_elevation": float(elevation[row, col]),
                        "distance_m": float(distances[nearest]), "weight": 1.0})
    return pd.DataFrame(records)


def validate_arrays(arrays, config, mapping):
    shape = tuple(config["grid_shape"])
    assert all(a.shape == shape for a in arrays.values()), "Array shapes differ"
    valid, flow = arrays["valid_mask"], arrays["flow_mask"]
    road, building = arrays["road_mask"], arrays["building_mask"]
    assert valid.any() and road.any() and building.any()
    assert np.array_equal(flow, valid & ~building)
    assert not (building & road).any() and not (road & ~flow).any()
    assert np.isfinite(arrays["elevation"]).all()
    assert np.isfinite(arrays["terrain"]).all()
    delta = arrays["elevation"] - arrays["terrain"]
    assert np.allclose(delta[building], config["building_raise_m"], atol=2e-4)
    assert np.allclose(delta[road], -config["road_lowering_m"], atol=2e-4)
    assert np.allclose(delta[valid & ~building & ~road], 0)
    assert np.all(arrays["resistance"][~flow] == 0)
    assert len(mapping) == config["n_nodes"] and mapping.node_id.is_unique
    for record in mapping.itertuples():
        r, c = record.cell_row, record.cell_col
        assert flow[r, c] and not building[r, c]
        assert record.smid == arrays["smid_grid"][r, c]
        assert record.cell_id == arrays["cell_id_grid"][r, c]
        assert np.isclose(record.cell_elevation, arrays["elevation"][r, c])


def render_previews(static, arrays, config, mapping, layout, image_size, source_bounds_ft):
    extent = config["bounds"][0], config["bounds"][2], config["bounds"][1], config["bounds"][3]
    source_m = np.asarray(source_bounds_ft) * FT_TO_M
    backdrop_extent = source_m[0], source_m[2], source_m[1], source_m[3]
    legend = [Patch(facecolor="#ed9c36", label="Road: ground - 0.10 m"),
              Patch(facecolor="#414650", label="Inferred building: ground + 15 m")]
    fig, axes = plt.subplots(1, 2, figsize=(13, 7.5), constrained_layout=True)
    ground = np.ma.masked_where(~arrays["valid_mask"], arrays["terrain"])
    terrain_plot = axes[1].imshow(ground, extent=extent, origin="upper", cmap="terrain")
    with Image.open(SOURCE_BACKDROP) as backdrop_image:
        axes[0].imshow(backdrop_image, extent=backdrop_extent, origin="upper", alpha=.85)
    for ax in axes:
        for key, color, alpha in [("road_mask", "#ed9c36", .70), ("building_mask", "#414650", .90)]:
            mask = arrays[key]
            ax.imshow(np.ma.masked_where(~mask, np.ones(mask.shape)), extent=extent, origin="upper",
                      cmap=ListedColormap([color]), interpolation="nearest", alpha=alpha)
        ax.scatter(mapping.node_x, mapping.node_y, s=17, c="#126bb7", edgecolors="white", linewidths=.4, zorder=5)
        for row in mapping.itertuples():
            ax.annotate(row.node_id, (row.node_x, row.node_y), xytext=(3, 3), textcoords="offset points", fontsize=6)
        ax.set_aspect("equal")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_xlim(extent[:2])
        ax.set_ylim(extent[2:])
    axes[0].set_title("Backdrop registration / inferred roads and footprints")
    axes[1].set_title(f"CA2D: {len(mapping)} nodes / {config['n_buildings']} buildings / 3 m cells")
    axes[1].legend(handles=legend, loc="lower left", fontsize=7)
    fig.colorbar(terrain_plot, ax=axes[1], shrink=.55, label="Ground elevation before buildings (m)")
    fig.savefig(static / "ca2d_static_preview.png", dpi=180)
    fig.savefig(static / "ca2d_layout_preview.png", dpi=180)
    plt.close(fig)

    # Separate trace-only overlay lets the road hypothesis be reviewed against
    # the backdrop even where the SWMM polygon domain clips perimeter roads.
    fig, ax = plt.subplots(figsize=(8, 8.5), constrained_layout=True)
    with Image.open(SOURCE_BACKDROP) as backdrop_image:
        ax.imshow(backdrop_image)
    for road in layout["roads"]:
        points = np.asarray(road["points_px"])
        ax.plot(points[:, 0], points[:, 1], c="#ed9c36", linewidth=2, alpha=.9)
    for parcel in layout["parcels"]:
        points = np.asarray(parcel["points_px"] + [parcel["points_px"][0]])
        ax.plot(points[:, 0], points[:, 1], c="#187cb7", linewidth=.8)
    ax.set_title("Orange: inferred road centres; blue: developable parcels")
    ax.set_axis_off()
    fig.savefig(static / "backdrop_layout_reference.png", dpi=180)
    plt.close(fig)

    # Raised roofs appear in this surface plot using the actual solver DEM.
    xx = extent[0] + (np.arange(arrays["elevation"].shape[1]) + .5) * CELL_SIZE_M
    yy = extent[3] - (np.arange(arrays["elevation"].shape[0]) + .5) * CELL_SIZE_M
    xx, yy = np.meshgrid(xx, yy)
    z = np.where(arrays["valid_mask"], arrays["elevation"], np.nan)
    fig = plt.figure(figsize=(11, 8), constrained_layout=True)
    ax = fig.add_subplot(111, projection="3d")
    surface = ax.plot_surface(xx, yy, z, rstride=1, cstride=1, cmap="terrain", linewidth=0, antialiased=False)
    ax.view_init(elev=48, azim=-65)
    ax.set_box_aspect((1, 1, .22))
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Elevation (m)")
    ax.set_title("Site CA2D solver surface: buildings raised 15 m")
    fig.colorbar(surface, ax=ax, shrink=.5, pad=.08, label="Elevation (m)")
    fig.savefig(static / "ca2d_elevation_3d.png", dpi=180)
    plt.close(fig)


def build_static_model():
    sections = parse_inp(SOURCE_INP)
    coords, nodes, polygons = read_named_points(sections), read_nodes(sections), read_polygons(sections)
    if not polygons:
        raise ValueError("The SWMM input has no subcatchment polygons")
    backdrop = {row[0].upper(): row[1:] for row in sections.get("BACKDROP", [])}
    if "DIMENSIONS" not in backdrop:
        # Scenario writers may omit display-only BACKDROP metadata. Recover
        # registration from the local source, never from a machine-global file.
        original = parse_inp(PROJECT_DIR / "swmm" / "Model.inp")
        backdrop = {row[0].upper(): row[1:] for row in original.get("BACKDROP", [])}
    source_bounds_ft = list(map(float, backdrop["DIMENSIONS"][:4]))
    minx_ft, miny_ft, maxx_ft, maxy_ft = source_bounds_ft
    nx = math.ceil((maxx_ft - minx_ft) / CELL_SIZE_FT)
    ny = math.ceil((maxy_ft - miny_ft) / CELL_SIZE_FT)
    xx_ft, yy_ft = np.meshgrid(minx_ft + (np.arange(nx) + .5) * CELL_SIZE_FT,
                              maxy_ft - (np.arange(ny) + .5) * CELL_SIZE_FT)
    xx, yy = xx_ft * FT_TO_M, yy_ft * FT_TO_M
    valid = np.zeros((ny, nx), dtype=bool)
    for polygon in polygons.values():
        valid |= polygon_mask(xx_ft, yy_ft, polygon)

    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    with Image.open(SOURCE_BACKDROP) as backdrop_image:
        image_size = backdrop_image.size
    if list(image_size) != layout["image_size_px"]:
        raise ValueError("Backdrop image dimensions changed; update pixel reference registration first")
    road_mask = np.zeros(valid.shape, dtype=bool)
    road_margin = np.zeros(valid.shape, dtype=bool)
    streets = []
    for road in layout["roads"]:
        points = pixel_to_world(road["points_px"], image_size, source_bounds_ft)
        distance = distance_to_polyline(xx, yy, points)
        mask = (distance <= road["width_m"] / 2) & valid
        road_mask |= mask
        road_margin |= distance <= road["width_m"] / 2 + layout["building_road_clearance_m"]
        streets.append({"street_id": road["id"], "source": "manually traced Site-Post.jpg road centreline",
                        "width_m": road["width_m"], "lowering_m": layout["road_lowering_m"],
                        "n_cells": int(mask.sum()), "vertices_m": json.dumps(points.tolist()),
                        "vertices_px": json.dumps(road["points_px"])})
    building, buildings = make_buildings(xx, yy, valid, road_margin, coords, layout, image_size, source_bounds_ft)
    flow = valid & ~building
    # Preserve the former terrain controls; this task only changes land features.
    manual_controls = [(80,1280,4975),(360,1420,4975),(690,1320,4974),(1110,1320,4973),
                       (1310,1110,4971),(1345,930,4969),(1380,700,4967),(1280,150,4970),
                       (780,70,4970),(430,760,4970.3),(800,820,4968.8),(1150,745,4968.4),(1410,477,4962)]
    controls = [(*coords[key], node["surface_ft"]) for key, node in nodes.items() if key in coords]
    terrain = (idw_surface(xx_ft, yy_ft, controls + manual_controls) * FT_TO_M).astype(np.float32)
    elevation = terrain.copy()
    elevation[road_mask] -= layout["road_lowering_m"]
    elevation[building] += layout["building_raise_m"]
    elevation[~valid] = 0
    terrain[~valid] = 0
    cell_ids = np.full(valid.shape, -1, dtype=np.int32)
    cell_ids[valid] = np.arange(valid.sum(), dtype=np.int32)
    smids = np.where(valid, cell_ids + 1, 0).astype(np.int32)
    # The solver multiplies flux by this coefficient: larger values convey more.
    resistance = np.zeros(valid.shape, dtype=np.float32)
    resistance[flow] = .62
    resistance[road_mask] = .90
    arrays = {"elevation": elevation, "terrain": terrain, "valid_mask": valid, "domain_mask": valid,
              "flow_mask": flow, "building_mask": building, "road_mask": road_mask,
              "cell_id_grid": cell_ids, "smid_grid": smids, "resistance": resistance}
    mapping = map_nodes(nodes, coords, flow, xx, yy, elevation, cell_ids, smids)
    # Pad the raster extent to match the 3 m cell edges, not the image extent.
    bounds = [minx_ft * FT_TO_M, maxy_ft * FT_TO_M - ny * CELL_SIZE_M,
              minx_ft * FT_TO_M + nx * CELL_SIZE_M, maxy_ft * FT_TO_M]
    config = {"source_inp": str(SOURCE_INP.relative_to(PROJECT_DIR)),
              "source_backdrop": str(SOURCE_BACKDROP.relative_to(PROJECT_DIR)),
              "layout_reference": str(LAYOUT.relative_to(PROJECT_DIR)),
              "backdrop_registration_source": "SWMM [BACKDROP] DIMENSIONS, falling back to local swmm/Model.inp",
              "spatial_units": "metre", "source_map_units": "feet", "source_elevation_units": "feet",
              "coordinate_conversion": "source feet multiplied by 0.3048", "crs": None,
              "bounds": bounds, "source_bounds_ft": source_bounds_ft,
              "backdrop_bounds_m": (np.asarray(source_bounds_ft) * FT_TO_M).tolist(),
              "backdrop_image_size_px": list(image_size), "cell_size": CELL_SIZE_M,
              "cell_size_ft": CELL_SIZE_FT, "grid_shape": [ny, nx], "n_cells": nx * ny,
              "n_valid_cells": int(valid.sum()), "n_flow_cells": int(flow.sum()),
              "n_building_cells": int(building.sum()), "n_road_cells": int(road_mask.sum()),
              "n_buildings": len(buildings), "n_streets": len(streets),
              "n_nodes": len(nodes), "n_mapped_nodes": len(mapping),
              "node_mapping_distance_median": float(mapping.distance_m.median()),
              "node_mapping_distance_95p": float(mapping.distance_m.quantile(.95)),
              "node_mapping_distance_max": float(mapping.distance_m.max()),
              "building_raise_m": layout["building_raise_m"], "road_lowering_m": layout["road_lowering_m"],
              "building_road_clearance_m": layout["building_road_clearance_m"],
              "building_node_clearance_m": layout["building_node_clearance_m"],
              "land_conveyance_coefficient": .62, "road_conveyance_coefficient": .90,
              "terrain_method": "IDW from SWMM node surfaces and original synthetic backdrop contour controls",
              "domain_method": "unchanged union of SWMM subcatchment polygons at cell centres",
              "road_method": "backdrop-inferred centre lines buffered to 8-10 m width and lowered by 0.10 m",
              "building_method": "varied rotated synthetic footprints within backdrop-inferred parcels, raised by 15 m",
              "assumption_status": "inferred roads and synthetic footprints; heights and widths are modelling assumptions",
              "historical_runs": "Existing runs predate this static rebuild; rerun CA2D to apply the new layout."}
    validate_arrays(arrays, config, mapping)
    static, mapping_dir = PROJECT_DIR / "static", PROJECT_DIR / "mapping"
    static.mkdir(exist_ok=True)
    mapping_dir.mkdir(exist_ok=True)
    for name, array in arrays.items():
        np.save(static / f"{name}.npy", array)
    for directory in [static, mapping_dir]:
        mapping.to_csv(directory / "node_to_cell_mapping.csv", index=False)
    buildings.to_csv(static / "synthetic_buildings.csv", index=False)
    pd.DataFrame(streets).to_csv(static / "synthetic_streets.csv", index=False)
    rows, cols = np.where(valid)
    cells = pd.DataFrame({"cell_id": cell_ids[valid], "smid": smids[valid], "row": rows, "col": cols,
                          "x": xx[valid], "y": yy[valid], "x_ft": xx_ft[valid], "y_ft": yy_ft[valid],
                          "area_m2": CELL_SIZE_M ** 2, "elevation": elevation[valid], "terrain": terrain[valid],
                          "is_valid": True, "is_building": building[valid], "is_road": road_mask[valid],
                          "is_flow": flow[valid]})
    cells.to_csv(static / "cells.csv", index=False)
    (static / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = ["# Site_Drainage_Model CA2D 静态模型改造", "",
               f"- 网格：{ny} × {nx}；分辨率 {CELL_SIZE_M:g} m；有效单元 {valid.sum()}。",
               f"- 建筑：{len(buildings)} 栋推测轮廓，{building.sum()} 个单元；相对原地面抬高 15 m，排除出过流域。",
               f"- 道路：{len(streets)} 条底图推测中心线，{road_mask.sum()} 个单元；宽 8–10 m，下凹 0.10 m。",
               "- 道路/其他土地过流系数：0.90 / 0.62（代码中的 resistance 数值越大，过流越强）。",
               f"- 耦合：{len(mapping)} 个节点全部映射至非建筑过流单元；最大距离 {mapping.distance_m.max():.2f} m。",
               "- terrain.npy 保存未叠加道路/建筑的原地面，elevation.npy 是实际求解高程。",
               "- 建筑避开道路及周边 3 m、节点周边 6 m；中央公园和排水廊道未作为建筑地块。", "",
               "位置依据 swmm/Site-Post.jpg 和 SWMM [BACKDROP] 范围配准。底图展示地块，不能确定真实建筑轮廓；",
               "楼高、道路宽度、下凹量与建筑占地均为可修改的建模假设，保存在 raw/references/site_layout_reference.json。",
               "未修改 SWMM 场景、降雨文件或既有运行结果；既有结果不会自动更新，需要重新运行 CA2D。", "",
               "重建命令：`python models/Site_Drainage_Model/scripts/build_site_ca2d.py`。", ""]
    (static / "build_summary.md").write_text("\n".join(summary), encoding="utf-8")
    render_previews(static, arrays, config, mapping, layout, image_size, source_bounds_ft)
    print(json.dumps({key: config[key] for key in ["grid_shape", "n_buildings", "n_building_cells",
                     "n_road_cells", "n_mapped_nodes", "node_mapping_distance_max"]}, indent=2))


if __name__ == "__main__":
    build_static_model()
