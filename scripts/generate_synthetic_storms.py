"""Generate three 4-hour, 80-mm, 5-minute Chicago-shaped synthetic events.

Shape parameters are illustrative, not calibrated local IDF coefficients.
No return period is assigned. Existing files are never overwritten.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "models/urban_drainage/events"
OUTPUT = ROOT / "models/urban_drainage/rainfall_generation/20260920"
START = datetime(2024, 1, 1)
STEP = 5
DURATION = 240
TOTAL = 80.0
B = 12.0
N = 0.75
R = 0.4


def pulse_cumulative(local_time, duration, depth):
    """Integral of a Chicago-shaped intensity, normalized to depth in mm."""
    t = np.clip(np.asarray(local_time, dtype=float), 0, duration)
    peak = R * duration
    def f(x):
        return x / (x + B) ** N
    before = R * (f(duration) - f(np.maximum(peak - t, 0) / R))
    after = R * f(duration) + (1 - R) * f(np.maximum(t - peak, 0) / (1 - R))
    return np.where(t <= peak, before, after) / f(duration) * depth


def main():
    EVENTS.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # start minute, duration in minutes, rainfall depth in mm
    specs = {
        "single": [(0, 240, 80)],
        "double": [(0, 110, 36), (130, 110, 44)],
        "triple": [(0, 70, 20), (85, 70, 36), (170, 70, 24)],
    }
    paths = {name: EVENTS / f"chicago_like_{name}_4h_80mm_5min.txt" for name in specs}
    if any(p.exists() for p in paths.values()) or (OUTPUT / "events.json").exists():
        raise FileExistsError("Generated event files already exist; choose a new output set.")
    edges = np.arange(0, DURATION + STEP, STEP)
    metadata = {"method": "normalized Chicago-shaped synthetic rainfall",
                "local_idf_calibration": False, "return_period_years": None,
                "shape_parameters": {"b_minutes": B, "n": N, "r": R},
                "start": START.isoformat(sep=" "), "duration_minutes": DURATION,
                "interval_minutes": STEP, "total_rainfall_mm": TOTAL,
                "intensity_unit": "mm/h", "timestamp_convention": "interval_start",
                "rainfall_end": "2024-01-01 04:00:00",
                "expected_simulation_end": "2024-01-01 07:00:00", "events": []}
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True, sharey=True)
    colors = ["#2578ac", "#dd8335", "#548757"]
    generated = []
    for index, (name, pulses) in enumerate(specs.items()):
        cumulative = sum(pulse_cumulative(edges - start, length, depth) for start, length, depth in pulses)
        intensity = np.diff(cumulative) * 60 / STEP
        # Milliths of mm/h match the current SWMM writer's three decimals.
        units = np.rint(intensity * 1000).astype(np.int64)
        units[np.argmax(units)] += int(round(TOTAL * 60 / STEP * 1000)) - int(units.sum())
        intensity = units / 1000
        assert np.all(intensity >= 0)
        assert abs(float(intensity.sum() * STEP / 60) - TOTAL) < 1e-10
        padded = np.r_[0, intensity, 0]
        peaks = np.where((padded[1:-1] > padded[:-2]) & (padded[1:-1] >= padded[2:]))[0]
        assert len(peaks) == index + 1, (name, peaks)
        rows = ["timestamp,value"]
        for minute, value in zip(edges, np.r_[intensity, 0]):
            time = START + timedelta(minutes=int(minute))
            rows.append(f"{time:%Y-%m-%d %H:%M:%S},{value:.3f}")
        paths[name].write_text("\n".join(rows) + "\n", encoding="utf-8")
        event = {"name": name, "file": str(paths[name].relative_to(ROOT)).replace("\\", "/"),
                 "peak_count": len(peaks), "rainfall_intervals": len(intensity), "rows_with_terminal_zero": len(edges),
                 "wet_minutes": int(np.count_nonzero(intensity) * STEP),
                 "total_rainfall_mm": float(intensity.sum() * STEP / 60),
                 "max_intensity_mm_h": float(intensity.max()),
                 "peak_intervals_minutes": [[int(edges[p]), int(edges[p+1])] for p in peaks],
                 "pulses": [{"start_min": s, "duration_min": d, "depth_mm": h} for s, d, h in pulses]}
        metadata["events"].append(event)
        generated.append((name, intensity))
        ax = axes[index]
        ax.bar(edges[:-1], intensity, width=STEP, align="edge", color=colors[index], alpha=.9)
        ax.set_title(f"{name.title()} peak | 4 h | 80 mm | 5-min intervals", loc="left", fontsize=12)
        ax.set_ylabel("Intensity (mm/h)")
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
    axes[-1].set_xlabel("Elapsed time (minutes)")
    axes[-1].set_xticks(np.arange(0, 241, 30))
    axes[-1].set_xlim(0, 240)
    fig.suptitle("Chicago-shaped synthetic rainfall events", fontsize=16)
    fig.tight_layout()
    fig.savefig(OUTPUT / "rainfall_comparison.png", dpi=180)
    plt.close(fig)
    (OUTPUT / "events.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
