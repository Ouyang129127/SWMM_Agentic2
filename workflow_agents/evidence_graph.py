"""Ontology-inspired evidence graph builder for overflow-node diagnostics."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

import pandas as pd

from .rainfall_context import build_rainfall_context, write_rainfall_context
from .schemas import WORKFLOW_SCHEMA_VERSION, artifacts_for_run
from .state import resolve_run_root


EVIDENCE_GRAPH_SCHEMA_NAME = "swmm_ca2d_overflow_node_evidence_graph"
DEFAULT_ANCHOR_LIMIT = 10
DEFAULT_NEIGHBOR_MODE = "8-neighbor"
DEFAULT_MAX_TRACE_DEPTH = 8
DEFAULT_MAX_CLUSTER_CELLS = 200
PONDING_DEPTH_THRESHOLD_M = 0.005
HIGH_FULLNESS_THRESHOLD = 0.80
FLOW_DIRECTION_CHANGE_THRESHOLD = 3
REPEATED_OVERFLOW_EVENT_THRESHOLD = 2
LINK_HYDRAULIC_METRICS = [
    "max_fullness",
    "fullness_ge_0_8_duration",
    "fullness_ge_0_95_duration",
    "surcharge_duration",
    "max_flow",
    "flow_direction_changes",
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_rainfall_file(summary: dict[str, Any], run_root: Path) -> Path:
    for key in ["rainfall_event_copy", "rainfall_file"]:
        value = summary.get(key)
        if value:
            path = Path(str(value))
            if path.exists():
                return path
            candidate = run_root / str(value)
            if candidate.exists():
                return candidate
    return run_root / "rainfall_event.txt"


def _resolve_model_file(run_root: Path, *parts: str) -> Path:
    model_root = run_root.parents[1]
    return model_root.joinpath(*parts)


def _parse_conduits(inp_path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not inp_path.exists():
        return pd.DataFrame(columns=["link_id", "from_node", "to_node", "length"])
    in_conduits = False
    for raw_line in inp_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("["):
            in_conduits = line.upper() == "[CONDUITS]"
            continue
        if not in_conduits or line.startswith(";"):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            length = float(parts[3])
        except ValueError:
            length = None
        rows.append(
            {
                "link_id": str(parts[0]),
                "from_node": str(parts[1]),
                "to_node": str(parts[2]),
                "length": length,
            }
        )
    return pd.DataFrame(rows)


def _parse_outfalls(inp_path: Path) -> set[str]:
    outfalls: set[str] = set()
    if not inp_path.exists():
        return outfalls
    in_outfalls = False
    for raw_line in inp_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("["):
            in_outfalls = line.upper() == "[OUTFALLS]"
            continue
        if not in_outfalls or line.startswith(";"):
            continue
        parts = line.split()
        if parts:
            outfalls.add(str(parts[0]))
    return outfalls


def _model_inp_path(run_root: Path, summary: dict[str, Any]) -> Path:
    candidates = [
        run_root / "swmm" / "model_with_event.inp",
        Path(str(summary.get("source_scenario_inp", ""))),
        _resolve_model_file(run_root, "swmm", "scenarios", "baseline", "Model.inp"),
        _resolve_model_file(run_root, "swmm", "scenarios", "baseline", "model.inp"),
        _resolve_model_file(run_root, "swmm", "Model.inp"),
        _resolve_model_file(run_root, "swmm", "model.inp"),
    ]
    for path in candidates:
        if str(path) and path.exists():
            return path
    return candidates[0]


def _metric_records(evidence: pd.DataFrame) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    records: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for _, row in evidence.iterrows():
        key = (str(row["object_type"]), str(row["object_id"]))
        records.setdefault(key, {})[str(row["metric_name"])] = row.to_dict()
    return records


def _metric_value(records: dict[tuple[str, str], dict[str, dict[str, Any]]], object_type: str, object_id: str, metric: str, default: float = 0.0) -> float:
    row = records.get((object_type, str(object_id)), {}).get(metric)
    if not row:
        return default
    try:
        return float(row.get("value", default))
    except (TypeError, ValueError):
        return default


def _metric_evidence_ids(records: dict[tuple[str, str], dict[str, dict[str, Any]]], object_type: str, object_id: str, metrics: list[str]) -> list[str]:
    ids = []
    object_metrics = records.get((object_type, str(object_id)), {})
    for metric in metrics:
        row = object_metrics.get(metric)
        if row and row.get("evidence_id"):
            ids.append(str(row["evidence_id"]))
    return ids


def _metric_payload(records: dict[tuple[str, str], dict[str, dict[str, Any]]], object_type: str, object_id: str, metrics: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {"object_id": str(object_id), "evidence_ids": []}
    for metric in metrics:
        row = records.get((object_type, str(object_id)), {}).get(metric)
        if not row:
            payload[metric] = None
            continue
        payload[metric] = row.get("value")
        payload["evidence_ids"].append(str(row.get("evidence_id")))
    return payload


def _load_anchor_claims(diagnosis: dict[str, Any], evidence: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    claims = [
        claim
        for claim in diagnosis.get("claims", [])
        if claim.get("claim_type") == "major_overflow_node" and claim.get("object_type") == "node"
    ]
    if claims:
        return claims[:limit]
    overflow = evidence[
        (evidence["object_type"] == "node")
        & (evidence["metric_name"] == "total_flooding_volume")
        & (evidence["value"] > 0)
    ].sort_values("value", ascending=False).head(limit)
    return [
        {
            "claim_id": f"overflow_anchor_{idx + 1}",
            "claim_type": "major_overflow_node",
            "object_type": "node",
            "object_id": str(row["object_id"]),
            "severity": "high",
            "evidence_ids": [str(row["evidence_id"])],
        }
        for idx, (_, row) in enumerate(overflow.iterrows())
    ]


def _neighbor_offsets(neighbor_mode: str) -> list[tuple[int, int]]:
    offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if neighbor_mode == "8-neighbor":
        offsets.extend([(-1, -1), (-1, 1), (1, -1), (1, 1)])
    return offsets


def _build_cell_cluster(
    start_smids: list[str],
    cell_by_smid: dict[str, dict[str, Any]],
    smid_by_row_col: dict[tuple[int, int], str],
    ponding_smids: set[str],
    neighbor_mode: str,
    max_cells: int,
) -> tuple[list[str], list[tuple[str, str]]]:
    offsets = _neighbor_offsets(neighbor_mode)
    queue: deque[str] = deque([str(smid) for smid in start_smids if str(smid) in cell_by_smid])
    visited: set[str] = set()
    edges: set[tuple[str, str]] = set()
    while queue and len(visited) < max_cells:
        smid = queue.popleft()
        if smid in visited:
            continue
        visited.add(smid)
        cell = cell_by_smid.get(smid)
        if not cell:
            continue
        row = int(cell["row"])
        col = int(cell["col"])
        for dr, dc in offsets:
            neighbor = smid_by_row_col.get((row + dr, col + dc))
            if not neighbor or neighbor not in ponding_smids:
                continue
            edge = tuple(sorted((smid, neighbor)))
            edges.add(edge)
            if neighbor not in visited:
                queue.append(neighbor)
    return sorted(visited), sorted(edges)


def _trace_upstream(
    link_id: str,
    link_by_id: dict[str, dict[str, Any]],
    incoming_by_node: dict[str, list[str]],
    outfalls: set[str],
    max_depth: int,
) -> tuple[list[str], str, list[tuple[str, str]]]:
    path = [str(link_id)]
    relations: list[tuple[str, str]] = []
    current_link = str(link_id)
    for _ in range(max_depth):
        link = link_by_id.get(current_link)
        if not link:
            return path, "missing_link_topology", relations
        current_node = str(link["from_node"])
        incoming = incoming_by_node.get(current_node, [])
        if current_node in outfalls:
            return path, "outfall", relations
        if not incoming:
            return path, "source_node", relations
        if len(incoming) > 1:
            return path, "previous_confluence_node", relations
        next_link = incoming[0]
        relations.append((next_link, current_link))
        path.append(next_link)
        current_link = next_link
    return path, "max_trace_depth", relations


def _trace_downstream(
    link_id: str,
    link_by_id: dict[str, dict[str, Any]],
    incoming_by_node: dict[str, list[str]],
    outgoing_by_node: dict[str, list[str]],
    outfalls: set[str],
    max_depth: int,
) -> tuple[list[str], str, list[tuple[str, str]]]:
    path = [str(link_id)]
    relations: list[tuple[str, str]] = []
    current_link = str(link_id)
    for _ in range(max_depth):
        link = link_by_id.get(current_link)
        if not link:
            return path, "missing_link_topology", relations
        current_node = str(link["to_node"])
        if current_node in outfalls:
            return path, "outfall", relations
        if len(incoming_by_node.get(current_node, [])) > 1:
            return path, "next_confluence_node", relations
        outgoing = outgoing_by_node.get(current_node, [])
        if not outgoing:
            return path, "terminal_node", relations
        if len(outgoing) > 1:
            return path, "branching_node", relations
        next_link = outgoing[0]
        relations.append((current_link, next_link))
        path.append(next_link)
        current_link = next_link
    return path, "max_trace_depth", relations


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _surface_cluster_summary(
    cluster_smids: list[str],
    cell_by_smid: dict[str, dict[str, Any]],
    records: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    cells = [cell_by_smid[smid] for smid in cluster_smids if smid in cell_by_smid]
    depths = [_metric_value(records, "cell", smid, "max_depth", 0.0) for smid in cluster_smids]
    durations = [_metric_value(records, "cell", smid, "ponding_duration", 0.0) for smid in cluster_smids]
    elevations = [_as_float(cell.get("elevation")) for cell in cells]
    area_values = [_as_float(cell.get("area_m2")) for cell in cells]
    top_cells = sorted(
        [
            {
                "cell_id": smid,
                "max_depth_m": _metric_value(records, "cell", smid, "max_depth", 0.0),
                "ponding_duration_min": _metric_value(records, "cell", smid, "ponding_duration", 0.0),
                "ground_elevation_m": _as_float(cell_by_smid.get(smid, {}).get("elevation")),
                "evidence_ids": _metric_evidence_ids(records, "cell", smid, ["max_depth", "ponding_duration"]),
            }
            for smid in cluster_smids
        ],
        key=lambda item: float(item["max_depth_m"]),
        reverse=True,
    )[:10]
    return {
        "cell_count": len(cluster_smids),
        "total_area_m2": round(sum(area_values), 3),
        "max_depth_m": max(depths) if depths else 0.0,
        "mean_depth_m": round(sum(depths) / len(depths), 6) if depths else 0.0,
        "max_duration_min": max(durations) if durations else 0.0,
        "mean_duration_min": round(sum(durations) / len(durations), 6) if durations else 0.0,
        "min_ground_elevation_m": min(elevations) if elevations else None,
        "mean_ground_elevation_m": round(sum(elevations) / len(elevations), 6) if elevations else None,
        "max_ground_elevation_m": max(elevations) if elevations else None,
        "top_cells_by_depth": top_cells,
    }


def _trace_link_stats(
    link_ids: list[str],
    records: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    unique_links = list(dict.fromkeys(str(link_id) for link_id in link_ids))
    link_rows = [
        {
            "link_id": link_id,
            "max_fullness": _metric_value(records, "link", link_id, "max_fullness", 0.0),
            "fullness_ge_0_8_duration_min": _metric_value(records, "link", link_id, "fullness_ge_0_8_duration", 0.0),
            "fullness_ge_0_95_duration_min": _metric_value(records, "link", link_id, "fullness_ge_0_95_duration", 0.0),
            "surcharge_duration_min": _metric_value(records, "link", link_id, "surcharge_duration", 0.0),
            "max_flow_Ls": _metric_value(records, "link", link_id, "max_flow", 0.0),
            "flow_direction_changes": _metric_value(records, "link", link_id, "flow_direction_changes", 0.0),
            "evidence_ids": _metric_evidence_ids(records, "link", link_id, LINK_HYDRAULIC_METRICS),
        }
        for link_id in unique_links
    ]
    return {
        "link_count": len(unique_links),
        "max_fullness": max([float(item["max_fullness"]) for item in link_rows] or [0.0]),
        "max_fullness_ge_0_8_duration_min": max([float(item["fullness_ge_0_8_duration_min"]) for item in link_rows] or [0.0]),
        "max_fullness_ge_0_95_duration_min": max([float(item["fullness_ge_0_95_duration_min"]) for item in link_rows] or [0.0]),
        "max_surcharge_duration_min": max([float(item["surcharge_duration_min"]) for item in link_rows] or [0.0]),
        "max_flow_Ls": max([float(item["max_flow_Ls"]) for item in link_rows] or [0.0]),
        "max_flow_direction_changes": max([float(item["flow_direction_changes"]) for item in link_rows] or [0.0]),
        "high_fullness_links": [item for item in link_rows if float(item["max_fullness"]) >= HIGH_FULLNESS_THRESHOLD],
        "flow_direction_unstable_links": [
            item for item in link_rows if float(item["flow_direction_changes"]) >= FLOW_DIRECTION_CHANGE_THRESHOLD
        ],
    }


def _network_trace_summary(
    connected_links: list[dict[str, Any]],
    upstream_trace_items: list[dict[str, Any]],
    downstream_trace_items: list[dict[str, Any]],
    records: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    upstream_path_links = [link_id for item in upstream_trace_items for link_id in item.get("path", [])]
    downstream_path_links = [link_id for item in downstream_trace_items for link_id in item.get("path", [])]
    upstream_stats = _trace_link_stats(upstream_path_links, records)
    downstream_stats = _trace_link_stats(downstream_path_links, records)
    connected_stats = _trace_link_stats([str(link.get("link_id")) for link in connected_links], records)
    return {
        "connected_link_count": len(connected_links),
        "upstream_direct_link_count": len([link for link in connected_links if link.get("position") == "upstream"]),
        "downstream_direct_link_count": len([link for link in connected_links if link.get("position") == "downstream"]),
        "upstream_trace_count": len(upstream_trace_items),
        "downstream_trace_count": len(downstream_trace_items),
        "upstream_stop_reasons": sorted(set(str(item.get("stop_reason")) for item in upstream_trace_items)),
        "downstream_stop_reasons": sorted(set(str(item.get("stop_reason")) for item in downstream_trace_items)),
        "connected_link_stats": connected_stats,
        "upstream_trace_stats": upstream_stats,
        "downstream_trace_stats": downstream_stats,
    }


def _diagnostic_summary(
    node_id: str,
    rainfall_context: dict[str, Any],
    node_evidence: dict[str, Any],
    surface_summary: dict[str, Any],
    network_summary: dict[str, Any],
) -> dict[str, Any]:
    signals = []
    if surface_summary.get("cell_count", 0) > 0 and float(surface_summary.get("max_depth_m", 0.0) or 0.0) >= PONDING_DEPTH_THRESHOLD_M:
        signals.append("surface_ponding_response")
    if float(network_summary.get("downstream_trace_stats", {}).get("max_fullness", 0.0) or 0.0) >= HIGH_FULLNESS_THRESHOLD:
        signals.append("downstream_high_fullness")
    if float(network_summary.get("upstream_trace_stats", {}).get("max_fullness", 0.0) or 0.0) >= HIGH_FULLNESS_THRESHOLD:
        signals.append("upstream_high_load")
    if float(network_summary.get("connected_link_stats", {}).get("max_flow_direction_changes", 0.0) or 0.0) >= FLOW_DIRECTION_CHANGE_THRESHOLD:
        signals.append("flow_direction_instability")
    if _as_float(node_evidence.get("overflow_event_count")) >= REPEATED_OVERFLOW_EVENT_THRESHOLD:
        signals.append("repeated_overflow")
    if rainfall_context.get("short_duration_heavy_rainfall"):
        signals.append("short_duration_heavy_rainfall_context")
    return {
        "anchor_node": node_id,
        "diagnostic_unit": "overflow_node_centered_local_evidence_package",
        "rainfall_class": rainfall_context.get("intensity_class", "unknown"),
        "node_total_flooding_volume_m3": node_evidence.get("total_flooding_volume"),
        "node_flooding_duration_min": node_evidence.get("flooding_duration"),
        "node_overflow_event_count": node_evidence.get("overflow_event_count"),
        "surface_cluster_cell_count": surface_summary.get("cell_count", 0),
        "surface_cluster_max_depth_m": surface_summary.get("max_depth_m", 0.0),
        "surface_cluster_max_duration_min": surface_summary.get("max_duration_min", 0.0),
        "connected_link_count": network_summary.get("connected_link_count", 0),
        "upstream_trace_max_fullness": network_summary.get("upstream_trace_stats", {}).get("max_fullness", 0.0),
        "downstream_trace_max_fullness": network_summary.get("downstream_trace_stats", {}).get("max_fullness", 0.0),
        "diagnostic_signals": signals,
        "diagnostic_readiness": "ready" if signals else "weak_context",
    }


def build_evidence_graph_for_run(
    model_name: str,
    run_id: str,
    anchor_limit: int = DEFAULT_ANCHOR_LIMIT,
    neighbor_mode: str = DEFAULT_NEIGHBOR_MODE,
    max_trace_depth: int = DEFAULT_MAX_TRACE_DEPTH,
    max_cluster_cells: int = DEFAULT_MAX_CLUSTER_CELLS,
) -> dict[str, Any]:
    """Build relation table and overflow-node diagnostic evidence packages."""
    run_root = resolve_run_root(model_name, run_id)
    artifacts = artifacts_for_run(run_root)
    if not artifacts.evidence_table.exists():
        raise FileNotFoundError(f"Missing evidence table: {artifacts.evidence_table}")

    summary = _read_json(artifacts.run_summary)
    evidence = pd.read_csv(artifacts.evidence_table, dtype={"object_id": str, "evidence_id": str}, low_memory=False)
    evidence["value"] = pd.to_numeric(evidence["value"], errors="coerce").fillna(0.0)
    diagnosis = _read_json(artifacts.diagnosis_claims)

    rainfall_context = _read_json(artifacts.rainfall_context)
    if not rainfall_context:
        rainfall_context = build_rainfall_context(
            _resolve_rainfall_file(summary, run_root),
            event_name=str(summary.get("event_name", "")),
            run_id=str(summary.get("run_id", run_root.name)),
            model_name=str(summary.get("model_name", run_root.parents[1].name)),
            scenario_name=str(summary.get("scenario_name", "")),
        )
        write_rainfall_context(artifacts.rainfall_context, rainfall_context)

    model_root = run_root.parents[1]
    mapping_path = model_root / "static" / "node_to_cell_mapping.csv"
    cells_path = model_root / "static" / "cells.csv"
    if not mapping_path.exists():
        raise FileNotFoundError(f"Missing node-cell mapping: {mapping_path}")
    if not cells_path.exists():
        raise FileNotFoundError(f"Missing cell table: {cells_path}")

    mapping = pd.read_csv(mapping_path, dtype={"node_id": str, "smid": str, "cell_id": str})
    cells = pd.read_csv(cells_path, dtype={"smid": str})
    cells["row"] = pd.to_numeric(cells["row"], errors="coerce").astype("Int64")
    cells["col"] = pd.to_numeric(cells["col"], errors="coerce").astype("Int64")
    cells = cells.dropna(subset=["row", "col"])
    cell_by_smid = {str(row["smid"]): row.to_dict() for _, row in cells.iterrows()}
    smid_by_row_col = {(int(row["row"]), int(row["col"])): str(row["smid"]) for _, row in cells.iterrows()}

    inp_path = _model_inp_path(run_root, summary)
    conduits = _parse_conduits(inp_path)
    outfalls = _parse_outfalls(inp_path)
    link_by_id = {str(row["link_id"]): row.to_dict() for _, row in conduits.iterrows()}
    incoming_by_node: dict[str, list[str]] = {}
    outgoing_by_node: dict[str, list[str]] = {}
    for _, row in conduits.iterrows():
        link_id = str(row["link_id"])
        outgoing_by_node.setdefault(str(row["from_node"]), []).append(link_id)
        incoming_by_node.setdefault(str(row["to_node"]), []).append(link_id)

    records = _metric_records(evidence)
    anchors = _load_anchor_claims(diagnosis, evidence, int(anchor_limit))
    ponding_smids = set(
        evidence[
            (evidence["object_type"] == "cell")
            & (evidence["metric_name"] == "max_depth")
            & (evidence["value"] >= PONDING_DEPTH_THRESHOLD_M)
        ]["object_id"].astype(str)
    )

    relation_rows: list[dict[str, Any]] = []
    relation_seen: set[tuple[str, str, str, str, str]] = set()
    packages: list[dict[str, Any]] = []

    def add_relation(
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relation_type: str,
        direction: str,
        distance_m: float | None = None,
        topology_order: int | None = None,
        weight: float | None = None,
        confidence: str = "medium",
        data_source: str = "",
        evidence_ids: list[str] | None = None,
    ) -> str:
        key = (source_type, str(source_id), target_type, str(target_id), relation_type)
        existing_idx = len(relation_rows) + 1
        if key in relation_seen:
            return ""
        relation_seen.add(key)
        relation_id = f"R{existing_idx:06d}"
        relation_rows.append(
            {
                "relation_id": relation_id,
                "run_id": run_root.name,
                "source_type": source_type,
                "source_id": str(source_id),
                "target_type": target_type,
                "target_id": str(target_id),
                "relation_type": relation_type,
                "direction": direction,
                "distance_m": "" if distance_m is None else distance_m,
                "topology_order": "" if topology_order is None else topology_order,
                "weight": "" if weight is None else weight,
                "confidence": confidence,
                "data_source": data_source,
                "evidence_ids": ";".join(evidence_ids or []),
            }
        )
        return relation_id

    for anchor in anchors:
        node_id = str(anchor["object_id"])
        node_evidence = _metric_payload(
            records,
            "node",
            node_id,
            ["total_flooding_volume", "max_flooding_flow", "flooding_duration", "overflow_event_count", "max_node_depth"],
        )
        node_mapping = mapping[mapping["node_id"] == node_id].sort_values("distance_m").head(1)
        nearby_cells: list[dict[str, Any]] = []
        start_smids: list[str] = []
        for _, row in node_mapping.iterrows():
            smid = str(row["smid"])
            start_smids.append(smid)
            cell_evidence_ids = _metric_evidence_ids(records, "cell", smid, ["max_depth", "ponding_duration"])
            node_evidence_ids = _metric_evidence_ids(records, "node", node_id, ["total_flooding_volume", "flooding_duration", "overflow_event_count"])
            relation_id = add_relation(
                "node",
                node_id,
                "cell",
                smid,
                "node_near_cell",
                "nearby",
                distance_m=float(row.get("distance_m", 0.0)),
                topology_order=0,
                weight=float(row.get("weight", 1.0)),
                confidence="medium",
                data_source="node_to_cell_mapping",
                evidence_ids=node_evidence_ids + cell_evidence_ids,
            )
            nearby_cells.append(
                {
                    "cell_id": smid,
                    "relation_id": relation_id,
                    "distance_m": float(row.get("distance_m", 0.0)),
                    "weight": float(row.get("weight", 1.0)),
                    "max_depth_m": _metric_value(records, "cell", smid, "max_depth", 0.0),
                    "ponding_duration_min": _metric_value(records, "cell", smid, "ponding_duration", 0.0),
                    "ground_elevation_m": float(row.get("cell_elevation", 0.0)),
                    "evidence_ids": cell_evidence_ids,
                }
            )

        cluster_smids, cluster_edges = _build_cell_cluster(
            start_smids,
            cell_by_smid,
            smid_by_row_col,
            ponding_smids,
            neighbor_mode,
            int(max_cluster_cells),
        )
        cluster_relation_ids = []
        for source_smid, target_smid in cluster_edges:
            relation_id = add_relation(
                "cell",
                source_smid,
                "cell",
                target_smid,
                "cell_adjacent_to_cell",
                "adjacent",
                topology_order=1,
                weight=1.0,
                confidence="high",
                data_source=f"cell_grid_{neighbor_mode}",
                evidence_ids=_metric_evidence_ids(records, "cell", source_smid, ["max_depth", "ponding_duration"])
                + _metric_evidence_ids(records, "cell", target_smid, ["max_depth", "ponding_duration"]),
            )
            if relation_id:
                cluster_relation_ids.append(relation_id)

        connected_links = []
        relation_paths = []
        node_relation_ids: list[str] = []
        upstream_links = incoming_by_node.get(node_id, [])
        downstream_links = outgoing_by_node.get(node_id, [])
        for direction, link_ids in [("upstream", upstream_links), ("downstream", downstream_links)]:
            for link_id in link_ids:
                link_evidence_ids = _metric_evidence_ids(records, "link", link_id, LINK_HYDRAULIC_METRICS)
                relation_id = add_relation(
                    "node",
                    node_id,
                    "link",
                    link_id,
                    "node_connected_to_link",
                    direction,
                    topology_order=1,
                    weight=1.0,
                    confidence="high",
                    data_source="swmm_conduits",
                    evidence_ids=node_evidence.get("evidence_ids", []) + link_evidence_ids,
                )
                node_relation_ids.append(relation_id)
                link = link_by_id.get(link_id, {})
                connected_links.append(
                    {
                        "link_id": link_id,
                        "position": direction,
                        "relation_id": relation_id,
                        "from_node": link.get("from_node"),
                        "to_node": link.get("to_node"),
                        "max_fullness": _metric_value(records, "link", link_id, "max_fullness", 0.0),
                        "fullness_ge_0_8_duration_min": _metric_value(records, "link", link_id, "fullness_ge_0_8_duration", 0.0),
                        "fullness_ge_0_95_duration_min": _metric_value(records, "link", link_id, "fullness_ge_0_95_duration", 0.0),
                        "surcharge_duration_min": _metric_value(records, "link", link_id, "surcharge_duration", 0.0),
                        "max_flow_Ls": _metric_value(records, "link", link_id, "max_flow", 0.0),
                        "flow_direction_changes": _metric_value(records, "link", link_id, "flow_direction_changes", 0.0),
                        "evidence_ids": link_evidence_ids,
                    }
                )

        upstream_trace_items = []
        downstream_trace_items = []
        for link_id in upstream_links:
            path, stop_reason, link_relations = _trace_upstream(link_id, link_by_id, incoming_by_node, outfalls, int(max_trace_depth))
            relation_ids = []
            for order, (source_link, target_link) in enumerate(link_relations, start=1):
                relation_id = add_relation(
                    "link",
                    source_link,
                    "link",
                    target_link,
                    "link_upstream_of_link",
                    "upstream",
                    topology_order=order,
                    weight=1.0 / (order + 1),
                    confidence="high",
                    data_source="swmm_conduits",
                    evidence_ids=_metric_evidence_ids(records, "link", source_link, LINK_HYDRAULIC_METRICS)
                    + _metric_evidence_ids(records, "link", target_link, LINK_HYDRAULIC_METRICS),
                )
                if relation_id:
                    relation_ids.append(relation_id)
            upstream_trace_items.append({"start_link": link_id, "path": path, "stop_reason": stop_reason, "relation_ids": relation_ids})

        for link_id in downstream_links:
            path, stop_reason, link_relations = _trace_downstream(link_id, link_by_id, incoming_by_node, outgoing_by_node, outfalls, int(max_trace_depth))
            relation_ids = []
            for order, (source_link, target_link) in enumerate(link_relations, start=1):
                relation_id = add_relation(
                    "link",
                    source_link,
                    "link",
                    target_link,
                    "link_downstream_of_link",
                    "downstream",
                    topology_order=order,
                    weight=1.0 / (order + 1),
                    confidence="high",
                    data_source="swmm_conduits",
                    evidence_ids=_metric_evidence_ids(records, "link", source_link, LINK_HYDRAULIC_METRICS)
                    + _metric_evidence_ids(records, "link", target_link, LINK_HYDRAULIC_METRICS),
                )
                if relation_id:
                    relation_ids.append(relation_id)
            downstream_trace_items.append({"start_link": link_id, "path": path, "stop_reason": stop_reason, "relation_ids": relation_ids})

        cluster_summary = _surface_cluster_summary(cluster_smids, cell_by_smid, records)
        network_summary = _network_trace_summary(connected_links, upstream_trace_items, downstream_trace_items, records)
        surface_relation_ids = [cell["relation_id"] for cell in nearby_cells if cell.get("relation_id")] + cluster_relation_ids
        if surface_relation_ids:
            cluster_top_evidence_ids = [
                evidence_id
                for cell in cluster_summary.get("top_cells_by_depth", [])
                for evidence_id in cell.get("evidence_ids", [])
            ]
            surface_evidence_ids = sorted(
                set(
                    node_evidence.get("evidence_ids", [])
                    + [eid for cell in nearby_cells for eid in cell.get("evidence_ids", [])]
                    + cluster_top_evidence_ids
                )
            )
            relation_paths.append(
                {
                    "path_id": f"rp_{node_id}_surface",
                    "path_type": "surface_response",
                    "diagnostic_role": "connect_overflow_node_to_nearby_surface_ponding_cluster",
                    "summary": {
                        "anchor": f"node:{node_id}",
                        "nearby_cell_count": len(nearby_cells),
                        "cluster_cell_count": cluster_summary["cell_count"],
                        "cluster_max_depth_m": cluster_summary["max_depth_m"],
                        "cluster_max_duration_min": cluster_summary["max_duration_min"],
                        "relation_count": len(surface_relation_ids),
                        "evidence_count": len(surface_evidence_ids),
                    },
                    "objects": [f"node:{node_id}"] + [f"cell:{cell['cell_id']}" for cell in nearby_cells],
                    "relation_ids": surface_relation_ids,
                    "evidence_ids": surface_evidence_ids,
                }
            )
        if node_relation_ids:
            trace_relation_ids = [
                relation_id
                for trace in upstream_trace_items + downstream_trace_items
                for relation_id in trace.get("relation_ids", [])
            ]
            network_relation_ids = [rid for rid in node_relation_ids + trace_relation_ids if rid]
            traced_link_ids = list(
                dict.fromkeys(
                    [str(link["link_id"]) for link in connected_links]
                    + [str(link_id) for item in upstream_trace_items + downstream_trace_items for link_id in item.get("path", [])]
                )
            )
            network_evidence_ids = sorted(
                set(
                    node_evidence.get("evidence_ids", [])
                    + [eid for link in connected_links for eid in link.get("evidence_ids", [])]
                    + [
                        eid
                        for link_id in traced_link_ids
                        for eid in _metric_evidence_ids(records, "link", link_id, LINK_HYDRAULIC_METRICS)
                    ]
                )
            )
            relation_paths.append(
                {
                    "path_id": f"rp_{node_id}_network",
                    "path_type": "network_pressure",
                    "diagnostic_role": "connect_overflow_node_to_upstream_and_downstream_pipe_hydraulic_state",
                    "summary": {
                        "anchor": f"node:{node_id}",
                        "connected_link_count": network_summary["connected_link_count"],
                        "traced_link_count": len(traced_link_ids),
                        "upstream_stop_reasons": network_summary["upstream_stop_reasons"],
                        "downstream_stop_reasons": network_summary["downstream_stop_reasons"],
                        "upstream_trace_max_fullness": network_summary["upstream_trace_stats"]["max_fullness"],
                        "downstream_trace_max_fullness": network_summary["downstream_trace_stats"]["max_fullness"],
                        "relation_count": len(network_relation_ids),
                        "evidence_count": len(network_evidence_ids),
                    },
                    "objects": [f"node:{node_id}"] + [f"link:{link_id}" for link_id in traced_link_ids],
                    "relation_ids": network_relation_ids,
                    "evidence_ids": network_evidence_ids,
                }
            )

        cluster_depths = [_metric_value(records, "cell", smid, "max_depth", 0.0) for smid in cluster_smids]
        cluster_durations = [_metric_value(records, "cell", smid, "ponding_duration", 0.0) for smid in cluster_smids]
        summary_block = _diagnostic_summary(node_id, rainfall_context, node_evidence, cluster_summary, network_summary)
        package = {
            "package_id": f"pkg_node_{node_id}",
            "diagnostic_summary": summary_block,
            "anchor": {
                "type": "node",
                "id": node_id,
                "reason": "overflow_node",
                "claim_id": anchor.get("claim_id"),
                "severity": anchor.get("severity", ""),
                "evidence_ids": node_evidence.get("evidence_ids", []),
            },
            "rainfall_context": rainfall_context,
            "node_evidence": node_evidence,
            "surface_context": {
                "nearby_cells": nearby_cells,
                "ponding_cluster": {
                    "neighbor_mode": neighbor_mode,
                    "cell_count": len(cluster_smids),
                    "max_depth_m": max(cluster_depths) if cluster_depths else 0.0,
                    "max_duration_min": max(cluster_durations) if cluster_durations else 0.0,
                    "summary": cluster_summary,
                    "cell_ids": cluster_smids[:max_cluster_cells],
                    "relation_ids": cluster_relation_ids,
                },
            },
            "network_context": {
                "summary": network_summary,
                "connected_links": connected_links,
                "upstream_trace": upstream_trace_items,
                "downstream_trace": downstream_trace_items,
            },
            "relation_paths": relation_paths,
            "diagnosis_ready_signals": {
                "has_surface_ponding_nearby": any(float(cell.get("max_depth_m", 0.0)) >= PONDING_DEPTH_THRESHOLD_M for cell in nearby_cells),
                "has_downstream_high_fullness": any(
                    link["position"] == "downstream" and float(link.get("max_fullness", 0.0)) >= HIGH_FULLNESS_THRESHOLD
                    for link in connected_links
                ),
                "has_upstream_high_load": any(
                    link["position"] == "upstream" and float(link.get("max_fullness", 0.0)) >= HIGH_FULLNESS_THRESHOLD
                    for link in connected_links
                ),
                "has_flow_direction_instability": any(
                    float(link.get("flow_direction_changes", 0.0)) >= FLOW_DIRECTION_CHANGE_THRESHOLD for link in connected_links
                ),
                "has_repeated_overflow": _metric_value(records, "node", node_id, "overflow_event_count", 0.0) >= REPEATED_OVERFLOW_EVENT_THRESHOLD,
                "has_short_duration_heavy_rainfall": bool(rainfall_context.get("short_duration_heavy_rainfall")),
            },
        }
        packages.append(package)

    relation_df = pd.DataFrame(
        relation_rows,
        columns=[
            "relation_id",
            "run_id",
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "relation_type",
            "direction",
            "distance_m",
            "topology_order",
            "weight",
            "confidence",
            "data_source",
            "evidence_ids",
        ],
    )
    artifacts.evidence_relation_table.parent.mkdir(parents=True, exist_ok=True)
    relation_df.to_csv(artifacts.evidence_relation_table, index=False, encoding="utf-8")
    package_payload = {
        "schema_name": EVIDENCE_GRAPH_SCHEMA_NAME,
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "run_id": run_root.name,
        "model_name": run_root.parents[1].name,
        "anchor_strategy": "overflow_node_centered",
        "neighbor_mode": neighbor_mode,
        "max_trace_depth": int(max_trace_depth),
        "package_count": len(packages),
        "packages": packages,
    }
    artifacts.overflow_node_evidence_packages.write_text(json.dumps(package_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_payload = {
        "schema_name": EVIDENCE_GRAPH_SCHEMA_NAME,
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "run_id": run_root.name,
        "model_name": run_root.parents[1].name,
        "relation_table": str(artifacts.evidence_relation_table),
        "overflow_node_evidence_packages": str(artifacts.overflow_node_evidence_packages),
        "relation_count": int(len(relation_df)),
        "package_count": len(packages),
        "anchor_nodes": [package["anchor"]["id"] for package in packages],
        "relation_types": relation_df.groupby("relation_type").size().to_dict() if not relation_df.empty else {},
    }
    return summary_payload
