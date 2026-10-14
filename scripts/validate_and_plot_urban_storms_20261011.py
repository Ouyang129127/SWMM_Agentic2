"""Validate four added storms and export figures; never run solvers or an LLM.

Rainfall TXT inputs and generation metadata are created with apply_patch.
This script reads them independently, reuses the previous validation utilities,
and refuses to overwrite existing figures. Without --plot it only validates.
"""
import argparse
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_and_plot_urban_storms_20261009 import (
    QUANTUM, digest, draw_panel, read_event, plt,
)
from workflow_agents.rainfall_context import build_rainfall_context

MODEL = ROOT / 'models/urban_drainage'
OUTPUT = MODEL / 'rainfall_generation/20261011'
ADDITIONS = {('single', 160), ('double', 120), ('triple', 120), ('triple', 160)}
PLOT_NAMES = ('additional_rainfall_curves.png', 'rainfall_comparison_nine_events.png',
              'rainfall_comparison_nine_events.svg')


def local_peaks(values):
    padded = [Decimal('0'), *values]
    return [i for i in range(48)
            if padded[i + 1] > padded[i] and padded[i + 1] >= padded[i + 2]]


def validate():
    metadata = json.loads((OUTPUT / 'events.json').read_text(encoding='utf-8'))
    assert {(e['shape'], e['target_total_rainfall_mm']) for e in metadata['events']} == ADDITIONS
    assert len(metadata['events']) == 4
    for source in metadata['original_sources_preserved']:
        assert digest(MODEL / source['file']) == source['sha256'], source['file']
    checks = []
    for event in metadata['events']:
        path = MODEL / event['file']
        source = MODEL / event['source_file']
        assert digest(source) == event['source_sha256'], source
        times, values = read_event(path)
        source_times, source_values = read_event(source)
        assert times == source_times, path
        factor = Decimal(str(event['scale_factor']))
        target = Decimal(str(event['target_total_rainfall_mm']))
        expected = [(v * factor).quantize(QUANTUM, rounding=ROUND_HALF_UP)
                    for v in source_values[:-1]]
        peak = max(range(48), key=lambda i: expected[i])
        correction = target * 12 - sum(expected)
        expected[peak] += correction
        expected.append(Decimal('0'))
        assert values == expected, path
        assert sum(values[:-1]) / 12 == target, path
        assert correction == Decimal(str(event['rounding_total_correction_mm_h'])), path
        assert times[peak].strftime('%Y-%m-%d %H:%M:%S') == event['correction_timestamp']
        assert [(v == 0) for v in values] == [(v == 0) for v in source_values], path
        peaks = local_peaks(values)
        assert peaks == local_peaks(source_values), path
        assert len(peaks) == event['peak_count']
        assert event['peak_count'] == {'single': 1, 'double': 2, 'triple': 3}[event['shape']]
        actual_peaks = [{'start': times[i].strftime('%Y-%m-%d %H:%M:%S'),
                         'end': times[i + 1].strftime('%Y-%m-%d %H:%M:%S'),
                         'intensity_mm_h': float(values[i])} for i in peaks]
        assert actual_peaks == event['peak_intervals'], path
        assert sum(5 for v in values[:-1] if v > 0) == event['wet_minutes']
        deviation = max(abs(v - s * factor) for v, s in zip(values, source_values))
        assert deviation == Decimal(str(event['max_deviation_from_exact_scaling_mm_h']))
        context = build_rainfall_context(path, model_name='urban_drainage')
        assert context['total_rainfall_mm'] == float(target), context
        assert context['rainfall_duration_min'] == 240, context
        assert context['rainfall_points'] == 49, context
        assert context['effective_rainfall_duration_min'] == event['wet_minutes']
        assert context['max_intensity_mm_per_h'] == float(max(values)), context
        checks.append({'file': event['file'], 'sha256': digest(path),
                       'total_rainfall_mm': float(target), 'rows': len(values),
                       'peak_count': len(peaks), 'max_intensity_mm_h': float(max(values)),
                       'scaling_total_timing_peaks_dry_intervals_check': 'passed',
                       'existing_rainfall_context_parser': 'passed'})
    matrix_checks = []
    for shape in ('single', 'double', 'triple'):
        for total in (80, 120, 160):
            name = f'chicago_like_{shape}_4h_{total}mm_5min.txt'
            _, values = read_event(MODEL / 'events' / name)
            assert sum(values[:-1]) / 12 == Decimal(total), name
            assert len(local_peaks(values)) == {'single': 1, 'double': 2, 'triple': 3}[shape]
            matrix_checks.append({'file': 'events/' + name, 'total_rainfall_mm': total,
                                  'sha256': digest(MODEL / 'events' / name)})
    return {'status': 'passed', 'original_six_events_unchanged': True,
            'simulation_executed': False, 'llm_called': False,
            'events': checks, 'nine_scene_matrix': matrix_checks}


def plots():
    paths = [OUTPUT / name for name in PLOT_NAMES]
    if any(path.exists() for path in paths):
        raise FileExistsError('Existing figures will not be overwritten; run without --plot to revalidate.')
    colors = {80: '#548757', 120: '#2578ac', 160: '#dd8335'}
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True, sharey=True)
    for ax, (shape, total) in zip(axes.flat, [('single', 160), ('double', 120),
                                            ('triple', 120), ('triple', 160)]):
        draw_panel(ax, f'chicago_like_{shape}_4h_{total}mm_5min.txt', colors[total],
                   f'{shape.title()} peak | 4 h | {total} mm')
        ax.set_ylim(0, 320)
    for ax in axes[-1]:
        ax.set_xlabel('Elapsed time (minutes)')
    fig.suptitle('Four additional Chicago-like synthetic rainfall events', fontsize=15)
    fig.tight_layout()
    fig.savefig(paths[0], dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(3, 3, figsize=(15, 10), sharex=True, sharey=True)
    for row, shape in enumerate(('single', 'double', 'triple')):
        for column, total in enumerate((80, 120, 160)):
            ax = axes[row, column]
            draw_panel(ax, f'chicago_like_{shape}_4h_{total}mm_5min.txt', colors[total],
                       f'{shape.title()} peak | {total} mm')
            ax.set_ylim(0, 320)
    for ax in axes[-1]:
        ax.set_xlabel('Elapsed time (minutes)')
    fig.suptitle('Urban drainage | 3 peak patterns x 3 rainfall depths | 4 h, 5-min intervals', fontsize=15)
    fig.tight_layout()
    fig.savefig(paths[1], dpi=180)
    fig.savefig(paths[2])
    plt.close(fig)
    return [str(path.relative_to(MODEL)).replace('\\', '/') for path in paths]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    result = validate()
    if args.plot:
        result['plots'] = plots()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
