"""Shared schema names, state names, and artifact conventions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


WORKFLOW_SCHEMA_NAME = "swmm_ca2d_workflow_state"
WORKFLOW_SCHEMA_VERSION = "0.1"

SCENARIO_REQUEST_SCHEMA_NAME = "swmm_ca2d_scenario_request"
EVIDENCE_SCHEMA_NAME = "swmm_ca2d_evidence_table"
DIAGNOSIS_SCHEMA_NAME = "swmm_ca2d_diagnosis_claims"
VERIFICATION_SCHEMA_NAME = "swmm_ca2d_verification_report"

START = "START"
SCENARIO_READY = "SCENARIO_READY"
RUN_READY = "RUN_READY"
EVIDENCE_READY = "EVIDENCE_READY"
DIAGNOSIS_READY = "DIAGNOSIS_READY"
VERIFIED_READY = "VERIFIED_READY"
FAILED = "FAILED"

NEXT_STAGE_BY_STATE = {
    START: "scenario",
    SCENARIO_READY: "simulation",
    RUN_READY: "evidence_building",
    EVIDENCE_READY: "diagnosis",
    DIAGNOSIS_READY: "verification",
    VERIFIED_READY: None,
    FAILED: None,
}

TARGET_STATE_BY_STAGE = {
    "scenario": SCENARIO_READY,
    "simulation": RUN_READY,
    "evidence_building": EVIDENCE_READY,
    "diagnosis": DIAGNOSIS_READY,
    "verification": VERIFIED_READY,
}

COMPLETED_STAGE_BY_STATE = {
    SCENARIO_READY: "scenario",
    RUN_READY: "simulation",
    EVIDENCE_READY: "evidence_building",
    DIAGNOSIS_READY: "diagnosis",
    VERIFIED_READY: "verification",
}


@dataclass(frozen=True)
class RunArtifacts:
    scenario_request: Path
    run_summary: Path
    run_metadata: Path
    swmm_node_flooding: Path
    swmm_nodes: Path
    swmm_links: Path
    ca2d_surface_depth: Path
    evidence_table: Path
    evidence_summary: Path
    diagnosis_claims: Path
    risk_ranking: Path
    verification_report: Path
    unsupported_rate: Path


def artifacts_for_run(run_root: Path) -> RunArtifacts:
    return RunArtifacts(
        scenario_request=run_root / "scenario_request.json",
        run_summary=run_root / "summary.json",
        run_metadata=run_root / "run.yaml",
        swmm_node_flooding=run_root / "swmm" / "node_flooding.tsv",
        swmm_nodes=run_root / "swmm" / "nodes.tsv",
        swmm_links=run_root / "swmm" / "links.tsv",
        ca2d_surface_depth=run_root / "ca2d" / "surface_depth.tsv",
        evidence_table=run_root / "evidence" / "evidence_table.csv",
        evidence_summary=run_root / "evidence" / "evidence_summary.json",
        diagnosis_claims=run_root / "diagnosis" / "diagnosis_claims.json",
        risk_ranking=run_root / "diagnosis" / "risk_ranking.csv",
        verification_report=run_root / "verification" / "verification_report.json",
        unsupported_rate=run_root / "verification" / "unsupported_rate.txt",
    )
