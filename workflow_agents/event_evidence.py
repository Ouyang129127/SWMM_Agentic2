"""Task-scoped, read-only extraction of direct inflow evidence from saved SWMM output.

No simulation, diagnosis, or run-level workflow state transition is performed.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .state import resolve_run_root

SCHEMA_VERSION = "1.0"
POSITIVE_FLOW_LS = 1e-9  # Same segmentation tolerance as the existing evidence builder.
LINK_SECTIONS = {"CONDUITS", "PUMPS", "ORIFICES", "WEIRS", "OUTLETS"}


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _validate_series(times, values):
    if len(times) < 2 or len(values) != len(times):
        raise ValueError("At least two aligned samples are required")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("Timestamps must be strictly increasing without duplicates")
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("Missing or non-finite values must not be replaced by zero")


def positive_volume(times, values) -> float:
    """Integrate the positive part of piecewise-linear signed flow, in L/s -> m3.

    Insert exact zero crossings: clipping only sample endpoints overcounts reversal.
    """
    _validate_series(times, values)
    volume = 0.0
    for t0, t1, a, b in zip(times, times[1:], values, values[1:]):
        seconds = (t1 - t0).total_seconds()
        if a >= 0 and b >= 0:
            volume += seconds * (a + b) / 2
        elif a > 0:
            volume += seconds * a * a / (2 * (a - b))
        elif b > 0:
            volume += seconds * b * b / (2 * (b - a))
    return volume / 1000


def segment_events(times, floods, node_id):
    """Preserve sampled positive runs; bracket each with available adjacent samples.

    Brackets define an explicit integration window, not a routing-step onset estimate.
    """
    _validate_series(times, floods)
    events = []
    first = None
    for i in range(len(times) + 1):
        positive = i < len(times) and floods[i] > POSITIVE_FLOW_LS
        if positive and first is None:
            first = i
        if not positive and first is not None:
            last = i - 1
            left, right = max(0, first - 1), min(len(times) - 1, last + 1)
            peak = max(range(first, last + 1), key=lambda index: floods[index])
            events.append({
                "event_id": f"{node_id}:E{len(events) + 1:03d}",
                "first_positive_time": times[first].isoformat(sep=" "),
                "last_positive_time": times[last].isoformat(sep=" "),
                "peak_time": times[peak].isoformat(sep=" "),
                "peak_flooding_Ls": floods[peak],
                "window": {"start": times[left].isoformat(sep=" "), "end": times[right].isoformat(sep=" ")},
                "left_censored": first == 0, "right_censored": last == len(times) - 1,
                "flooding_volume_m3": positive_volume(times[left:right + 1], floods[left:right + 1]),
            })
            first = None
    return events


def connected_links(inp_path: Path, node_id: str):
    links = []
    section = ""
    seen = set()
    for raw in inp_path.read_text(encoding="utf-8-sig", errors="strict").splitlines():
        line = raw.split(";", 1)[0].strip()
        if line.startswith("["):
            section = line.strip("[]").upper()
        elif line and section in LINK_SECTIONS:
            parts = line.split()
            if len(parts) < 3:
                raise ValueError(f"Malformed link in {section}")
            link_id, start, end = parts[:3]
            if node_id not in (start, end):
                continue
            if link_id in seen or start == end:
                raise ValueError(f"Duplicate or self-loop link: {link_id}")
            seen.add(link_id)
            links.append({"source_id": link_id, "source_type": "link", "link_type": section,
                          "from_node": start, "to_node": end,
                          "towards_node_multiplier": 1 if end == node_id else -1})
    return links


def load_node_data(run_root: Path, node_id: str):
    """Read the existing binary output only. Never call Simulation or the exporter."""
    from pyswmm import Output
    from swmm.toolkit.shared_enum import NodeAttribute, LinkAttribute

    paths = {"binary_output": run_root / "swmm/model.out", "model_input": run_root / "swmm/model_with_event.inp"}
    fingerprints = {key: file_hash(path) for key, path in paths.items()}
    inventory = connected_links(paths["model_input"], node_id)
    with Output(str(paths["binary_output"])) as output:
        if output.units["flow"] != "LPS":
            raise ValueError("Event evidence currently requires native LPS output; no implicit unit conversion")
        if node_id not in output.nodes:
            raise ValueError(f"Unknown node: {node_id}")
        times = list(output.times)

        def aligned(series):
            if set(series) != set(times):
                raise ValueError("Output series timestamps do not align")
            values = [float(series[t]) for t in times]
            _validate_series(times, values)
            return values

        floods = aligned(output.node_series(node_id, NodeAttribute.FLOODING_LOSSES))
        total = aligned(output.node_series(node_id, NodeAttribute.TOTAL_INFLOW))
        lateral = aligned(output.node_series(node_id, NodeAttribute.LATERAL_INFLOW))
        head = aligned(output.node_series(node_id, NodeAttribute.HYDRAULIC_HEAD))
        sources = []
        for link in inventory:
            values = aligned(output.link_series(link["source_id"], LinkAttribute.FLOW_RATE))
            sources.append({**link, "signed_towards_node_Ls": [v * link["towards_node_multiplier"] for v in values]})
        sources.append({"source_id": f"{node_id}:lateral", "source_type": "aggregate_lateral_inflow",
                        "signed_towards_node_Ls": lateral})
    if fingerprints != {key: file_hash(path) for key, path in paths.items()}:
        raise ValueError("Input artifacts changed during extraction")
    provenance = {key: {"path": path.relative_to(run_root).as_posix(), "sha256": fingerprints[key]}
                  for key, path in paths.items()}
    return {"times": times, "floods": floods, "total_inflow": total, "head": head,
            "sources": sources, "provenance": provenance}


def event_catalog(model_name: str, run_id: str, node_id: str):
    root = resolve_run_root(model_name, run_id)
    data = load_node_data(root, node_id)
    return {"schema_version": SCHEMA_VERSION, "model_name": root.parents[1].name,
            "run_id": root.name, "node_id": node_id, "provenance": data["provenance"],
            "events": segment_events(data["times"], data["floods"], node_id)}


def build_package(context, data, event):
    times = data["times"]
    start, end = (datetime.fromisoformat(event["window"][key]) for key in ("start", "end"))
    indices = [i for i, time in enumerate(times) if start <= time <= end]
    window_times = [times[i] for i in indices]
    peak = times.index(datetime.fromisoformat(event["peak_time"]))
    rows, inventory = [], []
    volumes = [positive_volume(window_times, [source["signed_towards_node_Ls"][i] for i in indices])
               for source in data["sources"]]
    volume_denominator = sum(volumes)
    peak_denominator = sum(max(0, s["signed_towards_node_Ls"][peak]) for s in data["sources"])
    for source, volume in zip(data["sources"], volumes):
        values = source["signed_towards_node_Ls"]
        inventory.append({key: value for key, value in source.items() if key != "signed_towards_node_Ls"})
        metrics = {
            "positive_entering_volume": (volume, "m3", event["window"]),
            "outgoing_volume": (positive_volume(window_times, [-values[i] for i in indices]), "m3", event["window"]),
            "event_volume_share": (volume / volume_denominator if volume_denominator else None, "ratio", event["window"]),
            "peak_entering_flow": (max(0, values[peak]), "L/s", {"at": event["peak_time"]}),
            "peak_flow_share": (max(0, values[peak]) / peak_denominator if peak_denominator else None, "ratio", {"at": event["peak_time"]}),
        }
        for metric, (value, unit, window) in metrics.items():
            rows.append({"evidence_id": f"{context['task_id']}:E{len(rows) + 1:03d}",
                         "source_id": source["source_id"], "source_type": source["source_type"],
                         "metric": metric, "value": value, "unit": unit, "window": window,
                         "source_file": data["provenance"]["binary_output"]["path"],
                         "method": "direct_inflow_piecewise_linear_v1"})
    series = []
    for i in indices:
        signed = {s["source_id"]: s["signed_towards_node_Ls"][i] for s in data["sources"]}
        positive_sum = sum(max(0, value) for value in signed.values())
        series.append({"time": times[i].isoformat(sep=" "), "signed_towards_node_Ls": signed,
                       "positive_source_sum_Ls": positive_sum, "swmm_total_inflow_Ls": data["total_inflow"][i],
                       "source_sum_minus_total_Ls": positive_sum - data["total_inflow"][i],
                       "flooding_Ls": data["floods"][i], "head_m": data["head"][i]})
    package = {"schema_name": "node_event_direct_inflow_evidence", "schema_version": SCHEMA_VERSION,
               "package_id": f"{context['task_id']}:direct_inflow", "task_id": context["task_id"],
               "model_name": context["model_name"], "run_id": context["run_id"], "node_id": context["node_id"],
               "event_id": event["event_id"], "task_context": context, "event": event,
               "source_inventory": inventory, "evidence_rows": rows, "series": series,
               "provenance": data["provenance"],
               "calculation_context": {
                   "flow_unit": "L/s", "volume_unit": "m3", "direction": "positive towards target node",
                   "integration": "piecewise linear signed flow with exact zero-crossing split",
                   "event_window": "adjacent available samples bracketing each positive flooding segment",
                   "segmentation_threshold_Ls": POSITIVE_FLOW_LS,
                   "volume_denominator_m3": volume_denominator, "peak_denominator_Ls": peak_denominator,
                   "zero_denominator": "null share", "total_inflow_role": "reconciliation only, not an added source",
                   "share_scope": "composition of covered direct entering paths, not flood attribution",
                   "lateral_scope": "aggregate lateral inflow, not separated subcatchment origins"},
               "availability": {"connected_link_series": "available", "aggregate_lateral_inflow": "available",
                                "subcatchment_origin_shares": "not_built", "causal_contributions": "not_built"},
               "reconciliation": {"max_abs_source_sum_minus_total_Ls": max(abs(row["source_sum_minus_total_Ls"]) for row in series),
                                  "status": "recorded_not_a_mass_balance_verdict"}}
    package["version"] = hashlib.sha256(json.dumps(package, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return package


def prepare_event_evidence(model_name: str, run_id: str, node_id: str, event_id: str,
                           original_question: str, confirmed: bool = False):
    """Create a new immutable task; existing run artifacts and state remain untouched."""
    if not confirmed:
        raise ValueError("Explicit confirmation of event evidence scope is required")
    if not original_question.strip() or not node_id or not event_id:
        raise ValueError("Original question, node_id and explicit event_id are required")
    root = resolve_run_root(model_name, run_id)
    data = load_node_data(root, node_id)
    events = segment_events(data["times"], data["floods"], node_id)
    event = next((e for e in events if e["event_id"] == event_id), None)
    if event is None:
        raise ValueError(f"Select an event from the catalog: {[e['event_id'] for e in events]}")
    task_id = "inflow_" + uuid4().hex
    context = {"schema_name": "diagnosis_task_context", "schema_version": SCHEMA_VERSION,
               "task_id": task_id, "created_at": datetime.now().astimezone().isoformat(),
               "original_question": original_question, "interpreted_intent": "direct_inflow_composition",
               "model_name": root.parents[1].name, "run_id": root.name, "node_id": node_id,
               "event_id": event_id, "event_window": event["window"], "analysis_window": event["window"],
               "question_scope": "five_questions_1_and_2_background", "primary_metric": "event_volume_share",
               "supplementary_metric": "peak_flow_share",
               "confirmation": {"confirmed": True, "scope": "build_selected_event_direct_inflow_evidence_only"},
               "next_stage": "llm_diagnosis_not_implemented", "state": "EVENT_EVIDENCE_READY"}
    package = build_package(context, data, event)
    task_root = root / "diagnostic_tasks" / task_id
    task_root.mkdir(parents=True, exist_ok=False)
    for name, value in (("context.json", context), ("event_catalog.json", events), ("evidence_package.json", package)):
        with (task_root / name).open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return {"ok": True, "task_id": task_id, "state": context["state"],
            "context_file": str(task_root / "context.json"), "evidence_package_file": str(task_root / "evidence_package.json"),
            "event_id": event_id, "evidence_count": len(package["evidence_rows"]),
            "version": package["version"], "next_stage": context["next_stage"]}
