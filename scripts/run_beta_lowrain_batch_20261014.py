"""Sequential pystorms_beta eight-event low-rainfall batch, using existing tools and bounded supplementation.

Default is read-only preflight. --execute is required for simulation/API calls.
Each case runs in a separate process; prior runs and failed attempts are retained.
Model-specific adapter of the repaired batch entry; diagnosis logic is unchanged.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EVENTS = {
    f'chicago_like_{pattern}_4h_{depth}mm_5min.txt'
    for pattern in ('single', 'double', 'triple')
    for depth in (20, 40, 60)
    if (pattern, depth) != ('single', 20)
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def relative_file(value):
    path = (ROOT / value).resolve()
    path.relative_to(ROOT)
    if not path.is_file():
        raise ValueError('Missing declared input: ' + value)
    return path


def preflight(plan):
    from ca2d import check_static_model
    from simulation_timing import load_timing
    from workflow_agents.rainfall_context import build_rainfall_context
    if plan['model_name'] != 'pystorms_beta' or plan['scenario_name'] != 'adapted_s1_wsqrt':
        raise ValueError('This runner is scoped to pystorms_beta/adapted_s1_wsqrt')
    if not plan['batch_id'] or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in plan['batch_id']):
        raise ValueError('Invalid batch directory identifier')
    cases = plan['cases']
    if len(cases) != 8 or {c['event_file'] for c in cases} != EVENTS:
        raise ValueError('Batch must contain exactly the eight remaining approved rainfall events')
    if len({c['run_id'] for c in cases}) != 8:
        raise ValueError('Run IDs must be unique')
    if plan['max_supplement_rounds'] != 2 or plan['max_provider_calls_per_case'] != 21:
        raise ValueError('Unexpected batch bounds')
    if plan['case_timeout_seconds'] != 1800:
        raise ValueError('Unexpected hard timeout')
    for case in cases:
        if not case['run_id'].startswith('bl_1014_') or len(case['run_id']) > 24:
            raise ValueError('Short beta low-rainfall run ID required')
        if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in case['run_id']):
            raise ValueError('Invalid run ID')
    for name, expected in plan['input_and_code_hashes'].items():
        if sha(relative_file(name)) != expected:
            raise ValueError('Frozen input/code changed: ' + name)
    if plan.get('reuse_completed_simulations'):
        for case in cases:
            validate_saved_simulation(plan, case)
    model = ROOT / 'models/pystorms_beta'
    if not check_static_model(model / 'static')['ok']:
        raise ValueError('CA2D static model is incomplete')
    if load_timing(model) != plan['simulation_timing']:
        raise ValueError('Model timing changed')
    contexts = []
    for case in cases:
        context = build_rainfall_context(model / 'events' / case['event_file'])
        if context['rainfall_points'] != 49 or context['rainfall_duration_min'] != 240:
            raise ValueError('Unexpected rainfall format')
        contexts.append({k: context[k] for k in
                         ('event_name', 'total_rainfall_mm', 'max_intensity_mm_per_h')})
    return contexts


SIMULATION_FILES = ('summary.json', 'swmm/model.rpt', 'swmm/model.out',
                    'swmm/nodes.tsv', 'swmm/links.tsv', 'swmm/node_flooding.tsv',
                    'ca2d/surface_depth.tsv', 'ca2d/boundary_inflow_5min.tsv')


def validate_saved_simulation(plan, case):
    run = ROOT / 'models/pystorms_beta/runs' / case['run_id']
    frozen = plan.get('saved_simulation_hashes', {}).get(case['run_id'], {})
    if not all(name in frozen for name in SIMULATION_FILES):
        raise ValueError('Recovery requires frozen completed simulation artifacts')
    for name, expected in frozen.items():
        path = (run / name).resolve()
        path.relative_to(run.resolve())
        if not path.is_file() or sha(path) != expected:
            raise ValueError('Saved simulation changed: ' + case['run_id'] + '/' + name)
    summary = read(run / 'summary.json')
    if (summary.get('model_name') != 'pystorms_beta'
            or summary.get('run_id') != case['run_id']
            or summary.get('event_name') != case['event_file'][:-4]
            or summary.get('scenario_name') != 'adapted_s1_wsqrt'
            or summary.get('ca2d', {}).get('status') != 'COMPLETED'):
        raise ValueError('Recovery simulation identity/completion mismatch')
    expected_event = plan['input_and_code_hashes']['models/pystorms_beta/events/' + case['event_file']]
    if summary.get('input_validation', {}).get('event_sha256') != expected_event:
        raise ValueError('Saved simulation rainfall does not match frozen event')
    return summary


def handoff_simulation(run, case, summary, reused=False):
    """Explicitly publish the simulator's saved outputs to the workflow state."""
    from workflow_agents.state import build_state, save_state, infer_state_from_artifacts
    from workflow_agents.schemas import RUN_READY, EVIDENCE_READY
    if summary.get('ca2d', {}).get('status') != 'COMPLETED':
        raise ValueError('Cannot hand off an incomplete simulation')
    if not all((run / name).is_file() for name in SIMULATION_FILES):
        raise ValueError('Cannot hand off missing simulation artifacts')
    target = infer_state_from_artifacts(run)
    if target not in {RUN_READY, EVIDENCE_READY}:
        raise ValueError('Simulation artifacts are not ready for evidence construction')
    state_path = run / 'workflow_state.json'
    previous = read(state_path) if state_path.exists() else {}
    state = build_state('pystorms_beta', case['run_id'], run, state=target)
    state['history'] = list(previous.get('history', []))
    state['history'].append({'stage': 'simulation_handoff', 'target_state': target,
                             'completed_at': stamp(), 'simulation_reused': reused,
                             'simulation_created_at': summary.get('created_at')})
    save_state(run, state)
    return {'previous_state': previous.get('state'), 'target_state': target}


def supplement_stop(state, rounds, limit):
    """Decide before authorizing another fixed-tool evidence action."""
    if state.get('execution_error'):
        return 'execution_failed'
    if state.get('state') not in {'preliminary_delivered', 'awaiting_evidence_confirmation'}:
        return 'unexpected_task_state'
    plan = state.get('evidence_plan', [])
    for item in plan:
        if item['request'].get('tool') not in {'evidence_lookup', 'saved_result_extract', 'unavailable'}:
            return 'request_outside_fixed_tool_policy'
    actionable = any(item.get('new_evidence_ids') or item.get('requires_extraction') for item in plan)
    if not actionable:
        return 'capability_gaps' if state.get('unresolved_evidence_requests') else 'no_new_evidence'
    if rounds >= limit:
        return 'supplement_round_limit'
    return None


async def worker(plan, case, folder):
    from tools import run_swmm_2d_project_from_rainfall
    from workflow_agents.scenario import prepare_scenario_request
    from workflow_agents.orchestrator import run_workflow_stage
    from workflow_agents.investigation import advance_investigation
    from workflow_agents.investigation_flow import continue_investigation
    from workflow_agents import investigation
    from workflow_agents.reporting import narrative
    record = {'status': 'running', 'run_id': case['run_id'], 'event_file': case['event_file'],
              'started_at': stamp(), 'pid': os.getpid(), 'supplement_rounds': 0,
              'provider_calls': 0, 'calls_by_role': {}, 'history': []}
    checkpoint = folder / (case['run_id'] + '.json')
    run = ROOT / 'models/pystorms_beta/runs' / case['run_id']
    reuse = plan.get('reuse_completed_simulations', False)
    if run.exists() and not reuse:
        raise ValueError('Refusing to overwrite an existing or partial run')

    def note(stage):
        record['stage'] = stage
        record['history'].append({'stage': stage, 'at': stamp()})
        save(checkpoint, record)
        print(json.dumps({'event': case['event_file'], 'stage': stage}), flush=True)

    def bounded(role, completion):
        async def call(*args, **kwargs):
            if record['provider_calls'] >= plan['max_provider_calls_per_case']:
                raise RuntimeError('Provider call ceiling reached')
            record['provider_calls'] += 1
            counts = record['calls_by_role']
            counts[role] = counts.get(role, 0) + 1
            save(checkpoint, record)
            try:
                return await completion(*args, **kwargs)
            except Exception as exc:
                http_status = getattr(exc, 'status_code', None)
                if http_status in {401, 403, 429, 500, 502, 503, 504}:
                    record['shared_provider_failure_http_status'] = http_status
                    save(checkpoint, record)
                raise
        return call

    # Preserve native call/usage auditing: wrap the configured functions rather
    # than injecting fabricated completions into the diagnosis/report contracts.
    investigation.configured_completion = bounded('diagnosis', investigation.configured_completion)
    narrative.configured_completion = bounded('report', narrative.configured_completion)
    try:
        record.update(simulation_reused=reuse, simulation_executed=not reuse)
        if reuse:
            note('validate_saved_simulation')
            summary = validate_saved_simulation(plan, case)
        else:
            note('scenario')
            prepared = prepare_scenario_request('pystorms_beta', 'events/' + case['event_file'],
                                                case['event_file'][:-4], 'adapted_s1_wsqrt', case['run_id'])
            note('simulation')
            run_swmm_2d_project_from_rainfall(model_name='pystorms_beta',
                rainfall_file='events/' + case['event_file'], event_name=case['event_file'][:-4],
                scenario_name='adapted_s1_wsqrt', run_id=case['run_id'], rain_gage_name='RG1',
                expected_event_sha256=prepared['scenario_request']['event_sha256'])
            summary = read(run / 'summary.json')
        if (summary['swmm']['simulation_start'] != '2016-10-08 00:00:00'
                or summary['swmm']['simulation_end'] != '2016-10-08 07:00:00'
                or summary['swmm']['saved_steps'] != 421
                or summary['ca2d']['saved_times'] != 85):
            raise RuntimeError('Unexpected simulation window or saved-time counts')
        record['actual_window_verified'] = True
        if summary['ca2d']['status'] != 'COMPLETED':
            raise RuntimeError('Simulation did not complete')
        record['simulation_summary'] = {
            'max_flooding_Ls': summary['swmm']['max_flooding_Ls'],
            'sampled_overflow_volume_m3': summary['ca2d']['source_volume_m3'],
            'max_surface_depth_m': summary['ca2d']['max_depth_m']}
        note('simulation_handoff')
        record['simulation_handoff'] = handoff_simulation(run, case, summary, reused=reuse)
        note('evidence')
        built = run_workflow_stage('pystorms_beta', case['run_id'])
        if not built['ok']:
            raise RuntimeError('Evidence construction failed')
        note('initial_diagnosis_verification_report')
        state = await advance_investigation('pystorms_beta', case['run_id'], action='initial')
        record['task_id'] = state['task_id']
        while True:
            reason = supplement_stop(state, record['supplement_rounds'], plan['max_supplement_rounds'])
            if reason:
                record['stop_reason'] = reason
                break
            record['supplement_rounds'] += 1
            note('supplement_round_' + str(record['supplement_rounds']))
            before = set(state['visible_ids'])
            state = await continue_investigation('pystorms_beta', case['run_id'], state['task_id'],
                                                  approve_evidence=True)
            if not set(state['visible_ids']) - before:
                record['stop_reason'] = 'no_progress'
                break
        if state.get('execution_error') or state.get('state') not in {
                'preliminary_delivered', 'awaiting_evidence_confirmation'}:
            raise RuntimeError('Diagnosis/verification stopped before current delivery')
        if state.get('report_revision') != state.get('revision'):
            raise RuntimeError('No current verified structured report')
        display = state.get('display_report', {})
        if display.get('status') != 'completed' or display.get('revision') != state['revision']:
            raise RuntimeError('Current HTML report did not pass delivery checks')
        record.update(status='completed_with_gaps' if state.get('unresolved_evidence_requests')
                      or state.get('pending_evidence_requests') else 'completed',
                      task_state=state['state'], revision=state['revision'],
                      event_count=len(state.get('event_manifest', [])),
                      report_file=display['html_file'],
                      evidence_closure=state.get('evidence_closure'),
                      pending_evidence_requests=bool(state.get('pending_evidence_requests')),
                      unresolved_evidence_requests=state.get('unresolved_evidence_requests', []),
                      causal_validity_checked=False)
    except Exception as exc:
        record.update(status='failed', error_type=type(exc).__name__)
        record['error_message'] = str(exc)[:1000]
        # Provider error details remain in the existing native per-attempt audit.
        print(json.dumps({'stage': record.get('stage'), 'error_type': type(exc).__name__}), flush=True)
    finally:
        record['finished_at'] = stamp()
        save(checkpoint, record)
        if 'llm' in sys.modules:
            await sys.modules['llm'].deepseek_flash.close()
    return 0 if record['status'].startswith('completed') else 1


def run_batch(plan, plan_path):
    folder = ROOT / 'models/pystorms_beta/batches' / plan['batch_id']
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / 'execution.lock'
    with lock.open('x', encoding='utf-8') as stream:
        stream.write(str(os.getpid()))
    results = []
    process = None
    try:
        for index, case in enumerate(plan['cases']):
            preflight(plan)  # Recheck frozen files before each independent case.
            checkpoint = folder / (case['run_id'] + '.json')
            if checkpoint.exists():
                previous = read(checkpoint)
                results.append(previous)
                print(json.dumps({'event': case['event_file'], 'retained_status': previous['status']}), flush=True)
                continue  # Never silently retry failed, partial, or completed cases.
            log = folder / (case['run_id'] + '.log')
            started = time.monotonic()
            with log.open('x', encoding='utf-8') as output:
                process = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()),
                    '--plan', str(plan_path), '--execute', '--case-index', str(index)],
                    cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
                previous_bytes, stalled_checks = -1, 0
                while process.poll() is None:
                    elapsed = time.monotonic() - started
                    if elapsed >= plan['case_timeout_seconds']:
                        print(json.dumps({'event': case['event_file'], 'alert': 'hard_timeout_terminating',
                                          'pid': process.pid}), flush=True)
                        if os.name == 'nt':
                            # The Windows venv launcher can own a real Python
                            # child. Stop only this launched process tree, not
                            # merely its launcher and never unrelated Python jobs.
                            subprocess.run(['taskkill', '/PID', str(process.pid), '/T'],
                                           capture_output=True, check=False)
                        else:
                            process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            if os.name == 'nt':
                                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                               capture_output=True, check=False)
                            else:
                                process.kill()
                            process.wait()
                        break
                    size = log.stat().st_size
                    stalled_checks = stalled_checks + 1 if size == previous_bytes else 0
                    previous_bytes = size
                    print(json.dumps({'event': case['event_file'], 'pid': process.pid,
                                      'alive': True, 'elapsed_seconds': round(elapsed),
                                      'log_bytes': size}), flush=True)
                    if stalled_checks in (3, 5):
                        print(json.dumps({'event': case['event_file'], 'alert': 'output_stall_advisory',
                                          'action': 'continue_without_retry_or_termination'}), flush=True)
                    time.sleep(30)
            result = read(checkpoint) if checkpoint.exists() else {'run_id': case['run_id'],
                     'event_file': case['event_file'], 'status': 'failed_without_checkpoint'}
            if not result['status'].startswith('completed'):
                result['status'] = 'timeout' if time.monotonic() - started >= plan['case_timeout_seconds'] else 'failed'
            result.update(exit_code=process.returncode, elapsed_seconds=round(time.monotonic() - started, 3),
                          log_file=str(log))
            save(checkpoint, result)
            results.append(result)
            save(folder / 'batch_summary.json', {'batch_id': plan['batch_id'], 'cases': results,
                                                'updated_at': stamp(), 'causal_validity_checked': False})
            if not result['status'].startswith('completed'):
                # Authentication/rate/service failures are shared: pause the
                # batch rather than spending calls on the remaining cases.
                run = ROOT / 'models/pystorms_beta/runs' / case['run_id']
                attempts = list(run.glob('diagnosis_tasks/*/diagnosis_attempt_*.json'))
                if result.get('shared_provider_failure_http_status') in {401, 403, 429, 500, 502, 503, 504} or any(
                        read(p).get('http_status') in {401, 403, 429, 500, 502, 503, 504} for p in attempts):
                    print('Shared provider failure: remaining cases were not started.', flush=True)
                    break
        save(folder / 'batch_summary.json', {'batch_id': plan['batch_id'], 'cases': results,
                                            'updated_at': stamp(), 'causal_validity_checked': False})
    finally:
        if process is None or process.poll() is not None:
            lock.unlink()  # Only this process's successfully acquired lock.
        else:
            print('Worker still alive; execution lock retained to prevent duplicate launches.', flush=True)
    return 0 if len(results) == 8 and all(r['status'].startswith('completed') for r in results) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--case-index', type=int, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()
    plan_path = args.plan.resolve()
    plan = read(plan_path)
    contexts = preflight(plan)
    if not args.execute:
        print(json.dumps({'preflight': 'passed', 'simulation_executed': False,
                          'llm_called': False, 'cases': contexts}, ensure_ascii=False, indent=2))
        return 0
    if args.case_index is not None:
        if not 0 <= args.case_index < len(plan['cases']):
            raise ValueError('Invalid case index')
        return asyncio.run(worker(plan, plan['cases'][args.case_index],
            ROOT / 'models/pystorms_beta/batches' / plan['batch_id']))
    return run_batch(plan, plan_path)


if __name__ == '__main__':
    sys.exit(main())
