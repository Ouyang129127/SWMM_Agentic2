"""Deterministic DiagnosisAgent core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .schemas import DIAGNOSIS_SCHEMA_NAME, WORKFLOW_SCHEMA_VERSION, artifacts_for_run
from .state import resolve_run_root


RULE_PATH = Path(__file__).resolve().parent / "rules" / "diagnosis_rules.json"


def _load_rules() -> dict[str, Any]:
    return json.loads(RULE_PATH.read_text(encoding="utf-8"))


def _severity_for_depth(value: float, rules: dict[str, Any]) -> str:
    depth_rules = rules["surface_depth"]
    if value >= depth_rules["critical_m"]:
        return "critical"
    if value >= depth_rules["high_m"]:
        return "high"
    if value >= depth_rules["moderate_m"]:
        return "moderate"
    return "low"


def _severity_for_fullness(value: float, rules: dict[str, Any]) -> str:
    load_rules = rules.get("link_load", {})
    if value >= float(load_rules.get("fullness_critical", 0.95)):
        return "critical"
    if value >= float(load_rules.get("fullness_high", 0.80)):
        return "high"
    return "moderate"


def _severity_for_direction_changes(value: float, rules: dict[str, Any]) -> str:
    direction_rules = rules.get("flow_direction", {})
    if value >= float(direction_rules.get("critical_changes", 6)):
        return "critical"
    if value >= float(direction_rules.get("frequent_changes", 3)):
        return "high"
    return "moderate"


def _claim_text(claim_type: str, object_id: str, severity: str, value: float, unit: str) -> str:
    if claim_type == "surface_hotspot":
        return f"Cell {object_id} is a {severity} surface ponding hotspot with {value:.3f} {unit} maximum depth."
    if claim_type == "long_duration_ponding":
        return f"Cell {object_id} has long-duration ponding lasting {value:.1f} {unit}."
    if claim_type == "major_overflow_node":
        return f"Node {object_id} is a major overflow node with {value:.3f} {unit} total flooding volume."
    if claim_type == "high_load_link":
        if unit == "ratio":
            return f"Link {object_id} is a {severity} high-load link with {value:.3f} maximum fullness ratio."
        return f"Link {object_id} is a high-load link with {value:.3f} {unit} maximum absolute flow."
    if claim_type == "unstable_flow_direction_link":
        return f"Link {object_id} has unstable flow direction with {value:.0f} flow direction changes."
    return f"{object_id} has a rule-triggered diagnostic signal."


def diagnose_run_from_evidence(model_name: str, run_id: str) -> dict[str, Any]:
    """Generate rule-bound diagnosis claims from evidence_table.csv."""
    run_root = resolve_run_root(model_name, run_id)
    artifacts = artifacts_for_run(run_root)
    if not artifacts.evidence_table.exists():
        raise FileNotFoundError(f"Missing evidence table: {artifacts.evidence_table}")

    rules = _load_rules()
    top_n = int(rules.get("top_n", 10))
    evidence = pd.read_csv(artifacts.evidence_table, dtype={"object_id": str, "evidence_id": str}, low_memory=False)
    evidence["value"] = pd.to_numeric(evidence["value"], errors="coerce").fillna(0.0)
    evidence["rank"] = pd.to_numeric(evidence["rank"], errors="coerce")

    diagnosis_dir = run_root / "diagnosis"
    diagnosis_dir.mkdir(parents=True, exist_ok=True)
    claims: list[dict[str, Any]] = []
    ranking_rows: list[dict[str, Any]] = []

    def add_claim(source: pd.Series, claim_type: str, severity: str, possible_cause: str, confidence: str = "medium") -> None:
        claim_id = f"C{len(claims) + 1:03d}"
        value = float(source["value"])
        claim = {
            "claim_id": claim_id,
            "claim_type": claim_type,
            "object_type": source["object_type"],
            "object_id": str(source["object_id"]),
            "severity": severity,
            "claim_text": _claim_text(claim_type, str(source["object_id"]), severity, value, str(source["unit"])),
            "possible_cause": possible_cause,
            "confidence": confidence,
            "evidence_ids": [str(source["evidence_id"])],
            "status": "pending_verification",
            "rule_id": claim_type,
        }
        claims.append(claim)
        ranking_rows.append(
            {
                "claim_id": claim_id,
                "claim_type": claim_type,
                "object_type": source["object_type"],
                "object_id": source["object_id"],
                "severity": severity,
                "metric_name": source["metric_name"],
                "value": value,
                "unit": source["unit"],
                "evidence_ids": ";".join(claim["evidence_ids"]),
            }
        )

    surface_depth = evidence[
        (evidence["object_type"] == "cell")
        & (evidence["metric_name"] == "max_depth")
        & (evidence["value"] >= float(rules["surface_depth"]["moderate_m"]))
    ].sort_values(["value", "rank"], ascending=[False, True]).head(top_n)
    for _, row in surface_depth.iterrows():
        add_claim(row, "surface_hotspot", _severity_for_depth(float(row["value"]), rules), "local_depression_or_concentrated_overflow")

    ponding = evidence[
        (evidence["object_type"] == "cell")
        & (evidence["metric_name"] == "ponding_duration")
        & (evidence["value"] >= float(rules["ponding_duration"]["long_duration_minutes"]))
    ].sort_values(["value", "rank"], ascending=[False, True]).head(top_n)
    for _, row in ponding.iterrows():
        add_claim(row, "long_duration_ponding", "moderate", "long_duration_surface_ponding")

    overflow = evidence[
        (evidence["object_type"] == "node")
        & (evidence["metric_name"] == "total_flooding_volume")
        & (evidence["value"] >= float(rules["node_flooding"]["significant_volume_m3"]))
    ].sort_values(["value", "rank"], ascending=[False, True]).head(top_n)
    for _, row in overflow.iterrows():
        add_claim(row, "major_overflow_node", "high", "network_overflow_source")

    link_rules = rules.get("link_load", {})
    link_top_n = int(link_rules.get("top_n", top_n))
    fullness_high = float(link_rules.get("fullness_high", 0.80))
    high_load_links = evidence[
        (evidence["object_type"] == "link")
        & (evidence["metric_name"] == "max_fullness")
        & (evidence["value"] >= fullness_high)
    ].sort_values(["value", "rank"], ascending=[False, True]).head(link_top_n)
    for _, row in high_load_links.iterrows():
        add_claim(row, "high_load_link", _severity_for_fullness(float(row["value"]), rules), "possible_network_bottleneck")

    if high_load_links.empty:
        high_load_links = evidence[
            (evidence["object_type"] == "link")
            & (evidence["metric_name"] == "max_flow")
            & (evidence["value"] > 0)
        ].sort_values(["value", "rank"], ascending=[False, True]).head(link_top_n)
        for _, row in high_load_links.iterrows():
            add_claim(row, "high_load_link", "moderate", "possible_network_bottleneck", confidence="low")

    direction_rules = rules.get("flow_direction", {})
    frequent_changes = float(direction_rules.get("frequent_changes", 3))
    direction_top_n = int(direction_rules.get("top_n", top_n))
    unstable_direction_links = evidence[
        (evidence["object_type"] == "link")
        & (evidence["metric_name"] == "flow_direction_changes")
        & (evidence["value"] >= frequent_changes)
    ].sort_values(["value", "rank"], ascending=[False, True]).head(direction_top_n)
    for _, row in unstable_direction_links.iterrows():
        add_claim(
            row,
            "unstable_flow_direction_link",
            _severity_for_direction_changes(float(row["value"]), rules),
            "possible_backwater_or_hydraulic_oscillation",
        )

    payload = {
        "schema_name": DIAGNOSIS_SCHEMA_NAME,
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "run_id": run_id,
        "model_name": run_root.parents[1].name,
        "claim_count": len(claims),
        "claims": claims,
        "rules_file": str(RULE_PATH),
    }
    artifacts.diagnosis_claims.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(ranking_rows).to_csv(artifacts.risk_ranking, index=False, encoding="utf-8")
    return payload
