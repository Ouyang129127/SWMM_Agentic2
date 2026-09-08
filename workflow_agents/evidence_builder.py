"""Deterministic EvidenceBuilderAgent core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .rainfall_context import build_rainfall_context, write_rainfall_context
from .schemas import EVIDENCE_SCHEMA_NAME, WORKFLOW_SCHEMA_VERSION, artifacts_for_run
from .state import resolve_run_root


POSITIVE_FLOW_LS = 1e-9
POSITIVE_DEPTH_M = 0.005
FULLNESS_HIGH_RATIO = 0.80
FULLNESS_NEAR_FULL_RATIO = 0.95
FULLNESS_SURCHARGE_RATIO = 1.00
FLOW_DIRECTION_CHANGE_THRESHOLD = 3
FLOW_DIRECTION_EPS_LS = 1e-6
REPEATED_OVERFLOW_EVENT_THRESHOLD = 2


def _load_summary(run_root: Path) -> dict[str, Any]:
    path = run_root / "summary.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing run summary: {path}")
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
    candidate = run_root / "rainfall_event.txt"
    return candidate


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


def _flow_direction_changes(flow: pd.Series) -> int:
    signs = []
    for value in flow:
        if value > FLOW_DIRECTION_EPS_LS:
            sign = 1
        elif value < -FLOW_DIRECTION_EPS_LS:
            sign = -1
        else:
            continue
        if not signs or signs[-1] != sign:
            signs.append(sign)
    if len(signs) < 2:
        return 0
    return len(signs) - 1


def _positive_event_count(values: pd.Series, threshold: float) -> int:
    """Count positive-event segments in a time-ordered numeric series."""
    event_count = 0
    in_event = False
    for value in values:
        positive = value > threshold
        if positive and not in_event:
            event_count += 1
        in_event = positive
    return event_count


def _parse_link_full_depths(run_root: Path) -> dict[str, float]:
    """Read SWMM [XSECTIONS] Geom1 as the full-depth reference for each link."""
    candidates = [
        run_root / "swmm" / "model_with_event.inp",
        run_root.parents[1] / "swmm" / "scenarios" / "baseline" / "Model.inp",
        run_root.parents[1] / "swmm" / "scenarios" / "baseline" / "model.inp",
        run_root.parents[1] / "swmm" / "Model.inp",
        run_root.parents[1] / "swmm" / "model.inp",
    ]
    inp_path = next((path for path in candidates if path.exists()), None)
    if inp_path is None:
        return {}

    full_depths: dict[str, float] = {}
    in_xsections = False
    for raw_line in inp_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("["):
            in_xsections = line.upper() == "[XSECTIONS]"
            continue
        if not in_xsections or line.startswith(";"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            full_depth = float(parts[2])
        except ValueError:
            continue
        if full_depth > 0:
            full_depths[str(parts[0])] = full_depth
    return full_depths


def build_evidence_for_run(model_name: str, run_id: str) -> dict[str, Any]:
    """Build evidence_table.csv and evidence_summary.json for one completed run."""
    run_root = resolve_run_root(model_name, run_id)
    summary = _load_summary(run_root)
    artifacts = artifacts_for_run(run_root)
    evidence_dir = run_root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    rainfall_context = build_rainfall_context(
        _resolve_rainfall_file(summary, run_root),
        event_name=str(summary.get("event_name", "")),
        run_id=str(summary.get("run_id", run_root.name)),
        model_name=str(summary.get("model_name", run_root.parents[1].name)),
        scenario_name=str(summary.get("scenario_name", "")),
    )
    write_rainfall_context(artifacts.rainfall_context, rainfall_context)

    rows: list[dict[str, Any]] = []
    overflow_event_rows: list[dict[str, Any]] = []

    flooding = _read_tsv(artifacts.swmm_node_flooding, {"node_id", "date", "time", "flow_Ls"})
    flooding["DateTime"] = _time_columns(flooding)
    flooding["flow_Ls"] = pd.to_numeric(flooding["flow_Ls"], errors="coerce").fillna(0.0)
    step_minutes = _infer_step_minutes(flooding["DateTime"])
    step_seconds = step_minutes * 60.0
    for node_id, group in flooding.groupby("node_id"):
        group = group.sort_values("DateTime")
        positive = group[group["flow_Ls"] > POSITIVE_FLOW_LS]
        total_volume_m3 = float(group["flow_Ls"].sum() / 1000.0 * step_seconds) if step_seconds else 0.0
        max_flow = float(group["flow_Ls"].max())
        duration = float(len(positive) * step_minutes)
        overflow_event_count = _positive_event_count(group["flow_Ls"], POSITIVE_FLOW_LS)
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
        row = _base_row(summary, run_root, artifacts.swmm_node_flooding, "node", node_id, "overflow_event_count")
        row.update(
            {
                "value": float(overflow_event_count),
                "unit": "count",
                "time_start": "" if pd.isna(first_time) else pd.Timestamp(first_time).isoformat(sep=" "),
                "time_end": "" if pd.isna(last_time) else pd.Timestamp(last_time).isoformat(sep=" "),
                "duration_minutes": duration,
                "rank": "",
                "threshold": REPEATED_OVERFLOW_EVENT_THRESHOLD,
                "exceedance_flag": bool(overflow_event_count >= REPEATED_OVERFLOW_EVENT_THRESHOLD),
            }
        )
        overflow_event_rows.append(row)

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
    link_full_depths = _parse_link_full_depths(run_root)
    links["DateTime"] = _time_columns(links)
    link_step_minutes = _infer_step_minutes(links["DateTime"])
    links["signed_flow_Ls"] = pd.to_numeric(links["flow_Ls"], errors="coerce").fillna(0.0)
    links["flow_Ls"] = links["signed_flow_Ls"].abs()
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
        direction_changes = _flow_direction_changes(group.sort_values("DateTime")["signed_flow_Ls"])
        row = _base_row(summary, run_root, artifacts.swmm_links, "link", link_id, "flow_direction_changes")
        row.update(
            {
                "value": float(direction_changes),
                "unit": "count",
                "time_start": pd.Timestamp(group["DateTime"].min()).isoformat(sep=" "),
                "time_end": pd.Timestamp(group["DateTime"].max()).isoformat(sep=" "),
                "duration_minutes": 0.0,
                "rank": "",
                "threshold": FLOW_DIRECTION_CHANGE_THRESHOLD,
                "exceedance_flag": bool(direction_changes >= FLOW_DIRECTION_CHANGE_THRESHOLD),
            }
        )
        rows.append(row)
        full_depth = link_full_depths.get(str(link_id))
        if full_depth:
            fullness = (group["depth_m"] / full_depth).clip(lower=0.0)
            idx = fullness.idxmax()
            max_fullness = float(fullness.loc[idx])
            row = _base_row(summary, run_root, artifacts.swmm_links, "link", link_id, "max_fullness")
            row.update(
                {
                    "value": max_fullness,
                    "unit": "ratio",
                    "time_start": pd.Timestamp(group.loc[idx, "DateTime"]).isoformat(sep=" "),
                    "time_end": pd.Timestamp(group.loc[idx, "DateTime"]).isoformat(sep=" "),
                    "duration_minutes": 0.0,
                    "rank": "",
                    "threshold": FULLNESS_HIGH_RATIO,
                    "exceedance_flag": bool(max_fullness >= FULLNESS_HIGH_RATIO),
                }
            )
            rows.append(row)
            for metric, threshold in [
                ("fullness_ge_0_8_duration", FULLNESS_HIGH_RATIO),
                ("fullness_ge_0_95_duration", FULLNESS_NEAR_FULL_RATIO),
                ("surcharge_duration", FULLNESS_SURCHARGE_RATIO),
            ]:
                exceedance = group[fullness >= threshold] if metric != "surcharge_duration" else group[fullness > threshold]
                duration = float(len(exceedance) * link_step_minutes)
                first_time = exceedance["DateTime"].min() if not exceedance.empty else group["DateTime"].min()
                last_time = exceedance["DateTime"].max() if not exceedance.empty else group["DateTime"].max()
                duration_row = _base_row(summary, run_root, artifacts.swmm_links, "link", link_id, metric)
                duration_row.update(
                    {
                        "value": duration,
                        "unit": "min",
                        "time_start": "" if pd.isna(first_time) else pd.Timestamp(first_time).isoformat(sep=" "),
                        "time_end": "" if pd.isna(last_time) else pd.Timestamp(last_time).isoformat(sep=" "),
                        "duration_minutes": duration,
                        "rank": "",
                        "threshold": threshold,
                        "exceedance_flag": bool(duration > 0.0),
                    }
                )
                rows.append(duration_row)

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

    rows.extend(overflow_event_rows)

    for metric in [
        "total_flooding_volume",
        "max_flooding_flow",
        "flooding_duration",
        "overflow_event_count",
        "max_node_depth",
        "max_flow",
        "max_link_depth",
        "max_fullness",
        "fullness_ge_0_8_duration",
        "fullness_ge_0_95_duration",
        "surcharge_duration",
        "flow_direction_changes",
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
        "rainfall_context": rainfall_context,
        "rainfall_context_file": str(artifacts.rainfall_context),
    }
    artifacts.evidence_summary.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_payload
