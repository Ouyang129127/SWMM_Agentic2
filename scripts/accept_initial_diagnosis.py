"""Run and audit a real initial diagnosis from an existing unified package.

No simulation, package rebuild, source edits, automatic evidence retrieval or
application token budget. --live explicitly enables the configured model call.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow_agents.evidence_package import load_package
from workflow_agents.investigation import advance_investigation
from workflow_agents.reference_checks import sha256_file
from workflow_agents.state import resolve_run_root
from workflow_agents.diagnosis_contract import apply_reviewed_reference_corrections


async def run(args):
    if not args.live and not args.replay_attempt:
        raise ValueError('Use --live to enable the real diagnosis call')
    root = resolve_run_root(args.model, args.run_id)
    package = load_package(root, verify_sources=True)
    original_hash = sha256_file(root / 'evidence/evidence_package.json')
    replay = None
    if args.task_id:
        if not args.task_id or len(args.task_id) != 32 or any(c not in '0123456789abcdef' for c in args.task_id):
            raise ValueError('Replay requires a valid existing task ID')
        folder = root / 'diagnosis_tasks' / args.task_id
        state = json.loads((folder / 'task.json').read_text(encoding='utf-8'))
        if state.get('task_kind') != 'initial_overflow':
            raise ValueError('Acceptance requires an initial overflow task')
        if args.replay_attempt:
            replay_path = folder / args.replay_attempt
            if replay_path.parent.resolve() != folder.resolve() or not replay_path.name.startswith('diagnosis_attempt_'):
                raise ValueError('Replay must name a saved attempt in this task')
            replay = json.loads(replay_path.read_text(encoding='utf-8'))
            if (replay.get('task_id') != args.task_id or replay.get('snapshot_hash') != state['snapshot_hash']
                    or set(replay.get('visible_ids', [])) != set(state['visible_ids'])
                    or not replay.get('network_call_started') or replay.get('response_source') != 'configured_model'
                    or not isinstance(replay.get('raw_response'), str)):
                raise ValueError('Saved provider response does not match the current task evidence')
    else:
        if args.replay_attempt:
            raise ValueError('Replay requires an existing task ID')
        state = await advance_investigation(args.model, args.run_id)
    task_id = state['task_id']
    folder = root / 'diagnosis_tasks' / task_id
    audit_path = folder / (f"acceptance_replay_r{state['revision'] + 1}.json" if replay else f"acceptance_r{state['revision'] + 1}.json" if args.task_id else 'acceptance.json')
    audit = {'task_id': task_id, 'model_name': args.model, 'run_id': args.run_id,
             'package_hash_before': original_hash, 'status': 'prepared',
             'event_count': len(state['event_manifest']), 'visible_record_count': len(state['visible_ids']),
             'simulation_performed': False, 'evidence_retrieval_performed': False,
             'numerical_prose_verified': False, 'causal_validity_checked': False}
    if replay:
        audit.update(replayed_provider_attempt=args.replay_attempt, new_model_call=False)
    retained = json.loads(replay['raw_response']) if replay else None
    if args.reference_corrections:
        if not replay:
            raise ValueError('Explicit reference corrections require a retained provider response')
        corrections = json.loads(Path(args.reference_corrections).read_text(encoding='utf-8'))
        snapshot = json.loads((folder / 'evidence_snapshot.json').read_text(encoding='utf-8'))
        retained, occurrences = apply_reviewed_reference_corrections(retained, corrections, snapshot, state['visible_ids'])
        audit.update(reviewed_reference_corrections=corrections, corrected_reference_occurrences=occurrences)
    async def retained_response(prompt):
        return retained
    if replay:
        retained_response.diagnosis_audit_metadata = {
            'response_source': 'retained_provider_response', 'replayed_provider_attempt': args.replay_attempt,
            'raw_response': replay['raw_response'], 'model': replay.get('model'), 'provider': replay.get('provider'),
            'reviewed_reference_corrections': audit.get('reviewed_reference_corrections', []),
            'corrected_reference_occurrences': audit.get('corrected_reference_occurrences', {})}
    def save():
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    print(json.dumps({'stage': 'prepared', 'task_id': task_id, 'events': audit['event_count'],
                      'audit_file': str(audit_path.resolve())}), flush=True)
    started = time.monotonic()
    try:
        for action in ('diagnose', 'verify', 'report'):
            audit['stage'] = action
            save()
            state = await advance_investigation(args.model, args.run_id, action, task_id,
                        complete=retained_response if replay and action == 'diagnose' else None)
            print(json.dumps({'stage': action, 'state': state['state'], 'revision': state['revision']}), flush=True)
            if action == 'verify' and state['state'] != 'ready_for_report':
                raise ValueError('Reference verification did not pass; preliminary report not delivered')
        expected = {e['event_id'] for e in state['event_manifest']}
        actual = {e['event_id'] for e in state['diagnosis']['event_assessments']}
        # Published event facts are program copies of event_context, not values
        # inferred from prose. Independent numerical prose validation is separate.
        by_id = {r['evidence_id']: r for r in package['evidence_rows']}
        facts_exact = all(e['facts'] == by_id[e['fact_evidence_id']]['value']['event'] for e in state['event_manifest'])
        audit.update(status='delivered', state=state['state'], revision=state['revision'],
                     covered_event_ids=sorted(actual), event_coverage_complete=actual == expected,
                     deterministic_event_facts_match_source=facts_exact,
                     report_file=state['report_file'],
                     report_delivered_before_evidence_retrieval=True,
                     claim_count=len(state['diagnosis']['claims']),
                     evidence_request_count=len(state['diagnosis']['evidence_requests']),
                     last_attempt=state.get('last_attempt'), reference_verification=state['verification']['summary'])
    except Exception as exc:
        audit.update(status='failed', error_type=type(exc).__name__)
        saved = json.loads((folder / 'task.json').read_text(encoding='utf-8'))
        audit['last_attempt'] = saved.get('last_attempt')
        if isinstance(exc, ValueError):
            audit['validation_error'] = str(exc)
    finally:
        audit.update(elapsed_seconds=round(time.monotonic() - started, 3),
                     package_hash_after=sha256_file(root / 'evidence/evidence_package.json'))
        audit['package_unchanged'] = original_hash == audit['package_hash_after']
        try:
            load_package(root, verify_sources=True)
            audit['source_integrity_after'] = 'passed'
        except Exception as exc:
            audit['source_integrity_after'] = type(exc).__name__
        save()
        if 'llm' in sys.modules:
            await sys.modules['llm'].deepseek_flash.close()
    print(json.dumps(audit, ensure_ascii=True), flush=True)
    return 0 if audit['status'] == 'delivered' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--task-id', default='')
    parser.add_argument('--replay-attempt', default='', help='Revalidate a retained provider response; no new model call')
    parser.add_argument('--reference-corrections', default='', help='Explicit reviewed invalid-ID to located evidence-ID corrections, saved in the audit')
    sys.exit(asyncio.run(run(parser.parse_args())))
