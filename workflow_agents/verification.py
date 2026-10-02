"""Deterministic VerificationAgent core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .schemas import VERIFICATION_SCHEMA_NAME, WORKFLOW_SCHEMA_VERSION, artifacts_for_run
from .state import resolve_run_root


RULE_PATH = Path(__file__).resolve().parent / "rules" / "verification_rules.json"


def _load_rules() -> dict[str, Any]:
    return json.loads(RULE_PATH.read_text(encoding="utf-8"))


def _legacy_verify_diagnosis_claims(model_name: str, run_id: str) -> dict[str, Any]:
    """Verify diagnosis claims against evidence_table.csv and calculate unsupported rate."""
    run_root = resolve_run_root(model_name, run_id)
    artifacts = artifacts_for_run(run_root)
    if not artifacts.evidence_table.exists():
        raise FileNotFoundError(f"Missing evidence table: {artifacts.evidence_table}")
    if not artifacts.diagnosis_claims.exists():
        raise FileNotFoundError(f"Missing diagnosis claims: {artifacts.diagnosis_claims}")

    rules = _load_rules()
    evidence = pd.read_csv(artifacts.evidence_table, dtype={"evidence_id": str, "object_id": str})
    evidence["value"] = pd.to_numeric(evidence["value"], errors="coerce").fillna(0.0)
    evidence_by_id = {str(row["evidence_id"]): row for _, row in evidence.iterrows()}
    claims_payload = json.loads(artifacts.diagnosis_claims.read_text(encoding="utf-8"))

    checks: list[dict[str, Any]] = []
    counts = {"supported": 0, "partially_supported": 0, "unsupported": 0, "uncertain": 0}
    required_by_type = rules["required_metrics_by_claim_type"]
    require_all_by_type = rules.get("require_all_metrics_by_claim_type", {})

    for claim in claims_payload.get("claims", []):
        issues: list[str] = []
        evidence_ids = [str(item) for item in claim.get("evidence_ids", []) if str(item).strip()]
        matched_evidence = []
        if not evidence_ids:
            issues.append("missing evidence_ids")
        for evidence_id in evidence_ids:
            row = evidence_by_id.get(evidence_id)
            if row is None:
                issues.append(f"evidence_id not found: {evidence_id}")
            else:
                matched_evidence.append(row)

        claim_type = claim.get("claim_type", "")
        required_metrics = required_by_type.get(claim_type, [])
        matched_metrics = {str(row["metric_name"]) for row in matched_evidence}
        if required_metrics and require_all_by_type.get(claim_type):
            missing_metrics = [metric for metric in required_metrics if metric not in matched_metrics]
            if missing_metrics:
                issues.append(f"required metric missing for {claim_type}: {missing_metrics}")
        elif required_metrics and not any(metric in required_metrics for metric in matched_metrics):
            issues.append(f"required metric missing for {claim_type}: {required_metrics}")

        claim_object_id = str(claim.get("object_id", ""))
        if matched_evidence and not any(str(row["object_id"]) == claim_object_id for row in matched_evidence):
            issues.append("claim object_id is not matched by cited evidence")

        if matched_evidence and not any(float(row["value"]) > 0 for row in matched_evidence):
            issues.append("cited evidence value is not positive")

        if not matched_evidence:
            status = "unsupported"
        elif not issues:
            status = "supported"
        elif any(issue.startswith("evidence_id not found") or issue == "missing evidence_ids" for issue in issues):
            status = "unsupported"
        else:
            status = "partially_supported"
        counts[status] += 1
        checks.append(
            {
                "claim_id": claim.get("claim_id"),
                "verification_status": status,
                "checked_evidence_ids": evidence_ids,
                "issues": issues,
            }
        )

    total = len(checks)
    unsupported_rate = (counts["unsupported"] / total) if total else 0.0
    payload = {
        "schema_name": VERIFICATION_SCHEMA_NAME,
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "run_id": run_id,
        "model_name": run_root.parents[1].name,
        "summary": {
            "total_claims": total,
            "supported": counts["supported"],
            "partially_supported": counts["partially_supported"],
            "unsupported": counts["unsupported"],
            "uncertain": counts["uncertain"],
            "unsupported_rate": unsupported_rate,
        },
        "claim_checks": checks,
        "rules_file": str(RULE_PATH),
    }
    verification_dir = run_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    artifacts.verification_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts.unsupported_rate.write_text(f"{unsupported_rate:.6f}\n", encoding="utf-8")
    return payload


def verify_diagnosis_claims(model_name: str, run_id: str) -> dict[str, Any]:
    """Check current-run references; does not validate hydraulic reasoning."""
    import csv
    from .reference_checks import check_references, sha256_file
    root = resolve_run_root(model_name, run_id)
    artifacts = artifacts_for_run(root)
    claims = json.loads(artifacts.diagnosis_claims.read_text(encoding='utf-8'))
    with artifacts.evidence_table.open(encoding='utf-8-sig', newline='') as stream:
        evidence = list(csv.DictReader(stream))
    payload = check_references(claims, evidence, root.parents[1].name, root.name)
    payload['input_hashes'] = {'evidence_table': sha256_file(artifacts.evidence_table),
                               'diagnosis_claims': sha256_file(artifacts.diagnosis_claims)}
    artifacts.verification_report.parent.mkdir(parents=True, exist_ok=True)
    artifacts.verification_report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    # Legacy path retained for state detection; metric now means reference failure.
    rate = payload['summary']['reference_failure_rate']
    artifacts.unsupported_rate.write_text('N/A\n' if rate is None else f'{rate:.6f}\n', encoding='utf-8')
    return payload
