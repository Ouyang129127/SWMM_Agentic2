"""Local audit/summary for the authorized nine-case cohort; never calls solvers or LLMs."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_site_drainage_batch_20261011 import read, save, sha, stamp

MODEL = ROOT / 'models/pystorms_beta'
BATCH = MODEL / 'batches/beta_lowrain_20261014_v1'


def summarize(verify=False):
    plan = read(BATCH / 'plan.json')
    cohort = read(MODEL / 'events/lowrain_matrix_20261014.json')['events']
    planned = {c['event_file']: c for c in plan['cases']}
    rows = []
    for event in cohort:
        file = event['event_file']
        if file in planned:
            run_id = planned[file]['run_id']
            checkpoint = BATCH / (run_id + '.json')
            record = read(checkpoint) if checkpoint.exists() else {'status': 'not_started'}
            reused = False
        else:
            run_id = 'ba20_7h_20261014'
            record = read(MODEL / 'validation/adapted20_7h_20261014/execution.json')
            reused = True
        run = MODEL / 'runs' / run_id
        row = dict(shape=event['shape'], depth_mm=event['depth_mm'], run_id=run_id,
            reused_completed_case=reused, status=record['status'], stage=record.get('stage'),
            provider_calls=record.get('provider_calls', 0), supplement_rounds=record.get('supplement_rounds', 0),
            error_message=record.get('error_message'), causal_validity_checked=False,
            expert_diagnostic_accuracy='NOT_EVALUATED', semantic_unsupported_rate='NOT_EVALUATED')
        summary_path = run / 'summary.json'
        if summary_path.exists():
            s = read(summary_path)
            row.update(simulation_status=s['ca2d']['status'], simulation_start=s['swmm']['simulation_start'],
                simulation_end=s['swmm']['simulation_end'], sampled_overflow_volume_m3=s['ca2d']['source_volume_m3'],
                max_surface_depth_m=s['ca2d']['max_depth_m'], swmm_saved_times=s['swmm']['saved_steps'],
                ca2d_saved_times=s['ca2d']['saved_times'])
            assert row['simulation_end'] == '2016-10-08 07:00:00'
            assert row['swmm_saved_times'] == 421 and row['ca2d_saved_times'] == 85
            rpt = (run / 'swmm/model.rpt').read_text(encoding='utf-8')
            errors = re.findall(r'Continuity Error \(%\)\s*\.+\s*([-\d.]+)', rpt)
            row['runoff_continuity_pct'] = float(errors[0])
            row['routing_continuity_pct'] = float(errors[-1])
            row['nonconverging_steps_pct'] = float(re.search(r'% of Steps Not Converging\s*:\s*([\d.]+)', rpt).group(1))
        package_path = run / 'evidence/evidence_package.json'
        if package_path.exists():
            package = read(package_path)
            row.update(event_count=package['overview']['event_count'],
                overflow_node_count=package['overview']['overflow_node_count'],
                evidence_count=len(package['evidence_rows']))
            if verify and record['status'] != 'running':
                from workflow_agents.evidence_package import load_package
                load_package(run, verify_sources=True)
                row['evidence_sources_verified'] = True
        pointer = run / 'diagnosis_tasks/active_task.json'
        if pointer.exists():
            task = run / 'diagnosis_tasks' / read(pointer)['task_id']
            state = read(task / 'task.json')
            row.update(task_id=state['task_id'], task_state=state['state'], revision=state['revision'],
                visible_records=len(state['visible_ids']), evidence_closure=state.get('evidence_closure'),
                pending_evidence_requests=state.get('pending_evidence_requests'),
                unavailable_request_count=len(state.get('unresolved_evidence_requests', [])))
            attempts = [read(p) for p in task.glob('diagnosis_attempt_*.json')]
            attempts.sort(key=lambda a: a['started_at'])
            row['diagnosis_attempts'] = []
            for a in attempts:
                error = a.get('error_message', '')
                token_match = re.search(r'you requested (\d+) tokens', error)
                row['diagnosis_attempts'].append(dict(status=a.get('status'), phase=a.get('phase'),
                    request_characters=a.get('request_characters'), usage=a.get('usage'),
                    http_status=a.get('http_status'), error_type=a.get('error_type'),
                    rejected_input_tokens=int(token_match.group(1)) if token_match else None))
            if attempts:
                row['first_request_characters'] = attempts[0].get('request_characters')
                row['first_request_usage'] = attempts[0].get('usage')
            verification = task / 'verification.json'
            row['verification_summary'] = read(verification)['summary'] if verification.exists() else None
            row['structured_report_current'] = (state.get('report_revision') == state['revision']
                and verification.exists() and read(verification)['revision'] == state['revision'])
            if row['structured_report_current']:
                row['structured_report_file'] = state['report_file']
                if verify:
                    assert sha(task / 'diagnosis.json') == state['diagnosis_hash']
                    assert sha(verification) == state['verification_hash']
                    report = read(task / 'report.json')
                    assert report['revision'] == state['revision']
                    assert report['diagnosis_hash'] == state['diagnosis_hash']
                    assert report['verification_hash'] == state['verification_hash']
                    row['structured_report_hashes_verified'] = True
            display = state.get('display_report', {})
            row['display_report_status'] = display.get('status')
            if display.get('status') == 'failed':
                row['display_report_failure'] = {k: display.get(k) for k in ('phase', 'error_type', 'error', 'output_dir')}
            row['prior_html_reports_not_current'] = [read(p)['html_file']
                for p in (task / 'display_reports').glob('r*/*/generation.json')
                if read(p).get('status') == 'completed' and read(p).get('revision') != state['revision']]
            if display.get('status') == 'completed':
                row['html_file'] = display['html_file']
                row['html_revision'] = display['revision']
            row['report_delivery_current'] = (display.get('status') == 'completed'
                and display.get('revision') == state['revision'] == state.get('report_revision'))
            row['failed_narrative_attempts'] = sum(read(p).get('status') == 'failed'
                for p in (task / 'display_reports').glob('r*/*/narrative_attempt_*.json'))
            if verify and record['status'].startswith('completed'):
                assert row['report_delivery_current'], 'Completed record lacks current report'
                assert sha(Path(display['html_file'])) == display['html_sha256']
                assert display['quality_checks']['status'] == 'passed'
                row['html_delivery_verified'] = True
        rows.append(row)
    frozen_ok = all(sha(ROOT / p) == expected for p, expected in plan['input_and_code_hashes'].items())
    if verify:
        assert frozen_ok, 'Frozen input/code or completed comparison case changed'
    result = dict(batch_id=plan['batch_id'], updated_at=stamp(), status_counts=dict(Counter(r['status'] for r in rows)),
        matrix_cases=9, newly_requested_cases=8, new_terminal_cases=sum(r['status'] not in {'running', 'not_started'}
            for r in rows if not r['reused_completed_case']), frozen_inputs_and_code_unchanged=frozen_ok,
        verification_run=verify, causal_validity_checked=False, cases=rows)
    save(BATCH / 'cohort_summary.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = summarize(args.verify)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))
    for row in result['cases']:
        print(json.dumps({k: row.get(k) for k in ('shape', 'depth_mm', 'run_id', 'status', 'stage',
            'event_count', 'overflow_node_count', 'report_delivery_current', 'provider_calls')}))
