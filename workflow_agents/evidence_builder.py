"""Deterministic EvidenceBuilderAgent core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .schemas import EVIDENCE_SCHEMA_NAME, WORKFLOW_SCHEMA_VERSION, artifacts_for_run
from .state import resolve_run_root


POSITIVE_FLOW_LS = 1e-9
POSITIVE_DEPTH_M = 0.005


def _load_summary(run_root: Path) -> dict[str, Any]:
    path = run_root / "summary.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing run summary: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_tsv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing source file: {path}")
    df = pd.read_csv(path, sep="\t")
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")
    return df


def _time_columns(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), errors="coerce")


def _infer_step_minutes(times: pd.Series) -> float:
    unique_times = sorted(pd.Timestamp(value) for value in times.dropna().unique())
    if len(unique_times) < 2:
        return 0.0
    deltas = [
        (unique_times[idx + 1] - unique_times[idx]).total_seconds() / 60.0
        for idx in range(len(unique_times) - 1)
        if unique_times[idx + 1] > unique_times[idx]
    ]
    return min(deltas) if deltas else 0.0


def _base_row(summary: dict[str, Any], run_root: Path, source_file: Path, object_type: str, object_id: str, metric_name: str) -> dict[str, Any]:
    return {
        "run_id": summary.get("run_id", run_root.name),
        "event_name": summary.get("event_name", ""),
        "scenario_name": summary.get("scenario_name", ""),
        "source_model": summary.get("model_name", ""),
        "source_file": str(source_file.relative_to(run_root)).replace("\\", "/"),
        "object_type": object_type,
        "object_id": str(object_id),
        "metric_name": metric_name,
    }


def _rank_metric(rows: list[dict[str, Any]], metric_name: str, descending: bool = True) -> None:
    subset = [row for row in rows if row["metric_name"] == metric_name]
    subset.sort(key=lambda row: float(row["value"]), reverse=descending)
    for rank, row in enumerate(subset, start=1):
        row["rank"] = rank


def build_evidence_for_run(model_name: str, run_id: str) -> dict[str, Any]:
    """Build evidence_table.csv and evidence_summary.json for one completed run."""
    run_root = resolve_run_root(model_name, run_id)
    summary = _load_summary(run_root)
    artifacts = artifacts_for_run(run_root)
    evidence_dir = run_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []

    flooding = _read_tsv(artifacts.swmm_node_flooding, {"node_id", "date", "time", "flow_Ls"})
    flooding["DateTime"] = _time_columns(flooding)
    flooding["flow_Ls"] = pd.to_numeric(flooding["flow_Ls"], errors="coerce").fillna(0.0)
    step_minutes = _infer_step_minutes(flooding["DateTime"])
    step_seconds = step_minutes * 60.0
    for node_id, group in flooding.groupby("node_id"):
        positive = group[group["flow_Ls"] > POSITIVE_FLOW_LS]
        total_volume_m3 = float(group["flow_Ls"].sum() / 1000.0 * step_seconds) if step_seconds else 0.0
        max_flow = float(group["flow_Ls"].max())
        duration = float(len(positive) * step_minutes)
        first_time = positive["DateTime"].min() if not positive.empty else group["DateTime"].min()
        last_time = positive["DateTime"].max() if not positive.empty else group["DateTime"].max()
        for metric, value, unit, threshold in [
            ("total_flooding_volume", total_volume_m3, "m3", 0.0),
            ("max_flooding_flow", max_flow, "L/s", 0.0),
            ("flooding_duration", duration, "min", 0.0),
        ]:
            row = _base_row(summary, run_root, artifacts.swmm_node_flooding, "node", node_id, metric)
            row.update(
                {
                    "value": value,
                    "unit": unit,
                    "time_start": "" if pd.isna(first_time) else pd.Timestamp(first_time).isoformat(sep=" "),
                    "time_end": "" if pd.isna(last_time) else pd.Timestamp(last_time).isoformat(sep=" "),
                    "duration_minutes": duration,
                    "rank": "",
                    "threshold": threshold,
                    "exceedance_flag": bool(value > threshold),
                }
            )
            rows.append(row)

    nodes = _read_tsv(artifacts.swmm_nodes, {"node_id", "depth_m", "flooding_Ls", "date", "time"})
    nodes["DateTime"] = _time_columns(nodes)
    nodes["depth_m"] = pd.to_numeric(nodes["depth_m"], errors="coerce").fillna(0.0)
    for node_id, group in nodes.groupby("node_id"):
        idx = group["depth_m"].idxmax()
        max_depth = float(group.loc[idx, "depth_m"])
        row = _base_row(summary, run_root, artifacts.swmm_nodes, "node", node_id, "max_node_depth")
        row.update(
            {
                "value": max_depth,
                "unit": "m",
                "time_start": pd.Timestamp(group.loc[idx, "DateTime"]).isoformat(sep=" "),
                "time_end": pd.Timestamp(group.loc[idx, "DateTime"]).isoformat(sep=" "),
                "duration_minutes": 0.0,
                "rank": "",
                "threshold": 0.0,
                "exceedance_flag": bool(max_depth > 0.0),
            }
        )
        rows.append(row)

    links = _read_tsv(artifacts.swmm_links, {"link_id", "flow_Ls", "depth_m", "date", "time"})
    links["DateTime"] = _time_columns(links)
    links["flow_Ls"] = pd.to_numeric(links["flow_Ls"], errors="coerce").fillna(0.0).abs()
    links["depth_m"] = pd.to_numeric(links["depth_m"], errors="coerce").fillna(0.0)
    for link_id, group in links.groupby("link_id"):
        for metric, col, unit in [("max_flow", "flow_Ls", "L/s"), ("max_link_depth", "depth_m", "m")]:
            idx = group[col].idxmax()
            value = float(group.loc[idx, col])
            row = _base_row(summary, run_root, artifacts.swmm_links, "link", link_id, metric)
            row.update(
                {
                    "value": value,
                    "unit": unit,
                    "time_start": pd.Timestamp(group.loc[idx, "DateTime"]).isoformat(sep=" "),
                    "time_end": pd.Timestamp(group.loc[idx, "DateTime"]).isoformat(sep=" "),
                    "duration_minutes": 0.0,
                    "rank": "",
                    "threshold": 0.0,
                    "exceedance_flag": bool(value > 0.0),
                }
            )
            rows.append(row)

    surface = _read_tsv(artifacts.ca2d_surface_depth, {"Smid", "Date", "Time", "Depth"})
    surface = surface.rename(columns={"Date": "date", "Time": "time", "Depth": "Depth"})
    surface["DateTime"] = _time_columns(surface)
    surface["Depth"] = pd.to_numeric(surface["Depth"], errors="coerce").fillna(0.0)
    surface_step = _infer_step_minutes(surface["DateTime"])
    for smid, group in surface.groupby("Smid"):
        positive = group[group["Depth"] > POSITIVE_DEPTH_M]
        idx = group["Depth"].idxmax()
        max_depth = float(group.loc[idx, "Depth"])
        duration = float(len(positive) * surface_step)
        first_time = positive["DateTime"].min() if not positive.empty else group["DateTime"].min()
        last_time = positive["DateTime"].max() if not positive.empty else group["DateTime"].max()
        for metric, value, unit, threshold in [
            ("max_depth", max_depth, "m", 0.3),
            ("ponding_duration", duration, "min", 60.0),
        ]:
            row = _base_row(summary, run_root, artifacts.ca2d_surface_depth, "cell", smid, metric)
            row.update(
                {
                    "value": value,
                    "unit": unit,
                    "time_start": "" if pd.isna(first_time) else pd.Timestamp(first_time).isoformat(sep=" "),
                    "time_end": "" if pd.isna(last_time) else pd.Timestamp(last_time).isoformat(sep=" "),
                    "duration_minutes": duration,
                    "rank": "",
                    "threshold": threshold,
                    "exceedance_flag": bool(value >= threshold),
                }
            )
            rows.append(row)

    for metric in [
        "total_flooding_volume",
        "max_flooding_flow",
        "flooding_duration",
        "max_node_depth",
        "max_flow",
        "max_link_depth",
        "max_depth",
        "ponding_duration",
    ]:
        _rank_metric(rows, metric)

    for idx, row in enumerate(rows, start=1):
        prefix = {
            "node": "N",
            "link": "L",
            "cell": "C",
        }.get(row["object_type"], "E")
        row["evidence_id"] = f"E_{prefix}_{idx:06d}"

    columns = [
        "evidence_id",
        "run_id",
        "event_name",
        "scenario_name",
        "source_model",
        "source_file",
        "object_type",
        "object_id",
        "metric_name",
        "value",
        "unit",
        "time_start",
        "time_end",
        "duration_minutes",
        "rank",
        "threshold",
        "exceedance_flag",
    ]
    evidence_df = pd.DataFrame(rows, columns=columns)
    evidence_df.to_csv(artifacts.evidence_table, index=False, encoding="utf-8")

    summary_payload = {
        "schema_name": EVIDENCE_SCHEMA_NAME,
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "run_id": summary.get("run_id", run_root.name),
        "model_name": summary.get("model_name", run_root.parents[1].name),
        "event_name": summary.get("event_name", ""),
        "scenario_name": summary.get("scenario_name", ""),
        "evidence_table": str(artifacts.evidence_table),
        "evidence_count": int(len(evidence_df)),
        "metrics": evidence_df.groupby("metric_name").size().to_dict(),
        "source_files": sorted(evidence_df["source_file"].unique().tolist()),
    }
    artifacts.evidence_summary.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_payload
