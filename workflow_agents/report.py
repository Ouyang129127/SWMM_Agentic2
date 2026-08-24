"""Evidence-grounded ReportAgent for user-facing SWMM-CA2D explanations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .schemas import VERIFIED_READY, artifacts_for_run
from .state import load_or_initialize_state, resolve_run_root


REPORT_SCHEMA_NAME = "swmm_ca2d_report"
REPORT_SCHEMA_VERSION = "0.1"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required ReportAgent input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_value(value: Any, unit: str = "") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{value} {unit}".strip()
    if unit == "ratio":
        return f"{number:.3f}"
    if abs(number) >= 100:
        text = f"{number:.1f}"
    elif abs(number) >= 10:
        text = f"{number:.2f}"
    else:
        text = f"{number:.3f}"
    return f"{text} {unit}".strip()


def _load_report_inputs(model_name: str, run_id: str) -> tuple[Path, dict[str, Any], dict[str, Any], pd.DataFrame, dict[str, Any], pd.DataFrame, dict[str, Any]]:
    run_root, state = load_or_initialize_state(model_name, run_id)
    if state.get("state") != VERIFIED_READY:
        raise ValueError(
            f"ReportAgent requires VERIFIED_READY, but current state is {state.get('state')}. "
            "Please finish diagnosis verification first."
        )

    artifacts = artifacts_for_run(run_root)
    summary = _read_json(artifacts.run_summary)
    evidence_summary = _read_json(artifacts.evidence_summary)
    diagnosis = _read_json(artifacts.diagnosis_claims)
    verification = _read_json(artifacts.verification_report)
    if not artifacts.evidence_table.exists():
        raise FileNotFoundError(f"Missing required ReportAgent input: {artifacts.evidence_table}")
    if not artifacts.risk_ranking.exists():
        raise FileNotFoundError(f"Missing required ReportAgent input: {artifacts.risk_ranking}")

    evidence = pd.read_csv(artifacts.evidence_table, dtype={"evidence_id": str, "object_id": str}, low_memory=False)
    risk_ranking = pd.read_csv(artifacts.risk_ranking, dtype={"claim_id": str, "object_id": str}, low_memory=False)
    evidence["value"] = pd.to_numeric(evidence["value"], errors="coerce").fillna(0.0)
    risk_ranking["value"] = pd.to_numeric(risk_ranking["value"], errors="coerce").fillna(0.0)
    return run_root, state, summary, evidence, diagnosis, risk_ranking, verification


def _verification_status_by_claim(verification: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("claim_id")): str(item.get("verification_status", "uncertain"))
        for item in verification.get("claim_checks", [])
    }


def _evidence_by_id(evidence: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {str(row["evidence_id"]): row.to_dict() for _, row in evidence.iterrows()}


def _claims_with_status(diagnosis: dict[str, Any], verification: dict[str, Any]) -> list[dict[str, Any]]:
    status_by_claim = _verification_status_by_claim(verification)
    claims = []
    for claim in diagnosis.get("claims", []):
        item = dict(claim)
        item["verification_status"] = status_by_claim.get(str(item.get("claim_id")), "uncertain")
        claims.append(item)
    return claims


def _supported_claims(diagnosis: dict[str, Any], verification: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        claim
        for claim in _claims_with_status(diagnosis, verification)
        if claim.get("verification_status") in {"supported", "partially_supported"}
    ]


def _top_rows(risk_ranking: pd.DataFrame, claim_type: str, limit: int = 5) -> pd.DataFrame:
    subset = risk_ranking[risk_ranking["claim_type"] == claim_type].copy()
    if subset.empty:
        return subset
    return subset.sort_values("value", ascending=False).head(limit)


def _claim_type_title(claim_type: str) -> str:
    return {
        "surface_hotspot": "地表积水热点",
        "long_duration_ponding": "长时间积水区域",
        "major_overflow_node": "主要冒溢节点",
        "high_load_link": "高负荷管段",
        "unstable_flow_direction_link": "流向不稳定管段",
    }.get(claim_type, claim_type)


def _metric_label(metric_name: str) -> str:
    return {
        "max_depth": "最大地表积水深度",
        "ponding_duration": "积水持续时间",
        "total_flooding_volume": "累计溢流量",
        "max_flooding_flow": "最大溢流流量",
        "flooding_duration": "节点溢流持续时间",
        "max_node_depth": "节点最大水深",
        "max_fullness": "最大充满度",
        "max_flow": "最大绝对流量",
        "max_link_depth": "管段最大水深",
        "flow_direction_changes": "流向改变次数",
    }.get(metric_name, metric_name)


def _claim_status_lookup(verification: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("claim_id")): str(item.get("verification_status", "uncertain"))
        for item in verification.get("claim_checks", [])
    }


def _append_claim_rows(lines: list[str], rows: pd.DataFrame, verification: dict[str, Any]) -> None:
    if rows.empty:
        lines.append("- 未生成该类型诊断结论。")
        return
    status_by_claim = _claim_status_lookup(verification)
    for _, row in rows.iterrows():
        claim_id = str(row.get("claim_id", ""))
        metric_name = str(row.get("metric_name", ""))
        status = status_by_claim.get(claim_id, "uncertain")
        lines.append(
            f"- `{claim_id}` {row.get('object_type')} `{row.get('object_id')}`："
            f"{_metric_label(metric_name)} {_fmt_value(row.get('value'), str(row.get('unit', '')))}，"
            f"风险等级 `{row.get('severity', '')}`，核查 `{status}`，证据 `{row.get('evidence_ids', '')}`。"
        )


def _claim_evidence_lines(claim: dict[str, Any], evidence_lookup: dict[str, dict[str, Any]]) -> list[str]:
    lines = []
    for evidence_id in claim.get("evidence_ids", []):
        row = evidence_lookup.get(str(evidence_id))
        if not row:
            continue
        lines.append(
            f"- `{evidence_id}`: {row.get('object_type')} `{row.get('object_id')}` 的 "
            f"`{row.get('metric_name')}` 为 {_fmt_value(row.get('value'), str(row.get('unit', '')))}，"
            f"时间范围 {row.get('time_start', '')} 至 {row.get('time_end', '')}。"
        )
    return lines


def _choose_explanation_claim(claims: list[dict[str, Any]], risk_ranking: pd.DataFrame) -> dict[str, Any] | None:
    preferred_types = ["surface_hotspot", "long_duration_ponding", "major_overflow_node"]
    ranking_by_claim = {
        str(row["claim_id"]): float(row["value"])
        for _, row in risk_ranking.iterrows()
        if str(row.get("claim_id", "")).strip()
    }
    verified_claims = [
        claim
        for claim in claims
        if claim.get("verification_status") in {"supported", "partially_supported"}
    ]
    for claim_type in preferred_types:
        candidates = [claim for claim in verified_claims if claim.get("claim_type") == claim_type]
        if candidates:
            return sorted(candidates, key=lambda item: ranking_by_claim.get(str(item.get("claim_id")), 0.0), reverse=True)[0]
    if not verified_claims:
        return None
    return sorted(verified_claims, key=lambda item: ranking_by_claim.get(str(item.get("claim_id")), 0.0), reverse=True)[0]


def _infer_point_causes(claim: dict[str, Any], evidence: pd.DataFrame) -> list[str]:
    causes = []
    object_id = str(claim.get("object_id", ""))
    object_type = str(claim.get("object_type", ""))
    claim_type = str(claim.get("claim_type", ""))

    if claim_type == "surface_hotspot":
        causes.append("该位置的最大地表积水深度已经达到规则阈值，说明局部承载或排泄能力不足。")
    if claim_type == "long_duration_ponding":
        causes.append("该位置积水持续时间较长，说明退水过程偏慢，风险不只是瞬时水深峰值。")
    if claim_type == "major_overflow_node":
        causes.append("对应节点存在显著溢流体积，管网外溢可能是该风险点的重要水源。")

    if object_type == "cell":
        overflow = evidence[(evidence["object_type"] == "node") & (evidence["metric_name"] == "total_flooding_volume")]
        overflow = overflow.sort_values("value", ascending=False).head(3)
        if not overflow.empty and float(overflow.iloc[0]["value"]) > 0:
            top = overflow.iloc[0]
            causes.append(
                f"本次运行中高溢流节点 `{top['object_id']}` 的总溢流体积为 "
                f"{_fmt_value(top['value'], str(top.get('unit', '')))}，提示地表积水可能与管网节点外溢叠加有关。"
            )
        link_load = evidence[(evidence["object_type"] == "link") & (evidence["metric_name"] == "max_fullness")]
        if link_load.empty:
            link_load = evidence[(evidence["object_type"] == "link") & (evidence["metric_name"] == "max_flow")]
        link_load = link_load.sort_values("value", ascending=False).head(3)
        if not link_load.empty and float(link_load.iloc[0]["value"]) > 0:
            top = link_load.iloc[0]
            label = "最大充满度" if str(top.get("metric_name", "")) == "max_fullness" else "最大绝对流量"
            causes.append(
                f"高负荷管段 `{top['object_id']}` 的{label}为 "
                f"{_fmt_value(top['value'], str(top.get('unit', '')))}，可作为排水系统压力较高的旁证。"
            )
        direction_changes = evidence[
            (evidence["object_type"] == "link")
            & (evidence["metric_name"] == "flow_direction_changes")
        ]
        direction_changes = direction_changes.sort_values("value", ascending=False).head(3)
        if not direction_changes.empty and float(direction_changes.iloc[0]["value"]) > 0:
            top = direction_changes.iloc[0]
            causes.append(
                f"管段 `{top['object_id']}` 在模拟过程中发生 "
                f"{_fmt_value(top['value'], str(top.get('unit', '')))} 次流向改变，提示可能存在顶托、回流或水力震荡线索。"
            )
    if not causes:
        causes.append(f"该对象 `{object_id}` 的诊断结论已有证据引用，但当前证据不足以继续细分成更具体的工程原因。")
    return causes


def generate_run_report(model_name: str, run_id: str, report_type: str = "summary_report") -> dict[str, Any]:
    """Generate a user-facing Markdown report from verified workflow artifacts."""
    run_root, _state, summary, evidence, diagnosis, risk_ranking, verification = _load_report_inputs(model_name, run_id)
    claims = _supported_claims(diagnosis, verification)
    verification_summary = verification.get("summary", {})
    metric_counts = evidence["metric_name"].value_counts().to_dict()
    claim_counts = risk_ranking["claim_type"].value_counts().to_dict() if not risk_ranking.empty else {}

    surface = _top_rows(risk_ranking, "surface_hotspot", limit=5)
    ponding = _top_rows(risk_ranking, "long_duration_ponding", limit=5)
    overflow = _top_rows(risk_ranking, "major_overflow_node", limit=5)
    link_load = _top_rows(risk_ranking, "high_load_link", limit=5)
    unstable_direction = _top_rows(risk_ranking, "unstable_flow_direction_link", limit=5)

    lines = [
        "# SWMM-CA2D 内涝分析报告",
        "",
        f"本次报告基于 `{run_id}` 的已核查工作流成果生成。当前可用诊断结论 {len(claims)} 条，"
        f"核查结果为 supported {verification_summary.get('supported', 0)} 条、"
        f"partially supported {verification_summary.get('partially_supported', 0)} 条、"
        f"unsupported {verification_summary.get('unsupported', 0)} 条，"
        f"unsupported rate 为 {verification_summary.get('unsupported_rate', 0):.3f}。",
        "",
        "## 运行概况",
        "",
        f"- 模型：`{summary.get('model_name', model_name)}`",
        f"- 降雨事件：`{summary.get('event_name', '')}`",
        f"- 情景：`{summary.get('scenario_name', '')}`",
        f"- 证据数量：{len(evidence)} 条",
        f"- 诊断结论数量：{len(claims)} 条",
        "",
        "## 证据与诊断概况",
        "",
        "本次报告使用的结构化证据包括：",
    ]
    for metric_name, count in sorted(metric_counts.items()):
        lines.append(f"- `{metric_name}`（{_metric_label(str(metric_name))}）：{count} 条。")
    lines.extend(["", "已核查诊断结论类型包括："])
    for claim_type, count in sorted(claim_counts.items()):
        lines.append(f"- `{claim_type}`（{_claim_type_title(str(claim_type))}）：{count} 条。")
    lines.extend(
        [
            "",
        "## 主要风险信号",
        "",
        ]
    )

    if not surface.empty:
        lines.append("地表积水热点主要集中在以下网格：")
        for _, row in surface.iterrows():
            lines.append(f"- Cell `{row['object_id']}`：{_fmt_value(row['value'], str(row.get('unit', '')))}，风险等级 `{row.get('severity', '')}`。")
    else:
        lines.append("未发现达到规则阈值的地表积水热点。")

    if not overflow.empty:
        lines.extend(["", "管网溢流方面，以下节点贡献较突出："])
        for _, row in overflow.iterrows():
            lines.append(f"- Node `{row['object_id']}`：总溢流量 {_fmt_value(row['value'], str(row.get('unit', '')))}。")

    if not ponding.empty:
        lines.extend(["", "积水持续性方面，以下位置需要关注："])
        for _, row in ponding.iterrows():
            lines.append(f"- Cell `{row['object_id']}`：持续时间 {_fmt_value(row['value'], str(row.get('unit', '')))}。")

    if not link_load.empty:
        lines.extend(["", "管段负荷方面，以下管段可作为排水压力较高的线索："])
        for _, row in link_load.iterrows():
            label = "最大充满度" if str(row.get("metric_name", "")) == "max_fullness" else "最大绝对流量"
            lines.append(f"- Link `{row['object_id']}`：{label} {_fmt_value(row['value'], str(row.get('unit', '')))}。")

    if not unstable_direction.empty:
        lines.extend(["", "管段流向稳定性方面，以下管段存在频繁流向改变信号："])
        for _, row in unstable_direction.iterrows():
            lines.append(f"- Link `{row['object_id']}`：流向改变 {_fmt_value(row['value'], str(row.get('unit', '')))} 次。")

    lines.extend(["", "## 完整诊断清单", ""])
    for claim_type in [
        "surface_hotspot",
        "long_duration_ponding",
        "major_overflow_node",
        "high_load_link",
        "unstable_flow_direction_link",
    ]:
        rows = risk_ranking[risk_ranking["claim_type"] == claim_type].copy()
        if not rows.empty:
            rows = rows.sort_values("value", ascending=False)
        lines.extend([f"### {_claim_type_title(claim_type)}", ""])
        _append_claim_rows(lines, rows, verification)
        lines.append("")

    lines.extend(
        [
            "## 证据核查结果",
            "",
            f"- 总诊断结论：{verification_summary.get('total_claims', 0)} 条。",
            f"- supported：{verification_summary.get('supported', 0)} 条。",
            f"- partially supported：{verification_summary.get('partially_supported', 0)} 条。",
            f"- unsupported：{verification_summary.get('unsupported', 0)} 条。",
            f"- uncertain：{verification_summary.get('uncertain', 0)} 条。",
            f"- unsupported rate：{verification_summary.get('unsupported_rate', 0):.3f}。",
        ]
    )

    lines.extend(
        [
            "",
            "## 综合判断",
            "",
            "本次结果显示，内涝风险应优先从地表积水热点、节点溢流贡献和管段高负荷三条证据线综合理解。"
            "其中，地表热点说明积水空间位置，节点溢流说明管网向地表释放水量的位置，管段高负荷和流向不稳定则提示排水系统在事件过程中的压力状态与水力扰动。",
            "",
            "## 使用边界",
            "",
            "以上文字只基于已生成并完成核查的结构化证据，不补充现场地形、土地利用、管径复核或人工巡查信息。"
            "若需要工程定因，应继续叠加 DEM、汇水分区、管网设计参数和现场排口条件。",
        ]
    )

    return {
        "schema_name": REPORT_SCHEMA_NAME,
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_type": report_type,
        "model_name": run_root.parents[1].name,
        "run_id": run_id,
        "markdown": "\n".join(lines),
    }


def explain_one_flood_point(model_name: str, run_id: str) -> dict[str, Any]:
    """Explain one representative verified flood point in plain language."""
    run_root, _state, _summary, evidence, diagnosis, risk_ranking, verification = _load_report_inputs(model_name, run_id)
    claims = _supported_claims(diagnosis, verification)
    claim = _choose_explanation_claim(claims, risk_ranking)
    if claim is None:
        raise ValueError("No supported diagnosis claim is available for point explanation.")

    evidence_lookup = _evidence_by_id(evidence)
    evidence_lines = _claim_evidence_lines(claim, evidence_lookup)
    cause_lines = _infer_point_causes(claim, evidence)

    lines = [
        f"# 典型内涝点原因分析：{claim.get('object_type')} `{claim.get('object_id')}`",
        "",
        f"我选取 `{claim.get('object_id')}` 作为例子，因为它在已验证诊断中被标记为 "
        f"`{claim.get('severity')}` 级别的 `{claim.get('claim_type')}`，核查状态为 "
        f"`{claim.get('verification_status')}`。",
        "",
        "## 直接证据",
        "",
    ]
    lines.extend(evidence_lines or ["- 当前 claim 没有可展开的证据行。"])
    lines.extend(["", "## 原因解释", ""])
    for item in cause_lines:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 需要谨慎的地方",
            "",
            "这里的“原因”是基于模拟证据链的工程解释，不等同于现场定责。若要进一步确认，建议叠加该点附近地面高程、汇水方向、雨水口位置、管段坡度和历史积水记录。",
        ]
    )

    return {
        "schema_name": REPORT_SCHEMA_NAME,
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_type": "single_point_explanation",
        "model_name": run_root.parents[1].name,
        "run_id": run_id,
        "selected_claim_id": claim.get("claim_id"),
        "selected_object_id": claim.get("object_id"),
        "markdown": "\n".join(lines),
    }


def generate_report_for_request(model_name: str, run_id: str, message: str = "") -> dict[str, Any]:
    """Select a ReportAgent output mode from a user-facing request."""
    lowered = message.lower()
    wants_point = any(marker in message for marker in ["一处", "一个", "某个", "内涝点", "原因", "为什么"]) or "point" in lowered
    if wants_point and not any(marker in message for marker in ["报告", "总报告", "完整报告"]):
        return explain_one_flood_point(model_name, run_id)
    return generate_run_report(model_name, run_id)
