import json
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import ca2d
from simulation_timing import load_timing
from tools import _replace_swmm_event_inputs
from workflow_agents.evidence_builder import _interval_duration, _interval_volume

ROOT = Path(__file__).resolve().parents[1]
POLICY = load_timing(ROOT / "models/urban_drainage")


class TimingTests(unittest.TestCase):
    def test_short_pulse_preserves_volume_and_partial_interval(self):
        start = pd.Timestamp("2024-01-01")
        # A one-minute peak lies between five-minute boundary endpoints.
        times = [start + pd.Timedelta(minutes=i) for i in range(8)]
        source = pd.DataFrame({"DateTime": times, "cell_row": 2, "cell_col": 2,
                               "weighted_flow_m3s": [0, 0, 2, 0, 0, 0, 1, 0]})
        result, _, boundaries = ca2d.interpolate_inflow_by_time(source, 5, "interval_mean")
        self.assertEqual(boundaries, [times[0], times[5], times[7]])
        np.testing.assert_allclose(result.weighted_flow_m3s, [0.4, 0.5])
        self.assertAlmostEqual(float(np.dot(result.weighted_flow_m3s, [300, 120])), 180)

    def test_rain_end_crosses_midnight_and_preserves_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "source.inp", Path(tmp) / "target.inp"
            source.write_text("[OPTIONS]\nROUTING_STEP 0.6\n[RAINGAGES]\nrain1 INTENSITY 0:05 1 TIMESERIES rain01\n[TIMESERIES]\n", encoding="utf-8")
            start = datetime(2024, 1, 1, 23, 50)
            entries = [(start, 10), (start + timedelta(minutes=5), 10)]
            result = _replace_swmm_event_inputs(source, target, entries, timing=POLICY)
            self.assertEqual(result["rainfall_end"], "2024-01-02 00:00:00")
            self.assertEqual(result["simulation_end"], "2024-01-02 03:00:00")
            text = target.read_text()
            self.assertIn("ROUTING_STEP 0.6", text)
            self.assertIn("00:01:00", text)
            self.assertIn("01/02/2024 00:00", text)
            # Existing zero tail must not move the rain stop to the file end.
            entries += [(start + timedelta(minutes=10), 0), (start + timedelta(hours=1), 0)]
            result = _replace_swmm_event_inputs(source, target, entries, timing=POLICY)
            self.assertEqual(result["simulation_end"], "2024-01-02 03:00:00")

    def test_ca2d_clock_volume_and_zero_flow(self):
        for flow in (0, 1000):
            with self.subTest(flow=flow), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                static = root / "static"
                static.mkdir()
                (root / "simulation_timing.json").write_text(json.dumps(POLICY))
                shape = (5, 5)
                model = {"config": {"cell_size": 1}, "elevation": np.zeros(shape),
                         "smid_grid": np.arange(1, 26).reshape(shape),
                         "flow_mask": np.ones(shape, dtype=bool),
                         "building_mask": np.zeros(shape, dtype=bool),
                         "resistance": np.zeros(shape),
                         "node_mapping": pd.DataFrame([{"node_id": "A", "cell_row": 2, "cell_col": 2, "weight": 1}])}
                flooding = root / "flood.tsv"
                times = pd.date_range("2024-01-01", periods=8, freq="min")
                flooding.write_text("node_id\tdate\ttime\tflow_Ls\n" + "".join(
                    f"A\t{t:%Y-%m-%d}\t{t:%H:%M:%S}\t{flow}\n" for t in times))
                with patch.object(ca2d, "load_model", return_value=model), \
                     patch.object(ca2d, "render_depth"), patch.object(ca2d, "make_gif"), \
                     patch.object(ca2d, "write_tif", return_value=False):
                    result = ca2d.run_ca2d_simulation(static, flooding, root / "out")
                self.assertAlmostEqual(result["input_volume_m3"], flow / 1000 * 420)
                self.assertAlmostEqual(result["coupling_volume_error_m3"], 0)
                self.assertEqual(result["saved_times"], 3)
                df = pd.read_csv(result["result_txt"], sep="\t")
                self.assertEqual(list(df.Time.unique()), ["00:00:00", "00:05:00", "00:07:00"])
                cell = df[df.Smid == 13]
                np.testing.assert_allclose(cell.Depth, np.array([0, 300, 420]) * flow / 1000)

    def test_terminal_sample_has_no_duration(self):
        times = pd.Series(pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:05", "2024-01-01 00:07"]))
        self.assertEqual(_interval_duration(times, pd.Series([True, True, True])), 7)
        self.assertEqual(_interval_duration(times, pd.Series([False, False, True])), 0)
        self.assertAlmostEqual(_interval_volume(pd.DataFrame({"DateTime": times, "flow_Ls": [1000, 1000, 1000]})), 420)

    def test_other_models_are_not_opted_in(self):
        self.assertEqual(load_timing(ROOT / "models/songhua_swmm_2d"), {})


if __name__ == "__main__":
    unittest.main()
