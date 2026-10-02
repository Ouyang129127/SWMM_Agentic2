# SWMM-Agentic2

## Unified LLM configuration (2026-10-01)

All LLM entry points now share `llm.deepseek_flash`, using DeepSeek-V4.1-Flash
through the official `https://api.deepseek.com` endpoint. Its API model ID is
`deepseek-flash`, as documented in the [official release notice](https://api-docs.deepseek.com/zh-cn/news/news260910/).

Before this migration, the local configuration enabled DeepSeek-V3.2 for
orchestration/diagnosis/explanation and DeepSeek-V3.1-Terminus for coding, both
through SiliconFlow. Qwen-VL-Max was an optional third model for DataAnalyzer;
it had no API key in the local `.env` and was therefore inactive.

| LLM entry point | Current model |
| --- | --- |
| Web and CLI StatefulOrchestrator; LegacyTaskExecutor | DeepSeek-V4.1-Flash |
| Task-scoped DiagnosisAgent investigation | DeepSeek-V4.1-Flash |
| EvidenceExplainer; SimulationEvidenceExplainer | DeepSeek-V4.1-Flash |
| CodeRunner's coder | DeepSeek-V4.1-Flash |
| DataAnalyzer (including images) | DeepSeek-V4.1-Flash |

Deterministic scenario, simulation, evidence building, reference verification
and report generation do not independently call an LLM.

Copy `.env.example` to `.env` for a fresh setup and set `DEEPSEEK_API_KEY` there.
Only `DEEPSEEK_MODEL` selects the model; retired per-role model and Qwen settings
are no longer used. `.env` is ignored by Git. Shell environment variables take
precedence; restart running Web/CLI processes after changing configuration.

Text, JSON diagnosis, coding and vision requests default to `reasoning_effort=high`.
Requests carrying tools use `reasoning_effort=none`: pinned AutoGen 0.6.1 drops
DeepSeek's required `reasoning_content` on tool-call response/replay, causing
HTTP 400 in thinking mode. This compatibility adjustment applies to both ordinary
and streaming requests. It changes the reasoning mode, not the model. See the
[DeepSeek thinking-mode requirements](https://api-docs.deepseek.com/guides/thinking_mode/).
Request timeout defaults to 300 seconds and output limit to 12,000 tokens.

Use `.venv/Scripts/python scripts/smoke_llm.py --live` for synthetic text/JSON,
vision and multi-turn tool checks. It sends no project evidence and does not
simulate or modify diagnosis tasks. These connectivity checks do not establish
hydraulic diagnosis quality.

## Evidence selection update (2026-10-01)

New investigation tasks no longer select the first 60 rows or any top-N fraction.
They select complete event packages for the requested node/event scope, with
available adjacent node/link background. Global tasks retain all event packages
and receive deterministic scalar summaries across node, link and surface data;
raw grid rows remain in the frozen local snapshot. Summaries separate metrics,
units, calculation methods and thresholds, preserve per-source-window statistics,
and have independent evidence IDs and source selectors/hashes. They do not imply
causality, simultaneity or that every underlying object has been investigated.

Process series use lossless field-path tables when smaller: no samples, signs,
nulls or precision are dropped. Identical event scalar duplicates can be omitted
only when the event package already contains the same value, unit, time window
and calculation method. Missing package categories remain explicit.

Evidence lookup now returns all matching rows for an explicit object, event,
metric or evidence ID. Positional offsets are rejected. The complete serialized
request (system plus user text) is checked against a 120,000-character transport
budget; overflow is an explicit failure before any model call, never truncation.
Very large tasks still require explicit division by event/investigation question.
This is a character guard, not a provider-specific token guarantee.

Prepared legacy tasks migrate from their frozen snapshot on the next diagnosis
attempt and retain pre-migration copies. Legacy tasks with diagnosis revisions
must start a new task to use the new selection; historical results are preserved.
Restart the Web service to load the changed Python code. This update does not
repair the separate outer-orchestrator false-completion/state-integration issue.

## Diagnostic contract update (2026-09-27)

### Task-scoped LLM investigation (initial implementation)

EvidenceBuilder now prebuilds `evidence/first_pass_evidence.json` for every
sampled overflow episode, using all saved nodes rather than only surface-mapped
nodes. It contains event context, direct connectivity/settings, aligned local
head/flow series, directional inflow composition, facility/storage availability,
and explicit surface-association availability. Head, total inflow and lateral
inflow are read from the existing native `model.out`, not resimulated.
Initial implementation requires SI/LPS for the derived flow metrics. Missing
inputs remain null/unavailable. Process windows include one saved sample before
and after the event; they are initial context, not a universal causal window.

Investigation preparation imports this prebuilt package before legacy scalar
rows, checks its source hashes, and freezes the resulting snapshot. Thus the
DiagnosisAgent consumes EvidenceBuilder products, not raw simulation files.
Pump/control action series, storage volume series, and surface source attribution
remain explicitly unbuilt. Existing runs must rebuild evidence to receive the new
package; this change does not automatically mutate their stored artifacts.

`DiagnosisAgent(message=<original question>)` prepares a run-bound evidence
snapshot and returns `task_id`; it does not call the model during preparation.
After confirmation, `DiagnosisAgent(task_id=...)` runs one LLM investigation or
revision step. The model must address four questions and six mechanism statuses,
return structured claims and justified evidence requests, and cite visible IDs.

Follow the returned task state, one confirmed action at a time:

- `ready_for_diagnosis` / `revision_requested`: DiagnosisAgent.
- `awaiting_evidence_confirmation`: EvidenceBuilderAgent(task_id=...).
- `ready_for_verification`: VerificationAgent(task_id=...).
- `ready_for_report`: ReportAgent(task_id=...).
- `needs_user_decision`: stop and ask; do not automatically retry.

The investigation evidence tool retrieves prebuilt evidence by explicit filters
(the 2026-10-01 update replaces the original positional pagination).
Any additional, unbuilt evidence is recorded as unavailable, not computed or
invented by Diagnosis. This is not yet full six-mechanism engineering coverage.
Artifacts and revisions live under `runs/<run_id>/diagnosis_tasks/<task_id>/`.
Run-level deterministic screening remains available separately; it is not the
LLM investigation mode. Web requests involving diagnosis/tasks are sent through
the LLM orchestrator instead of the deterministic diagnosis shortcut.

CLI equivalent (replace placeholders with actual model/run/task IDs):

```powershell
python run_workflow.py --model <model> --run-id <run> --investigation-action prepare --question "全局洪涝诊断"
python run_workflow.py --model <model> --run-id <run> --investigation-action diagnose --task-id <task>
```

Subsequent `--investigation-action` values are `evidence`, `diagnose`, `verify`,
and `report`, as allowed by task state. Only `diagnose` calls the configured
external model using the selected evidence; review the task before invoking it.
Offline tests use a fake model client, not a live diagnostic-quality evaluation.

The initial diagnostic workflow now adds saved-sample overflow episodes in
`evidence/overflow_events.json` and event-specific evidence/claims. Consecutive
positive samples form one episode; a non-positive sample separates episodes.
Duration uses left-sample intervals (the terminal sample adds no duration).
Episode volume is explicitly a left-rectangle estimate, separate from existing
run-level volume metrics; no sub-step onset interpolation or gap merging is done.

Verification now checks current-model/run EvidenceID traceability only. Its
statuses are `references_verified`, `references_missing`, and `no_references`;
these do **not** establish hydraulic or causal validity. The legacy
`unsupported_rate.txt` path stores reference failure rate (N/A for zero claims).
Old verification artifacts must be regenerated before using the new reporter.

Reports default to a global view, retain explicitly selected node/event IDs,
and never add new causes. Unresolved follow-up references request an explicit
object. New mechanism questions request Diagnosis review; automatic dispatch
of a new report question still requires a newly confirmed investigation task.
`--until` now executes only the next stage and returns remaining stages for
human confirmation; it no longer runs through all stages in one call.

Run regression tests: `.venv/Scripts/python -m unittest discover -s tests -v`.
Historical architecture descriptions below include legacy behavior; this
section defines the updated reference-check and report semantics.

SWMM-Agentic2 is a workflow-stage-oriented SWMM-CA2D Agentic prototype. It keeps
the proven tool-first execution layer from SWMM-Agentic, then adds deterministic
stage agents for evidence construction, flood diagnosis, and evidence
verification.

The purpose of this version is to reduce routing drift: simulation should use
fixed tools, diagnosis should read evidence tables, and unsupported conclusions
should be measurable instead of hidden in natural-language output.

## Architecture

```text
User / expert request
  -> StatefulOrchestrator
  -> ScenarioAgent
  -> SCENARIO_READY
  -> SimulationAgent
  -> RUN_READY
  -> EvidenceBuilderAgent
  -> EVIDENCE_READY
  -> DiagnosisAgent
  -> DIAGNOSIS_READY
  -> VerificationAgent
  -> VERIFIED_READY
  -> ReportAgent
```

The first implementation now covers the pre-run and diagnostic stages:

- `ScenarioAgent`: validates model/event/scenario inputs and writes
  `runs/<run_id>/scenario_request.json`; the workflow state becomes
  `SCENARIO_READY`.
- `SimulationAgent`: reads `scenario_request.json` or equivalent parameters,
  runs the fixed SWMM-to-CA2D pipeline, and writes `workflow_state.json` as
  `RUN_READY` after successful simulation.
- `EvidenceBuilderAgent`: converts standardized SWMM/CA2D run outputs into
  `evidence/evidence_table.csv` and `evidence/evidence_summary.json`.
- `DiagnosisAgent`: reads only the evidence table and writes
  `diagnosis/diagnosis_claims.json` plus `diagnosis/risk_ranking.csv`.
- `VerificationAgent`: checks every claim against cited evidence and writes
  `verification/verification_report.json` plus `verification/unsupported_rate.txt`.
- `ReportAgent`: reads `VERIFIED_READY` artifacts and turns verified claims,
  evidence rows, and verification status into natural-language reports or
  single-point cause explanations.

## File Map

```text
workflow_agents/
  __init__.py
  schemas.py
  state.py
  scenario.py
  evidence_builder.py
  diagnosis.py
  verification.py
  orchestrator.py
  rules/
    diagnosis_rules.json
    verification_rules.json

run_workflow.py       Command-line workflow-stage runner
tools.py              Original SWMM/CA2D tools plus workflow-stage wrappers
main.py               AutoGen agents, now aware of workflow-stage tools
prompts.py            Tool-first and workflow-state routing instructions
ca2d.py               CA2D surface-flooding model
models/               Model projects copied from SWMM-Agentic
```

## Agent Boundary

SWMM-Agentic2 uses workflow-stage agents as the primary architecture:

```text
StatefulOrchestrator
ScenarioAgent
SimulationAgent
EvidenceBuilderAgent
DiagnosisAgent
VerificationAgent
ReportAgent
```

The legacy capability agents from SWMM-Agentic are retained only as lower-level
or auxiliary capabilities:

```text
LegacyTaskExecutor    legacy fixed-tool compatibility layer
CodeRunner      auxiliary custom analysis / temporary plotting only
DataAnalyzer    auxiliary result explanation only
```

The Web and CLI orchestrator now expose the workflow-stage agents directly.
Explicit workflow requests such as evidence construction, diagnosis,
verification, and unsupported-rate calculation should not be routed through the
legacy capability-agent shell.

Suggested Web test prompts:

```text
请列出 models 下的模型项目，并检查是否完整。
```

Expected route: `ScenarioAgent`.

```text
请准备 scenario_request，模型 songhua_swmm_2d，使用 events/rain1.txt，scenario baseline，run_id: my_test_run_001
```

Expected route: `ScenarioAgent -> SCENARIO_READY`.

```text
继续
```

Expected route after `SCENARIO_READY`: `SimulationAgent -> RUN_READY`.

```text
对 rain1__baseline__20260721_165600 推进到 verification 阶段，使用工作流 Agent。
```

Expected route: `StatefulOrchestrator -> EvidenceBuilderAgent / DiagnosisAgent / VerificationAgent`
depending on the current `workflow_state.json`.

## Model Assets

Model files are copied directly from the first SWMM-Agentic project. The primary
project is:

```text
models/songhua_swmm_2d/
```

It contains the baseline SWMM model, reusable CA2D static model, rainfall event
files, and completed run outputs.

## Run A Workflow Stage

Prepare a scenario request without running simulation:

```powershell
python -c "import asyncio, main; print(asyncio.run(main.ScenarioAgent(message='prepare scenario', model_name='songhua_swmm_2d', rainfall_file='events/rain1.txt', event_name='rain1', scenario_name='baseline', run_id='rain1__baseline__manual_test')))"
```

Advance an existing run to the next legal stage:

```powershell
python run_workflow.py --model songhua_swmm_2d --run-id rain1__baseline__20260721_165600
```

Run all implemented stages through verification:

```powershell
python run_workflow.py --model songhua_swmm_2d --run-id rain1__baseline__20260721_165600 --until verification
```

Rerun a completed stage:

```powershell
python run_workflow.py --model songhua_swmm_2d --run-id rain1__baseline__20260721_165600 --stage verification --rerun
```

## API And Web Test Setup

The local `.env` configures the official DeepSeek API and one model for all LLM
agents. For a fresh checkout, copy `.env.example` to `.env` and supply your
DeepSeek API key before starting the service.

Create and install the local environment:

```powershell
cd E:\SWMM_Agentic\SWMM-Agentic2
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the new SWMM-Agentic2 web frontend:

```powershell
.\run_web.ps1
```

Open:

```text
http://127.0.0.1:8001
```

The original SWMM-Agentic frontend can remain on `http://127.0.0.1:8000`.

## Verified Baseline

The run below has been processed through the SWMM-Agentic2 workflow:

```text
models/songhua_swmm_2d/runs/rain1__baseline__20260721_165600/
```

Generated artifacts:

```text
workflow_state.json
evidence/evidence_table.csv
evidence/evidence_summary.json
diagnosis/diagnosis_claims.json
diagnosis/risk_ranking.csv
verification/verification_report.json
verification/unsupported_rate.txt
```

Observed verification summary:

```text
total_claims: 40
supported: 40
partially_supported: 0
unsupported: 0
unsupported_rate: 0.0
```

## Design Rules

- Do not route official rainfall-to-SWMM-to-CA2D simulation to CodeRunner.
- Do not build diagnosis claims from raw SWMM/CA2D files; use
  `evidence_table.csv`.
- Do not calculate unsupported rate with LLM free text; use
  `VerificationAgent`.
- Do not answer user-facing reports by rerunning diagnosis or verification; use
  `ReportAgent` after `VERIFIED_READY`.
- Do not skip workflow states unless rerun behavior is explicitly requested and
  recorded in `workflow_state.json`.

## Next Extensions

Recommended next stages are:

- `BenchmarkAgent`: execute task sets and compare tool-only, tool-using LLM, and
  full workflow-stage Agentic variants.
