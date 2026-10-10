"""Read-only rainfall validation plus plot export; does not run either solver.

The three additional TXT inputs and their metadata were created with apply_patch.
This script independently checks decimal scaling, totals, timing, and source
hashes, then renders comparison plots. It never rewrites rainfall inputs.
"""
import csv
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from workflow_agents.rainfall_context import build_rainfall_context


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models/urban_drainage"
OUTPUT = MODEL / "rainfall_generation/20261009"
QUANTUM = Decimal("0.001")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_event(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ["timestamp", "value"], path
        rows = list(reader)
    times = [datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S") for row in rows]
    values = [Decimal(row["value"]) for row in rows]
    assert len(rows) == 49, path
    assert times[0] == datetime(2024, 1, 1), path
    assert times[-1] == datetime(2024, 1, 1, 4), path
    assert all(b - a == timedelta(minutes=5) for a, b in zip(times, times[1:])), path
    assert values[-1] == 0 and all(v >= 0 for v in values), path
    assert all(v == v.quantize(QUANTUM) for v in values), path
    return times, values


def draw_panel(ax, filename, color, title):
    _, values = read_event(MODEL / "events" / filename)
    ax.bar(range(0, 240, 5), [float(v) for v in values[:-1]], width=5,
           align="edge", color=color, alpha=.9)
    ax.set_title(title, loc="left", fontsize=11)
    ax.set_ylabel("Intensity (mm/h)")
    ax.set_xlim(0, 240)
    ax.set_ylim(0, 250)
    ax.set_xticks(range(0, 241, 30))
    ax.grid(axis="y", alpha=.2)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


def main():
    metadata = json.loads((OUTPUT / "events.json").read_text(encoding="utf-8"))
    for source in metadata["original_sources_preserved"]:
        assert digest(MODEL / source["file"]) == source["sha256"], source
    checks = []
    for event in metadata["events"]:
        path = MODEL / event["file"]
        times, values = read_event(path)
        source_times, source_values = read_event(MODEL / event["source_file"])
        assert times == source_times, path
        factor = Decimal(str(event["scale_factor"]))
        expected = [(v * factor).quantize(QUANTUM, rounding=ROUND_HALF_UP)
                    for v in source_values[:-1]]
        peak = max(range(48), key=lambda i: expected[i])
        target = Decimal(str(event["target_total_rainfall_mm"]))
        correction = target * 12 - sum(expected)
        expected[peak] += correction
        expected.append(Decimal("0"))
        assert values == expected, path
        assert sum(values[:-1]) / 12 == target, path
        assert correction == Decimal(str(event["rounding_total_correction_mm_h"])), path
        assert [(v == 0) for v in values] == [(v == 0) for v in source_values], path
        padded = [Decimal("0"), *values]
        peaks = [i for i in range(48)
                 if padded[i + 1] > padded[i] and padded[i + 1] >= padded[i + 2]]
        assert len(peaks) == event["peak_count"], path
        assert [times[i].strftime("%Y-%m-%d %H:%M:%S") for i in peaks] == [
            p["start"] for p in event["peak_intervals"]], path
        context = build_rainfall_context(path, model_name="urban_drainage")
        assert context["total_rainfall_mm"] == float(target), context
        assert context["rainfall_duration_min"] == 240, context
        assert context["rainfall_points"] == 49, context
        assert context["max_intensity_mm_per_h"] == float(max(values)), context
        checks.append({"file": event["file"], "sha256": digest(path),
                       "total_rainfall_mm": float(target), "rows": len(values),
                       "peak_count": len(peaks), "max_intensity_mm_h": float(max(values)),
                       "source_scaling_and_total_check": "passed",
                       "existing_rainfall_context_parser": "passed"})

    plot_paths = [OUTPUT / "additional_rainfall_curves.png",
                  OUTPUT / "rainfall_comparison_six_events.png",
                  OUTPUT / "rainfall_comparison_six_events.svg"]
    if any(path.exists() for path in plot_paths):
        raise FileExistsError("Plot exports already exist; no existing outputs were overwritten.")

    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True, sharey=True)
    new_specs = [("single", 60, "#548757"), ("single", 120, "#2578ac"),
                 ("double", 160, "#dd8335")]
    for ax, (shape, total, color) in zip(axes, new_specs):
        draw_panel(ax, f"chicago_like_{shape}_4h_{total}mm_5min.txt", color,
                   f"{shape.title()} peak | 4 h | {total} mm | 5-min intervals")
    axes[-1].set_xlabel("Elapsed time (minutes)")
    fig.suptitle("Additional Chicago-like synthetic rainfall events", fontsize=15)
    fig.tight_layout()
    fig.savefig(plot_paths[0], dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(15, 7.5), sharex=True, sharey=True)
    specs = [("single", 60, "#548757", "Added"), ("single", 80, "#2578ac", "Existing"),
             ("single", 120, "#22506d", "Added"), ("double", 80, "#e5b180", "Existing"),
             ("double", 160, "#dd8335", "Added"), ("triple", 80, "#8676a2", "Existing")]
    for ax, (shape, total, color, status) in zip(axes.flat, specs):
        draw_panel(ax, f"chicago_like_{shape}_4h_{total}mm_5min.txt", color,
                   f"{status}: {shape.title()} peak | 4 h | {total} mm")
    for ax in axes[-1]:
        ax.set_xlabel("Elapsed time (minutes)")
    fig.suptitle("Urban drainage rainfall test set | 5-minute mean intensities", fontsize=15)
    fig.tight_layout()
    fig.savefig(plot_paths[1], dpi=180)
    fig.savefig(plot_paths[2])
    plt.close(fig)
    print(json.dumps({"status": "passed", "original_sources_unchanged": True,
                      "simulation_executed": False, "events": checks,
                      "plots": [str(p.relative_to(MODEL)) for p in plot_paths]}, indent=2))


if __name__ == "__main__":
    main()
