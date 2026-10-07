# Report Agent

`pipeline.generate_display_report(root, task_directory, state, complete=None)`
is the generation entry point. `attach_display_report` adds its explicit result to
task state. `complete` is an optional sync/async callback receiving the structured
report prompt, used for offline testing; production uses the configured model.

`materials.py` validates the current task binding and reads saved rainfall, SWMM,
surface grid and diagnosis files. It calculates metrics without rerunning the solver
or inferring new causes. `plots.py` regenerates charts for the actual timestamps,
node set and event set; `labels.py` carries forward the preview's automatic label
placement. `narrative.py` gives the model fact references, existing event judgments
and a JSON contract. Invalid responses receive up to two corrective attempts.
`render.py` escapes prose and embeds images. The pipeline checks coverage, decoded
images and source freshness before publishing the completed path to task state.

The report consumes the current verified diagnosis, including supported combined
mechanisms and separately worded possible influences. It is not a second Diagnosis
Agent. Immutable structured inputs and their internal Markdown remain in material
records; implementation fields and evidence IDs are not rendered in report prose.

Each generation has an independent directory. Failure is explicit and retains
attempt records. A previous successful file is preserved, but a failed new revision
cannot advertise it as the current report. No template narrative is substituted
when the model is unavailable.

## Node prose experiment (v1.2)

`prompts/event_rewrite_v1.md` teaches fact selection, process narration and faithful
explanation of joint mechanisms. `prompts/event_example_v1.json` supplies the paired
P6 teaching input/output. The guide is part of the system prompt; the example is
included in every writing request and in `report_prompt.json`. Example facts use an
`EX` namespace and cannot be substituted into the current report.

Event process facts retain the local time window and separate bound flow comparisons,
depth, flooding and head. Values remain tied to object and time inside each clause;
the model selects useful clauses instead of copying every metric at every timestamp.
Event-owned fact references cannot be reused under a different event. Candidate
influences retain explicit uncertainty, and internal assessment patches are rejected.
Generated node titles are escaped and shown above the process analysis.

The prompt assets participate in producer hashes, invalidating cached reports when
they change. Generations retain independent output directories and raw attempt logs.
This first experiment focuses on node analysis; the other sections receive shared
writing guidance and still need subsequent case review. Structural validation alone
does not certify prose quality or causal fidelity.

## Chapter-five overview (v1.3)

`prompts/causes_overview_v1.md` supplies a dedicated input/output example for the
overall cause assessment before the event analyses. It teaches a direct explanation
of joint causes and node differences, followed by the downstream influence where
relevant. Detailed topology lists stay in event analyses instead of dominating the
overview.

The product prose directly presents the diagnosis. Internal statements such as
"只能作为候选影响" or "不能据此确定主因" are excluded and rejected by the validator;
the prose does not end by withdrawing its preceding explanation. Supported causes
are stated directly, while a source candidate retains natural possible wording.
Removing status commentary does not upgrade that source judgment into a proved cause.

`scripts/probe_report_causes_overview.py` tests just this overview with the configured
model against an existing report's saved material. It saves the actual prompt, model
attempts and prose excerpt in a separate directory and leaves the existing HTML and
task state intact. Normal full generation also consumes this guide.
