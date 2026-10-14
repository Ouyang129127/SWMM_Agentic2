"""Offline checks for the four newly authorized rainfall cases."""
import unittest
from unittest.mock import patch

from scripts import run_urban_drainage_additions_20261011 as batch
from tests import test_urban_batch as fixtures


class FourCaseScopeTests(unittest.TestCase):
    def test_exact_authorized_event_set(self):
        self.assertEqual(batch.EVENTS, {
            'chicago_like_single_4h_160mm_5min.txt',
            'chicago_like_double_4h_120mm_5min.txt',
            'chicago_like_triple_4h_120mm_5min.txt',
            'chicago_like_triple_4h_160mm_5min.txt',
        })

    def test_three_cases_are_rejected_before_file_access(self):
        with self.assertRaisesRegex(ValueError, 'four approved'):
            batch.preflight({'model_name': 'urban_drainage', 'scenario_name': 'baseline',
                             'batch_id': 'test_four', 'cases': [
                                 {'event_file': name, 'run_id': str(i)}
                                 for i, name in enumerate(sorted(batch.EVENTS)[:3])]})


class FourWorkerTests(fixtures.WorkerTests):
    async def run_fake(self, *args, **kwargs):
        # Exercise the new worker using the same isolated saved-artifact fixture.
        with patch('tests.test_urban_batch.batch', batch):
            return await super().run_fake(*args, **kwargs)

    def test_handoff_rejects_missing_artifacts(self):
        with patch('tests.test_urban_batch.batch', batch):
            super().test_handoff_rejects_missing_artifacts()


if __name__ == '__main__':
    unittest.main()
