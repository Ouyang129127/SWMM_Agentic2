import copy
import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from workflow_agents.sampled_events import identify_events
from workflow_agents.reference_checks import check_references
from workflow_agents.verification import verify_diagnosis_claims
from workflow_agents.scoped_report import build_scoped_report, select_scope
from workflow_agents.orchestrator import run_workflow_stage
from workflow_agents.evidence_builder import build_evidence_for_run
from workflow_agents.diagnosis import diagnose_run_from_evidence


def records(flows, node='N1'):
    return [{'node_id': node, 'DateTime': str(datetime(2024, 1, 1) + timedelta(minutes=i)), 'flow_Ls': f}
            for i, f in enumerate(flows)]


class EventTests(unittest.TestCase):
    def test_separate_positive_runs(self):
        result = identify_events(records([0, 2, 3, 0, 4, 0]), 'r', 'm')['events']
        self.assertEqual([e['event_id'] for e in result], ['N1:E001', 'N1:E002'])
        self.assertEqual([e['duration_minutes'] for e in result], [2, 1])
        self.assertAlmostEqual(result[0]['estimated_volume_m3'], .3)
        self.assertEqual(result[0]['end'], '2024-01-01 00:03:00')

    def test_dry_singleton_and_terminal(self):
        self.assertEqual(identify_events(records([0, 0]), 'r', 'm')['events'], [])
        event = identify_events(records([5]), 'r', 'm')['events'][0]
        self.assertTrue(event['right_censored'])
        self.assertEqual(event['duration_minutes'], 0)
        self.assertEqual(event['estimated_volume_m3'], 0)

    def test_missing_and_duplicates(self):
        for data in (records([0, float('nan')]), records([0, 1]) + records([0])[:1]):
            with self.assertRaises(ValueError):
                identify_events(data, 'r', 'm')
        data = records([0, 1, 2, 0])
        del data[2]
        with self.assertRaises(ValueError):
            identify_events(data, 'r', 'm')


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'evidence_id': 'E1', 'source_model': 'm', 'run_id': 'r', 'value': 0}]
        self.payload = {'model_name': 'm', 'run_id': 'r', 'claims': [
            {'claim_id': 'C1', 'evidence_ids': ['E1']},
            {'claim_id': 'C2', 'evidence_ids': ['E9']},
            {'claim_id': 'C3', 'evidence_ids': []}]}

    def test_three_reference_states(self):
        result = check_references(self.payload, self.rows, 'm', 'r')
        self.assertEqual([x['verification_status'] for x in result['claim_checks']],
                         ['references_verified', 'references_missing', 'no_references'])
        self.assertFalse(result['causal_validity_checked'])
        self.assertAlmostEqual(result['summary']['reference_failure_rate'], 2 / 3)

    def test_foreign_run_and_duplicate(self):
        bad = copy.deepcopy(self.rows)
        bad[0]['run_id'] = 'other'
        with self.assertRaises(ValueError):
            check_references(self.payload, bad, 'm', 'r')
        with self.assertRaises(ValueError):
            check_references(self.payload, self.rows * 2, 'm', 'r')

    def test_no_claims_not_perfect_score(self):
        self.payload['claims'] = []
        self.assertIsNone(check_references(self.payload, self.rows, 'm', 'r')['summary']['reference_failure_rate'])


class ScopeTests(unittest.TestCase):
    def test_global_and_node(self):
        self.assertEqual(select_scope('给我整体评估报告', {'N1', 'N10'})['scope'], 'global')
        self.assertEqual(select_scope('分析N1为什么冒溢', {'N1', 'N10'})['node_id'], 'N1')
        self.assertEqual(select_scope('N1:E002', {'N1'})['event_id'], 'N1:E002')

    def test_unknown_and_ambiguous(self):
        for message in ('分析节点 N9', '分析N1和N10', '为什么这个节点冒溢'):
            with self.assertRaises(ValueError):
                select_scope(message, {'N1', 'N10'})


class IntegrationTests(unittest.TestCase):
    def test_builder_diagnosis_verification_report(self):
        # Fully synthetic outputs; does not run SWMM or modify a saved run.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'm' / 'runs' / 'r'
            (root / 'swmm').mkdir(parents=True)
            (root / 'ca2d').mkdir()
            (root / 'summary.json').write_text(json.dumps({'run_id': 'r', 'model_name': 'm', 'event_name': 'synthetic', 'simulation_timing': {'test': True}}), encoding='utf-8')
            def write_table(path, rows):
                with path.open('w', encoding='utf-8', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t')
                    writer.writeheader()
                    writer.writerows(rows)
            floods, nodes, links, surface = [], [], [], []
            for i, flow in enumerate([0, 2, 0, 3, 0]):
                time = f'00:0{i}:00'
                floods.append(dict(node_id='N1', date='2024-01-01', time=time, flow_Ls=flow))
                nodes.append(dict(node_id='N1', date='2024-01-01', time=time, depth_m=1, flooding_Ls=flow))
                links.append(dict(link_id='L1', date='2024-01-01', time=time, flow_Ls=1, depth_m=.1))
                surface.append(dict(Smid=1, Date='2024-01-01', Time=time, Depth=.2))
            write_table(root / 'swmm/node_flooding.tsv', floods)
            write_table(root / 'swmm/nodes.tsv', nodes)
            write_table(root / 'swmm/links.tsv', links)
            write_table(root / 'ca2d/surface_depth.tsv', surface)
            with patch('workflow_agents.evidence_builder.resolve_run_root', return_value=root):
                built = build_evidence_for_run('m', 'r')
            self.assertEqual(built['overflow_event_count'], 2)
            with patch('workflow_agents.diagnosis.resolve_run_root', return_value=root):
                diagnosed = diagnose_run_from_evidence('m', 'r')
            episode_claims = [c for c in diagnosed['claims'] if c.get('event_id')]
            self.assertEqual(len(episode_claims), 2)
            with patch('workflow_agents.verification.resolve_run_root', return_value=root):
                verified = verify_diagnosis_claims('m', 'r')
            self.assertEqual(verified['summary']['reference_failure_rate'], 0)
            with patch('workflow_agents.scoped_report.resolve_run_root', return_value=root):
                report = build_scoped_report('m', 'r', '分析N1:E002')
            self.assertIn(episode_claims[1]['claim_id'], report['markdown'])
            self.assertNotIn(episode_claims[0]['claim_id'], report['markdown'])

    def test_until_stops_at_next_confirmation(self):
        state = {'model_name': 'm', 'run_id': 'r', 'state': 'RUN_READY', 'next_allowed_stage': 'evidence_building'}
        new_state = dict(state, state='EVIDENCE_READY', next_allowed_stage='diagnosis')
        with patch('workflow_agents.orchestrator.load_or_initialize_state', return_value=(Path('dummy'), state)), \
             patch('workflow_agents.orchestrator._run_single_stage', return_value={}) as execute, \
             patch('workflow_agents.orchestrator.build_state', return_value=new_state), \
             patch('workflow_agents.orchestrator.save_state'):
            result = run_workflow_stage('m', 'r', until_stage='verification')
        execute.assert_called_once_with('m', 'r', 'evidence_building')
        self.assertTrue(result['awaiting_user_confirmation'])
        self.assertEqual(result['remaining_requested_stages'], ['diagnosis', 'verification'])

    def test_verification_to_report_and_stale_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'm' / 'runs' / 'r'
            (root / 'evidence').mkdir(parents=True)
            (root / 'diagnosis').mkdir()
            rows = [{'evidence_id': 'E1', 'source_model': 'm', 'run_id': 'r',
                     'object_type': 'node', 'object_id': 'N1', 'metric_name': 'total_flooding_volume',
                     'value': 1, 'unit': 'm3'}]
            with (root / 'evidence/evidence_table.csv').open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            claims = {'model_name': 'm', 'run_id': 'r', 'claims': [
                {'claim_id': 'C1', 'object_type': 'node', 'object_id': 'N1',
                 'claim_text': '保存结果存在冒溢。', 'evidence_ids': ['E1']},
                {'claim_id': 'C2', 'object_type': 'node', 'object_id': 'N1',
                 'claim_text': '此句不应被发布', 'evidence_ids': ['BAD']}]}
            claim_path = root / 'diagnosis/diagnosis_claims.json'
            claim_path.write_text(json.dumps(claims), encoding='utf-8')
            (root / 'evidence/overflow_events.json').write_text(json.dumps(identify_events(records([0, 1, 0]), 'r', 'm')), encoding='utf-8')
            with patch('workflow_agents.verification.resolve_run_root', return_value=root):
                verified = verify_diagnosis_claims('m', 'r')
            self.assertEqual(verified['summary']['references_verified'], 1)
            with patch('workflow_agents.scoped_report.resolve_run_root', return_value=root):
                report = build_scoped_report('m', 'r', '分析N1')
                self.assertIn('N1:E001', report['markdown'])
                self.assertNotIn('此句不应被发布', report['markdown'])
                report = build_scoped_report('m', 'r', '分析N1:E001')
                self.assertNotIn('[C1]', report['markdown'])  # run-level claim is not event-level
                self.assertEqual(report['next_action'], 'diagnosis_review_requested')
                claims['claims'][0]['claim_text'] = 'changed'
                claim_path.write_text(json.dumps(claims), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'changed'):
                    build_scoped_report('m', 'r')


if __name__ == '__main__':
    unittest.main()
