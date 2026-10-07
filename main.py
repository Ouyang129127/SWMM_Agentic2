import asyncio
import json
import re
from pathlib import Path
from typing import Any

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from typing_extensions import Annotated

from prompts import (
    orchestrator_prompt,
    simulation_evidence_explainer_prompt,
    validation_evidence_explainer_prompt,
    web_interactive_prompt,
)
from tools import (
    check_all_swmm_2d_projects,
    check_ca2d_model,
    check_swmm_2d_project,
    list_rainfall_events,
    list_swmm_2d_models,
    parse_and_convert_to_markdown,
    run_workflow_stage,
    run_swmm_2d_project_from_rainfall,
)
from workflow_agents import load_scenario_request, prepare_scenario_request
from workflow_agents.schemas import RUN_READY
from workflow_agents.state import build_state, save_state

APP_ROOT = Path(__file__).resolve().parent
WORKSPACE_DIR = APP_ROOT


def _final_message_content(messages):
    for message in reversed(messages):
        content = getattr(message, "content", "")
        text = _stringify_content(content).strip()
        if text:
            return text
    return ""


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_stringify_content(item) for item in content)
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _is_unrelated_reply(text: str) -> bool:
    unrelated_markers = [
        "leetcode",
        "两数之和",
        "哈希表",
        "二叉搜索树",
        "监控二叉树",
        "rust的hashmap",
        "TreeNode",
        "class Solution",
        "vector<int>",
    ]
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in unrelated_markers)


def _parse_json_from_evidence(evidence: str) -> Any | None:
    try:
        return json.loads(evidence)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", evidence, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None


def _normalize_evidence_block(evidence: str) -> tuple[str, str]:
    parsed = _parse_json_from_evidence(evidence)
    if parsed is not None:
        return json.dumps(parsed, ensure_ascii=False, indent=2), "json"
    return evidence.strip(), "text"


def _fallback_validation_explanation(evidence: str) -> str:
    parsed = _parse_json_from_evidence(evidence)
    if parsed is None:
        return "本次结果来自固定验证器。由于解释层暂时不可用，下面保留原始验证结果作为正式依据。"

    validator = parsed.get("validator", "fixed validator")
    schema_name = parsed.get("schema_name", "SWMM-2D project layout")
    schema_version = parsed.get("schema_version", "unknown")
    if "projects" in parsed:
        ready_count = sum(1 for item in parsed["projects"] if item.get("ready"))
        return (
            f"本次检查使用固定验证器 `{validator}`，依据 `{schema_name}` "
            f"({schema_version}) 结构规范完成。共发现 {parsed.get('project_count', len(parsed['projects']))} "
            f"个模型项目，其中 {ready_count} 个项目处于 ready 状态。"
        )
    if "model_name" in parsed:
        status = "完整，未发现缺失项" if parsed.get("ready") else "存在问题"
        return (
            f"本次检查使用固定验证器 `{validator}`，依据 `{schema_name}` "
            f"({schema_version}) 结构规范完成。模型 `{parsed['model_name']}` 的检查结论为：{status}。"
        )
    return (
        f"本次结果来自固定验证器 `{validator}`，依据 `{schema_name}` "
        f"({schema_version}) 结构规范生成。"
    )


def _fallback_simulation_explanation(evidence: str) -> str:
    parsed = _parse_json_from_evidence(evidence)
    if parsed is None:
        return "本次结果来自固定模拟工具。由于解释层暂时不可用，下面保留原始工具结果作为正式依据。"

    run_id = parsed.get("run_id", "")
    model_name = parsed.get("model_name", "")
    swmm = parsed.get("swmm", {}) or {}
    ca2d = parsed.get("ca2d", {}) or {}
    swmm_steps = swmm.get("total_steps", "未知")
    saved_steps = swmm.get("saved_steps", "未知")
    max_depth = ca2d.get("max_depth_m", "未知")
    run_root = parsed.get("run_root") or str(Path(parsed.get("swmm_output_dir", "")).parent)
    return (
        "本次执行已走 tool-first 固定模拟管线：降雨事件写入 SWMM，随后通过 PySWMM 导出节点溢流，"
        "再交给 CA2D 计算并保存到 runs 目录。"
        f"模型 `{model_name}` 的运行编号为 `{run_id}`，SWMM 总步数为 {swmm_steps}，"
        f"保存步数为 {saved_steps}，CA2D 最大水深为 {max_depth} m。"
        f"输出位置为 `{run_root}`。"
    )


def _contains_any(text: str, markers: list[str]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


async def ScenarioAgent(
    message: Annotated[
        str,
        "User request about model project, rainfall event, scenario name, or run parameters.",
    ],
    model_name: Annotated[
        str,
        "Optional model project name under project-root models/.",
    ] = "",
    rainfall_file: Annotated[
        str,
        "Optional rainfall event path, usually events/<file>.txt. If provided, ScenarioAgent writes scenario_request.json.",
    ] = "",
    event_name: Annotated[
        str,
        "Optional event name for scenario_request.json.",
    ] = "",
    scenario_name: Annotated[
        str,
        "Scenario name under swmm/scenarios/<scenario_name>/.",
    ] = "baseline",
    run_id: Annotated[
        str,
        "Optional run ID for the prepared scenario request.",
    ] = "",
) -> str:
    """Workflow-stage ScenarioAgent: organize model/event/scenario prerequisites."""
    if rainfall_file:
        result = prepare_scenario_request(
            model_name=model_name,
            rainfall_file=rainfall_file,
            event_name=event_name,
            scenario_name=scenario_name,
            run_id=run_id,
        )
        return "ScenarioAgent completed:\n" + json.dumps(result, ensure_ascii=False, indent=2)

    wants_events = _contains_any(message, ["降雨", "rainfall", "event", "events", "雨型"])
    wants_check = _contains_any(message, ["检查", "验证", "完整", "check", "validate"])
    wants_list = _contains_any(message, ["列出", "list", "available", "有哪些"])

    if wants_events:
        return "ScenarioAgent completed:\n" + list_rainfall_events(model_name)
    if wants_check:
        return "ScenarioAgent completed:\n" + check_swmm_2d_project(model_name)
    if wants_list or not model_name:
        return "ScenarioAgent completed:\n" + list_swmm_2d_models()
    return "ScenarioAgent completed:\n" + check_swmm_2d_project(model_name)


async def SimulationAgent(
    model_name: Annotated[
        str,
        "Name of a SWMM-2D model project under project-root models/.",
    ],
    rainfall_file: Annotated[
        str,
        "Rainfall event file path, usually events/<file>.txt relative to the model project.",
    ],
    event_name: Annotated[
        str,
        "Rainfall event ID for run metadata.",
    ] = "manual_event",
    scenario_name: Annotated[
        str,
        "Scenario name under swmm/scenarios/<scenario_name>/.",
    ] = "baseline",
    run_id: Annotated[
        str,
        "Run ID. If scenario_request.json exists for this run, SimulationAgent reads it. Empty means generate from event, scenario, and timestamp.",
    ] = "",
) -> str:
    """Workflow-stage SimulationAgent: run the official fixed SWMM->CA2D pipeline."""
    scenario_request = None
    if run_id:
        try:
            scenario_request = load_scenario_request(model_name, run_id)
        except FileNotFoundError:
            scenario_request = None

    if scenario_request is None:
        if not rainfall_file:
            return "SimulationAgent failed: rainfall_file is required unless scenario_request.json already exists for run_id."
        prepared = prepare_scenario_request(
            model_name=model_name,
            rainfall_file=rainfall_file,
            event_name=event_name,
            scenario_name=scenario_name,
            run_id=run_id,
        )
        scenario_request = prepared["scenario_request"]

    result_text = run_swmm_2d_project_from_rainfall(
        model_name=scenario_request["model_name"],
        rainfall_file=scenario_request["rainfall_file"],
        event_name=scenario_request["event_name"],
        scenario_name=scenario_request["scenario_name"],
        run_id=scenario_request["run_id"],
    )
    parsed = _parse_json_from_evidence(result_text)
    if isinstance(parsed, dict) and parsed.get("run_root"):
        run_root = Path(parsed["run_root"])
        state = build_state(parsed["model_name"], parsed["run_id"], run_root, state=RUN_READY)
        previous_state_path = run_root / "workflow_state.json"
        if previous_state_path.exists():
            try:
                previous_state = json.loads(previous_state_path.read_text(encoding="utf-8"))
                state["history"] = list(previous_state.get("history", []))
            except json.JSONDecodeError:
                state["history"] = []
        else:
            state["history"] = []
        state["history"].append(
            {
                "stage": "simulation",
                "target_state": RUN_READY,
                "completed_at": parsed.get("created_at", ""),
                "rerun": bool(run_id),
            }
        )
        save_state(run_root, state)
    return "SimulationAgent completed:\n" + result_text


async def EvidenceBuilderAgent(
    model_name: Annotated[str, "Model project name under project-root models/."],
    run_id: Annotated[str, "Run ID under models/<model_name>/runs/."],
    rerun: Annotated[bool, "Allow rerunning this stage."] = False,
    task_id: Annotated[str, "Existing investigation task whose displayed evidence requests the user approved."] = "",
) -> str:
    """Workflow-stage EvidenceBuilderAgent."""
    if task_id:
        return await _investigation_action(model_name, run_id, 'evidence', task_id)
    return run_workflow_stage(
        model_name=model_name,
        run_id=run_id,
        target_stage="evidence_building",
        rerun=rerun,
    )


async def DiagnosisAgent(
    model_name: Annotated[str, "Model project name under project-root models/."],
    run_id: Annotated[str, "Run ID under models/<model_name>/runs/."],
    rerun: Annotated[bool, "Allow rerunning this stage."] = False,
    message: Annotated[str, "Empty starts the default whole-run preliminary overflow diagnosis. A user follow-up question prepares a scoped task."] = "",
    task_id: Annotated[str, "Existing task runs one diagnosis/revision; without task/question the initial diagnosis, reference check and report are delivered together."] = "",
) -> str:
    """Workflow-stage DiagnosisAgent."""
    action = 'diagnose' if task_id else 'prepare' if message.strip() else 'initial'
    return await _investigation_action(model_name, run_id, action, task_id, message)


async def VerificationAgent(
    model_name: Annotated[str, "Model project name under project-root models/."],
    run_id: Annotated[str, "Run ID under models/<model_name>/runs/."],
    rerun: Annotated[bool, "Allow rerunning this stage."] = False,
    task_id: Annotated[str, "Required task to reference-check; no run-level fallback."] = "",
) -> str:
    """Workflow-stage VerificationAgent."""
    if task_id:
        return await _investigation_action(model_name, run_id, 'verify', task_id)
    raise ValueError("VerificationAgent必须指定task_id；运行级核查已删除。")


async def ReportAgent(
    model_name: Annotated[str, "Model project name under project-root models/."],
    run_id: Annotated[str, "Run ID containing saved simulation and verified diagnosis files."],
    message: Annotated[str, "User-facing report or explanation request."] = "",
    task_id: Annotated[str, "Verified task; omit to resolve this run's active task."] = "",
) -> str:
    """Generate a self-contained HTML report from this task's saved results."""
    from workflow_agents.investigation_flow import load_active_task
    state = load_active_task(model_name, run_id, task_id)
    if state is None:
        raise ValueError('ReportAgent需要已完成诊断与引用核查的任务。')
    action = 'report' if state['state'] == 'ready_for_report' else 'display_report'
    return await _investigation_action(model_name, run_id, action, state['task_id'])


async def _investigation_action(model_name, run_id, action, task_id='', question=''):
    from workflow_agents.investigation import advance_investigation
    if action == 'diagnose' and not question:
        from workflow_agents.investigation_flow import diagnose_with_repair
        result = await diagnose_with_repair(model_name, run_id, task_id)
    else:
        result = await advance_investigation(model_name, run_id, action, task_id, question)
    return json.dumps(result, ensure_ascii=False, indent=2)


async def explain_validation_evidence(user_message: str, evidence: str) -> str:
    """Explain fixed-validator evidence without deciding project status in the web layer."""
    from llm import deepseek_flash

    evidence_block, fence_type = _normalize_evidence_block(evidence)
    task = (
        "请把下面的 SWMM-2D 固定验证器结果解释给用户。\n"
        "严格规则：\n"
        "1. 只能依据 Evidence 中已有字段解释，不得新增缺失项、路径、文件名或检查结论。\n"
        "2. 如果 Evidence 中 problems 为空或 ready=true，只能说明未发现缺失项。\n"
        "3. 如果 Evidence 中列出 problems 或 missing，只能逐条解释这些已有问题。\n"
        "4. 必须说明本结果来自固定验证器，并提到 schema_name/schema_version/validator（如果 Evidence 中存在）。\n"
        "5. 用中文，先给 3-6 句自然语言说明，再给一个简短结论。\n"
        "6. 不要输出代码，不要输出与 SWMM-2D 无关的内容。\n\n"
        f"User request:\n{user_message}\n\n"
        f"Evidence:\n```{fence_type}\n{evidence_block}\n```"
    )
    try:
        explainer = AssistantAgent(
            name="EvidenceExplainer",
            system_message=validation_evidence_explainer_prompt,
            model_client=deepseek_flash,
        )
        team = RoundRobinGroupChat(participants=[explainer], max_turns=1)
        result = await team.run(task=task)
        explanation = _final_message_content(result.messages)
        if not explanation or _is_unrelated_reply(explanation):
            explanation = _fallback_validation_explanation(evidence)
    except Exception:
        explanation = _fallback_validation_explanation(evidence)

    return (
        explanation.strip()
        + "\n\n**结构化证据**\n"
        + f"```{fence_type}\n{evidence_block}\n```"
    )


async def explain_simulation_evidence(user_message: str, evidence: str) -> str:
    """Explain fixed simulation-pipeline evidence without rerunning or altering facts."""
    from llm import deepseek_flash

    evidence_block, fence_type = _normalize_evidence_block(evidence)
    task = (
        "请把下面的 SWMM-2D 固定模拟管线结果解释给用户。\n"
        "严格规则：\n"
        "1. 只能依据 Evidence 中已有字段解释，不得新增文件、指标、成功状态或失败原因。\n"
        "2. 必须说明本次执行走的是 tool-first 固定管线：降雨事件写入 SWMM -> PySWMM 运行 -> 导出节点溢流 -> CA2D 计算 -> 保存 runs 结果。\n"
        "3. 如果 Evidence 表明运行完成，概括 run_id、输出目录、SWMM 步数/保存步数、CA2D 最大水深等已有指标。\n"
        "4. 如果 Evidence 是错误文本，只解释该错误文本，并提示下一步应检查已有字段指向的路径或参数。\n"
        "5. 用中文，先给 3-6 句自然语言说明，再给一个简短结论。\n"
        "6. 不要输出代码，不要输出与 SWMM-2D 无关的内容。\n\n"
        f"User request:\n{user_message}\n\n"
        f"Evidence:\n```{fence_type}\n{evidence_block}\n```"
    )
    try:
        explainer = AssistantAgent(
            name="SimulationEvidenceExplainer",
            system_message=simulation_evidence_explainer_prompt,
            model_client=deepseek_flash,
        )
        team = RoundRobinGroupChat(participants=[explainer], max_turns=1)
        result = await team.run(task=task)
        explanation = _final_message_content(result.messages)
        if not explanation or _is_unrelated_reply(explanation):
            explanation = _fallback_simulation_explanation(evidence)
    except Exception:
        explanation = _fallback_simulation_explanation(evidence)

    return (
        explanation.strip()
        + "\n\n**结构化证据**\n"
        + f"```{fence_type}\n{evidence_block}\n```"
    )


async def run_web_orchestrator_agent_turn(task_prompt: str, planning_only: bool = False) -> str:
    """Run the web-chat StatefulOrchestrator while keeping construction out of web_app.py."""
    from llm import deepseek_flash

    tool_list = [] if planning_only else [
        ScenarioAgent,
        SimulationAgent,
        EvidenceBuilderAgent,
        DiagnosisAgent,
        VerificationAgent,
        ReportAgent,
    ]
    mode_prompt = (
        "\nThis is a planning-only turn. Do not call any tools. Give a short step-by-step plan, "
        "state that no execution has been performed yet, and ask the user whether to continue.\n"
        if planning_only
        else ""
    )
    orchestrator = AssistantAgent(
        name="StatefulOrchestrator",
        system_message=orchestrator_prompt + web_interactive_prompt + mode_prompt,
        model_client=deepseek_flash,
        tools=tool_list,
    )
    termination = MaxMessageTermination(8) | TextMentionTermination("TERMINATE")
    team = RoundRobinGroupChat(
        participants=[orchestrator],
        termination_condition=termination,
        max_turns=8,
    )
    result = await team.run(task=task_prompt)
    return _extract_agent_reply(result.messages)


def _extract_agent_reply(messages) -> str:
    for message in reversed(messages):
        content = getattr(message, "content", "")
        text = _stringify_content(content).strip()
        if "Final Answer:" in text and not _is_unrelated_reply(text):
            return text.split("Final Answer:", 1)[1].strip()
    for message in reversed(messages):
        content = getattr(message, "content", "")
        text = _stringify_content(content).strip()
        if text and not _is_unrelated_reply(text):
            return text
    text = _final_message_content(messages)
    if text and not _is_unrelated_reply(text):
        return text
    return (
        "本轮没有得到可靠的 SWMM-2D 相关回复。请重新确认要执行的模型、降雨事件或下一步。"
    )


async def main(task_description):
    from llm import deepseek_flash

    user = UserProxyAgent("user", input_func=input)
    orchestrator = AssistantAgent(
        name="StatefulOrchestrator",
        system_message=orchestrator_prompt,
        model_client=deepseek_flash,
        tools=[
            ScenarioAgent,
            SimulationAgent,
            EvidenceBuilderAgent,
            DiagnosisAgent,
            VerificationAgent,
                ReportAgent,
                ],
    )

    termination = MaxMessageTermination(30) | TextMentionTermination("TERMINATE")
    team = RoundRobinGroupChat(
        participants=[orchestrator, user],
        termination_condition=termination,
        max_turns=30,
    )

    stream = team.run_stream(task=task_description)
    await Console(stream)


def load_startup_task() -> str:
    default_task = (
        "List available SWMM-2D model projects under the project-root models directory, "
        "then check each discovered model project for model.yaml, baseline SWMM scenario, "
        "CA2D static model, mapping, events, and runs structure. "
        "Do not use data/example.inp as a default model."
    )
    try:
        with open(APP_ROOT / "tasks" / "manuscript.json", "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default_task

    if not tasks:
        return default_task
    task_description = str(tasks[0].get("description", "")).strip()
    if not task_description or "data/example.inp" in task_description:
        return default_task
    return task_description


if __name__ == "__main__":
    asyncio.run(main(load_startup_task()))
