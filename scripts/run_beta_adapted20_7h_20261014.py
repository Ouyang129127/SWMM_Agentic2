"""Authorized 7 h rerun; reuses the existing bounded workflow runner unchanged."""
import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import run_beta_adapted20_20261013 as worker
from simulation_timing import load_timing

worker.RUN_ID = 'ba20_7h_20261014'
worker.RUN = worker.MODEL_ROOT / 'runs' / worker.RUN_ID
worker.FOLDER = worker.MODEL_ROOT / 'validation/adapted20_7h_20261014'
worker.CHECKPOINT = worker.FOLDER / 'execution.json'
TIMING_PATH = worker.MODEL_ROOT / 'simulation_timing.json'
assert load_timing(worker.MODEL_ROOT, required=True)['post_rainfall_hours'] == 3.0
TIMING_SHA = worker.sha(TIMING_PATH)
OLD_RUN = worker.MODEL_ROOT / 'runs/ba20_20261013_p1'
OLD_TASK = OLD_RUN / 'diagnosis_tasks/1cd7377d4a9f4c26b85366154fe38c1a'
PROTECTED = [OLD_RUN / 'summary.json', OLD_RUN / 'swmm/model.out',
             OLD_TASK / 'task.json', OLD_TASK / 'diagnosis.json', OLD_TASK / 'verification.json',
             worker.MODEL_ROOT / 'swmm/scenarios/adapted_s1_wsqrt/model.inp']
OLD_HASHES = {str(p.resolve()): worker.sha(p) for p in PROTECTED}
worker.record.update(run_id=worker.RUN_ID, comparison_run_id=OLD_RUN.name,
    expected_simulation_hours=7, timing_policy=load_timing(worker.MODEL_ROOT),
    timing_policy_sha256=TIMING_SHA, comparison_artifact_hashes_before=OLD_HASHES)
original_note = worker.note


def checked_note(stage):
    assert worker.sha(TIMING_PATH) == TIMING_SHA, 'Timing policy changed during run'
    if stage == 'simulation_handoff':
        summary = worker.read(worker.RUN / 'summary.json')
        assert summary['swmm']['simulation_start'] == '2016-10-08 00:00:00'
        assert summary['swmm']['simulation_end'] == '2016-10-08 07:00:00'
        assert summary['swmm']['saved_steps'] == 421
        assert summary['ca2d']['saved_times'] == 85
        worker.record['actual_window_verified'] = True
    original_note(stage)


async def main():
    worker.note = checked_note
    code = await worker.main()
    worker.record['comparison_artifacts_unchanged'] = all(worker.sha(Path(p)) == h for p, h in OLD_HASHES.items())
    worker.record['timing_policy_unchanged'] = worker.sha(TIMING_PATH) == TIMING_SHA
    worker.save(worker.CHECKPOINT, worker.record)
    return code


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
