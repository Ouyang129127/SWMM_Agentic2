# Report display specimens

These files produce human-facing HTML specimens from an existing saved simulation.
They do not change DiagnosisAgent, ReportAgent, or model inputs.

## Versions

- `build_display_report_v1.py`: original specimen, retained unchanged.
- `build_display_report_v2.py`: workflow branding, all seven overflow-node analyses,
  each with its own saved process chart, and automatic map labels.
- `build_display_report_v3.py`: each node retains its process and adds causal
  judgments rendered from the saved diagnosis, including conditional downstream
  influence and combined mechanisms. A diagnosis-to-prose mapping stays internal.
- Outputs are separated under the saved run's `report_preview_v1/` and
  `report_preview_v2/` and `report_preview_v3/`. The HTML embeds all PNG/GIF media
  and can open offline.
- `v1_preservation_manifest.json` records the original version's file hashes.
- `v2_preservation_manifest.json` records version 2 and the shared label module.

From the project root:

```powershell
.\.venv\Scripts\python.exe report_previews\build_display_report_v3.py
```

The specimen builder's narrative and data selection target the current single-peak
UrbanDrainage run. The label-placement module is independent of that run.

## Reusable map labels

`map_annotations.place_node_labels(ax, points)` takes an existing Matplotlib axes
and a list of `{label, x, y}` objects in that axes' data coordinates. Node names,
coordinates, and the number of nodes come from data; there is no model-specific
offset table.

1. Plot the terrain/land categories and water depth.
2. Plot node markers at their mapped coordinates.
3. Finish figure layout, subplot adjustment, legends, and colorbar placement.
4. Call `place_node_labels` before saving the figure; do not alter layout after it.
5. Save the returned label boxes and coordinates in the internal rendering record.

The module evaluates the rendered text boxes against plot boundaries, other
labels, and node markers, and searches deterministic candidate positions. If
the plot has insufficient space, it raises a clear error; a caller can then
choose a larger figure or an inset. It never silently drops a node.

```python
from map_annotations import place_node_labels

points = [
    {"label": row.node_id, "x": float(row.cell_col), "y": float(row.cell_row)}
    for row in selected_node_mapping.itertuples()
]
layout = place_node_labels(ax, points)
fig.savefig(output_path, dpi=160, bbox_inches="tight")
```

## Internal records

Each specimen's metrics, source-file hashes, and derivation choices are saved
beside the HTML. Version 2 also saves all node-analysis materials and map-label
geometry. These are engineering records; they are not sections of the report.
Version 3 saves the original per-node mechanism statuses and alternatives beside
the corresponding human-facing paragraphs. Supported mechanisms remain stated as
supported causes; candidate downstream effects retain conditional wording.
Inapplicable facility checks and unresolved storage effects remain internal.

ReportAgent prompting and full model-independent report generation remain
separate follow-up work after the display template is settled.
