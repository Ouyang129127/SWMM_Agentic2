import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workflow_agents.first_pass_evidence import build_first_pass, parse_run_input
from workflow_agents.sampled_events import identify_events
from workflow_agents.investigation import advance_investigation


class FirstPassTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'm/runs/r'
        (self.root / 'swmm').mkdir(parents=True)
        (self.root / 'evidence').mkdir()
        self.inp = self.root / 'swmm/model_with_event.inp'
        self.inp.write_text('[OPTIONS]\nFLOW_UNITS LPS\nLINK_OFFSETS ELEVATION\nALLOW_PONDING NO\n'
                            '[JUNCTIONS]\nN0 9 3 0 0 0\nN1 8 3 0 0 0\nN2 7 3 0 0 0\n'
                            '[CONDUITS]\nL1 N0 N1 100 .013 9 8\nL2 N1 N2 100 .013 8 7\n'
                            '[XSECTIONS]\nL1 CIRCULAR 1 0 0 0 1\nL2 CIRCULAR 1 0 0 0 1\n', encoding='utf-8')
        self.node_rows, self.link_rows, self.native = [], [], {}
        for node in ('N0', 'N1', 'N2'):
            self.native[node] = {}
            for i in range(4):
                time = f'00:0{i}:00'
                stamp = '2024-01-01 ' + time
                self.node_rows.append(dict(node_id=node, date='2024-01-01', time=time,
                                           depth_m=1, flooding_Ls=1 if node == 'N1' and i in (1, 2) else 0))
                if i:
                    self.native[node][stamp] = {'head_m': 10, 'lateral_inflow_Ls': 3, 'total_inflow_Ls': 13}
        for key, flows in [('L1', [0, 10, -4, 0]), ('L2', [0, 5, -2, 0])]:
            for i, flow in enumerate(flows):
                self.link_rows.append(dict(link_id=key, date='2024-01-01', time=f'00:0{i}:00', flow_Ls=flow, depth_m=.5))
        self.write_table(self.root / 'swmm/nodes.tsv', self.node_rows)
        self.write_table(self.root / 'swmm/links.tsv', self.link_rows)
        self.catalog = identify_events([dict(r, flow_Ls=r['flooding_Ls']) for r in self.node_rows], 'r', 'm')

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write_table(path, rows, delimiter='\t'):
        with path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)

    def build(self, native=None):
        return build_first_pass(self.root, self.catalog,
                                binary_reader=lambda path, nodes: (self.native if native is None else native, {'status': 'test_fixture'}))

    @staticmethod
    def value(package, metric):
        return next(r['value'] for r in package['evidence_rows'] if r['metric_name'] == metric)

    def test_structure_and_directional_composition(self):
        package = self.build()
        self.assertEqual(len(package['evidence_rows']), 6)
        structure = self.value(package, 'local_structure')
        self.assertEqual(structure['links']['L1']['offset_convention'], 'ELEVATION')
        self.assertEqual(structure['links']['L1']['length'], 100)
        composition = self.value(package, 'direct_source_composition')
        self.assertEqual(composition['status'], 'complete')
        self.assertAlmostEqual(composition['volume_denominator_m3'], 1.08)
        sources = {s['source_id']: s for s in composition['sources']}
        self.assertAlmostEqual(sources['L1']['outgoing_volume_over_covered_intervals_m3'], .24)
        self.assertAlmostEqual(sources['L2']['entering_volume_over_covered_intervals_m3'], .12)
        self.assertAlmostEqual(sum(s['event_volume_share'] for s in sources.values()), 1)
        self.assertAlmostEqual(composition['peak_denominator_Ls'], 13)

    def test_initial_head_fallback_not_zero_lateral(self):
        series = self.value(self.build(), 'local_process_series')['series']
        self.assertEqual(series[0]['nodes']['N1']['head_m'], 9)
        self.assertEqual(series[0]['nodes']['N1']['head_method'], 'invert_plus_saved_depth')
        self.assertIsNone(series[0]['signed_towards_node_Ls']['aggregate_lateral'])

    def test_missing_lateral_prevents_complete_shares(self):
        del self.native['N1']['2024-01-01 00:02:00']['lateral_inflow_Ls']
        composition = self.value(self.build(), 'direct_source_composition')
        self.assertEqual(composition['status'], 'partial')
        self.assertIsNone(composition['volume_denominator_m3'])
        self.assertTrue(all(s['event_volume_share'] is None for s in composition['sources']))

    def test_missing_input_and_units_are_explicit(self):
        self.inp.write_text('[OPTIONS]\nFLOW_UNITS CFS\n', encoding='utf-8')
        composition = self.value(self.build(native={}), 'direct_source_composition')
        self.assertEqual(composition['status'], 'unavailable')
        missing = parse_run_input(self.root / 'absent.inp')
        self.assertFalse(missing['available'])

    def test_facilities_and_storage_do_not_claim_normal_operation(self):
        facts = self.value(self.build(), 'facilities_and_storage')
        self.assertEqual(facts['local_facilities'], {})
        self.assertEqual(facts['facility_actions'], 'not_extracted')
        self.assertEqual(facts['storage_volume_process'], 'not_extracted')

    def test_zero_denominator_and_absent_link_are_not_zero_shares(self):
        for row in self.link_rows:
            row['flow_Ls'] = 0
        self.write_table(self.root / 'swmm/links.tsv', self.link_rows)
        for values in self.native['N1'].values():
            values['lateral_inflow_Ls'] = 0
        composition = self.value(self.build(), 'direct_source_composition')
        self.assertEqual(composition['volume_denominator_m3'], 0)
        self.assertTrue(all(s['event_volume_share'] is None for s in composition['sources']))
        self.write_table(self.root / 'swmm/links.tsv', [r for r in self.link_rows if r['link_id'] == 'L1'])
        self.assertEqual(self.value(self.build(), 'direct_source_composition')['status'], 'partial')

    async def test_investigation_receives_prebuilt_package(self):
        package = self.build()
        (self.root / 'evidence/first_pass_evidence.json').write_text(json.dumps(package), encoding='utf-8')
        base = [{'evidence_id': 'E1', 'source_model': 'm', 'run_id': 'r', 'object_type': 'node',
                 'object_id': 'N1', 'metric_name': 'event_peak_flooding', 'event_id': 'N1:E001', 'value': 1}]
        self.write_table(self.root / 'evidence/evidence_table.csv', base, ',')
        with patch('workflow_agents.investigation.resolve_run_root', return_value=self.root):
            state = await advance_investigation('m', 'r', question='分析N1:E001')
            snapshot = json.loads((self.root / 'diagnosis_tasks' / state['task_id'] / 'evidence_snapshot.json').read_text(encoding='utf-8'))
            self.assertEqual(len(state['visible_ids']), 7)
            self.assertIn('local_process_series', {r['metric_name'] for r in snapshot})
            with (self.root / 'swmm/nodes.tsv').open('a', encoding='utf-8') as f:
                f.write('\n')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                await advance_investigation('m', 'r', question='分析N1')


if __name__ == '__main__':
    unittest.main()
