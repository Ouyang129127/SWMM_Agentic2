"""Read-only post-run inspection: no simulation, LLM call or artifact write."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from workflow_agents.reference_checks import sha256_file
from workflow_agents.reporting.materials import assert_sources_current, verify_task
from workflow_agents.reporting.pipeline import check_html


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    folder = Path(__file__).resolve().parent
    plan = read(folder / 'plan.json')
    result = {'batch_id': plan['batch_id'], 'cases': [],
              'causal_validity_checked': False,
              'frozen_file_count': len(plan['input_and_code_hashes']),
              'changed_frozen_files': []}
    for name, expected in plan['input_and_code_hashes'].items():
        path = ROOT / name
        if not path.is_file() or sha256_file(path) != expected:
            result['changed_frozen_files'].append(name)
    for case in plan['cases']:
        checkpoint = folder / (case['run_id'] + '.json')
        record = read(checkpoint) if checkpoint.is_file() else {'status': 'not_started'}
        item = {'run_id': case['run_id'], 'status': record['status'],
                'provider_calls': record.get('provider_calls', 0),
                'supplement_rounds': record.get('supplement_rounds', 0)}
        run = ROOT / 'models/urban_drainage/runs' / case['run_id']
        summary = run / 'summary.json'
        if summary.is_file():
            doc = read(summary)
            item['simulation_status'] = doc['ca2d']['status']
            item['simulation_files'] = sum(p.is_file() for p in run.glob('swmm/*')) + sum(
                p.is_file() for p in run.glob('ca2d/*'))
            item['simulation_summary'] = record.get('simulation_summary')
        active = run / 'diagnosis_tasks/active_task.json'
        if not active.is_file():
            result['cases'].append(item)
            continue
        directory = active.parent / read(active)['task_id']
        state = read(directory / 'task.json')
        item.update(task_state=state['state'], revision=state['revision'],
                    events=len(state.get('event_manifest', [])),
                    visible_evidence=len(state.get('visible_ids', [])),
                    supplement_files=len(state.get('supplements', [])),
                    last_failure=state.get('last_failure'),
                    execution_error=state.get('execution_error'))
        audits = []
        for path in sorted(list(directory.glob('diagnosis_attempt_*.json')) + list(
                directory.glob('display_reports/*/*/narrative_attempt_*.json'))):
            doc = read(path)
            audits.append({'file': str(path.relative_to(run)), **{k: doc[k] for k in (
                'status', 'phase', 'http_status', 'error_type', 'error_message', 'validation_error',
                'error', 'request_characters', 'finish_reason', 'usage') if k in doc}})
        item['attempt_audits'] = audits
        item['reported_token_totals'] = {key: sum((a.get('usage') or {}).get(key, 0) or 0
                                                 for a in audits)
                                          for key in ('prompt_tokens', 'completion_tokens')}
        verification = directory / 'verification.json'
        if verification.is_file():
            doc = read(verification)
            item['reference_revision'] = doc.get('revision')
            item['reference_summary'] = doc.get('summary')
        display = state.get('display_report', {})
        if display.get('status') == 'completed':
            html = Path(display['html_file'])
            materials = read(Path(display['materials_file']))
            current = record['status'].startswith('completed') and display['revision'] == state['revision']
            item.update(html_file=str(html), html_sha256=sha256_file(html),
                        html_bytes=html.stat().st_size,
                        delivery='current' if current else 'historical_not_current_final_delivery')
            try:
                if current:
                    verify_task(run, directory, state)
                assert_sources_current(materials)
                if item['html_sha256'] != display['html_sha256']:
                    raise ValueError('HTML hash mismatch')
                item['html_checks'] = check_html(html, materials)
                item['artifact_verification'] = 'passed'
            except Exception as exc:
                item['artifact_verification'] = 'failed'
                item['artifact_error'] = str(exc)
        elif display:
            item['display_report_status'] = display.get('status')
            generation_file = Path(display['output_dir']) / 'generation.json'
            if generation_file.is_file():
                generation = read(generation_file)
                item['display_failure'] = {k: generation[k] for k in (
                    'phase', 'error_type', 'error', 'status') if k in generation}
        result['cases'].append(item)
    result['execution_lock_present'] = (folder / 'execution.lock').exists()
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
