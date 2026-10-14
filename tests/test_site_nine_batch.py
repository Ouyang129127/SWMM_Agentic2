"""Offline policy tests: no simulations, API calls, or project output writes."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from scripts import run_site_drainage_batch_20261011 as batch
from scripts.run_site_drainage_batch_20261011 import EVENTS, supplement_stop


class SiteBatchPolicyTests(unittest.TestCase):
    def state(self, **changes):
        value = {'state': 'preliminary_delivered', 'evidence_plan': [
            {'request': {'tool': 'saved_result_extract'}, 'requires_extraction': True}],
            'unresolved_evidence_requests': []}
        value.update(changes)
        return value

    def test_exact_nine_events(self):
        self.assertEqual(len(EVENTS), 9)
        self.assertNotIn('chicago_like_single_4h_60mm_5min.txt', EVENTS)

    def test_two_rounds_only(self):
        for rounds in (0, 1):
            self.assertIsNone(supplement_stop(self.state(), rounds, 2))
        self.assertEqual(supplement_stop(self.state(), 2, 2), 'supplement_round_limit')

    def test_no_new_evidence(self):
        state = self.state(evidence_plan=[{'request': {'tool': 'evidence_lookup'},
                                           'new_evidence_ids': [], 'status': 'already_visible'}])
        self.assertEqual(supplement_stop(state, 0, 2), 'no_new_evidence')

    def test_capability_gap_stops(self):
        state = self.state(evidence_plan=[], unresolved_evidence_requests=[{'status': 'unavailable'}])
        self.assertEqual(supplement_stop(state, 0, 2), 'capability_gaps')

    def test_arbitrary_tool_rejected(self):
        state = self.state(evidence_plan=[{'request': {'tool': 'execute_code'}, 'new_evidence_ids': ['X']}])
        self.assertEqual(supplement_stop(state, 0, 2), 'request_outside_fixed_tool_policy')

    def test_failure_stops(self):
        self.assertEqual(supplement_stop(self.state(execution_error='failed'), 0, 2), 'execution_failed')

    def test_unverified_state_stops(self):
        self.assertEqual(supplement_stop(self.state(state='revision_requested'), 0, 2), 'unexpected_task_state')


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def run_fake(self, state, progress=True, reuse=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event = 'chicago_like_single_4h_80mm_5min.txt'
            case = {'event_file': event, 'run_id': 'fake_new_case'}
            run = root / 'models/Site_Drainage_Model/runs/fake_new_case'
            folder = root / 'batch'

            def simulate(**kwargs):
                batch.save(run / 'summary.json', {'ca2d': {'status': 'COMPLETED',
                    'source_volume_m3': 1, 'max_depth_m': .1}, 'swmm': {'max_flooding_Ls': 1}})
                for name in batch.SIMULATION_FILES[1:]:
                    path = run / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('test fixture', encoding='utf-8')
                batch.save(run / 'workflow_state.json', {'state': 'SCENARIO_READY',
                                                       'history': [{'stage': 'scenario'}]})

            if reuse:
                simulate()

            async def continuation(*args, **kwargs):
                if progress:
                    state['visible_ids'].append('new_' + str(len(state['visible_ids'])))
                return state

            with patch.object(batch, 'ROOT', root), \
                 patch('tools.run_swmm_2d_project_from_rainfall', side_effect=simulate) as simulator, \
                 patch.object(batch, 'validate_saved_simulation', side_effect=lambda *a: batch.read(run / 'summary.json')), \
                 patch('workflow_agents.scenario.prepare_scenario_request', return_value={
                     'scenario_request': {'event_sha256': 'fake'}}), \
                 patch('workflow_agents.orchestrator.run_workflow_stage', return_value={'ok': True}), \
                 patch('workflow_agents.investigation.advance_investigation', new=AsyncMock(return_value=state)), \
                 patch('workflow_agents.investigation_flow.continue_investigation', new=AsyncMock(side_effect=continuation)) as proceed, \
                 patch('workflow_agents.investigation.configured_completion', new=AsyncMock()), \
                 patch('workflow_agents.reporting.narrative.configured_completion', new=AsyncMock()):
                code = await batch.worker({'max_supplement_rounds': 2,
                                           'max_provider_calls_per_case': 21,
                                           'reuse_completed_simulations': reuse}, case, folder)
                self.assertEqual(simulator.call_count, 0 if reuse else 1)
                saved_state = batch.read(run / 'workflow_state.json')
                self.assertEqual(saved_state['state'], 'RUN_READY')
                self.assertEqual(saved_state['history'][0]['stage'], 'scenario')
                return code, batch.read(folder / 'fake_new_case.json'), proceed.call_count

    def delivered(self):
        return {'task_id': 'fake', 'state': 'preliminary_delivered', 'visible_ids': ['first'],
                'revision': 1, 'report_revision': 1, 'event_manifest': [],
                'display_report': {'status': 'completed', 'revision': 1, 'html_file': 'fake.html'},
                'evidence_plan': [{'request': {'tool': 'saved_result_extract'}, 'requires_extraction': True}],
                'pending_evidence_requests': True, 'unresolved_evidence_requests': []}

    async def test_worker_enforces_two_rounds(self):
        code, record, calls = await self.run_fake(self.delivered())
        self.assertEqual((code, calls, record['supplement_rounds']), (0, 2, 2))
        self.assertEqual(record['stop_reason'], 'supplement_round_limit')
        self.assertEqual(record['status'], 'completed_with_gaps')

    async def test_worker_stops_without_new_visible_evidence(self):
        code, record, calls = await self.run_fake(self.delivered(), progress=False)
        self.assertEqual((code, calls), (0, 1))
        self.assertEqual(record['stop_reason'], 'no_progress')

    async def test_failed_report_is_not_success(self):
        state = self.delivered()
        state['display_report']['status'] = 'failed'
        state['evidence_plan'] = []
        code, record, _ = await self.run_fake(state)
        self.assertEqual(code, 1)
        self.assertEqual(record['status'], 'failed')

    async def test_no_overflow_does_not_force_supplement(self):
        state = self.delivered()
        state.update(evidence_plan=[], pending_evidence_requests=False)
        code, record, calls = await self.run_fake(state)
        self.assertEqual((code, calls), (0, 0))
        self.assertEqual(record['status'], 'completed')

    async def test_recovery_hands_off_without_resimulation(self):
        state = self.delivered()
        state.update(evidence_plan=[], pending_evidence_requests=False)
        code, record, _ = await self.run_fake(state, reuse=True)
        self.assertEqual(code, 0)
        self.assertTrue(record['simulation_reused'])
        self.assertFalse(record['simulation_executed'])
        self.assertEqual(record['simulation_handoff'],
                         {'previous_state': 'SCENARIO_READY', 'target_state': 'RUN_READY'})

    def test_handoff_rejects_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                batch.handoff_simulation(Path(directory), {'run_id': 'fake'},
                                         {'ca2d': {'status': 'COMPLETED'}})


if __name__ == '__main__':
    unittest.main()


