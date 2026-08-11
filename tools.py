import json
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from typing_extensions import Annotated

from ca2d import check_static_model, create_demo_static_model, run_ca2d_simulation
from workflow_agents import (
    build_evidence_for_run as _build_evidence_for_run,
    diagnose_run_from_evidence as _diagnose_run_from_evidence,
    run_workflow_stage as _run_workflow_stage,
    verify_diagnosis_claims as _verify_diagnosis_claims,
)

APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_DIR = APP_ROOT
MODELS_DIR = APP_ROOT / "models"
PROJECT_SCHEMA_NAME = "SWMM-2D project layout"
PROJECT_SCHEMA_VERSION = "models-readme-2026-07-18"


def _resolve_workspace_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    candidate = WORKSPACE_DIR / candidate
    return candidate


def _resolve_model_root(model_name: str) -> Path:
    if not model_name:
        model_names = sorted(path.name for path in MODELS_DIR.iterdir() if path.is_dir()) if MODELS_DIR.exists() else []
        if len(model_names) == 1:
            model_name = model_names[0]
        elif not model_names:
            return MODELS_DIR / "__no_models_found__"
        else:
            return MODELS_DIR / "__multiple_models_found__"
    return MODELS_DIR / model_name


def _model_selection_error(model_root: Path) -> Optional[str]:
    if model_root.name == "__no_models_found__":
        return "No SWMM-2D model projects found under the project-root models/ directory."
    if model_root.name == "__multiple_models_found__":
        model_names = sorted(path.name for path in MODELS_DIR.iterdir() if path.is_dir())
        return f"Multiple model projects found. Please specify model_name. Available models: {model_names}"
    return None


def _resolve_model_input(model_root: Path, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    project_candidate = model_root / candidate
    if project_candidate.exists():
        return project_candidate
    return WORKSPACE_DIR / candidate


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "run"


def _read_lines(inp_path: Path) -> List[str]:
    with open(inp_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def _write_lines(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)


def _section_name(line: str):
    match = re.match(r"^\s*\[([A-Za-z0-9_]+)\]\s*$", line)
    return match.group(1).upper() if match else None


def parse_sections(lines: List[str]) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current = None
    for line in lines:
        name = _section_name(line)
        if name:
            current = name
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return sections


def _data_rows(section_lines: List[str]) -> List[List[str]]:
    rows = []
    for line in section_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        rows.append(stripped.split())
    return rows


def _first_col_ids(sections: Dict[str, List[str]], section: str) -> List[str]:
    return [row[0] for row in _data_rows(sections.get(section, [])) if row]


def _find_section_bounds(lines: List[str], section: str):
    target = section.upper()
    start = None
    end = None
    for idx, line in enumerate(lines):
        name = _section_name(line)
        if name == target:
            start = idx
            continue
        if start is not None and name is not None:
            end = idx
            break
    if start is None:
        return None
    if end is None:
        end = len(lines)
    return start, end


def _insert_or_replace_section(lines: List[str], section: str, content_lines: List[str]) -> List[str]:
    bounds = _find_section_bounds(lines, section)
    block = [f"\n[{section.upper()}]\n"] + content_lines
    if content_lines and not content_lines[-1].endswith("\n"):
        block[-1] += "\n"
    if bounds is None:
        return lines + block
    start, end = bounds
    return lines[: start + 1] + content_lines + lines[end:]


def _parse_datetime_value_file(path: Path) -> List[Tuple[datetime, float]]:
    entries: List[Tuple[datetime, float]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.startswith(";"):
            continue
        if "," in line:
            left, right = line.rsplit(",", 1)
        else:
            parts = line.split()
            if len(parts) < 3:
                continue
            left, right = " ".join(parts[:2]), parts[2]
        try:
            value = float(right.strip())
        except ValueError:
            continue

        dt_text = left.strip()
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"):
            try:
                parsed = datetime.strptime(dt_text, fmt)
                break
            except ValueError:
                pass
        if parsed is not None:
            entries.append((parsed, value))

    if len(entries) < 2:
        raise ValueError(f"Rainfall file needs at least two timestamp,value rows: {path}")
    return sorted(entries, key=lambda item: item[0])


def _format_swmm_interval(delta: timedelta) -> str:
    total_seconds = max(60, int(delta.total_seconds()))
    hours, rem = divmod(total_seconds, 3600)
    minutes = rem // 60
    return f"{hours}:{minutes:02d}"


def _infer_rainfall_interval(entries: List[Tuple[datetime, float]]) -> str:
    deltas = [
        entries[idx + 1][0] - entries[idx][0]
        for idx in range(len(entries) - 1)
        if entries[idx + 1][0] > entries[idx][0]
    ]
    return _format_swmm_interval(min(deltas) if deltas else timedelta(minutes=5))


def _find_raingage_timeseries(lines: List[str], rain_gage_name: str) -> Optional[str]:
    bounds = _find_section_bounds(lines, "RAINGAGES")
    if bounds is None:
        return None
    start, end = bounds
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        parts = stripped.split()
        if parts and parts[0] == rain_gage_name:
            if "TIMESERIES" in [part.upper() for part in parts]:
                for idx, part in enumerate(parts):
                    if part.upper() == "TIMESERIES" and idx + 1 < len(parts):
                        return parts[idx + 1]
            return parts[-1] if len(parts) >= 6 else None
    return None


def _replace_swmm_event_inputs(
    source_inp: Path,
    target_inp: Path,
    rainfall_entries: List[Tuple[datetime, float]],
    rain_gage_name: str = "rain1",
    timeseries_name: Optional[str] = None,
) -> Dict[str, object]:
    lines = _read_lines(source_inp)
    start_dt = rainfall_entries[0][0]
    end_dt = rainfall_entries[-1][0]
    interval = _infer_rainfall_interval(rainfall_entries)
    timeseries_name = timeseries_name or _find_raingage_timeseries(lines, rain_gage_name) or "rain01"

    option_values = {
        "IGNORE_RAINFALL": "NO",
        "START_DATE": start_dt.strftime("%m/%d/%Y"),
        "START_TIME": start_dt.strftime("%H:%M:%S"),
        "REPORT_START_DATE": start_dt.strftime("%m/%d/%Y"),
        "REPORT_START_TIME": start_dt.strftime("%H:%M:%S"),
        "END_DATE": end_dt.strftime("%m/%d/%Y"),
        "END_TIME": end_dt.strftime("%H:%M:%S"),
    }

    bounds = _find_section_bounds(lines, "OPTIONS")
    if bounds:
        start, end = bounds
        for idx in range(start + 1, end):
            parts = lines[idx].strip().split()
            if len(parts) >= 2 and parts[0].upper() in option_values:
                key = parts[0].upper()
                lines[idx] = f"{key.ljust(22)}{option_values[key]}\n"

    ts_lines = [";;Name           Date       Time       Value\n", ";;-------------- ---------- ---------- ----------\n"]
    for dt_value, value in rainfall_entries:
        ts_lines.append(
            f"{timeseries_name.ljust(16)} {dt_value.strftime('%m/%d/%Y')} "
            f"{dt_value.strftime('%H:%M').ljust(8)} {value:.3f}\n"
        )
    lines = _insert_or_replace_section(lines, "TIMESERIES", ts_lines)

    raingage_lines = [";;Name           Format    Interval SCF      Source\n", ";;-------------- --------- ------ ------ ----------\n"]
    replaced = False
    bounds = _find_section_bounds(lines, "RAINGAGES")
    existing = lines[bounds[0] + 1 : bounds[1]] if bounds else []
    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        parts = stripped.split()
        if parts and parts[0] == rain_gage_name:
            raingage_lines.append(
                f"{rain_gage_name.ljust(16)} INTENSITY {interval.ljust(8)} 1.0      TIMESERIES {timeseries_name}\n"
            )
            replaced = True
        else:
            raingage_lines.append(line if line.endswith("\n") else line + "\n")
    if not replaced:
        raingage_lines.append(
            f"{rain_gage_name.ljust(16)} INTENSITY {interval.ljust(8)} 1.0      TIMESERIES {timeseries_name}\n"
        )
    lines = _insert_or_replace_section(lines, "RAINGAGES", raingage_lines)

    _write_lines(target_inp, lines)
    return {
        "rain_gage_name": rain_gage_name,
        "timeseries_name": timeseries_name,
        "rainfall_points": len(rainfall_entries),
        "rainfall_start": start_dt.isoformat(sep=" "),
        "rainfall_end": end_dt.isoformat(sep=" "),
        "rainfall_interval": interval,
    }


def _load_mapped_node_ids(mapping_path: Path) -> set[str]:
    if not mapping_path.exists():
        return set()
    import csv

    with mapping_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "node_id" not in reader.fieldnames:
            return set()
        return {str(row["node_id"]).strip() for row in reader if row.get("node_id")}


def _run_swmm_and_export_flooding(
    inp_path: Path,
    swmm_output_dir: Path,
    node_mapping_path: Path,
    save_interval_minutes: float,
) -> Dict[str, object]:
    from pyswmm import Links, Nodes, Simulation

    swmm_output_dir.mkdir(parents=True, exist_ok=True)
    report_path = swmm_output_dir / "model.rpt"
    binary_output_path = swmm_output_dir / "model.out"
    flooding_path = swmm_output_dir / "node_flooding.tsv"
    nodes_path = swmm_output_dir / "nodes.tsv"
    links_path = swmm_output_dir / "links.tsv"

    mapped_node_ids = _load_mapped_node_ids(node_mapping_path)
    total_steps = 0
    saved_steps = 0
    flooding_record_count = 0
    max_flooding_lps = 0.0
    max_depth_m = 0.0
    link_count = 0

    with flooding_path.open("w", encoding="utf-8", newline="") as flooding_f, nodes_path.open(
        "w", encoding="utf-8", newline=""
    ) as nodes_f, links_path.open("w", encoding="utf-8", newline="") as links_f:
        flooding_f.write("node_id\tdate\ttime\tflow_Ls\n")
        nodes_f.write("node_id\tdepth_m\tflooding_Ls\tdate\ttime\n")
        links_f.write("link_id\tflow_Ls\tdepth_m\tdate\ttime\n")

        with Simulation(str(inp_path), str(report_path), str(binary_output_path)) as sim:
            nodes = {node.nodeid: node for node in Nodes(sim)}
            links = {link.linkid: link for link in Links(sim)}
            link_count = len(links)
            last_save_time = sim.start_time - timedelta(minutes=save_interval_minutes)

            for _ in sim:
                total_steps += 1
                current_time = sim.current_time.replace(second=0, microsecond=0)
                if (current_time - last_save_time) < timedelta(minutes=save_interval_minutes):
                    continue

                saved_steps += 1
                date_text = current_time.strftime("%Y-%m-%d")
                time_text = current_time.strftime("%H:%M:%S")
                for node_id, node in nodes.items():
                    flooding_lps = float(getattr(node, "flooding", 0.0) or 0.0)
                    depth_m = float(getattr(node, "depth", 0.0) or 0.0)
                    max_flooding_lps = max(max_flooding_lps, flooding_lps)
                    max_depth_m = max(max_depth_m, depth_m)
                    nodes_f.write(f"{node_id}\t{depth_m:.6f}\t{flooding_lps:.6f}\t{date_text}\t{time_text}\n")
                    if not mapped_node_ids or node_id in mapped_node_ids:
                        flooding_f.write(f"{node_id}\t{date_text}\t{time_text}\t{flooding_lps:.6f}\n")
                        flooding_record_count += 1

                for link_id, link in links.items():
                    flow_lps = float(getattr(link, "flow", 0.0) or 0.0)
                    depth_m = float(getattr(link, "depth", 0.0) or 0.0)
                    links_f.write(f"{link_id}\t{flow_lps:.6f}\t{depth_m:.6f}\t{date_text}\t{time_text}\n")

                last_save_time = current_time

    return {
        "modified_inp": str(inp_path),
        "report_file": str(report_path),
        "binary_output_file": str(binary_output_path),
        "flooding_file": str(flooding_path),
        "nodes_file": str(nodes_path),
        "links_file": str(links_path),
        "total_steps": total_steps,
        "saved_steps": saved_steps,
        "node_count": len(mapped_node_ids) if mapped_node_ids else None,
        "link_count": link_count,
        "flooding_records": flooding_record_count,
        "max_flooding_Ls": max_flooding_lps,
        "max_node_depth_m": max_depth_m,
    }


def is_runnable_inp(
    inp_file: Annotated[str, "Path to a SWMM .inp file relative to the project root."],
    task_elements: Annotated[
        Dict[str, Union[List[str], List[int]]],
        "Optional dictionary with nodes, links, subcatchments, rain_gages, and times to validate.",
    ] = None,
    run_simulation: Annotated[
        bool,
        "If True, try to run the model through PySWMM. If False, only perform structural checks.",
    ] = False,
) -> str:
    inp_path = _resolve_workspace_path(inp_file)
    if not inp_path.exists():
        return f"File not found: {inp_file}"

    lines = _read_lines(inp_path)
    sections = parse_sections(lines)

    required = ["TITLE", "OPTIONS", "RAINGAGES", "SUBCATCHMENTS", "JUNCTIONS", "CONDUITS"]
    missing_required = [name for name in required if name not in sections]

    node_ids = sorted(set(_first_col_ids(sections, "JUNCTIONS") + _first_col_ids(sections, "OUTFALLS") + _first_col_ids(sections, "STORAGE")))
    link_ids = sorted(set(_first_col_ids(sections, "CONDUITS") + _first_col_ids(sections, "PUMPS") + _first_col_ids(sections, "ORIFICES") + _first_col_ids(sections, "WEIRS") + _first_col_ids(sections, "OUTLETS")))
    subcatchment_ids = sorted(set(_first_col_ids(sections, "SUBCATCHMENTS")))
    rain_gage_ids = sorted(set(_first_col_ids(sections, "RAINGAGES")))

    if task_elements:
        invalid_nodes = [x for x in task_elements.get("nodes", []) if x not in node_ids]
        invalid_links = [x for x in task_elements.get("links", []) if x not in link_ids]
        invalid_subcatchments = [x for x in task_elements.get("subcatchments", []) if x not in subcatchment_ids]
        invalid_rain_gages = [x for x in task_elements.get("rain_gages", []) if x not in rain_gage_ids]
        problems = []
        if invalid_nodes:
            problems.append(f"missing nodes: {invalid_nodes}")
        if invalid_links:
            problems.append(f"missing links: {invalid_links}")
        if invalid_subcatchments:
            problems.append(f"missing subcatchments: {invalid_subcatchments}")
        if invalid_rain_gages:
            problems.append(f"missing rain gages: {invalid_rain_gages}")
        if problems:
            return "Task element validation failed: " + "; ".join(problems)

    simulation_note = "Simulation was not requested."
    if run_simulation:
        try:
            from pyswmm import Simulation

            with Simulation(str(inp_path)) as sim:
                steps = 0
                for _ in sim:
                    steps += 1
                    if steps >= 1:
                        break
            simulation_note = "PySWMM simulation opened and advanced at least one step."
        except Exception as exc:
            return f"Structural parsing succeeded, but PySWMM simulation failed: {exc}"

    status = "valid with warnings" if missing_required else "valid"
    return (
        f"SWMM INP structural check: {status}.\n"
        f"Sections found: {', '.join(sorted(sections.keys()))}\n"
        f"Counts: {len(subcatchment_ids)} subcatchments, {len(rain_gage_ids)} rain gages, "
        f"{len(node_ids)} nodes, {len(link_ids)} links.\n"
        f"Missing commonly expected sections: {missing_required or 'none'}.\n"
        f"{simulation_note}"
    )


def add_controls(
    inp_file: Annotated[str, "Path to the SWMM .inp file relative to the project root."],
    controls: Annotated[List[str], "List of SWMM control-rule text blocks."],
    save_name: Annotated[str, "Path for the modified .inp relative to the project root."] = "control_model.inp",
) -> str:
    inp_path = _resolve_workspace_path(inp_file)
    if not inp_path.exists():
        return f"File not found: {inp_file}"
    if not controls:
        return "No controls were provided."

    lines = _read_lines(inp_path)
    existing_bounds = _find_section_bounds(lines, "CONTROLS")
    if existing_bounds:
        start, end = existing_bounds
        existing = lines[start + 1 : end]
    else:
        existing = []

    new_control_lines = existing[:]
    if new_control_lines and not new_control_lines[-1].endswith("\n"):
        new_control_lines[-1] += "\n"
    if new_control_lines and new_control_lines[-1].strip():
        new_control_lines.append("\n")

    for idx, control in enumerate(controls, start=1):
        new_control_lines.append(f"; Added by SWMM-Agentic control block {idx}\n")
        for line in control.strip().splitlines():
            new_control_lines.append(line.rstrip() + "\n")
        new_control_lines.append("\n")

    modified = _insert_or_replace_section(lines, "CONTROLS", new_control_lines)
    save_path = _resolve_workspace_path(save_name)
    _write_lines(save_path, modified)
    return f"Controls added and saved as '{save_name}'."


def apply_scenario(
    inp_file: Annotated[str, "Path to the SWMM .inp file relative to the project root."],
    scenario_list: Annotated[List[Dict[str, Union[str, float, Dict]]], "List of SWMM scenario definitions."],
    save_name: Annotated[str, "Path for the modified .inp relative to the project root."],
) -> str:
    inp_path = _resolve_workspace_path(inp_file)
    if not inp_path.exists():
        return f"File not found: {inp_file}"

    lines = _read_lines(inp_path)
    sections = parse_sections(lines)
    edits = []

    for scenario in scenario_list:
        scenario_type = scenario.get("scenario_type")
        params = scenario.get("params", {})

        if scenario_type == "rainfall_scale":
            factor = float(params.get("factor", 1.0))
            lines = _scale_timeseries_rainfall(lines, factor)
            edits.append(f"scaled [TIMESERIES] numeric rainfall values by {factor}")

        elif scenario_type == "conduit_blockage":
            conduit_id = str(params.get("link_name", "")).strip()
            roughness_multiplier = float(params.get("roughness_multiplier", 1.5))
            if conduit_id not in _first_col_ids(sections, "CONDUITS"):
                return f"Conduit '{conduit_id}' not found."
            lines = _multiply_conduit_roughness(lines, conduit_id, roughness_multiplier)
            edits.append(f"multiplied conduit {conduit_id} roughness by {roughness_multiplier}")

        elif scenario_type == "junction_surcharge":
            node_id = str(params.get("node_name", "")).strip()
            surcharge_depth = float(params.get("surcharge_depth", 0.0))
            if node_id not in _first_col_ids(sections, "JUNCTIONS"):
                return f"Junction '{node_id}' not found."
            lines = _set_junction_surcharge(lines, node_id, surcharge_depth)
            edits.append(f"set junction {node_id} surcharge depth to {surcharge_depth}")

        elif scenario_type == "storage_initial_depth":
            storage_id = str(params.get("storage_name", "")).strip()
            initial_depth = float(params.get("initial_depth", 0.0))
            if storage_id not in _first_col_ids(sections, "STORAGE"):
                return f"Storage '{storage_id}' not found."
            lines = _set_storage_initial_depth(lines, storage_id, initial_depth)
            edits.append(f"set storage {storage_id} initial depth to {initial_depth}")

        else:
            return f"Unsupported scenario_type: {scenario_type}"

        sections = parse_sections(lines)

    save_path = _resolve_workspace_path(save_name)
    _write_lines(save_path, lines)
    return f"Scenario edits applied and saved as '{save_name}': " + "; ".join(edits)


def check_ca2d_model(
    model_dir: Annotated[
        str,
        "Path to a CA2D static model directory relative to the project root. If empty, use the selected model project's static/ directory.",
    ] = "",
) -> str:
    if model_dir:
        model_path = _resolve_workspace_path(model_dir)
        display_dir = model_dir
        if (model_path / "static").is_dir():
            model_path = model_path / "static"
            display_dir = str(Path(model_dir) / "static")
    else:
        model_root = _resolve_model_root("")
        selection_error = _model_selection_error(model_root)
        if selection_error:
            return selection_error
        model_path = model_root / "static"
        display_dir = str(model_path)
    status = check_static_model(model_path)
    if not status["ok"]:
        return (
            "CA2D static model is incomplete.\n"
            f"Schema: {PROJECT_SCHEMA_NAME} ({PROJECT_SCHEMA_VERSION})\n"
            "Validator: check_ca2d_model\n"
            f"Model directory: {display_dir}\n"
            f"Missing files: {status['missing']}"
        )
    return (
        "CA2D static model is ready.\n"
        f"Schema: {PROJECT_SCHEMA_NAME} ({PROJECT_SCHEMA_VERSION})\n"
        "Validator: check_ca2d_model\n"
        f"Model directory: {display_dir}\n"
        f"Grid shape: {status['grid_shape']}\n"
        f"Cell size: {status['cell_size']} m\n"
        f"Mapped SWMM nodes: {status['mapped_nodes']}\n"
        f"Flowable cells: {status['flow_cells']}"
    )


def create_demo_ca2d_model(
    model_dir: Annotated[
        str,
        "Output directory for a synthetic CA2D static model relative to the project root.",
    ] = "outputs/ca2d_model_demo",
) -> str:
    model_path = _resolve_workspace_path(model_dir)
    status = create_demo_static_model(model_path)
    return (
        "Demo CA2D static model created.\n"
        f"Model directory: {model_dir}\n"
        f"Grid shape: {status['grid_shape']}\n"
        f"Cell size: {status['cell_size']} m\n"
        f"Mapped demo nodes: {status['mapped_nodes']}\n"
        "Demo node IDs: J1, J2, J3"
    )


def run_swmm_2d_from_flooding(
    flooding_file: Annotated[
        str,
        "Path to a SWMM node flooding file relative to the project root. Expected columns: node_id, date, time, flow_Ls.",
    ],
    model_dir: Annotated[
        str,
        "Path to a CA2D static model directory relative to the project root. If empty, use the selected model project's static/ directory.",
    ] = "",
    output_dir: Annotated[
        str,
        "Output directory for SWMM-2D results relative to the project root.",
    ] = "outputs/swmm_2d_outputs",
    dt_seconds: Annotated[float, "CA2D internal time step in seconds."] = 10.0,
    boundary_interval_minutes: Annotated[
        float,
        "Boundary interpolation interval in minutes for SWMM node overflow injection.",
    ] = 5.0,
    save_interval_minutes: Annotated[
        float,
        "Interval in minutes for writing tabular surface-depth records.",
    ] = 30.0,
    output_txt_name: Annotated[
        str,
        "Optional output table filename under output_dir.",
    ] = "swmm_2d_surface_depth.tsv",
) -> str:
    flooding_path = _resolve_workspace_path(flooding_file)
    if not flooding_path.exists():
        return f"Flooding file not found: {flooding_file}"

    if model_dir:
        model_path = _resolve_workspace_path(model_dir)
    else:
        model_root = _resolve_model_root("")
        selection_error = _model_selection_error(model_root)
        if selection_error:
            return selection_error
        model_path = model_root / "static"
    output_path = _resolve_workspace_path(output_dir)
    result = run_ca2d_simulation(
        model_dir=model_path,
        flooding_file=flooding_path,
        output_dir=output_path,
        dt_seconds=dt_seconds,
        boundary_interval_minutes=boundary_interval_minutes,
        save_interval_minutes=save_interval_minutes,
        output_txt_path=output_path / output_txt_name,
    )
    rel_result = {
        key: str(Path(value).relative_to(WORKSPACE_DIR)) if isinstance(value, str) and Path(value).is_absolute() and Path(value).is_relative_to(WORKSPACE_DIR) else value
        for key, value in result.items()
    }
    return "SWMM-2D CA2D simulation completed:\n" + json.dumps(rel_result, ensure_ascii=False, indent=2)


def run_swmm_2d_project_from_rainfall(
    model_name: Annotated[
        str,
        "Name of a SWMM-2D model project under the project-root models/ directory.",
    ] = "",
    rainfall_file: Annotated[
        str,
        "Rainfall event file path. Relative paths are resolved first under the model project, then under the project root. Expected rows: timestamp,value.",
    ] = "",
    event_name: Annotated[
        str,
        "Rainfall event ID used for run metadata and comparison grouping.",
    ] = "manual_event",
    scenario_name: Annotated[
        str,
        "SWMM scenario ID under swmm/scenarios/<scenario_name>/.",
    ] = "baseline",
    run_id: Annotated[
        str,
        "Optional run ID. If empty, one is generated from event, scenario, and timestamp.",
    ] = "",
    rain_gage_name: Annotated[
        str,
        "SWMM rain gage name to receive the event rainfall.",
    ] = "rain1",
    timeseries_name: Annotated[
        str,
        "Optional SWMM time series name. If empty, the existing rain gage source is reused.",
    ] = "",
    swmm_save_interval_minutes: Annotated[
        float,
        "Interval in minutes for exporting SWMM node/link/flooding time series.",
    ] = 30.0,
    dt_seconds: Annotated[float, "CA2D internal time step in seconds."] = 10.0,
    boundary_interval_minutes: Annotated[
        float,
        "Boundary interpolation interval in minutes for SWMM node overflow injection.",
    ] = 5.0,
    ca2d_save_interval_minutes: Annotated[
        float,
        "Interval in minutes for writing CA2D tabular surface-depth records.",
    ] = 30.0,
) -> str:
    model_root = _resolve_model_root(model_name)
    selection_error = _model_selection_error(model_root)
    if selection_error:
        return selection_error
    if not model_root.exists():
        return f"SWMM-2D model project not found: models/{model_name}"
    model_name = model_root.name
    if not rainfall_file:
        return "Rainfall event file is required. Use list_rainfall_events first if you need to discover available event files."

    static_model = model_root / "static"
    static_status = check_static_model(static_model)
    if not static_status["ok"]:
        return f"CA2D static model is incomplete for {model_name}: {static_status['missing']}"

    scenario_inp = model_root / "swmm" / "scenarios" / scenario_name / "model.inp"
    if not scenario_inp.exists():
        return f"SWMM scenario input not found: {scenario_inp}"

    rainfall_path = _resolve_model_input(model_root, rainfall_file)
    if not rainfall_path.exists():
        return f"Rainfall event file not found: {rainfall_file}"

    if not run_id:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{_safe_id(event_name)}__{_safe_id(scenario_name)}__{timestamp}"
    else:
        run_id = _safe_id(run_id)

    run_root = model_root / "runs" / run_id
    swmm_output_dir = run_root / "swmm"
    ca2d_output_dir = run_root / "ca2d"
    swmm_output_dir.mkdir(parents=True, exist_ok=True)
    ca2d_output_dir.mkdir(parents=True, exist_ok=True)

    event_copy = run_root / "rainfall_event.txt"
    shutil.copy2(rainfall_path, event_copy)
    modified_inp = swmm_output_dir / "model_with_event.inp"
    rainfall_entries = _parse_datetime_value_file(rainfall_path)
    rainfall_summary = _replace_swmm_event_inputs(
        source_inp=scenario_inp,
        target_inp=modified_inp,
        rainfall_entries=rainfall_entries,
        rain_gage_name=rain_gage_name,
        timeseries_name=timeseries_name or None,
    )

    node_mapping = static_model / "node_to_cell_mapping.csv"
    swmm_result = _run_swmm_and_export_flooding(
        inp_path=modified_inp,
        swmm_output_dir=swmm_output_dir,
        node_mapping_path=node_mapping,
        save_interval_minutes=swmm_save_interval_minutes,
    )

    ca2d_result = run_ca2d_simulation(
        model_dir=static_model,
        flooding_file=Path(swmm_result["flooding_file"]),
        output_dir=ca2d_output_dir,
        dt_seconds=dt_seconds,
        boundary_interval_minutes=boundary_interval_minutes,
        save_interval_minutes=ca2d_save_interval_minutes,
        output_txt_path=ca2d_output_dir / "surface_depth.tsv",
    )

    metadata = {
        "execution_policy": "tool-first",
        "pipeline_tool": "run_swmm_2d_project_from_rainfall",
        "schema_name": PROJECT_SCHEMA_NAME,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "run_id": run_id,
        "model_name": model_name,
        "event_name": event_name,
        "scenario_name": scenario_name,
        "run_root": str(run_root),
        "source_scenario_inp": str(scenario_inp),
        "rainfall_file": str(rainfall_path),
        "rainfall_event_copy": str(event_copy),
        "static_model": str(static_model),
        "swmm_output_dir": str(swmm_output_dir),
        "ca2d_output_dir": str(ca2d_output_dir),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "rainfall": rainfall_summary,
        "swmm": swmm_result,
        "ca2d": ca2d_result,
    }
    (run_root / "summary.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_root / "run.yaml").write_text(
        "\n".join(
            [
                f"run_id: {run_id}",
                f"model_name: {model_name}",
                f"event_name: {event_name}",
                f"scenario_name: {scenario_name}",
                f"source_scenario_inp: {scenario_inp}",
                f"rainfall_file: {rainfall_path}",
                f"static_model: {static_model}",
                f"swmm_output_dir: {swmm_output_dir}",
                f"ca2d_output_dir: {ca2d_output_dir}",
                f"created_at: {metadata['created_at']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return "SWMM-2D project rainfall run completed:\n" + json.dumps(metadata, ensure_ascii=False, indent=2)


def list_swmm_2d_models() -> str:
    if not MODELS_DIR.exists():
        return "No models directory exists yet."

    rows = []
    for model_root in sorted(MODELS_DIR.iterdir()):
        if not model_root.is_dir():
            continue
        marker = model_root / "model.yaml"
        static_status = check_static_model(model_root / "static") if (model_root / "static").exists() else {"ok": False}
        rows.append(
            {
                "schema_name": PROJECT_SCHEMA_NAME,
                "schema_version": PROJECT_SCHEMA_VERSION,
                "validator": "list_swmm_2d_models",
                "model": model_root.name,
                "has_model_yaml": marker.exists(),
                "static_ready": bool(static_status.get("ok")),
                "baseline_inp": (model_root / "swmm" / "scenarios" / "baseline" / "model.inp").exists(),
            }
        )

    if not rows:
        return "No SWMM-2D model projects found under the project-root models/ directory."
    return json.dumps(rows, ensure_ascii=False, indent=2)


def list_rainfall_events(
    model_name: Annotated[
        str,
        "Name of a SWMM-2D model project under the project-root models/ directory.",
    ] = "",
) -> str:
    model_root = _resolve_model_root(model_name)
    selection_error = _model_selection_error(model_root)
    if selection_error:
        return selection_error
    model_name = model_root.name
    events_dir = model_root / "events"
    if not model_root.exists():
        return f"SWMM-2D model project not found: models/{model_name}"
    if not events_dir.exists():
        return f"Rainfall events directory not found: {events_dir}"

    rainfall_extensions = {".txt", ".csv", ".dat", ".rain", ".prcp", ".precip", ".ts"}
    rows = []
    for file_path in sorted(path for path in events_dir.rglob("*") if path.is_file()):
        if file_path.suffix.lower() not in rainfall_extensions:
            continue
        preview = []
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                for idx, line in enumerate(f):
                    if idx >= 3:
                        break
                    preview.append(line.strip())
        except Exception as exc:
            preview = [f"failed to read preview: {exc}"]
        rows.append(
            {
                "file": str(file_path),
                "relative_to_model": str(file_path.relative_to(model_root)),
                "size_bytes": file_path.stat().st_size,
                "preview": preview,
            }
        )

    if not rows:
        return f"No rainfall event files found under {events_dir}"
    return json.dumps(rows, ensure_ascii=False, indent=2)


def check_swmm_2d_project(
    model_name: Annotated[
        str,
        "Name of a SWMM-2D model project under the project-root models/ directory.",
    ] = "",
) -> str:
    model_root = _resolve_model_root(model_name)
    selection_error = _model_selection_error(model_root)
    if selection_error:
        return selection_error
    model_name = model_root.name
    if not model_root.exists():
        return f"SWMM-2D model project not found: models/{model_name}"

    required_dirs = ["raw", "static", "swmm", "mapping", "events", "runs"]
    missing_dirs = [name for name in required_dirs if not (model_root / name).is_dir()]
    baseline_inp = model_root / "swmm" / "scenarios" / "baseline" / "model.inp"
    static_status = check_static_model(model_root / "static")
    problems = []
    if missing_dirs:
        problems.append(f"missing directories: {missing_dirs}")
    if not (model_root / "model.yaml").exists():
        problems.append("missing model.yaml")
    if not baseline_inp.exists():
        problems.append("missing baseline SWMM input: swmm/scenarios/baseline/model.inp")
    if not static_status["ok"]:
        problems.append(f"incomplete CA2D static model: {static_status['missing']}")

    summary = {
        "schema_name": PROJECT_SCHEMA_NAME,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "validator": "check_swmm_2d_project",
        "model_name": model_name,
        "model_root": str(model_root),
        "ready": not problems,
        "problems": problems,
        "baseline_inp": str(baseline_inp),
        "static_model": static_status,
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def check_all_swmm_2d_projects() -> str:
    if not MODELS_DIR.exists():
        return "No models directory exists yet."

    model_names = sorted(path.name for path in MODELS_DIR.iterdir() if path.is_dir())
    if not model_names:
        return "No SWMM-2D model projects found under the project-root models/ directory."

    summaries = []
    for model_name in model_names:
        summaries.append(json.loads(check_swmm_2d_project(model_name)))
    return json.dumps(
        {
            "schema_name": PROJECT_SCHEMA_NAME,
            "schema_version": PROJECT_SCHEMA_VERSION,
            "validator": "check_all_swmm_2d_projects",
            "project_count": len(summaries),
            "projects": summaries,
        },
        ensure_ascii=False,
        indent=2,
    )


def run_swmm_2d_project_from_flooding(
    model_name: Annotated[
        str,
        "Name of a SWMM-2D model project under the project-root models/ directory.",
    ] = "",
    flooding_file: Annotated[
        str,
        "Flooding file path. Relative paths are resolved first under the model project, then under the project root.",
    ] = "",
    event_name: Annotated[
        str,
        "Rainfall event ID used for run metadata and comparison grouping.",
    ] = "manual_event",
    scenario_name: Annotated[
        str,
        "SWMM scenario ID used for run metadata and comparison grouping.",
    ] = "baseline",
    run_id: Annotated[
        str,
        "Optional run ID. If empty, one is generated from event, scenario, and timestamp.",
    ] = "",
    dt_seconds: Annotated[float, "CA2D internal time step in seconds."] = 10.0,
    boundary_interval_minutes: Annotated[
        float,
        "Boundary interpolation interval in minutes for SWMM node overflow injection.",
    ] = 5.0,
    save_interval_minutes: Annotated[
        float,
        "Interval in minutes for writing tabular surface-depth records.",
    ] = 30.0,
) -> str:
    model_root = _resolve_model_root(model_name)
    selection_error = _model_selection_error(model_root)
    if selection_error:
        return selection_error
    if not model_root.exists():
        return f"SWMM-2D model project not found: models/{model_name}"
    model_name = model_root.name
    if not flooding_file:
        return "Flooding file is required."

    static_model = model_root / "static"
    static_status = check_static_model(static_model)
    if not static_status["ok"]:
        return f"CA2D static model is incomplete for {model_name}: {static_status['missing']}"

    scenario_inp = model_root / "swmm" / "scenarios" / scenario_name / "model.inp"
    if not scenario_inp.exists():
        return f"SWMM scenario input not found: {scenario_inp}"

    flooding_path = _resolve_model_input(model_root, flooding_file)
    if not flooding_path.exists():
        return f"Flooding file not found: {flooding_file}"

    if not run_id:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{_safe_id(event_name)}__{_safe_id(scenario_name)}__{timestamp}"
    else:
        run_id = _safe_id(run_id)

    run_root = model_root / "runs" / run_id
    ca2d_output_dir = run_root / "ca2d"
    swmm_output_dir = run_root / "swmm"
    swmm_output_dir.mkdir(parents=True, exist_ok=True)
    ca2d_output_dir.mkdir(parents=True, exist_ok=True)

    result = run_ca2d_simulation(
        model_dir=static_model,
        flooding_file=flooding_path,
        output_dir=ca2d_output_dir,
        dt_seconds=dt_seconds,
        boundary_interval_minutes=boundary_interval_minutes,
        save_interval_minutes=save_interval_minutes,
        output_txt_path=ca2d_output_dir / "surface_depth.tsv",
    )

    metadata = {
        "execution_policy": "tool-first",
        "pipeline_tool": "run_swmm_2d_project_from_flooding",
        "schema_name": PROJECT_SCHEMA_NAME,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "run_id": run_id,
        "model_name": model_name,
        "event_name": event_name,
        "scenario_name": scenario_name,
        "run_root": str(run_root),
        "scenario_inp": str(scenario_inp),
        "flooding_file": str(flooding_path),
        "static_model": str(static_model),
        "swmm_output_dir": str(swmm_output_dir),
        "ca2d_output_dir": str(ca2d_output_dir),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "ca2d": result,
    }
    (run_root / "summary.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_root / "run.yaml").write_text(
        "\n".join(
            [
                f"run_id: {run_id}",
                f"model_name: {model_name}",
                f"event_name: {event_name}",
                f"scenario_name: {scenario_name}",
                f"scenario_inp: {scenario_inp}",
                f"flooding_file: {flooding_path}",
                f"static_model: {static_model}",
                f"swmm_output_dir: {swmm_output_dir}",
                f"ca2d_output_dir: {ca2d_output_dir}",
                f"created_at: {metadata['created_at']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return "SWMM-2D project run completed:\n" + json.dumps(metadata, ensure_ascii=False, indent=2)
def _scale_timeseries_rainfall(lines: List[str], factor: float) -> List[str]:
    bounds = _find_section_bounds(lines, "TIMESERIES")
    if bounds is None:
        raise ValueError("[TIMESERIES] section not found.")
    start, end = bounds
    modified = lines[:]
    for idx in range(start + 1, end):
        raw = modified[idx]
        stripped = raw.strip()
        if not stripped or stripped.startswith(";"):
            continue
        parts = stripped.split()
        for pos in range(len(parts) - 1, -1, -1):
            try:
                value = float(parts[pos])
            except ValueError:
                continue
            parts[pos] = f"{value * factor:g}"
            modified[idx] = " ".join(parts) + "\n"
            break
    return modified


def _multiply_conduit_roughness(lines: List[str], conduit_id: str, multiplier: float) -> List[str]:
    bounds = _find_section_bounds(lines, "CONDUITS")
    if bounds is None:
        raise ValueError("[CONDUITS] section not found.")
    modified = lines[:]
    start, end = bounds
    for idx in range(start + 1, end):
        parts = modified[idx].strip().split()
        if parts and parts[0] == conduit_id:
            if len(parts) < 5:
                raise ValueError(f"Conduit row for {conduit_id} is too short to edit roughness.")
            parts[4] = f"{float(parts[4]) * multiplier:g}"
            modified[idx] = " ".join(parts) + "\n"
            return modified
    return modified


def _set_junction_surcharge(lines: List[str], node_id: str, surcharge_depth: float) -> List[str]:
    bounds = _find_section_bounds(lines, "JUNCTIONS")
    if bounds is None:
        raise ValueError("[JUNCTIONS] section not found.")
    modified = lines[:]
    start, end = bounds
    for idx in range(start + 1, end):
        parts = modified[idx].strip().split()
        if parts and parts[0] == node_id:
            while len(parts) < 6:
                parts.append("0")
            parts[5] = f"{surcharge_depth:g}"
            modified[idx] = " ".join(parts) + "\n"
            return modified
    return modified


def _set_storage_initial_depth(lines: List[str], storage_id: str, initial_depth: float) -> List[str]:
    bounds = _find_section_bounds(lines, "STORAGE")
    if bounds is None:
        raise ValueError("[STORAGE] section not found.")
    modified = lines[:]
    start, end = bounds
    for idx in range(start + 1, end):
        parts = modified[idx].strip().split()
        if parts and parts[0] == storage_id:
            if len(parts) < 3:
                raise ValueError(f"Storage row for {storage_id} is too short to edit initial depth.")
            parts[2] = f"{initial_depth:g}"
            modified[idx] = " ".join(parts) + "\n"
            return modified
    return modified


def parse_and_convert_to_markdown(txt_path, md_path):
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    md_lines = ["### Conversation Log: SWMM-Agentic Interaction\n"]
    role_map = {
        "TextMessage (user)": "user",
        "TextMessage (Orchestrator)": "Orchestrator",
        "TextMessage (TaskExecutor)": "TaskExecutor",
        "TextMessage (CodeRunner)": "CodeRunner",
        "TextMessage (DataAnalyzer)": "DataAnalyzer",
        "ToolCallRequestEvent": "TOOL CALL",
        "ToolCallExecutionEvent": "TOOL RESULT",
        "ToolCallSummaryMessage": "TOOL SUMMARY",
        "UserInputRequestedEvent": "user",
    }

    current_role = None
    buffer = []

    def flush_buffer():
        if current_role and buffer:
            content = "".join(buffer).strip()
            md_lines.append(f"\n**{current_role}**:\n```\n{content}\n```\n")
        buffer.clear()

    for line in lines:
        role_match = re.match(r"^-+ (.+?) -+\n$", line)
        if role_match:
            flush_buffer()
            role_raw = role_match.group(1).strip()
            current_role = role_map.get(role_raw, role_raw)
        else:
            buffer.append(line)

    flush_buffer()
    md_lines.append("\n---\nConversation Ended\n")

    with open(md_path, "w", encoding="utf-8") as f:
        f.writelines(md_lines)


def build_run_evidence(
    model_name: Annotated[
        str,
        "Name of a SWMM-2D model project under the project-root models/ directory.",
    ] = "",
    run_id: Annotated[
        str,
        "Run ID under models/<model_name>/runs/.",
    ] = "",
) -> str:
    result = _build_evidence_for_run(model_name=model_name, run_id=run_id)
    return "EvidenceBuilderAgent completed:\n" + json.dumps(result, ensure_ascii=False, indent=2)


def diagnose_run(
    model_name: Annotated[
        str,
        "Name of a SWMM-2D model project under the project-root models/ directory.",
    ] = "",
    run_id: Annotated[
        str,
        "Run ID under models/<model_name>/runs/.",
    ] = "",
) -> str:
    result = _diagnose_run_from_evidence(model_name=model_name, run_id=run_id)
    return "DiagnosisAgent completed:\n" + json.dumps(result, ensure_ascii=False, indent=2)


def verify_run_diagnosis(
    model_name: Annotated[
        str,
        "Name of a SWMM-2D model project under the project-root models/ directory.",
    ] = "",
    run_id: Annotated[
        str,
        "Run ID under models/<model_name>/runs/.",
    ] = "",
) -> str:
    result = _verify_diagnosis_claims(model_name=model_name, run_id=run_id)
    return "VerificationAgent completed:\n" + json.dumps(result, ensure_ascii=False, indent=2)


def run_workflow_stage(
    model_name: Annotated[
        str,
        "Name of a SWMM-2D model project under the project-root models/ directory.",
    ] = "",
    run_id: Annotated[
        str,
        "Run ID under models/<model_name>/runs/.",
    ] = "",
    target_stage: Annotated[
        str,
        "Optional exact stage: evidence_building, diagnosis, or verification. Empty means next legal stage.",
    ] = "",
    until_stage: Annotated[
        str,
        "Optional final stage to reach sequentially: evidence_building, diagnosis, or verification.",
    ] = "",
    rerun: Annotated[
        bool,
        "Allow rerunning a stage instead of enforcing the next legal state transition.",
    ] = False,
) -> str:
    result = _run_workflow_stage(
        model_name=model_name,
        run_id=run_id,
        target_stage=target_stage,
        until_stage=until_stage,
        rerun=rerun,
    )
    return "StatefulOrchestrator completed:\n" + json.dumps(result, ensure_ascii=False, indent=2)
