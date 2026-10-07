import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from main import (
    explain_simulation_evidence,
    explain_validation_evidence,
    run_web_orchestrator_agent_turn,
)
from tools import (
    check_all_swmm_2d_projects,
    check_ca2d_model,
    check_swmm_2d_project,
    list_rainfall_events,
    list_swmm_2d_models,
    run_workflow_stage,
    run_swmm_2d_project_from_rainfall,
)
from workflow_agents import load_scenario_request, prepare_scenario_request
from workflow_agents.schemas import EVIDENCE_READY, NO_SURFACE_INFLOW, RUN_READY, SCENARIO_READY
from workflow_agents.state import build_state, load_or_initialize_state, save_state
from workflow_agents.investigation import advance_investigation
from workflow_agents.investigation_flow import load_active_task


APP_ROOT = Path(__file__).resolve().parent
MODELS_DIR = APP_ROOT / "models"
WEB_DIR = APP_ROOT / "web"
INDEX_HTML_PATH = WEB_DIR / "index.html"
WEB_LOG_DIR = APP_ROOT / "conversation" / "web_sessions"
CHAT_TIMEOUT_SECONDS = 900


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    transcript: list[dict[str, str]]


class ChatSession:
    def __init__(self) -> None:
        self.transcript: list[dict[str, str]] = []
        self.lock = asyncio.Lock()


app = FastAPI(title="SWMM-Agentic2 Workflow Chat")
sessions: dict[str, ChatSession] = {}
WEB_LOG_DIR.mkdir(parents=True, exist_ok=True)

if MODELS_DIR.exists():
    app.mount("/models", StaticFiles(directory=str(MODELS_DIR)), name="models")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    if not INDEX_HTML_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Frontend file not found: {INDEX_HTML_PATH}")
    return HTMLResponse(
        content=INDEX_HTML_PATH.read_text(encoding="utf-8"),
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        restored = ChatSession()
        path = session_log_path(session_id)
        if path.exists():
            restored.transcript = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        sessions[session_id] = restored
    session = sessions[session_id]
    user_message = repair_mojibake(request.message)

    async with session.lock:
        session.transcript.append({"role": "user", "content": user_message})
        append_session_log(session_id, "user", user_message)
        try:
            reply = await asyncio.wait_for(
                run_orchestrator_turn(session.transcript),
                timeout=CHAT_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            reply = (
                "This request did not return within 15 minutes, so the web chat stopped waiting. "
                "If you started a long simulation, check the latest models/<model_name>/runs/ output folder. "
                "If this was only a normal question, the model service or a tool call likely hung; you can retry now."
            )
        except Exception as exc:
            if is_rate_limit_error(exc):
                reply = (
                    "模型服务当前繁忙，刚才这一轮没有成功执行，也没有产生可靠结果。"
                    "请稍等几十秒后直接重试同一句，或点击“新会话”后再试。"
                )
                session.transcript.append({"role": "assistant", "content": reply})
                append_session_log(session_id, "assistant", reply)
                return ChatResponse(session_id=session_id, reply=reply, transcript=session.transcript)
            if is_llm_timeout_error(exc):
                reply = (
                    "模型服务本轮响应超时，刚才这一轮没有成功执行，也没有产生可靠结果。"
                    "这通常是 LLM 服务商响应慢、网络连接不稳定，或当前请求过长导致的。"
                    "请稍后重试；如果连续出现，可以换更快的模型或把任务拆小。"
                )
                session.transcript.append({"role": "assistant", "content": reply})
                append_session_log(session_id, "assistant", reply)
                return ChatResponse(session_id=session_id, reply=reply, transcript=session.transcript)
            session.transcript.append({"role": "assistant", "content": f"Execution failed: {exc}"})
            append_session_log(session_id, "assistant", f"Execution failed: {exc}")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        session.transcript.append({"role": "assistant", "content": reply})
        append_session_log(session_id, "assistant", reply)
        return ChatResponse(session_id=session_id, reply=reply, transcript=session.transcript)


@app.get("/api/session/{session_id}", response_model=ChatResponse)
async def get_session(session_id: str) -> ChatResponse:
    session = sessions.get(session_id)
    if session is not None:
        return ChatResponse(session_id=session_id, reply="", transcript=session.transcript)

    log_path = session_log_path(session_id)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    transcript = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        transcript.append({"role": record["role"], "content": record["content"]})
    return ChatResponse(session_id=session_id, reply="", transcript=transcript)


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str) -> dict[str, bool]:
    sessions.pop(session_id, None)
    return {"ok": True}


async def run_orchestrator_turn(transcript: list[dict[str, str]]) -> str:
    latest = transcript[-1]["content"]
    planning_only = is_planning_only_request(latest)
    if not planning_only:
        continue_result = await continue_workflow_from_state(latest, transcript)
        if continue_result is not None:
            return continue_result
        if latest.strip(' ，。!?！？').lower() in {'下一步我该做什么', '好的，下一步我该做什么', '现在下一步是什么', '下一步是什么'}:
            binding = investigation_binding(transcript)
            if binding:
                model_name, run_id, task_id = binding
                state = load_active_task(model_name, run_id, task_id)
                if state:
                    state = await advance_investigation(model_name, run_id, 'status', state['task_id'])
                    return format_investigation_result(state)
        # Investigation tasks must not fall through to run-level deterministic
        # shortcuts. The LLM orchestrator selects one role/action after approval.
        recent = '\n'.join(item['content'] for item in transcript[-10:])
        if ('"task_id"' in recent or 'EVIDENCE_READY' in recent or
                any(marker in latest.lower() for marker in ('诊断', '主因', 'diagnosis', '核查', 'verification', '报告', 'report', '原因', '为什么'))):
            return await run_web_orchestrator_agent_turn(build_task_prompt(transcript), planning_only=False)
        deterministic_workflow = deterministic_workflow_stage_evidence(latest, transcript)
        if deterministic_workflow is not None:
            return deterministic_workflow

        simulation_result = simulation_agent_evidence(latest, transcript)
        if simulation_result is not None:
            if "SWMM-2D project run rejected:" in simulation_result:
                return "本轮模拟未启动：输入校验未通过。\n\n" + simulation_result
            if "NO_SURFACE_INFLOW" in simulation_result:
                return simulation_result
            explanation = await explain_simulation_evidence(latest, simulation_result)
            return (
                "本轮已由 SWMM-Agentic2 的 `SimulationAgent` 处理标准化模拟请求，"
                "使用固定模拟管线。\n\n"
                + explanation
            )

        scenario_result = scenario_agent_evidence(latest)
        if scenario_result is not None:
            if "scenario_request" in scenario_result:
                return (
                    "本轮已由 SWMM-Agentic2 的 `ScenarioAgent` 准备情景请求，"
                    "并写入 `scenario_request.json`；当前工作流可进入 `SimulationAgent`。\n\n"
                    "**结构化情景结果**\n"
                    f"```text\n{scenario_result}\n```"
                )
            explanation = await explain_validation_evidence(latest, scenario_result)
            return (
                "本轮已由 SWMM-Agentic2 的 `ScenarioAgent` 处理模型、情景或降雨事件组织请求，"
                "没有进入旧的自由路由。\n\n"
                + explanation
            )

    task = build_task_prompt(transcript)
    return await run_web_orchestrator_agent_turn(task, planning_only=planning_only)


def investigation_binding(transcript: list[dict[str, str]]) -> tuple[str, str, str] | None:
    # Work backwards by message, not by regex-pattern priority. A durable run
    # binding remains usable even when the conversation exceeds ten turns.
    run_id = ''
    task_id = ''
    for item in reversed(transcript):
        text = item['content']
        if not task_id:
            ids = re.findall(r'task_id[\s`\"\'=:：()]*([0-9a-f]{32})', text, re.IGNORECASE)
            task_id = ids[-1] if ids else ''
        run_id = extract_workflow_run_id(text)
        if run_id:
            break
    if not run_id:
        return None
    context = '\n'.join(item['content'] for item in transcript)
    model_name = extract_model_name(context)
    # resolve_run_root checks uniqueness across models for stale/absent model names.
    from workflow_agents.state import resolve_run_root
    root = resolve_run_root(model_name or '__unspecified__', run_id)
    return root.parents[1].name, root.name, task_id


def format_investigation_result(state: dict[str, Any]) -> str:
    current = state['state']
    lines = [f"诊断任务 `{state['task_id']}`；当前状态：`{current}`。"]
    if state.get('execution_error'):
        lines.append('本次修正未通过，已保留原任务、失败响应和反馈：' + state['execution_error'])
        lines.append('下一步：继续修正此任务，无需重跑模拟或重建诊断任务。')
    elif current == 'awaiting_evidence_confirmation':
        lines.append('初步诊断已交付。下一步：回复“继续”，按下列请求查询已有证据或从本次保存结果提取／计算，再更新诊断、核查和报告。')
    elif current == 'preliminary_delivered':
        lines.append('初步诊断流程已完成。')
        if state.get('evidence_closure') == 'capability_gaps':
            lines.append('当前请求没有新增证据；未满足的变量、时窗或方法已保留为证据缺口，不再重复运行诊断。下一步可调整请求，或针对保存数据能力以外的缺口确定其他调查方法。')
        else:
            lines.append('下一步可针对报告提出具体问题；再次“继续”会展示已有结果。')
    else:
        actions = {'ready_for_diagnosis': '诊断', 'revision_requested': '按反馈修正诊断',
                   'ready_for_verification': '核查引用', 'ready_for_report': '交付报告'}
        lines.append('下一步：' + actions.get(current, '检查当前任务状态') + '。')
    if state.get('evidence_plan'):
        labels = {'available': '可补充', 'already_visible': '已经读取', 'no_match': '请求对象／时段无匹配项', 'unavailable': '当前保存数据或提取方法不能满足'}
        lines.append('\n补证处理结果：')
        for item in state['evidence_plan']:
            req = item['request']
            lines.append(f"- {labels[item['status']]}：{req.get('reason', '')}")
            if item.get('execution') == 'saved_result_extract':
                resolved = item.get('resolved_request', {})
                lines.append('  方法：本次保存结果提取／计算；' + resolved.get('scope_note', ''))
                for scope in resolved.get('scopes', []):
                    objects = scope['nodes'] + scope['links'] + scope['cells']
                    lines.append(f"  {scope['event_id'] or '无事件限定'}：{', '.join(objects)}；{scope['time_start'] or '保存起点'} 至 {scope['time_end'] or '保存终点'}。")
            if item.get('reason'):
                lines.append('  能力边界：' + item['reason'])
    if state.get('report_revision') == state.get('revision') and state.get('report'):
        lines.append('\n' + state['report'])
        lines.append(f"\n报告文件：`{state['report_file']}`")
    display = state.get('display_report', {})
    if display.get('status') == 'completed' and display.get('revision') == state.get('revision'):
        from urllib.parse import quote
        path = Path(display['html_file']).resolve()
        try:
            relative = path.relative_to(MODELS_DIR.resolve()).as_posix()
            lines.append(f'\n[打开 HTML 诊断报告](/models/{quote(relative, safe="/")})')
        except ValueError:
            lines.append(f"\nHTML 报告文件：`{path}`")
    elif display.get('status') == 'failed':
        lines.append('\nHTML 报告生成失败，已保留诊断与内部报告：' + display.get('error', '请检查生成记录后重试。'))
    return '\n\n'.join(lines)


async def continue_workflow_from_state(message: str, transcript: list[dict[str, str]]) -> str | None:
    """Continue exactly the next allowed workflow stage after a user confirmation."""
    prior = transcript[-2]['content'] if len(transcript) > 1 else ''
    approve_option = message.strip().lower() == 'a' and 'EvidenceBuilderAgent' in prior and 'awaiting_evidence_confirmation' in prior
    if not is_continue_confirmation(message) and not approve_option:
        return None
    try:
        binding = investigation_binding(transcript)
        if not binding:
            return None
        model_name, run_id, task_id = binding
        run_root, state = load_or_initialize_state(model_name, run_id)
    except Exception as exc:
        return (
            "我识别到你想继续工作流，但读取当前 workflow state 失败。\n\n"
            f"```text\n{exc}\n```"
        )
    # The directory location is authoritative.  A prior user turn can mention
    # another model, while this run ID may uniquely belong to a different one.
    model_name = run_root.parents[1].name

    current_state = state.get("state")
    if current_state == SCENARIO_READY:
        try:
            scenario_request = load_scenario_request(model_name, run_id)
            result = run_simulation_from_scenario_request(scenario_request, rerun=False)
        except Exception as exc:
            return (
                "当前状态是 `SCENARIO_READY`，下一步应由 `SimulationAgent` 执行，但模拟阶段失败。\n\n"
                f"```text\n{exc}\n```"
            )
        return (
            "收到“继续”。我读取了 `workflow_state.json`，当前状态为 `SCENARIO_READY`，"
            "所以本轮只执行下一合法阶段：`SimulationAgent -> RUN_READY`。\n\n"
            "**结构化模拟结果**\n"
            f"```text\n{result}\n```"
        )

    if current_state in {RUN_READY, NO_SURFACE_INFLOW}:
        result = run_workflow_stage(model_name=model_name, run_id=run_id, target_stage='evidence_building')
        return '本轮只执行证据构建：\n' + result
    if current_state == EVIDENCE_READY:
        result = await advance_investigation(model_name, run_id, 'continue', task_id)
        return format_investigation_result(result)

    return None


def deterministic_workflow_stage_evidence(message: str, transcript: list[dict[str, str]]) -> str | None:
    """Route explicit SWMM-Agentic2 workflow-stage requests to StatefulOrchestrator."""
    context = "\n".join(item["content"] for item in transcript[-8:])
    combined = f"{context}\n{message}"
    wants_workflow = contains_any(
        message,
        [
            "workflow",
            "工作流",
            "状态机",
            "evidence",
            "证据",
            "diagnosis",
            "诊断",
            "verification",
            "核查",
            "unsupported",
            "推进到",
            "advance",
            "verified_ready",
        ],
    )
    if not wants_workflow:
        return None

    run_id = extract_run_id(combined)
    if not run_id:
        run_match = re.search(r"\b([A-Za-z0-9]+__[A-Za-z0-9_.-]+__\d{8}_\d{6})\b", combined)
        run_id = run_match.group(1) if run_match else ""
    if not run_id:
        return None

    model_name = extract_model_name(message) or extract_model_name(combined) or "songhua_swmm_2d"
    lowered = message.lower()
    if contains_any(lowered, ['diagnosis', '诊断', 'verification', '核查', '报告', 'report']):
        return None  # Only task-scoped roles can handle these actions.
    result = run_workflow_stage(model_name=model_name, run_id=run_id, target_stage='evidence_building',
                                rerun=contains_any(lowered, ['rerun', '重建', '重新', '覆盖']))
    return '结构化证据构建结果：\n' + result


def scenario_agent_evidence(message: str) -> str | None:
    """Route model/project/event organization to the workflow ScenarioAgent."""
    model_name = extract_model_name(message)
    rainfall_file = extract_rainfall_file(message)
    run_id = extract_run_id(message)
    scenario_name = extract_scenario_name(message) or "baseline"
    wants_prepare = contains_any(message, ["准备", "创建", "生成", "scenario_request", "情景请求", "场景请求", "prepare scenario"])
    if wants_prepare and rainfall_file:
        result = prepare_scenario_request(
            model_name=model_name,
            rainfall_file=rainfall_file,
            event_name=Path(rainfall_file.replace("\\", "/")).stem,
            scenario_name=scenario_name,
            run_id=run_id,
        )
        return "ScenarioAgent evidence:\n" + json.dumps(result, ensure_ascii=False, indent=2)

    wants_models = contains_any(message, ["models", "模型项目", "项目", "模型"])
    wants_list = contains_any(message, ["列出", "list", "available"])
    wants_check = contains_any(message, ["检查", "验证", "完整", "check", "validate"])
    wants_ca2d = contains_any(message, ["ca2d", "静态模型", "static"])
    wants_rainfall = contains_any(message, ["降雨事件", "降雨文件", "rainfall event", "list rainfall"])
    wants_simulation_or_analysis = contains_any(
        message,
        ["模拟", "运行", "run", "simulate", "plot", "绘图", "图", "报告", "分析"],
    )

    if wants_rainfall:
        return "ScenarioAgent evidence:\n" + list_rainfall_events(model_name)

    if wants_ca2d and wants_check:
        target = f"models/{model_name}" if model_name else ""
        return "ScenarioAgent evidence:\n" + check_ca2d_model(target)

    if wants_ca2d and not wants_simulation_or_analysis:
        target = f"models/{model_name}" if model_name else ""
        return "ScenarioAgent evidence:\n" + check_ca2d_model(target)

    if wants_models and wants_list and wants_check:
        if model_name:
            return "ScenarioAgent evidence:\n" + check_swmm_2d_project(model_name)
        return "ScenarioAgent evidence:\n" + check_all_swmm_2d_projects()

    if wants_models and wants_list:
        return "ScenarioAgent evidence:\n" + list_swmm_2d_models()

    if wants_models and wants_check:
        if model_name:
            return "ScenarioAgent evidence:\n" + check_swmm_2d_project(model_name)
        return "ScenarioAgent evidence:\n" + check_all_swmm_2d_projects()

    if "models" in message.lower() and not wants_simulation_or_analysis:
        return "ScenarioAgent evidence:\n" + check_all_swmm_2d_projects()

    if model_name and not wants_simulation_or_analysis:
        return "ScenarioAgent evidence:\n" + check_swmm_2d_project(model_name)

    return None


def simulation_agent_evidence(message: str, transcript: list[dict[str, str]]) -> str | None:
    """Route rainfall-driven coupled runs to the workflow SimulationAgent."""
    request = build_simulation_request(message, transcript)
    if request is None:
        # A rainfall file plus an execution request is not enough authority to
        # guess a model.  Keep this deterministic instead of falling back to LLM.
        if extract_rainfall_file(message) and contains_any(message, ["执行模拟", "运行模拟", "模拟计算", "开始模拟", "执行计算", "运行模型", "完整模拟", "耦合模拟"]):
            return (
                "INPUT_REJECTED: 未执行模拟。请使用完整、精确的 model_name，并选择该模型 events/ 目录中的降雨文件；"
                "系统不会根据相近名称或历史对话猜测模型。"
            )
        return None
    prepared = prepare_scenario_request(**request)
    scenario_request = prepared["scenario_request"]
    return "SimulationAgent evidence:\n" + run_simulation_from_scenario_request(scenario_request, rerun=False)


def run_simulation_from_scenario_request(scenario_request: dict[str, Any], rerun: bool = False) -> str:
    """Run SimulationAgent from scenario_request and write RUN_READY state."""
    result = run_swmm_2d_project_from_rainfall(
        model_name=scenario_request["model_name"],
        rainfall_file=scenario_request["rainfall_file"],
        event_name=scenario_request["event_name"],
        scenario_name=scenario_request["scenario_name"],
        run_id=scenario_request["run_id"],
        expected_event_sha256=scenario_request.get("event_sha256", ""),
    )
    parsed = None
    try:
        parsed = json.loads(result.split("\n", 1)[1])
    except Exception:
        parsed = None
    if isinstance(parsed, dict) and parsed.get("run_root"):
        run_root = Path(parsed["run_root"])
        ca2d_status = parsed.get("ca2d", {}).get("status")
        target_state = NO_SURFACE_INFLOW if ca2d_status == NO_SURFACE_INFLOW else RUN_READY
        state = build_state(parsed["model_name"], parsed["run_id"], run_root, state=target_state)
        existing_history = []
        state_path = run_root / "workflow_state.json"
        if state_path.exists():
            try:
                existing_history = json.loads(state_path.read_text(encoding="utf-8")).get("history", [])
            except json.JSONDecodeError:
                existing_history = []
        state["history"] = list(existing_history)
        state["history"].append(
            {
                "stage": "simulation",
                "target_state": target_state,
                "completed_at": parsed.get("created_at", ""),
                "rerun": bool(rerun),
            }
        )
        save_state(run_root, state)
        if parsed.get("ca2d", {}).get("surface_inflow_status") == NO_SURFACE_INFLOW:
            return (
                "SWMM 与 CA2D 均已完成。本次未检测到正节点溢流，"
                "因此二维边界入流为零；已生成地表水深为零的 CA2D 结果。\n\n"
                + result
            )
    return result


def build_simulation_request(message: str, transcript: list[dict[str, str]]) -> dict[str, Any] | None:
    """Infer a fixed-tool simulation request from the latest message and recent plan."""
    # Assistant replies contain inventories and old paths. They are evidence, not
    # authority to select a model/event. Only user-authored turns may supply input.
    recent_context = "\n".join(item["content"] for item in transcript[-8:] if item["role"] == "user")
    wants_run = contains_any(
        message,
        [
            "执行模拟",
            "运行模拟",
            "模拟计算",
            "开始模拟",
            "执行计算",
            "运行模型",
            "完整模拟",
            "耦合模拟",
            "run simulation",
            "run model",
            "simulate",
        ],
    )
    confirmation = is_continue_confirmation(message)
    prior_planned_run = contains_any(
        recent_context,
        [
            "执行模拟计算",
            "运行完整的swmm-2d",
            "运行完整的 SWMM-2D",
            "使用这个降雨事件文件运行",
            "run_swmm_2d_project_from_rainfall",
            "写入降雨",
            "导出节点溢流",
        ],
    )
    if not wants_run and not (confirmation and prior_planned_run):
        return None

    rainfall_file = extract_rainfall_file(message) or extract_rainfall_file(recent_context)
    if not rainfall_file:
        return None

    model_name = extract_model_name(message)
    if not model_name:
        # Preserve the latest explicit user model selection; do not let an older
        # model mentioned in an inventory win because paths are alphabetically sorted.
        for item in reversed(transcript[:-1]):
            if item["role"] != "user":
                continue
            model_name = extract_model_name(item["content"])
            if model_name:
                break
    if not model_name:
        return None
    scenario_name = extract_scenario_name(message) or extract_scenario_name(recent_context) or "baseline"
    run_id = extract_run_id(message) or extract_run_id(recent_context)
    event_name = Path(rainfall_file.replace("\\", "/")).stem or "manual_event"
    return {
        "model_name": model_name,
        "rainfall_file": rainfall_file,
        "event_name": event_name,
        "scenario_name": scenario_name,
        "run_id": run_id,
    }


def is_continue_confirmation(message: str) -> bool:
    compact = message.strip().lower()
    for token in [" ", "\t", "\r", "\n", "，", "。", ",", ".", "!", "！", "?", "？"]:
        compact = compact.replace(token, "")
    return compact in {
        "继续",
        "继续补证",
        "同意补证",
        "开始补证",
        "开始",
        "下一步",
        "执行",
        "运行",
        "确认",
        "好的",
        "好",
        "是的",
        "可以",
        "按此计划执行",
        "按计划执行",
        "continue",
        "go",
        "yes",
        "ok",
    }


def extract_rainfall_file(text: str) -> str:
    normalized = text.replace("\\", "/")
    patterns = [
        r"(models/[A-Za-z0-9_.-]+/events/[^\s，。；;\"'<>]+?\.(?:txt|csv|dat|rain|prcp|precip|ts))",
        r"(events/[^\s，。；;\"'<>]+?\.(?:txt|csv|dat|rain|prcp|precip|ts))",
        r"([A-Za-z0-9_.-]*rain[A-Za-z0-9_.\-/]*\.(?:txt|csv|dat|rain|prcp|precip|ts))",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip()
        if value.lower().startswith("models/"):
            parts = value.split("/", 2)
            if len(parts) == 3:
                return parts[2]
        if "/" not in value:
            return f"events/{value}"
        return value
    return ""


def extract_run_id(text: str) -> str:
    patterns = [
        r"(?:run_id|运行ID|运行编号|输出编号)\s*[:=：]\s*([A-Za-z0-9_.-]+)",
        r"(?:保存为|命名为|编号为)\s*([A-Za-z0-9_.-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def extract_workflow_run_id(text: str) -> str:
    patterns = [
        r"['\"]?run_id['\"]?\s*[:=：]\s*['\"]?([A-Za-z0-9_.-]+)",
        r"(?:运行ID|运行编号|输出编号)\s*[:=：]\s*['\"]?([A-Za-z0-9_.-]+)",
        r"\b([A-Za-z0-9_]+__[A-Za-z0-9_.-]+__\d{8}_\d{6})\b",
        r"\b(agentic2_[A-Za-z0-9_.-]+)\b",
        r"\b(my_[A-Za-z0-9_.-]+)\b",
    ]
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return matches[-1] if matches else extract_run_id(text)


def extract_scenario_name(text: str) -> str:
    patterns = [
        r"(?:scenario|情景|场景)\s*[:=：]\s*([A-Za-z0-9_.-]+)",
        r"scenarios/([A-Za-z0-9_.-]+)/model\.inp",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    if "baseline" in text.lower():
        return "baseline"
    return ""


def contains_any(text: str, markers: list[str]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def extract_model_name(text: str) -> str:
    normalized = text.replace("\\", "/")
    path_match = re_search_model_path(normalized)
    if path_match and (MODELS_DIR / path_match).is_dir():
        return path_match
    model_roots = sorted(path for path in MODELS_DIR.iterdir() if path.is_dir()) if MODELS_DIR.exists() else []
    # Only an exact identifier token is accepted. For example,
    # "suanliguanw_swmm_2d" must never match "Gsuanliguanw_swmm_2d".
    matches = [
        model_root.name
        for model_root in model_roots
        if re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(model_root.name)}(?![A-Za-z0-9_.-])", text, flags=re.IGNORECASE)
    ]
    return matches[0] if len(matches) == 1 else ""


def re_search_model_path(text: str) -> str:
    import re

    match = re.search(r"models/([A-Za-z0-9_.-]+)", text)
    if match and match.group(1).lower() != "models":
        return match.group(1)
    return ""


def build_task_prompt(transcript: list[dict[str, str]]) -> str:
    conversation = "\n".join(
        f"{item['role']}: {item['content']}" for item in transcript[-12:]
    )
    latest = transcript[-1]["content"]
    model_inventory = build_model_inventory_context()
    live_context = ''
    try:
        binding = investigation_binding(transcript)
        if binding:
            model_name, run_id, task_id = binding
            state = load_active_task(model_name, run_id, task_id)
            if state:
                fields = ('task_id', 'model_name', 'run_id', 'state', 'revision', 'report_revision',
                          'report_file', 'display_report', 'display_report_file', 'pending_evidence_requests', 'evidence_plan', 'evidence_closure', 'last_attempt')
                live_context = 'Persisted active task state:\n' + json.dumps({k: state[k] for k in fields if k in state}, ensure_ascii=False)
    except (ValueError, FileNotFoundError) as exc:
        live_context = 'Persisted task binding could not be resolved: ' + str(exc)
    return (
        "You are continuing a human-in-the-loop SWMM-Agentic2 workflow-stage web chat.\n"
        "The active architecture is StatefulOrchestrator plus workflow-stage agents: "
        "ScenarioAgent, SimulationAgent, EvidenceBuilderAgent, DiagnosisAgent, VerificationAgent, and ReportAgent.\n"
        "At service startup and before handling user work, treat the project-root models/ directory as the source of truth.\n"
        "Never assume data/example.inp exists or use it as a default model.\n"
        f"{model_inventory}\n\n"
        f"{live_context}\n\n"
        "Use the transcript to preserve the current plan and next-step state.\n"
        "If the latest user message is a confirmation, continue with exactly the next step.\n"
        "If there is no clear next step in the transcript, ask the user to confirm the next step instead of guessing.\n"
        "After evidence construction call DiagnosisAgent(model_name, run_id) without a question to deliver the default whole-run preliminary overflow diagnosis.\n"
        "User follow-up questions prepare scoped tasks. Preserve task_id for subsequent diagnosis, evidence retrieval, verification and reports.\n"
        "Deliver the preliminary report before retrieving pending evidence. There is no legacy run-level diagnosis fallback.\n"
        "Never say a tool or simulation succeeded unless the current turn actually observed that result.\n"
        "If it is a new request, give a concise plan and ask whether to continue.\n\n"
        f"Transcript:\n{conversation}\n\n"
        f"Latest user message:\n{latest}"
    )


def build_model_inventory_context() -> str:
    if not MODELS_DIR.exists():
        return f"Current model inventory: no project-root models directory exists at {MODELS_DIR}."

    model_lines = []
    for model_root in sorted(path for path in MODELS_DIR.iterdir() if path.is_dir()):
        baseline = model_root / "swmm" / "scenarios" / "baseline" / "model.inp"
        events_dir = model_root / "events"
        event_files = []
        if events_dir.exists():
            event_files = [
                str(path.relative_to(model_root))
                for path in sorted(events_dir.rglob("*"))
                if path.is_file() and path.suffix.lower() in {".txt", ".csv", ".dat", ".rain", ".prcp", ".precip", ".ts"}
            ]
        model_lines.append(
            "- "
            f"{model_root.name}: model_yaml={(model_root / 'model.yaml').exists()}, "
            f"baseline_inp={baseline.exists()}, "
            f"events={event_files or 'none'}"
        )

    if not model_lines:
        return f"Current model inventory: project-root models directory is empty at {MODELS_DIR}."
    return "Current model inventory from project-root models/:\n" + "\n".join(model_lines)


def session_log_path(session_id: str) -> Path:
    safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")[:80]
    return WEB_LOG_DIR / f"{safe_id}.jsonl"


def append_session_log(session_id: str, role: str, content: str) -> None:
    record = {"role": role, "content": content}
    with session_log_path(session_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def is_planning_only_request(message: str) -> bool:
    normalized = message.lower()
    planning_markers = [
        "\u5148\u7ed9\u8ba1\u5212",
        "\u4e0d\u8981\u7acb\u5373\u6267\u884c",
        "\u4e0d\u8981\u6267\u884c",
        "\u522b\u6267\u884c",
        "\u53ea\u7ed9\u8ba1\u5212",
        "\u4ec5\u7ed9\u8ba1\u5212",
        "plan only",
        "do not execute",
        "don't execute",
    ]
    return any(marker in normalized for marker in planning_markers)


def repair_mojibake(text: str) -> str:
    if not looks_like_mojibake(text):
        return text
    try:
        repaired = text.encode("gbk", errors="strict").decode("utf-8", errors="strict")
    except UnicodeError:
        return text
    if chinese_score(repaired) > chinese_score(text):
        return repaired
    return text


def looks_like_mojibake(text: str) -> bool:
    if any("\ue000" <= char <= "\uf8ff" for char in text):
        return True
    markers = [
        "\u7487",
        "\u9359",
        "\u93b4",
        "\u6d93",
        "\u6b22",
        "\u95c6",
        "\u6a3f",
        "\u951b",
        "\u6d93",
        "\u6f36",
        "\u935a",
        "\u5d41",
        "\u5d46",
        "\u20ac",
        "\ufffd",
    ]
    return any(marker in text for marker in markers)


def chinese_score(text: str) -> int:
    common = set(
        "\u7684\u4e00\u662f\u5728\u4e86\u8bf7\u68c0\u67e5\u9879\u76ee\u662f\u5426\u5b8c\u6574"
        "\u5148\u7ed9\u8ba1\u5212\u4e0d\u8981\u7acb\u5373\u6267\u884c\u7ee7\u7eed\u6a21\u62df"
    )
    return sum(1 for char in text if char in common)


def is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "ratelimiterror" in exc.__class__.__name__.lower()
        or "rate limit" in text
        or "rate limiting" in text
        or "system is too busy" in text
        or "error code: 429" in text
        or "'code': 50609" in text
    )


def is_llm_timeout_error(exc: Exception) -> bool:
    text = str(exc).lower()
    class_name = exc.__class__.__name__.lower()
    return (
        "apitimeouterror" in class_name
        or "readtimeout" in class_name
        or "request timed out" in text
        or "readtimeout" in text
        or "httpx.readtimeout" in text
        or "httpcore.readtimeout" in text
    )
