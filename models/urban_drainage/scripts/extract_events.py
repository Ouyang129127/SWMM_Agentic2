"""Extract one timestamp/value rainfall file for each UrbanDrainage scenario."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
EVENTS = PROJECT / "events"


def section(text: str, name: str) -> list[str]:
    match = re.search(rf"(?ms)^\[{name}\]\s*\r?\n(.*?)(?=^\[|\Z)", text)
    if not match:
        return []
    return [line.strip() for line in match.group(1).splitlines() if line.strip() and not line.strip().startswith(";")]


def scenario_start(text: str) -> datetime:
    options = {row.split()[0].upper(): row.split(maxsplit=1)[1] for row in section(text, "OPTIONS") if len(row.split()) >= 2}
    return datetime.strptime(options.get("START_DATE", "11/13/2024") + " " + options.get("START_TIME", "00:00:00"), "%m/%d/%Y %H:%M:%S")


def rainfall_series(text: str) -> tuple[str, list[tuple[str, float]]]:
    raingages = section(text, "RAINGAGES")
    if not raingages:
        raise ValueError("No RAINGAGES section")
    fields = raingages[0].split()
    try:
        ts_name = fields[fields.index("TIMESERIES") + 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("The first raingage is not linked to a TIMESERIES") from exc
    rows = []
    for row in section(text, "TIMESERIES"):
        fields = row.split()
        if len(fields) < 3 or fields[0] != ts_name:
            continue
        try:
            rows.append((fields[1], float(fields[2])))
        except ValueError:
            continue
    if not rows:
        raise ValueError(f"Rainfall timeseries {ts_name} has no values")
    return ts_name, rows


def main():
    EVENTS.mkdir(parents=True, exist_ok=True)
    manifest = []
    for inp in sorted((PROJECT / "swmm" / "scenarios").glob("cenario_*/model.inp")):
        text = inp.read_text(encoding="utf-8", errors="ignore")
        ts_name, values = rainfall_series(text)
        start = scenario_start(text)
        if len(values) == 1:
            # SWMM accepts a single point for a short pulse, while the
            # ScenarioAgent event-file contract requires at least two times.
            # Add a zero-intensity start point without changing the pulse.
            values = [("00:00:00", 0.0), values[0]]
        output = EVENTS / f"{inp.parent.name}_{ts_name}.txt"
        lines = []
        for time_text, value in values:
            parsed = None
            for fmt in ("%H:%M:%S", "%H:%M", "%H:%M:%S"):
                try:
                    parsed = datetime.strptime(time_text, fmt)
                    break
                except ValueError:
                    pass
            if parsed is None:
                continue
            dt = start.replace(hour=parsed.hour, minute=parsed.minute, second=parsed.second)
            lines.append(f"{dt:%Y-%m-%d %H:%M:%S},{value:g}")
        output.write_text("timestamp,value\n" + "\n".join(lines) + "\n", encoding="utf-8")
        manifest.append({"scenario": inp.parent.name, "timeseries": ts_name, "event_file": str(output.relative_to(PROJECT)).replace("\\", "/"), "records": len(lines)})
    (EVENTS / "manifest.json").write_text(__import__("json").dumps(manifest, indent=2), encoding="utf-8")
    print(__import__("json").dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
