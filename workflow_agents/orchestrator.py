"""StatefulOrchestrator for workflow-stage agents."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .diagnosis import diagnose_run_from_evidence
from .evidence_builder import build_evidence_for_run
from .schemas import (
    DIAGNOSIS_READY,
    EVIDENCE_READY,
    FAILED,
    NEXT_STAGE_BY_STATE,
    RUN_READY,
    TARGET_STATE_BY_STAGE,
    VERIFIED_READY,
)
from .state import build_state, load_or_initialize_state, save_state
from .verification import verify_diagnosis_claims


STAGE_ORDER = ["evidence_building", "diagnosis", "verification"]


def _stage_index(stage: str) -> int:
    if stage not in STAGE_ORDER:
        raise ValueError(f"Unsupported workflow stage: {stage}. Expected one of {STAGE_ORDER}")
    return STAGE_ORDER.index(stage)


def _next_stage(state: dict[str, Any]) -> str | None:
    return state.get("next_allowed_stage") or NEXT_STAGE_BY_STATE.get(state.get("state"))


def _run_single_stage(model_name: str, run_id: str, stage: str) -> dict[str, Any]:
    if stage == "evidence_building":
        return build_evidence_for_run(model_name, run_id)
    if stage == "diagnosis":
        return diagnose_run_from_evidence(model_name, run_id)
    if stage == "verification":
        return verify_diagnosis_claims(model_name, run_id)
    raise ValueError(f"Unsupported workflow stage: {stage}")


def run_workflow_stage(
    model_name: str,
    run_id: str,
    target_stage: str = "",
    until_stage: str = "",
    rerun: bool = False,
) -> dict[str, Any]:
    """Advance a run through one or more legal workflow stages.

    target_stage executes exactly one stage. until_stage executes sequentially
    until that stage has completed. With neither argument, the next legal stage
    is executed.
    """
    run_root, state = load_or_initialize_state(model_name, run_id)
    model_name = state["model_name"]
    current_stage = _next_stage(state)
    if state.get("state") == FAILED:
        return {
            "ok": False,
            "message": "Workflow is in FAILED state; inspect workflow_state.json errors before continuing.",
            "state": state,
        }
    if current_stage is None and not (rerun and (target_stage or until_stage)):
        return {
            "ok": True,
            "message": "Workflow is already complete for the implemented stages.",
            "state": state,
        }
    if current_stage in {"scenario", "simulation"} and not rerun:
        return {
            "ok": False,
            "message": f"Current state {state['state']} requires {current_stage} stage. Use ScenarioAgent or SimulationAgent for this pre-run stage.",
            "state": state,
        }

    if target_stage and until_stage:
        raise ValueError("Use only one of target_stage or until_stage.")

    stages_to_run: list[str]
    if target_stage:
        if current_stage is not None and target_stage != current_stage and not rerun:
            return {
                "ok": False,
                "message": f"Illegal transition: current state {state['state']} allows {current_stage}, not {target_stage}.",
                "state": state,
            }
        stages_to_run = [target_stage]
    elif until_stage:
        if current_stage is None:
            stages_to_run = STAGE_ORDER[: _stage_index(until_stage) + 1]
        elif _stage_index(until_stage) < _stage_index(current_stage) and not rerun:
            return {
                "ok": True,
                "message": f"Requested stage {until_stage} is already behind current next stage {current_stage}.",
                "state": state,
            }
        else:
            stages_to_run = STAGE_ORDER[_stage_index(current_stage) : _stage_index(until_stage) + 1]
    else:
        stages_to_run = [current_stage]

    stage_results = []
    errors: list[str] = []
    try:
        for stage in stages_to_run:
            result = _run_single_stage(model_name, run_id, stage)
            stage_results.append({"stage": stage, "result": result})
            new_state = TARGET_STATE_BY_STAGE[stage]
            previous_history = list(state.get("history", []))
            state = build_state(model_name, run_id, run_root, state=new_state)
            state["history"] = previous_history
            state["history"].append(
                {
                    "stage": stage,
                    "target_state": new_state,
                    "completed_at": datetime.now().isoformat(timespec="seconds"),
                    "rerun": bool(rerun),
                }
            )
            save_state(run_root, state)
    except Exception as exc:
        errors.append(str(exc))
        state = build_state(model_name, run_id, run_root, state=FAILED, errors=errors)
        save_state(run_root, state)
        return {
            "ok": False,
            "message": f"Workflow stage failed: {exc}",
            "state": state,
            "stage_results": stage_results,
        }

    return {
        "ok": True,
        "message": f"Workflow advanced through: {[item['stage'] for item in stage_results]}",
        "state": state,
        "stage_results": stage_results,
    }


def workflow_result_to_text(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
