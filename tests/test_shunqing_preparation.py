"""Deterministic Shunqing preparation checks; no rainfall simulation or LLM."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
from simulation_timing import load_timing
from tools import _replace_swmm_event_inputs, _parse_datetime_value_file

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT/'models/Sichuan_Shunqing'
spec = importlib.util.spec_from_file_location('shunqing_prepare', MODEL/'scripts/prepare_shunqing.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class ShunqingPreparationTests(unittest.TestCase):
    def test_current_and_regenerated_timing_policies_use_three_hour_tail(self):
        policy = load_timing(MODEL, required=True)
        self.assertEqual(policy['post_rainfall_hours'], 3.)
        self.assertEqual(prepare.timing_policy(), policy)

    def test_all_candidate_inputs_end_three_hours_after_rain(self):
        source = MODEL/'swmm/scenarios/baseline/model.inp'
        policy = load_timing(MODEL, required=True)
        inventory = json.loads((MODEL/'events/manifest.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            for item in inventory:
                with self.subTest(event=item['event_file']):
                    entries = _parse_datetime_value_file(MODEL/item['event_file'])
                    meta = _replace_swmm_event_inputs(source, Path(tmp)/'event.inp', entries, timing=policy)
                    rain_end = datetime.fromisoformat(meta['rainfall_end'])
                    end = datetime.fromisoformat(meta['simulation_end'])
                    self.assertEqual(end-rain_end, timedelta(hours=3))
                    expected = (datetime(2020, 7, 16, 4) if item['purpose']=='original_input_rainfall'
                                else datetime(2020, 7, 15, 7))
                    self.assertEqual(end, expected)
                    self.assertEqual(item['simulation_end'], meta['simulation_end'])
                    options = dict(prepare.read_sections(Path(tmp)/'event.inp')['OPTIONS'])
                    self.assertEqual(options['END_DATE'], end.strftime('%m/%d/%Y'))
                    self.assertEqual(options['END_TIME'], end.strftime('%H:%M:%S'))

    def test_original_source_and_hydraulic_fields_preserved(self):
        manifest = json.loads((MODEL/'preparation_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(prepare.digest(MODEL/'shunqing.inp'), manifest['source_sha256'])
        self.assertEqual(prepare.digest(MODEL/'raw/shunqing_original.inp'), manifest['source_sha256'])
        source = prepare.read_sections(MODEL/'shunqing.inp')
        derived = prepare.read_sections(MODEL/'swmm/scenarios/baseline/model.inp')
        for key in ('JUNCTIONS','OUTFALLS','CONDUITS','XSECTIONS','SUBCATCHMENTS','SUBAREAS','INFILTRATION','TIMESERIES','EVAPORATION'):
            self.assertEqual(source[key],derived[key])
        options_a, options_b = dict(source['OPTIONS']),dict(derived['OPTIONS'])
        self.assertEqual(options_b.pop('REPORT_STEP'),'00:01:00')
        options_a.pop('REPORT_STEP')
        self.assertEqual(options_a,options_b)
        self.assertEqual(options_b['ROUTING_STEP'],'0:00:01')

    def test_coordinate_translation_only_and_no_crs_fabrication(self):
        config = json.loads((MODEL/'static/config.json').read_text(encoding='utf-8'))
        source = prepare.read_sections(MODEL/'shunqing.inp')
        derived = prepare.read_sections(MODEL/'swmm/scenarios/baseline/model.inp')
        origin = np.array(config['coordinate_transform']['source_origin'])
        self.assertIsNone(config['crs'])
        self.assertEqual(config['coordinate_transform']['scale'],1.)
        for key in ('COORDINATES','POLYGONS','SYMBOLS'):
            for old,new in zip(source[key],derived[key]):
                np.testing.assert_allclose(np.array(old[1:3],float)-origin,np.array(new[1:3],float),atol=1e-8,rtol=0)

    def test_mapping_matches_arrays_and_all_junction_rims(self):
        mapping = pd.read_csv(MODEL/'static/node_to_cell_mapping.csv')
        elevation = np.load(MODEL/'static/elevation.npy')
        flow = np.load(MODEL/'static/flow_mask.npy')
        smids = np.load(MODEL/'static/smid_grid.npy')
        self.assertEqual(len(mapping),113)
        self.assertTrue(mapping.node_id.is_unique)
        self.assertTrue((mapping.weight==1).all())
        for row in mapping.itertuples():
            self.assertTrue(flow[row.cell_row,row.cell_col])
            self.assertEqual(row.smid,smids[row.cell_row,row.cell_col])
            self.assertAlmostEqual(row.cell_elevation,float(elevation[row.cell_row,row.cell_col]))
            if row.node_type=='JUNCTION':
                self.assertLess(abs(row.rim_cell_difference_m),.02)

    def test_event_library_is_candidate_and_integrates_to_declared_depth(self):
        inventory = json.loads((MODEL/'events/manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(inventory),19)
        for item in inventory:
            entries = _parse_datetime_value_file(MODEL/item['event_file'])
            dt = (entries[1][0]-entries[0][0]).total_seconds()/3600
            self.assertAlmostEqual(sum(v for _,v in entries[:-1])*dt,item['total_rain_mm'])
            self.assertEqual(entries[-1][1],0)
            self.assertFalse(item['formal_matrix_frozen'])
            self.assertEqual(item['status'],'PREPARED_NOT_SIMULATED')

    def test_generic_rainfall_injection_uses_source_gage_and_free_outfalls(self):
        source_path = MODEL/'swmm/scenarios/baseline/model.inp'
        source = prepare.read_sections(source_path)
        entries = _parse_datetime_value_file(MODEL/'events/chicago_like_single_4h_40mm_5min.txt')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'event.inp'
            meta = _replace_swmm_event_inputs(source_path,output,entries,timing=load_timing(MODEL))
            derived = prepare.read_sections(output)
            self.assertEqual(meta['rain_gage_name'],'RainGage')
            self.assertEqual(meta['rainfall_end'],'2020-07-15 04:00:00')
            self.assertEqual(meta['simulation_end'],'2020-07-15 07:00:00')
            self.assertEqual(derived['OUTFALLS'],source['OUTFALLS'])
            self.assertEqual(len(derived['RAINGAGES']),1)
            self.assertEqual(derived['RAINGAGES'][0][:3],['RainGage','INTENSITY','0:05'])
            self.assertEqual([r for r in derived['TIMESERIES'] if r[0]!='bpswmm_2413'],
                             [r for r in source['TIMESERIES'] if r[0]!='bpswmm_2413'])

    def test_artificial_injection_is_not_reported_as_rainfall_validation(self):
        report = json.loads((MODEL/'validation/preflight_report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['rainfall_runs_executed'],0)
        self.assertEqual(report['llm_calls'],0)
        self.assertLess(report['artificial_injection']['relative_mass_error'],1e-5)
        self.assertTrue(all(r['steps_executed']==0 for r in report['engine_initialization']))
        self.assertEqual(report['shared_cell_rim_conflicts'],[])
        self.assertEqual(report['cell_size_m'],20.)


if __name__=='__main__':
    unittest.main()
