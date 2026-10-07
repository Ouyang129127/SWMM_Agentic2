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
