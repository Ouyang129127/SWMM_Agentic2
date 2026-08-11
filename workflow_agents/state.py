"""Workflow state loading, initialization, validation, and persistence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schemas import (
    COMPLETED_STAGE_BY_STATE,
    EVIDENCE_READY,
    DIAGNOSIS_READY,
    FAILED,
    NEXT_STAGE_BY_STATE,
    RUN_READY,
    SCENARIO_READY,
    START,
    VERIFIED_READY,
    WORKFLOW_SCHEMA_NAME,
    WORKFLOW_SCHEMA_VERSION,
    artifacts_for_run,
)


APP_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = APP_ROOT / "models"


def resolve_run_root(model_name: str, run_id: str) -> Path:
    if not model_name:
        model_names = sorted(path.name for path in MODELS_DIR.iterdir() if path.is_dir()) if MODELS_DIR.exists() else []
        if len(model_names) == 1:
            model_name = model_names[0]
        elif not model_names:
            raise FileNotFoundError("No model projects found under models/.")
        else:
            raise ValueError(f"Multiple model projects found; specify model_name. Available: {model_names}")
    if not run_id:
        raise ValueError("run_id is required.")
    run_root = MODELS_DIR / model_name / "runs" / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run directory not found: {run_root}")
    return run_root


def _rel(run_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(run_root)).replace("\\", "/")
    except ValueError:
        return str(path)


def infer_state_from_artifacts(run_root: Path) -> str:
    artifacts = artifacts_for_run(run_root)
    if artifacts.verification_report.exists() and artifacts.unsupported_rate.exists():
        return VERIFIED_READY
    if artifacts.diagnosis_claims.exists() and artifacts.risk_ranking.exists():
        return DIAGNOSIS_READY
    if artifacts.evidence_table.exists() and artifacts.evidence_summary.exists():
        return EVIDENCE_READY
    if artifacts.run_summary.exists() and artifacts.swmm_node_flooding.exists() and artifacts.ca2d_surface_depth.exists():
        return RUN_READY
    if artifacts.scenario_request.exists():
        return SCENARIO_READY
    return FAILED


def build_state(model_name: str, run_id: str, run_root: Path, state: str | None = None, errors: list[str] | None = None) -> dict[str, Any]:
    artifacts = artifacts_for_run(run_root)
    current_state = state or infer_state_from_artifacts(run_root)
    completed = []
    for candidate in [SCENARIO_READY, RUN_READY, EVIDENCE_READY, DIAGNOSIS_READY, VERIFIED_READY]:
        stage = COMPLETED_STAGE_BY_STATE[candidate]
        if candidate == SCENARIO_READY:
            ok = artifacts.scenario_request.exists()
        elif candidate == RUN_READY:
            ok = artifacts.run_summary.exists()
        elif candidate == EVIDENCE_READY:
            ok = artifacts.evidence_table.exists() and artifacts.evidence_summary.exists()
        elif candidate == DIAGNOSIS_READY:
            ok = artifacts.diagnosis_claims.exists() and artifacts.risk_ranking.exists()
        else:
            ok = artifacts.verification_report.exists() and artifacts.unsupported_rate.exists()
        if ok:
            completed.append(stage)

    return {
        "schema_name": WORKFLOW_SCHEMA_NAME,
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "model_name": model_name,
        "run_id": run_id,
        "state": current_state,
        "completed_stages": completed,
        "next_allowed_stage": NEXT_STAGE_BY_STATE.get(current_state),
        "artifacts": {
            "scenario_request": _rel(run_root, artifacts.scenario_request),
            "run_summary": _rel(run_root, artifacts.run_summary),
            "run_metadata": _rel(run_root, artifacts.run_metadata),
            "swmm_node_flooding": _rel(run_root, artifacts.swmm_node_flooding),
            "swmm_nodes": _rel(run_root, artifacts.swmm_nodes),
            "swmm_links": _rel(run_root, artifacts.swmm_links),
            "ca2d_surface_depth": _rel(run_root, artifacts.ca2d_surface_depth),
            "evidence_table": _rel(run_root, artifacts.evidence_table),
            "evidence_summary": _rel(run_root, artifacts.evidence_summary),
            "diagnosis_claims": _rel(run_root, artifacts.diagnosis_claims),
            "risk_ranking": _rel(run_root, artifacts.risk_ranking),
            "verification_report": _rel(run_root, artifacts.verification_report),
            "unsupported_rate": _rel(run_root, artifacts.unsupported_rate),
        },
        "errors": errors or [],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def load_or_initialize_state(model_name: str, run_id: str) -> tuple[Path, dict[str, Any]]:
    run_root = resolve_run_root(model_name, run_id)
    model_name = run_root.parents[1].name
    state_path = run_root / "workflow_state.json"
    if state_path.exists():
        return run_root, json.loads(state_path.read_text(encoding="utf-8"))
    state = build_state(model_name, run_id, run_root)
    save_state(run_root, state)
    return run_root, state


def save_state(run_root: Path, state: dict[str, Any]) -> None:
    (run_root / "workflow_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
