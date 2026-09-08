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


def _severity_rank(severity: str) -> int:
    return {
        "critical": 4,
        "high": 3,
        "moderate": 2,
        "low": 1,
    }.get(severity, 0)


def _severity_for_surface_ponding(depth_m: float, duration_min: float, rules: dict[str, Any]) -> str:
    risk_rules = rules.get("surface_ponding_risk", {})
    if (
        depth_m >= float(risk_rules.get("critical_depth_m", 0.6))
        and duration_min >= float(risk_rules.get("critical_duration_minutes", 120))
    ):
        return "critical"
    if depth_m >= float(risk_rules.get("force_high_depth_m", 0.6)):
        return "high"
    if (
        depth_m >= float(risk_rules.get("high_depth_m", 0.4))
        and duration_min >= float(risk_rules.get("high_duration_minutes", 120))
    ):
        return "high"
    if (
        depth_m >= float(risk_rules.get("moderate_depth_m", 0.27))
        and duration_min >= float(risk_rules.get("moderate_duration_minutes", 60))
    ):
        return "moderate"
    if (
        depth_m >= float(risk_rules.get("low_depth_m", 0.15))
        and duration_min >= float(risk_rules.get("low_duration_minutes", 30))
    ):
        return "low"
    return "none"


def _severity_for_fullness(value: float, rules: dict[str, Any]) -> str:
    load_rules = rules.get("link_load", {})
    if value > float(load_rules.get("fullness_surcharge", 1.0)):
        return "critical"
    if value >= float(load_rules.get("fullness_high", 0.80)):
        return "high"
    return "moderate"


def _severity_for_link_fullness(max_fullness: float, high_duration: float, near_full_duration: float, surcharge_duration: float, rules: dict[str, Any]) -> str:
    load_rules = rules.get("link_load", {})
    if max_fullness > float(load_rules.get("fullness_surcharge", 1.0)) or surcharge_duration > float(load_rules.get("surcharge_duration_minutes", 0)):
        return "critical"
    if max_fullness >= float(load_rules.get("fullness_high", 0.95)) or near_full_duration >= float(load_rules.get("near_full_duration_minutes", 15)):
        return "high"
    if max_fullness >= float(load_rules.get("fullness_warning", 0.8)) or high_duration >= float(load_rules.get("warning_duration_minutes", 30)):
        return "moderate"
    return "none"


def _severity_for_direction_changes(value: float, rules: dict[str, Any]) -> str:
    direction_rules = rules.get("flow_direction", {})
    if value >= float(direction_rules.get("critical_changes", 6)):
        return "critical"
    if value >= float(direction_rules.get("frequent_changes", 3)):
        return "high"
    return "moderate"


def _severity_for_relation_signal(signal_type: str, package: dict[str, Any], rules: dict[str, Any]) -> str:
    if signal_type == "surface_response":
        max_depth = float(package.get("surface_context", {}).get("ponding_cluster", {}).get("max_depth_m", 0.0) or 0.0)
        return _severity_for_depth(max_depth, rules)
    if signal_type in {"downstream_high_fullness", "upstream_high_load"}:
        links = package.get("network_context", {}).get("connected_links", [])
        direction = "downstream" if signal_type == "downstream_high_fullness" else "upstream"
        max_fullness = max(
            [float(link.get("max_fullness", 0.0) or 0.0) for link in links if link.get("position") == direction] or [0.0]
        )
        return _severity_for_fullness(max_fullness, rules)
    if signal_type == "flow_direction_instability":
        links = package.get("network_context", {}).get("connected_links", [])
        max_changes = max([float(link.get("flow_direction_changes", 0.0) or 0.0) for link in links] or [0.0])
        return _severity_for_direction_changes(max_changes, rules)
    if signal_type == "repeated_overflow":
        event_count = float(package.get("node_evidence", {}).get("overflow_event_count", 0.0) or 0.0)
        critical_count = float(rules.get("node_flooding", {}).get("repeated_event_count", 2)) + 2
        return "critical" if event_count >= critical_count else "high"
    return "moderate"


def _claim_text(claim_type: str, object_id: str, severity: str, value: float, unit: str) -> str:
    if claim_type == "surface_ponding_risk":
        return f"Cell {object_id} is a {severity} surface ponding risk area based on joint depth-duration evidence."
    if claim_type == "surface_hotspot":
        return f"Cell {object_id} is a {severity} surface ponding hotspot with {value:.3f} {unit} maximum depth."
    if claim_type == "long_duration_ponding":
        return f"Cell {object_id} has long-duration ponding lasting {value:.1f} {unit}."
    if claim_type == "major_overflow_node":
        return f"Node {object_id} is a major overflow node with {value:.3f} {unit} total flooding volume."
    if claim_type == "high_load_link":
        if unit == "ratio":
            return f"Link {object_id} has {severity} hydraulic loading based on fullness magnitude and duration evidence."
        return f"Link {object_id} is a high-load link with {value:.3f} {unit} maximum absolute flow."
    if claim_type == "unstable_flow_direction_link":
        return f"Link {object_id} has unstable flow direction with {value:.0f} flow direction changes."
    if claim_type == "node_overflow_with_surface_ponding":
        return f"Node {object_id} overflow is spatially associated with nearby surface ponding evidence."
    if claim_type == "node_overflow_with_downstream_high_fullness":
        return f"Node {object_id} overflow is associated with high-fullness downstream conduit evidence."
    if claim_type == "node_overflow_with_upstream_high_load":
        return f"Node {object_id} overflow is associated with high-load upstream conduit evidence."
    if claim_type == "node_overflow_with_flow_direction_instability":
        return f"Node {object_id} overflow is associated with unstable flow-direction evidence in connected conduits."
    if claim_type == "node_repeated_overflow":
        return f"Node {object_id} shows repeated overflow event evidence."
    return f"{object_id} has a rule-triggered diagnostic signal."


def _relation_path_ids(package: dict[str, Any], path_type: str) -> list[str]:
    return [
        str(path.get("path_id"))
        for path in package.get("relation_paths", [])
        if path.get("path_type") == path_type and path.get("path_id")
    ]


def _relation_path_evidence_ids(package: dict[str, Any], path_type: str) -> list[str]:
    evidence_ids: list[str] = []
    for path in package.get("relation_paths", []):
        if path.get("path_type") != path_type:
            continue
        evidence_ids.extend(str(item) for item in path.get("evidence_ids", []) if str(item).strip())
    return sorted(set(evidence_ids))


def _connected_link_evidence_ids(package: dict[str, Any], position: str = "") -> list[str]:
    evidence_ids: list[str] = []
    for link in package.get("network_context", {}).get("connected_links", []):
        if position and link.get("position") != position:
            continue
        evidence_ids.extend(str(item) for item in link.get("evidence_ids", []) if str(item).strip())
    return sorted(set(evidence_ids))


def _append_relation_claims(
    claims: list[dict[str, Any]],
    ranking_rows: list[dict[str, Any]],
    artifacts: Any,
    rules: dict[str, Any],
) -> None:
    if not artifacts.overflow_node_evidence_packages.exists():
        return
    packages_payload = json.loads(artifacts.overflow_node_evidence_packages.read_text(encoding="utf-8"))

    def add_relation_claim(
        package: dict[str, Any],
        claim_type: str,
        severity: str,
        possible_cause: str,
        evidence_ids: list[str],
        relation_path_ids: list[str],
        value: float,
        metric_name: str,
        unit: str = "signal",
        confidence: str = "high",
    ) -> None:
        if not evidence_ids or not relation_path_ids:
            confidence = "medium" if evidence_ids else "low"
        claim_id = f"C{len(claims) + 1:03d}"
        anchor = package.get("anchor", {})
        object_id = str(anchor.get("id", ""))
        claim = {
            "claim_id": claim_id,
            "claim_type": claim_type,
            "object_type": "node",
            "object_id": object_id,
            "severity": severity,
            "claim_text": _claim_text(claim_type, object_id, severity, value, unit),
            "possible_cause": possible_cause,
            "confidence": confidence,
            "evidence_ids": sorted(set(evidence_ids)),
            "relation_path_ids": relation_path_ids,
            "package_id": package.get("package_id"),
            "rainfall_context": package.get("rainfall_context", {}),
            "status": "pending_verification",
            "rule_id": claim_type,
        }
        claims.append(claim)
        ranking_rows.append(
            {
                "claim_id": claim_id,
                "claim_type": claim_type,
                "object_type": "node",
                "object_id": object_id,
                "severity": severity,
                "metric_name": metric_name,
                "value": value,
                "unit": unit,
                "evidence_ids": ";".join(claim["evidence_ids"]),
                "relation_path_ids": ";".join(relation_path_ids),
                "package_id": package.get("package_id", ""),
            }
        )

    for package in packages_payload.get("packages", []):
        signals = package.get("diagnosis_ready_signals", {})
        anchor_evidence_ids = [str(item) for item in package.get("anchor", {}).get("evidence_ids", []) if str(item).strip()]
        if signals.get("has_surface_ponding_nearby"):
            evidence_ids = anchor_evidence_ids + _relation_path_evidence_ids(package, "surface_response")
            cluster = package.get("surface_context", {}).get("ponding_cluster", {})
            add_relation_claim(
                package,
                "node_overflow_with_surface_ponding",
                _severity_for_relation_signal("surface_response", package, rules),
                "overflow_surface_ponding_coupling",
                evidence_ids,
                _relation_path_ids(package, "surface_response"),
                float(cluster.get("max_depth_m", 0.0) or 0.0),
                "relation_surface_max_depth",
                "m",
            )
        if signals.get("has_downstream_high_fullness"):
            downstream_links = [
                link for link in package.get("network_context", {}).get("connected_links", []) if link.get("position") == "downstream"
            ]
            max_fullness = max([float(link.get("max_fullness", 0.0) or 0.0) for link in downstream_links] or [0.0])
            add_relation_claim(
                package,
                "node_overflow_with_downstream_high_fullness",
                _severity_for_relation_signal("downstream_high_fullness", package, rules),
                "possible_downstream_bottleneck_or_backwater",
                anchor_evidence_ids + _connected_link_evidence_ids(package, "downstream"),
                _relation_path_ids(package, "network_pressure"),
                max_fullness,
                "relation_downstream_max_fullness",
                "ratio",
            )
        if signals.get("has_upstream_high_load"):
            upstream_links = [
                link for link in package.get("network_context", {}).get("connected_links", []) if link.get("position") == "upstream"
            ]
            max_fullness = max([float(link.get("max_fullness", 0.0) or 0.0) for link in upstream_links] or [0.0])
            add_relation_claim(
                package,
                "node_overflow_with_upstream_high_load",
                _severity_for_relation_signal("upstream_high_load", package, rules),
                "possible_upstream_concentrated_inflow",
                anchor_evidence_ids + _connected_link_evidence_ids(package, "upstream"),
                _relation_path_ids(package, "network_pressure"),
                max_fullness,
                "relation_upstream_max_fullness",
                "ratio",
            )
        if signals.get("has_flow_direction_instability"):
            max_changes = max(
                [
                    float(link.get("flow_direction_changes", 0.0) or 0.0)
                    for link in package.get("network_context", {}).get("connected_links", [])
                ]
                or [0.0]
            )
            add_relation_claim(
                package,
                "node_overflow_with_flow_direction_instability",
                _severity_for_relation_signal("flow_direction_instability", package, rules),
                "possible_backwater_or_hydraulic_oscillation_near_overflow_node",
                anchor_evidence_ids + _connected_link_evidence_ids(package),
                _relation_path_ids(package, "network_pressure"),
                max_changes,
                "relation_flow_direction_changes",
                "count",
            )
        if signals.get("has_repeated_overflow"):
            event_count = float(package.get("node_evidence", {}).get("overflow_event_count", 0.0) or 0.0)
            add_relation_claim(
                package,
                "node_repeated_overflow",
                _severity_for_relation_signal("repeated_overflow", package, rules),
                "repeated_network_overflow_signal",
                anchor_evidence_ids,
                _relation_path_ids(package, "network_pressure") or _relation_path_ids(package, "surface_response"),
                event_count,
                "overflow_event_count",
                "count",
            )


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

    def add_claim(
        source: pd.Series,
        claim_type: str,
        severity: str,
        possible_cause: str,
        confidence: str = "medium",
        evidence_ids: list[str] | None = None,
        ranking_extra: dict[str, Any] | None = None,
    ) -> None:
        claim_id = f"C{len(claims) + 1:03d}"
        value = float(source["value"])
        claim_evidence_ids = evidence_ids or [str(source["evidence_id"])]
        claim = {
            "claim_id": claim_id,
            "claim_type": claim_type,
            "object_type": source["object_type"],
            "object_id": str(source["object_id"]),
            "severity": severity,
            "claim_text": _claim_text(claim_type, str(source["object_id"]), severity, value, str(source["unit"])),
            "possible_cause": possible_cause,
            "confidence": confidence,
            "evidence_ids": sorted(set(claim_evidence_ids)),
            "status": "pending_verification",
            "rule_id": claim_type,
        }
        claims.append(claim)
        row_payload = {
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
        if ranking_extra:
            row_payload.update(ranking_extra)
        ranking_rows.append(row_payload)

    surface_depth = evidence[
        (evidence["object_type"] == "cell")
        & (evidence["metric_name"] == "max_depth")
    ][["object_id", "value", "unit", "evidence_id", "rank"]].rename(
        columns={
            "value": "depth_m",
            "unit": "depth_unit",
            "evidence_id": "depth_evidence_id",
            "rank": "depth_rank",
        }
    )
    ponding_duration = evidence[
        (evidence["object_type"] == "cell")
        & (evidence["metric_name"] == "ponding_duration")
    ][["object_id", "value", "unit", "evidence_id", "rank"]].rename(
        columns={
            "value": "duration_min",
            "unit": "duration_unit",
            "evidence_id": "duration_evidence_id",
            "rank": "duration_rank",
        }
    )
    surface_risk = surface_depth.merge(ponding_duration, on="object_id", how="inner")
    if not surface_risk.empty:
        surface_risk["severity"] = surface_risk.apply(
            lambda row: _severity_for_surface_ponding(float(row["depth_m"]), float(row["duration_min"]), rules),
            axis=1,
        )
        surface_risk["severity_score"] = surface_risk["severity"].map(_severity_rank)
        surface_risk = surface_risk[surface_risk["severity"] != "none"]
        surface_risk = surface_risk.sort_values(
            ["severity_score", "depth_m", "duration_min", "depth_rank"],
            ascending=[False, False, False, True],
        ).head(top_n)
        for _, row in surface_risk.iterrows():
            source = pd.Series(
                {
                    "object_type": "cell",
                    "object_id": row["object_id"],
                    "metric_name": "surface_ponding_depth_duration",
                    "value": row["depth_m"],
                    "unit": "m",
                    "evidence_id": row["depth_evidence_id"],
                }
            )
            add_claim(
                source,
                "surface_ponding_risk",
                str(row["severity"]),
                "depth_duration_surface_ponding_risk",
                evidence_ids=[str(row["depth_evidence_id"]), str(row["duration_evidence_id"])],
                ranking_extra={
                    "severity_score": int(row["severity_score"]),
                    "max_depth_m": float(row["depth_m"]),
                    "ponding_duration_min": float(row["duration_min"]),
                    "duration_evidence_id": str(row["duration_evidence_id"]),
                },
            )

    overflow = evidence[
        (evidence["object_type"] == "node")
        & (evidence["metric_name"] == "total_flooding_volume")
        & (evidence["value"] >= float(rules["node_flooding"]["significant_volume_m3"]))
    ].sort_values(["value", "rank"], ascending=[False, True]).head(top_n)
    for _, row in overflow.iterrows():
        add_claim(row, "major_overflow_node", "high", "network_overflow_source")

    link_rules = rules.get("link_load", {})
    link_top_n = int(link_rules.get("top_n", top_n))
    fullness_warning = float(link_rules.get("fullness_warning", 0.80))
    link_fullness = evidence[
        (evidence["object_type"] == "link")
        & (evidence["metric_name"] == "max_fullness")
    ][["object_id", "value", "unit", "evidence_id", "rank"]].rename(
        columns={"value": "max_fullness", "unit": "fullness_unit", "evidence_id": "fullness_evidence_id", "rank": "fullness_rank"}
    )
    link_duration_metrics = evidence[
        (evidence["object_type"] == "link")
        & (evidence["metric_name"].isin(["fullness_ge_0_8_duration", "fullness_ge_0_95_duration", "surcharge_duration"]))
    ][["object_id", "metric_name", "value", "evidence_id"]]
    if not link_duration_metrics.empty:
        link_duration_values = link_duration_metrics.pivot_table(index="object_id", columns="metric_name", values="value", aggfunc="max").reset_index()
        link_duration_evidence = link_duration_metrics.pivot_table(index="object_id", columns="metric_name", values="evidence_id", aggfunc="first").reset_index()
        link_duration_evidence = link_duration_evidence.rename(
            columns={
                "fullness_ge_0_8_duration": "fullness_ge_0_8_evidence_id",
                "fullness_ge_0_95_duration": "fullness_ge_0_95_evidence_id",
                "surcharge_duration": "surcharge_duration_evidence_id",
            }
        )
        high_load_links = link_fullness.merge(link_duration_values, on="object_id", how="left").merge(link_duration_evidence, on="object_id", how="left")
    else:
        high_load_links = link_fullness.copy()
    for column in ["fullness_ge_0_8_duration", "fullness_ge_0_95_duration", "surcharge_duration"]:
        if column not in high_load_links.columns:
            high_load_links[column] = 0.0
        high_load_links[column] = pd.to_numeric(high_load_links[column], errors="coerce").fillna(0.0)
    if not high_load_links.empty:
        high_load_links["severity"] = high_load_links.apply(
            lambda row: _severity_for_link_fullness(
                float(row["max_fullness"]),
                float(row["fullness_ge_0_8_duration"]),
                float(row["fullness_ge_0_95_duration"]),
                float(row["surcharge_duration"]),
                rules,
            ),
            axis=1,
        )
        high_load_links["severity_score"] = high_load_links["severity"].map(_severity_rank)
        high_load_links = high_load_links[high_load_links["severity"] != "none"]
        high_load_links = high_load_links.sort_values(
            ["severity_score", "max_fullness", "fullness_ge_0_95_duration", "fullness_ge_0_8_duration", "fullness_rank"],
            ascending=[False, False, False, False, True],
        ).head(link_top_n)
    for _, row in high_load_links.iterrows():
        evidence_ids = [
            str(row.get("fullness_evidence_id", "")),
            str(row.get("fullness_ge_0_8_evidence_id", "")),
            str(row.get("fullness_ge_0_95_evidence_id", "")),
            str(row.get("surcharge_duration_evidence_id", "")),
        ]
        evidence_ids = [evidence_id for evidence_id in evidence_ids if evidence_id and evidence_id != "nan"]
        source = pd.Series(
            {
                "object_type": "link",
                "object_id": row["object_id"],
                "metric_name": "link_fullness_load",
                "value": row["max_fullness"],
                "unit": "ratio",
                "evidence_id": row["fullness_evidence_id"],
            }
        )
        add_claim(
            source,
            "high_load_link",
            str(row["severity"]),
            "possible_network_bottleneck",
            evidence_ids=evidence_ids,
            ranking_extra={
                "severity_score": int(row["severity_score"]),
                "max_fullness": float(row["max_fullness"]),
                "fullness_ge_0_8_duration_min": float(row["fullness_ge_0_8_duration"]),
                "fullness_ge_0_95_duration_min": float(row["fullness_ge_0_95_duration"]),
                "surcharge_duration_min": float(row["surcharge_duration"]),
            },
        )

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

    _append_relation_claims(claims, ranking_rows, artifacts, rules)

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
