"""Workflow-stage agents for the SWMM-CA2D diagnostic pipeline."""

from .evidence_builder import build_evidence_for_run
from .evidence_graph import build_evidence_graph_for_run
from .rainfall_context import build_rainfall_context
from .diagnosis import diagnose_run_from_evidence
from .orchestrator import run_workflow_stage
from .report import explain_one_flood_point, generate_report_for_request, generate_run_report
from .scenario import load_scenario_request, prepare_scenario_request
from .verification import verify_diagnosis_claims

__all__ = [
    "build_evidence_for_run",
    "build_evidence_graph_for_run",
    "build_rainfall_context",
    "diagnose_run_from_evidence",
    "explain_one_flood_point",
    "generate_report_for_request",
    "generate_run_report",
    "load_scenario_request",
    "prepare_scenario_request",
    "run_workflow_stage",
    "verify_diagnosis_claims",
]
