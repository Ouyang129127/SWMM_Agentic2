"""One authorized adapted beta case using existing workflow APIs; no architecture changes."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_site_drainage_batch_20261011 import read, save, sha, stamp, supplement_stop, SIMULATION_FILES

MODEL = 'pystorms_beta'
RUN_ID = 'ba20_20261013_p1'
SCENARIO = 'adapted_s1_wsqrt'
EVENT = 'chicago_like_single_4h_20mm_5min.txt'
MODEL_ROOT = ROOT / 'models' / MODEL
RUN = MODEL_ROOT / 'runs' / RUN_ID
FOLDER = MODEL_ROOT / 'validation/adapted_20mm_full_20261013'
CHECKPOINT = FOLDER / 'execution.json'
record = {'status': 'running', 'run_id': RUN_ID, 'model_name': MODEL,
          'scenario_name': SCENARIO, 'event_file': EVENT, 'started_at': stamp(),
          'pid': os.getpid(), 'provider_calls': 0, 'calls_by_role': {},
          'supplement_rounds': 0, 'history': [], 'causal_validity_checked': False}
stage_start = time.monotonic()
done = threading.Event()


def note(stage):
    global stage_start
    stage_start = time.monotonic()
    record['stage'] = stage
    record['history'].append({'stage': stage, 'at': stamp()})
    save(CHECKPOINT, record)
    print(json.dumps({'stage': stage, 'at': stamp()}), flush=True)


def watchdog():
    while not done.wait(10):
        if time.monotonic() - stage_start > 1800:
            record.update(status='timed_out', finished_at=stamp(), error_message='Stage exceeded 30 minute hard limit')
            save(CHECKPOINT, record)
            print('Hard timeout: terminating only this owned workflow process; artifacts retained.', flush=True)
            os._exit(2)


def bounded(role, completion):
    async def call(*args, **kwargs):
        if record['provider_calls'] >= 21:
            raise RuntimeError('Provider completion call ceiling reached')
        record['provider_calls'] += 1
        record['calls_by_role'][role] = record['calls_by_role'].get(role, 0) + 1
        save(CHECKPOINT, record)
        return await completion(*args, **kwargs)
    return call


async def main():
    from tools import run_swmm_2d_project_from_rainfall
    from workflow_agents.scenario import prepare_scenario_request
    from workflow_agents.state import build_state, save_state, infer_state_from_artifacts
    from workflow_agents.schemas import RUN_READY, EVIDENCE_READY
    from workflow_agents.orchestrator import run_workflow_stage
    from workflow_agents.investigation import advance_investigation
    from workflow_agents.investigation_flow import continue_investigation
    from workflow_agents import investigation
    from workflow_agents.reporting import narrative

    assert not RUN.exists(), 'Refusing to overwrite any existing or partial run'
    assert not CHECKPOINT.exists(), 'Execution already recorded'
    changes = read(MODEL_ROOT / 'validation/width_screening_20261012/input_changes.json')
    protected = changes['protected_input_hashes']
    assert all(sha(Path(p)) == h for p, h in protected.items()), 'Protected inputs changed'
    record['protected_input_hashes_before'] = protected
    record['scenario_inp_sha256'] = sha(MODEL_ROOT / 'swmm/scenarios' / SCENARIO / 'model.inp')
    assert sha(MODEL_ROOT / 'events' / EVENT) == 'a378a2850a7941f3d480dda18f68e78740283dfba33999a1d9e2dbbbb7fcec50'
    investigation.configured_completion = bounded('diagnosis', investigation.configured_completion)
    narrative.configured_completion = bounded('report', narrative.configured_completion)
    threading.Thread(target=watchdog, daemon=True).start()
    try:
        note('scenario')
        prepared = prepare_scenario_request(MODEL, 'events/' + EVENT, EVENT[:-4], SCENARIO, RUN_ID)
        note('simulation')
        run_swmm_2d_project_from_rainfall(model_name=MODEL, rainfall_file='events/' + EVENT,
            event_name=EVENT[:-4], scenario_name=SCENARIO, run_id=RUN_ID,
            rain_gage_name='RG1', dt_seconds=10,
            expected_event_sha256=prepared['scenario_request']['event_sha256'])
        summary = read(RUN / 'summary.json')
        assert summary['ca2d']['status'] == 'COMPLETED'
        assert all((RUN / f).is_file() for f in SIMULATION_FILES)
        record['simulation_summary'] = {
            'max_flooding_Ls': summary['swmm']['max_flooding_Ls'],
            'sampled_overflow_volume_m3': summary['ca2d']['source_volume_m3'],
            'max_surface_depth_m': summary['ca2d']['max_depth_m']}
        note('simulation_handoff')
        previous = read(RUN / 'workflow_state.json')
        target = infer_state_from_artifacts(RUN)
        assert target in {RUN_READY, EVIDENCE_READY}
        state = build_state(MODEL, RUN_ID, RUN, state=target)
        state['history'] = previous.get('history', []) + [{'stage': 'simulation_handoff',
            'target_state': target, 'completed_at': stamp(), 'simulation_reused': False}]
        save_state(RUN, state)
        record['simulation_handoff'] = {'previous_state': previous['state'], 'target_state': target}
        note('evidence')
        built = run_workflow_stage(MODEL, RUN_ID)
        assert built['ok'], 'Evidence construction failed'
        note('initial_diagnosis_verification_report')
        state = await advance_investigation(MODEL, RUN_ID, action='initial')
        record['task_id'] = state['task_id']
        while True:
            reason = supplement_stop(state, record['supplement_rounds'], 2)
            if reason:
                record['stop_reason'] = reason
                break
            record['supplement_rounds'] += 1
            note('supplement_round_' + str(record['supplement_rounds']))
            before = set(state['visible_ids'])
            state = await continue_investigation(MODEL, RUN_ID, state['task_id'], approve_evidence=True)
            if not set(state['visible_ids']) - before:
                record['stop_reason'] = 'no_progress'
                break
        record.update(task_state=state['state'], revision=state['revision'],
                      execution_error=state.get('execution_error'),
                      display_report=state.get('display_report'))
        if state.get('execution_error'):
            raise RuntimeError(state['execution_error'])
        assert state['state'] in {'preliminary_delivered', 'awaiting_evidence_confirmation'}
        assert state.get('report_revision') == state['revision'], 'No current verified structured report'
        display = state.get('display_report', {})
        assert display.get('status') == 'completed' and display.get('revision') == state['revision'], 'HTML delivery failed'
        record.update(status='completed_with_gaps' if state.get('unresolved_evidence_requests')
            or state.get('pending_evidence_requests') else 'completed',
            report_file=display['html_file'], evidence_closure=state.get('evidence_closure'),
            pending_evidence_requests=bool(state.get('pending_evidence_requests')),
            unresolved_evidence_requests=state.get('unresolved_evidence_requests', []))
    except Exception as exc:
        record.update(status='failed', error_type=type(exc).__name__, error_message=str(exc)[:2000])
        print(json.dumps({'stage': record.get('stage'), 'error_type': type(exc).__name__}), flush=True)
    finally:
        record['protected_inputs_unchanged'] = all(sha(Path(p)) == h for p, h in protected.items())
        record['finished_at'] = stamp()
        save(CHECKPOINT, record)
        done.set()
        if 'llm' in sys.modules:
            await sys.modules['llm'].deepseek_flash.close()
    return 0 if record['status'].startswith('completed') else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
