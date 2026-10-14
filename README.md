# SWMM-Agentic2

## 模拟时间配置与导出 — 2026-10-11

新的降雨模拟统一从 SWMM 原生结果文件导出节点、管道和冒溢时序，
已移除模拟过程中采样导出的旧实现。每个模型必须在其模型文件夹中提供
`simulation_timing.json`；缺失时在计算和运行文件写入前明确报错。
当前已配置 `urban_drainage` 与 `Site_Drainage_Model`：管网保存 1 分钟，
地表入流采用 5 分钟区间平均，地表保存 5 分钟，雨后继续计算 3 小时。
已有运行结果保留原来的时间范围；新增配置不会自动更新历史模拟或报告。

## Web 分步状态机 — 2026-10-10

网页流程由程序控制执行权限。新任务先展示计划并明确选择模型、降雨文件；
每次用户回复“继续”，只执行一个动作，完成后立即返回等待确认：

准备情景 → 模拟 → 构建证据 → 准备诊断任务 → 诊断 → 核查引用 → 生成报告。

补证、诊断修正、引用核查和报告更新也分别需要确认。诊断阶段内部仍可针对
解析／合同校验错误进行一次修正，但不会自动进入核查或报告。核查失败时停在
诊断修正入口；模拟失败不会继续构建证据。“状态”“下一步是什么”只查询；
“暂停”暂停流程，恢复时先展示待执行步骤，重新等待确认。

`workflow_agents/web_session.py` 定义会话的模型、降雨、run_id、task_id、待执行动作
和确认版本。状态与聊天日志分别保存在 `conversation/web_sessions/<session_id>.state.json`
和 `.jsonl` 中；刷新页面恢复历史与待确认步骤。服务重启不会重放执行中的确认。
同一运行的网页操作会串行执行，过期的确认版本或已变化的保存状态不能推进下一步。

网页聊天模型只输出一轮解释／计划，不持有执行工具。执行阶段直接调用现有固定
管线和任务级动作，不使用 `initial` / `continue` 等会连续执行多个阶段的便利入口。
命令行及显式调用这些便利入口的脚本仍保留原行为。

更新后请重新启动 Web 服务、刷新页面，再点击“新会话”测试新流程。
自动回归：`.venv\Scripts\python.exe -m unittest discover -s tests`。

聊天默认只展示本步结果、关键发现与下一步；完整检查／模拟输出、补证对象和时窗
可展开查看，报告通过链接打开，不反复粘贴全文。旧会话中的长回复也默认折叠。
聊天解释模型的历史输入只保留摘要，不回传折叠的原始 JSON 和完整报告。
这不删减 DiagnosisAgent 的科学证据，也不改变保存文件与诊断引用。

模型返回上下文超限时，网页保留原任务与错误，停止同一输入的重复尝试。
请明确指定节点或事件，确认后建立新的较小调查任务。大规模补证仍可能超出
模型容量；页面折叠不会缩小 DiagnosisAgent 的实际证据输入，尚未实现自动分批诊断。

## CA2D 默认底图 — 2026-10-08

后续模拟的 `ca2d_animation.gif`、`ca2d_max_depth.png` 和 `ca2d_final_depth.png`
统一采用灰绿地形、灰色道路（`#d5dcdf`）、灰褐建筑的底图。土地保留柔和地形阴影
和淡等高线；积水沿用黄—橙—红配色、0.005 m 显示阈值及至少 0–0.35 m 的色标范围。
灰绿色只表示其余土地的显示颜色，不代表新增植被分类。没有道路图层的模型不绘制道路。

`surface_rendering.py` 管理统一底图。新建 UrbanDrainage 和 demo 静态模型保存原始
`terrain.npy` 供绘图使用；已有 UrbanDrainage 模型根据配置中记录的建筑抬高和道路降低
恢复显示地形。其他模型没有原始地面图层时，建筑处的阴影采用周围地面插值。
这些处理不修改求解器高程、阻力、水深或模拟时间。已有运行结果不会被自动覆盖。

## Current workflow — 2026-10-03

The only diagnosis workflow is task-scoped LLM investigation:
ScenarioAgent → SimulationAgent → EvidenceBuilderAgent → DiagnosisAgent → VerificationAgent → ReportAgent.
Run-level rule diagnosis, risk rankings, run-level verification/reporting, evidence graphs,
and generic CodeRunner/DataAnalyzer/LegacyTaskExecutor agents have been removed.

Run states stop at EVIDENCE_READY. That state means evidence construction completed;
it never means a diagnosis, verification or report completed. Diagnosis progress belongs
to a specific task_id under runs/<run_id>/diagnosis_tasks/.

## One evidence file

EvidenceBuilder creates only evidence/evidence_package.json. Its contract is:

- schema_name / schema_version: swmm_ca2d_evidence_package / 1.1.
- model_name / run_id / event_name / scenario_name: run binding.
- source_hashes / missing_sources: source integrity and explicit absence.
- event_detection: saved-sample resolution, positive tolerance and segmentation policy.
- overview: object/event counts, metric inventory and source availability.
- packages: node/event indexes referencing evidence IDs.
- evidence_rows: whole-run scalar statistics, event-local evidence and rainfall context.

Each event has six records: event_context, local_structure, local_process_series,
direct_source_composition, facilities_and_storage, surface_association. The latter
categories may contain unavailable/unbuilt data. Single-event facts are stored only
in event_context, not duplicated as scalar event rows or a separate event catalog.
Whole-run statistics have different scope and retain their independent meaning.

Event scope follows input connections upstream to the previous confluence,
downstream to the next divergence, and intermediate tributaries upstream to their
previous confluence. Boundary nodes and all their incident links are included;
the opposite endpoints supply head data but do not seed further traversal.
Facilities, special nodes, terminals, cycles and missing node definitions stop a
trace with an explicit reason. There is no fixed hop depth or object count.
All intermediate lateral inflows and signed model flows stay in the saved event
window. Direct-source composition still counts only target-incident links and the
target lateral inflow, preventing repeated counting of upstream corridor flows.
topology_scope records paths, roles and stop reasons. This is a deterministic
initial scope, not proof that every hydraulic cause lies within it.

Node flooding statistics use all saved nodes.tsv records, not only surface-mapped nodes.
Sources, units and calculation methods are explicit. Invalid/non-finite numeric data
cause a clear construction failure; they are not silently replaced with zero.
Whole-run volumes and event volumes use left-sample integration. Whole-run durations
use left intervals; terminal samples add no duration. Time_start/time_end describe
source coverage; at_time identifies an extremum. Link depth/reference metrics are
proxies, not proof of pressure, a bottleneck or capacity failure.

The package is a local evidence library, not the complete model input. Task preparation
selects complete related event evidence and connected scalar background, or all events
plus deterministic global summaries. Rainfall context is supplied for each scope.
Selection never uses top-N, row order, a fixed count or a percentage. Lookup returns all
matches for explicit objects/events/metrics/IDs. Selected records are sent in their
original JSON structure, including each record's metadata and all process samples.
The application sets no token generation budget or input character limit, including
in live-check scripts. There is no local limit configuration switch. The provider's
own defaults and context/output limits still apply. Evidence is never truncated
to satisfy a budget. Automatic multi-batch investigation is not
implemented. Transmission encoding, shared metadata/structure tables and roundtrip
validation have been removed. Source/snapshot integrity and evidence-reference
verification remain part of the workflow.

## Task states and artifacts

DiagnosisAgent(model_name, run_id) with no question/task resumes or creates a default
initial_overflow task, diagnoses every saved overflow event, reference-checks the
result and delivers a preliminary report. No initial user question is required.
Whole-run event counts, time range and integrated event volume are derived by
the program from the validated index/event_context, with a citable SUM_EVT record.
Each event must have its own process, six mechanism statuses and evidence gaps.
DiagnosisAgent(message=<follow-up question>) prepares a scoped task without a diagnosis LLM call.
DiagnosisAgent(task_id=...) executes an investigation/revision, including a corrective
response with saved parsing/contract feedback if necessary. Persistent failures
return execution_error and the same task_id, without verification/report delivery.

- ready_for_diagnosis / revision_requested → DiagnosisAgent(task_id).
- awaiting_evidence_confirmation → EvidenceBuilderAgent(task_id), after scope approval; only requests that add new evidence remain pending.
- ready_for_verification → VerificationAgent(task_id).
- ready_for_report → ReportAgent(task_id).
- preliminary_delivered → the preliminary report is available; a follow-up question creates a new scoped task.
- needs_user_decision → stop and ask the user.

Tasks freeze evidence_snapshot.json and record task.json. Diagnosis and verification
are versioned as diagnosis_rN.json and verification_rN.json, with latest copies and
file hashes. Every model attempt retains raw response, finish reason, usage,
parsed response and validation failure in diagnosis_attempt_<id>.json. Task
history records failures without replacing a valid diagnosis/report revision.
Reports are versioned as report_rN.json and preliminary_report_rN.md, with
report.json as the latest copy. Pending requests do not prevent preliminary
delivery: diagnose → verify → report → awaiting_evidence_confirmation → evidence.
Requests are classified as available, already_visible, no_match or unavailable.
Without new evidence, delivery finishes with the capability gaps preserved instead
of invoking another diagnosis. The active task is persisted in
diagnosis_tasks/active_task.json; existing tasks without a pointer are recovered by
snapshot creation order and current evidence-package binding. Web confirmations
read persisted task state and execute the next action before any conversational
routing. Chat logs are restored after service restart.
Ordinary empty claims cannot pass; a complete initial overview/event assessment
can pass reference checking independently of optional claims. A validated dry
run delivers a deterministic diagnosis without a diagnosis-model call; HTML writing still uses Report Agent.
Object/event validation recognizes declared nested nodes/links in the cited
event structure/process and rejects unrelated objects, events or citations.
Verification currently checks reference traceability only. It does not certify that
numbers, engineering interpretations or causal explanations are correct.
Task operations never fall back to run-level rules. Verification requires a task_id;
ReportAgent may resolve the run's persisted active task. Changed diagnosis questions require new tasks.

## HTML Report Agent

ReportAgent now prepares saved-result facts and plots, calls the configured report
model for structured Chinese prose, and renders a self-contained HTML report with
six sections, every diagnosed overflow event, node navigation and embedded images.
It runs after each verified diagnosis delivery. An already delivered task can also
generate HTML without repeating simulation, diagnosis or internal Markdown delivery:

```powershell
python scripts/build_display_report.py --model urban_drainage --run <run> --task <task>
```

Omit `--task` to use that run's active task. The public `ReportAgent(model_name,
run_id, task_id=...)` uses the same pipeline. The workflow CLI supports
`--investigation-action display_report --task-id <task>` for existing deliveries.
Code lives in `workflow_agents/reporting/`; the preview scripts remain examples.

Outputs live under `diagnosis_tasks/<task>/display_reports/rN/<generation>/`:
the HTML, calculated materials, figures, structured narrative, fact-text registry,
model attempts, generation status and quality checks. `task.json` exposes
`display_report.status` and `display_report_file`; the web chat links the completed
HTML. Unchanged successful generations are reused. Failed generations keep their
records and internal diagnosis delivery and never present old HTML as current.

Numbers and times in generated prose must reference program-supplied facts;
event coverage and source mechanism statuses are checked before rendering.
Source hashes and the current diagnosis/evidence binding are checked before and
after writing. These checks do not constitute independent hydraulic causal validation.
The report distinguishes 0.01 m general ponding from 0.15 m attention areas;
the solver is unchanged. Its surface opening explains the 0.15/0.27/0.40 m depth
classes from the CECS draft and the 0.15 m ponding/waterlogging boundary used by
Beijing Water Authority. Maps use a yellow-to-red depth gradient and a shared
numeric colorbar, without claiming formal warning grades from depth alone.
Current inputs require the existing LPS/m saved-output and static-grid formats.

## CLI

```powershell
python run_workflow.py --model urban_drainage --run-id <run> --stage evidence_building
python run_workflow.py --model urban_drainage --run-id <run> --investigation-action initial
python run_workflow.py --model urban_drainage --run-id <run> --investigation-action continue
python run_workflow.py --model urban_drainage --run-id <run> --investigation-action prepare --question "分析P6"
python run_workflow.py --model urban_drainage --run-id <run> --investigation-action diagnose --task-id <task>
```

`continue` resumes the active task (or an explicit --task-id), retrieves evidence
after confirmation if pending, and delivers the resulting verified report.
Other explicit task actions: status, evidence, verify, report. Follow the returned state.
An explicit review can request revision without evidence retrieval:
`--investigation-action review --task-id <task> --review-feedback <json-file>`.
The JSON contains issues with message and visible evidence_ids. Findings are
saved and bound by hash, passed to the next diagnosis, and do not replace the
previous report. This is a review channel, not an automatic causal verifier.
There is no fixed count limit on evidence_requests; each request still requires
valid parameters and a concrete engineering purpose.
Old runs must rebuild the unified package from saved simulation outputs and create
new tasks. Old CSV/first-pass JSON and old task formats are not runtime inputs.
Historical outputs are retained as history; no legacy compatibility implementation is kept.
Restart the Web service to load changed Python modules. Offline tests never
simulate or call an external model. Real initial-diagnosis acceptance uses:
`python scripts/accept_initial_diagnosis.py --model urban_drainage --run-id <run> --live`.
It preserves source/package hashes, checks complete event coverage and exact
program-rendered event facts, and stores acceptance.json in the new task.
Reference traceability, numerical prose validation and causal validity are
distinct; the latter two are not certified by this acceptance script.

## Model and simulation conventions

Models live under models/<model_name>/; discover available projects rather than
assuming a fixed model. Assets include model.yaml, static/, mapping/, events/,
swmm/scenarios/<scenario_name>/model.inp and runs/<run_id>/.
ScenarioAgent organizes/checks models and rainfall. SimulationAgent uses the fixed
SWMM-CA2D pipeline. Existing SI/LPS outputs are required for the current evidence
extraction. Missing surface output is accepted only when the simulation explicitly
records NO_SURFACE_INFLOW; it is not interpreted as a complete surface assessment.

## Runtime and LLM

Install requirements.txt in the project virtual environment. Copy .env.example to
.env and set DEEPSEEK_API_KEY. Model configuration is in llm.py; active orchestrator,
diagnosis and evidence-explanation clients share llm.deepseek_flash. Keep keys private.
Shell settings take precedence over .env. Launch the Web UI using run_web.ps1 or
run_web.bat. run_workflow.py is the offline construction / explicit investigation CLI.
Deterministic construction, retrieval, reference checking and report formatting do not
independently call an LLM. Orchestration and diagnosis do call the configured client.

## Validation and known limits

Run offline regression tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

scripts/audit_unified_evidence.py rebuilds the two recorded Chicago cases in temporary
copies, preserves historical event facts/direct composition, checks expanded
processes against saved outputs and compares selected request records directly to
their snapshot JSON.
It never simulates or invokes the model. scripts/smoke_live_investigation.py
requires an explicit --live option and a prepared modern task; it is not part of the
offline suite.

Not yet implemented: arbitrary-window new evidence calculation, diagnosis-directed
new topology expansion, pump/control action and storage-volume extraction, reliable
surface-source attribution, automatic task batching, CSO optimization, comprehensive
high-load assessment, and independent hydraulic/causal validation. Outer LLM reply
claims still require a separate execution-audit guard; deleting the old workflow does
not by itself eliminate unsupported natural-language completion claims.
