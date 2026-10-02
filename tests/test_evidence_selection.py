import csv
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from workflow_agents.evidence_selection import (
    EVENT_GROUPS, SELECTION_VERSION, decode_series, encode_series,
    lookup_evidence, select_initial_evidence, transport_evidence,
)
from workflow_agents.investigation import advance_investigation, build_diagnosis_prompt
from workflow_agents.reference_checks import check_references, sha256_file


def row(eid, kind='node', obj='N1', metric='max_flooding_flow', value='0', event='', unit='L/s', **kwargs):
    return dict(evidence_id=eid, object_type=kind, object_id=obj, metric_name=metric,
                value=value, event_id=event, unit=unit, source_model='m', run_id='r', **kwargs)


def scope(node=None, event=None):
    return {'scope': 'event' if event else 'node' if node else 'global',
            'node_id': node, 'event_id': event, 'original_question': '分析'}


def packages(count=12):
    result = []
    for i in range(count):
        for metric in sorted(EVENT_GROUPS):
            value = {'status': 'available'}
            if metric == 'local_structure':
                value = {'nodes': {'N1': {}, 'N2': {}}, 'links': {'L1': {}}}
            result.append(row(f'FP{i}_{metric}', metric=metric, event=f'N1:E{i:03}', value=value))
    return result


class SelectionTests(unittest.TestCase):
    def test_all_event_groups_survive_order_changes_and_irrelevant_grid_growth(self):
        required = packages()  # 72 rows: a fixed 60-row gate loses events.
        initial = select_initial_evidence(required, scope('N1'), 'm', 'r')
        shuffled = required + [row(f'cell{i}', 'cell', str(i), 'max_depth', '0', unit='m') for i in range(2000)]
        random.Random(42).shuffle(shuffled)
        actual = select_initial_evidence(shuffled, scope('N1'), 'm', 'r')
        self.assertEqual(actual, initial)
        self.assertEqual(len(actual[1]), 72)
        self.assertTrue(all(not event['missing_groups'] for event in actual[2]['event_coverage']))

    def test_global_keeps_every_event_without_sending_grid_rows(self):
        rows = packages() + [row(f'C{i}', 'cell', str(i), 'max_depth', str(i), unit='m') for i in range(1000)]
        derived, ids, manifest = select_initial_evidence(rows, scope(), 'm', 'r')
        self.assertEqual(len(manifest['event_coverage']), 12)
        self.assertTrue(all(r['evidence_id'] in ids for r in packages()))
        self.assertFalse(any(eid.startswith('C') for eid in ids))
        summary = derived[0]
        self.assertEqual(summary['value']['source_row_count'], 1000)
        self.assertEqual(summary['value']['maximum'], 999)
        # All rows affect statistics, not just the first or most severe subset.
        self.assertEqual(summary['value']['zero_value_count'], 1)
        reversed_result = select_initial_evidence(list(reversed(rows)), scope(), 'm', 'r')
        self.assertEqual((derived, ids, manifest), reversed_result)

    def test_event_scope_includes_connected_context_but_not_other_events(self):
        rows = packages(2) + [row('N2bg', obj='N2'), row('link', 'link', 'L1', 'max_fullness', '.9'),
                              row('unrelated', obj='N3'), row('other', obj='N2', event='N2:E001')]
        _, ids, manifest = select_initial_evidence(rows, scope('N1', 'N1:E001'), 'm', 'r')
        self.assertEqual(len(ids), 8)
        self.assertIn('N2bg', ids)
        self.assertIn('link', ids)
        self.assertNotIn('other', ids)
        self.assertNotIn('unrelated', ids)
        self.assertEqual(manifest['related_links'], ['L1'])

    def test_missing_package_types_are_explicit(self):
        rows = [row('event', metric='event_duration', event='N1:E001', unit='min')]
        _, ids, manifest = select_initial_evidence(rows, scope('N1'), 'm', 'r')
        self.assertEqual(ids, ['event'])
        self.assertEqual(set(manifest['event_coverage'][0]['missing_groups']), EVENT_GROUPS)

    def test_no_overflow_still_has_all_metric_classes_and_separate_units(self):
        rows = [row('n'), row('l', 'link', 'L1', 'max_fullness', '1', unit='ratio'),
                row('m', 'cell', 'C1', 'max_depth', '', unit='m'),
                row('ft', 'cell', 'C2', 'max_depth', '3', unit='ft')]
        derived, ids, manifest = select_initial_evidence(rows, scope(), 'm', 'r')
        self.assertEqual(len(derived), 4)
        self.assertEqual(len(ids), 4)
        missing = next(r for r in derived if r['unit'] == 'm')
        self.assertIsNone(missing['value']['maximum'])
        self.assertEqual(missing['value']['missing_or_nonfinite_count'], 1)
        self.assertEqual(manifest['event_coverage'], [])
        self.assertEqual(next(r for r in derived if r['unit'] == 'ratio')['value']['maximum'], 1)

    def test_summary_groups_do_not_mix_time_or_methods(self):
        rows = [row('a', time_start='t1', calculation_method='left'),
                row('b', time_start='t2', calculation_method='left'),
                row('c', time_start='t1', calculation_method='trapezoid')]
        derived, _, _ = select_initial_evidence(rows, scope(), 'm', 'r')
        self.assertEqual(len(derived), 2)
        left = next(r for r in derived if r['source_calculation_method'] == 'left')
        self.assertEqual(len(left['value']['by_source_window']['records']), 2)
        self.assertEqual([r[0] for r in left['value']['by_source_window']['records']], ['t1', 't2'])

    def test_different_thresholds_are_not_combined(self):
        rows = [row('a', threshold='.8'), row('b', threshold='.95')]
        derived, _, _ = select_initial_evidence(rows, scope(), 'm', 'r')
        self.assertEqual(len(derived), 2)

    def test_duplicate_event_scalar_requires_matching_value_window_and_method(self):
        context = row('ctx', metric='event_context', event='N1:E001', value={'event': {
            'duration_minutes': 5, 'start': 't1', 'end': 't2', 'integration_method': 'left'}})
        same = row('same', metric='event_duration', event='N1:E001', value='5', unit='min',
                   time_start='t1', time_end='t2', calculation_method='left')
        conflict = dict(same, evidence_id='conflict', value='6')
        other_window = dict(same, evidence_id='window', time_end='t3')
        _, ids, manifest = select_initial_evidence([context, same, conflict, other_window], scope('N1'), 'm', 'r')
        self.assertEqual(ids, ['conflict', 'ctx', 'window'])
        self.assertEqual(manifest['duplicate_scalar_ids_available_on_request'], ['same'])

    def test_prompt_metadata_can_be_reconstructed_without_changing_sources(self):
        rows = [row('a', source_file='swmm/nodes.tsv'), row('b', source_file='swmm/links.tsv')]
        state = {'task_context': scope('N1'), 'visible_ids': ['a', 'b'],
                 'first_pass_overview': {}, 'observations': []}
        prompt = build_diagnosis_prompt(state, rows)
        restored = []
        for supplied in prompt['visible_evidence']:
            supplied = dict(supplied)
            supplied['source_file'] = prompt['evidence_source_files'][supplied.pop('source_file_ref')]
            supplied['source_model'] = prompt['evidence_run']['model_name']
            supplied['run_id'] = prompt['evidence_run']['run_id']
            restored.append(supplied)
        self.assertEqual(restored, rows)

    def test_summary_is_citable_without_pretending_raw_ids_were_seen(self):
        derived, _, _ = select_initial_evidence([row('raw')], scope(), 'm', 'r')
        claims = {'source_model': 'm', 'model_name': 'm', 'run_id': 'r', 'claims': [
            {'claim_id': 'c1', 'evidence_ids': [derived[0]['evidence_id']]},
            {'claim_id': 'c2', 'evidence_ids': ['raw']}]}
        checked = check_references(claims, derived, 'm', 'r')['claim_checks']
        self.assertEqual(checked[0]['verification_status'], 'references_verified')
        self.assertEqual(checked[1]['verification_status'], 'references_missing')

    def test_queries_return_full_matching_set_and_reject_positional_scans(self):
        rows = [row(f'E{i}') for i in range(101)]
        result = lookup_evidence(rows, {'object_id': 'N1'})
        self.assertEqual(len(result['rows']), 101)
        self.assertTrue(result['complete_match_set'])
        for request in ({}, {'object_type': 'node'}, {'object_id': 'N1', 'offset': 60}):
            with self.assertRaises(ValueError):
                lookup_evidence(rows, request)

    def test_lossless_series_preserves_null_missing_signed_flow_and_all_samples(self):
        series = [{'time': str(i), 'nodes': {'N1': {'head': 1.0000000000001 + i,
                  'method': 'native_output', 'missing': None}}, 'flow': -i, 'empty': {}}
                  for i in range(100)]
        series[3]['nodes']['N1'].pop('missing')
        before = json.dumps(series)
        encoded = encode_series(series)
        self.assertIsInstance(encoded, dict)
        self.assertEqual(decode_series(encoded), series)
        self.assertEqual(json.dumps(series), before)
        source = row('S', metric='local_process_series', value={'series': series})
        transported = transport_evidence([source])[0]
        self.assertEqual(transported['evidence_id'], 'S')
        self.assertEqual(decode_series(transported['value']['series']), source['value']['series'])

    def test_over_budget_is_rejected_not_truncated(self):
        rows = [row('huge', value='x' * 130000)]
        state = {'task_context': scope('N1'), 'visible_ids': ['huge'],
                 'first_pass_overview': {}, 'observations': []}
        with self.assertRaisesRegex(ValueError, '未截断'):
            build_diagnosis_prompt(state, rows)


class SelectionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'm/runs/r'
        (self.root / 'evidence').mkdir(parents=True)
        self.rows = [row(f'E{i}', event='N1:E001') for i in range(75)]
        self.rows.append(row('other', obj='N2', value='x' * 130000))
        with (self.root / 'evidence/evidence_table.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(self.rows[0]))
            writer.writeheader()
            writer.writerows(self.rows)
        self.patcher = patch('workflow_agents.investigation.resolve_run_root', return_value=self.root)
        self.patcher.start()
        self.state = await advance_investigation('m', 'r', question='分析N1')
        self.task = self.state['task_id']
        self.folder = self.root / 'diagnosis_tasks' / self.task

    async def asyncTearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def answer(self, requests=None):
        return {'question_assessments': [{'question_id': f'Q{i}', 'status': 'needs_evidence', 'reason': '缺过程'} for i in range(1, 5)],
                'mechanism_assessments': [{'mechanism_id': f'M{i}', 'status': 'not_investigated', 'reason': '未调查'} for i in range(1, 7)],
                'claims': [], 'evidence_requests': requests or [], 'stop_reason': '需补证'}

    async def test_legacy_prepared_task_migrates_from_frozen_snapshot(self):
        legacy = dict(self.state)
        legacy.pop('selection_version')
        legacy.pop('evidence_selection')
        legacy['visible_ids'] = [f'E{i}' for i in range(60)]
        (self.folder / 'task.json').write_text(json.dumps(legacy), encoding='utf-8')
        complete = AsyncMock(return_value=self.answer())
        result = await advance_investigation('m', 'r', 'diagnose', self.task, complete=complete)
        self.assertEqual(result['selection_version'], SELECTION_VERSION)
        self.assertEqual(len(complete.call_args.args[0]['visible_evidence']), 75)
        self.assertEqual(json.loads((self.folder / 'task_before_selection_v2.json').read_text(encoding='utf-8')), legacy)
        self.assertEqual(result['snapshot_hash'], sha256_file(self.folder / 'evidence_snapshot.json'))

    async def test_legacy_diagnosed_task_cannot_silently_change_selection(self):
        legacy = dict(self.state, revision=1)
        legacy.pop('selection_version')
        (self.folder / 'task.json').write_text(json.dumps(legacy), encoding='utf-8')
        complete = AsyncMock()
        with self.assertRaisesRegex(ValueError, '旧任务已有诊断版本'):
            await advance_investigation('m', 'r', 'diagnose', self.task, complete=complete)
        complete.assert_not_called()

    async def test_over_budget_evidence_request_does_not_change_visibility(self):
        req = {'tool': 'evidence_lookup', 'object_id': 'N2', 'reason': '补查相关节点'}
        state = await advance_investigation('m', 'r', 'diagnose', self.task,
                                            complete=AsyncMock(return_value=self.answer([req])))
        before = (self.folder / 'task.json').read_text(encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '未截断'):
            await advance_investigation('m', 'r', 'evidence', self.task)
        saved = json.loads((self.folder / 'task.json').read_text(encoding='utf-8'))
        self.assertEqual(saved, json.loads(before))
        self.assertNotIn('other', saved['visible_ids'])


if __name__ == '__main__':
    unittest.main()
