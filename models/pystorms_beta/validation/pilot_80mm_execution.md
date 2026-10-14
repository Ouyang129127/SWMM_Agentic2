## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run
- Origin Date: 2026-10-12 (Asia/Shanghai)
- Verification Status: UNVERIFIED (execution record; not independent physical/causal validation)
- Version Label: beta_pilot_80mm_v1

## Execution scope

User authorized rainfall simulation and diagnosis. First pilot: the same 4 h, 80 mm single-peak event under `baseline` and `free_outfall`; no other rainfall/scenario is authorized by this pilot record. Use the existing simulation, evidence, diagnosis, reference-check and reporting functions, without changing diagnostic logic. Supplementation: existing saved results and fixed tools only, at most two rounds. Provider completion calls capped at 21 per case. Hard execution timeout: 30 minutes per launched stage. No silent retry of a failed stage or simulation.

The worktree already contained two completed simulation outputs when this execution turn inspected it. They were reused only after verifying identities, rainfall copy/source/recorded hash, exact parsed equality with the prepared event INP, 1,441 SWMM samples, 289 CA2D samples and no native ERROR record. This turn did not launch duplicate simulations and does not attribute the pre-existing runs to a new simulation execution.

| Scenario | Retained run ID | Summary SHA-256 | Event INP SHA-256 |
| --- | --- | --- | --- |
| baseline | b80t_20261012_200227 | d735a409aa253a9540c456cba4326b39c023a171d690ecb44f45d441589b7306 | d4899b23f31f031ded307e0b6a6150f6f9601081a63bc01e47a39f7c36f534e3 |
| free_outfall | b80f_20261012_200334 | 10b2a21ca1cbe890c36e34c0ae6aa0a5611020e14e82e31210827f9be1e07110 | 53f23a9dea76594452a687441b924493516bc33e774c92b0f6b708c4867ea333 |

Rainfall SHA-256: `7322cb37ffe0cb4b0e3a4e737be4bd6fdb41004647e1bf828537f73dcd2641a6`.

## Initial numerical-quality observations

Both cases have positive surface injection. Source model, routing parameters, terrain, rainfall and time settings match the prepared pair; only the intended outfall boundary differs between scenario inputs.

| Metric | baseline | free_outfall |
| --- | ---: | ---: |
| Native runoff continuity error (%) | -0.003 | -0.003 |
| Native routing continuity error (%) | -3.348 | -0.266 |
| Overflow nodes (positive sampled-event count, not mapping row count) | 31 | 27 |
| Sampled contiguous overflow segments (not rainfall event count) | 302 | 239 |
| Native flooding loss (m³, rounded RPT totals) | 17,756 | 6,619 |
| Sampled overflow sent to CA2D (m³) | 17,003.329 | 6,703.751 |
| Peak single-node flooding (L/s, 1 min reports) | 8,428.336 | 1,818.217 |
| CA2D maximum depth (m) | 3.063913 | 0.542478 |
| Native initial stored volume (m³, rounded RPT) | 176 | 0 |
| Native final stored volume (m³, rounded RPT) | 30,229 | 17,833 |

Three shared native warnings: C33 minimum elevation drop; R1 crest raised to downstream invert; J120 maximum depth increased. In baseline, OUT0 is listed as nonconverging in 63.47% of steps; this is a numerical-quality caution, not proof of a hydraulic mechanism. The baseline continuity error is larger than the free-outfall case and should be addressed before treating the pair as a high-quality physical benchmark.

The native solver flooding budget and integration of the 1 min saved overflow reports are different accounting bases. Their differences are about -4.24% / +1.28% respectively, using rounded RPT totals. Near-zero resampling/coupling error concerns the sampled-flow transfer only; it does not eliminate native-routing or sampling error.

Both source INPs retain the same zero initial depth settings, but the native initial stored volume differs following boundary-dependent initialization. Therefore this pair includes boundary/startup response; no warm-up experiment has been conducted. Final native stored volume is substantial in both cases: a 24 h window is not evidence of complete drainage. The CA2D domain is closed and lacks infiltration, drainage and recoupling sinks; terminal surface water is not a validated real-world recession prediction.

Construction assumptions remain in the preparation README and manifests, suitable for supporting-methods documentation. No manuscript or diagnostic prompt is edited by this execution record. The observed contrast is provisional; expert-reviewed diagnostic accuracy and causal correctness are not established by reference checks alone.

## Stage commands and outputs

Evidence stage uses the existing CLI:

```powershell
.\.venv\Scripts\python.exe -u run_workflow.py --model pystorms_beta --run-id b80t_20261012_200227 --stage evidence_building
.\.venv\Scripts\python.exe -u run_workflow.py --model pystorms_beta --run-id b80f_20261012_200334 --stage evidence_building
```

Initial diagnosis uses `advance_investigation('pystorms_beta', run_id, action='initial')`. Continuation uses `continue_investigation(..., approve_evidence=True)` only when the unchanged existing `supplement_stop` fixed-tool policy permits it; two rounds maximum. Configured provider functions are wrapped for counting only, not replaced by fabricated completions. Native task audit files preserve responses, usage, failures and reference checks. A generated per-run `pilot_execution.json` records completion status and provider-call counts. Failed runs/tasks remain in place and are not retried automatically.

## Final execution status of this pilot turn

Both evidence stages completed via the unchanged CLI: 109,326 evidence rows for baseline and 108,948 for free outfall. The evidence packages include 302 and 239 sampled contiguous overflow segments, associated with 31 and 27 overflowing nodes respectively. They are not 302/239 separate rainstorms. The simulator's `ca2d.flooding_nodes=210` denotes nodes represented in its input table; it must not be used as the number of nodes that actually overflowed.

The baseline diagnosis made one configured DeepSeek completion call. The provider returned HTTP 400 before producing a diagnostic answer: requested input 8,849,839 tokens versus a 1,048,576-token context limit, as reported by that provider. The task remains at revision 0. No corrective retry, evidence supplementation, diagnosis-reference verification, unsupported-rate result or final HTML report was produced. This is an observed context-limit failure, not a simulation failure and not a measured diagnosis error/unsupported rate.

Free-outfall diagnosis was prepared locally, but its completion request was deliberately not sent after the baseline refusal. Offline serialization shows 15,761,956 input characters versus baseline's 22,899,678. Scaling by the baseline provider-reported token/character ratio gives approximately 6.09 million tokens; this is an **estimate**, not a measured provider token count. Status: `not_started_context_risk`, not a second observed HTTP failure. Both cases used zero supplement rounds.

The principal baseline input components are `local_process_series` (16,996,923 characters) and `local_structure` (4,394,829 characters), approximately 93.4% of request characters together. Free-outfall counterparts are 11,487,089 and 3,090,530 characters. Most scalar cell metrics were already represented as compact summaries; simply reducing the number of CA2D cell rows is not the identified primary remedy. The current whole-run initial-task policy selects and supplies all event records in full. Local structure and overlapping process windows recur across events; event/task partitioning and retrieval policy would need deliberate implementation and validation rather than silently truncating evidence.

See `pilot_prompt_size_preflight.json` for component counts and per-run `pilot_execution.json` for execution statuses. The baseline native failed-attempt audit is under `diagnosis_tasks/1bb3770dcbb74beeb8bf20c162da1e9c/`; the free task `84ba4fd5106748ac970ddadd2094a84f` is locally prepared with no model response. No original simulation output, source model or diagnostic implementation was changed.

The existing workflow produces **no delivered diagnosis in this pilot**. Completing the requested whole-run diagnosis now requires a decision about context-scale handling (e.g., scoped event/node tasks followed by audited aggregation), not repeat simulation. No new architecture or narrower replacement diagnosis was implemented automatically. This record preserves the failure boundary as experiment evidence, while numerical-quality cautions remain separate from the software-execution failure.
