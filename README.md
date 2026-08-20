# SWMM-Agentic2

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

The `.env` file is copied from the original SWMM-Agentic project, so the same
OpenAI-compatible API URLs and keys are used by SWMM-Agentic2.

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
