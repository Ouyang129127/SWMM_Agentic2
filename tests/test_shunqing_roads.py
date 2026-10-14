import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT/'models/Sichuan_Shunqing'
spec = importlib.util.spec_from_file_location('shunqing_roads',MODEL/'scripts/complete_roads.py')
roads = importlib.util.module_from_spec(spec)
import sys
sys.path.insert(0,str(MODEL/'scripts'))
spec.loader.exec_module(roads)


class ShunqingRoadTests(unittest.TestCase):
    def test_grid_crossings_produce_four_connected_paths(self):
        for a,b in (((10,10),(170,170)),((170,10),(10,170)),((20,20),(20,180)),
                    ((10,20),(180,20)),((40,40),(40,40))):
            path = roads.pipe_cells(a,b,20,(10,10))
            self.assertTrue(roads.connected(path))
            self.assertEqual(set(path),set(roads.pipe_cells(b,a,20,(10,10))))

    def test_all_pipe_path_cells_are_road(self):
        data = roads.read_sections(MODEL/'swmm/scenarios/baseline/model.inp')
        coords = {r[0]:np.array(r[1:3],float) for r in data['COORDINATES']}
        mask = np.load(MODEL/'static/road_mask.npy')
        for row in data['CONDUITS']:
            cells = roads.pipe_cells(coords[row[1]],coords[row[2]],20,mask.shape)
            rr,cc = np.array(cells).T
            self.assertTrue(mask[rr,cc].all(),row[0])

    def test_nodes_roads_and_obstacles_do_not_overlap(self):
        mask = np.load(MODEL/'static/road_mask.npy')
        buildings = np.load(MODEL/'static/building_mask.npy')
        flow = np.load(MODEL/'static/flow_mask.npy')
        mapping = pd.read_csv(MODEL/'static/node_to_cell_mapping.csv')
        self.assertTrue(mask[mapping.cell_row,mapping.cell_col].all())
        self.assertFalse((mask & buildings).any())
        self.assertFalse((mask & ~flow).any())

    def test_hydraulics_and_ground_preserved_with_recoverable_backup(self):
        report = json.loads((MODEL/'validation/road_upgrade_20261013_v2/report.json').read_text(encoding='utf-8'))
        for name,digest in report['unchanged_inputs_sha256'].items():
            self.assertEqual(roads.digest(MODEL/name),digest,name)
        before = MODEL/report['backup_directory']
        for name in ('terrain.npy','building_mask.npy','flow_mask.npy','valid_mask.npy','cell_id_grid.npy','smid_grid.npy'):
            self.assertEqual(roads.digest(MODEL/'static'/name),roads.digest(before/'static'/name))
        self.assertEqual(report['pipes_with_current_gaps'],0)
        self.assertEqual(report['nodes_on_roads'],113)

    def test_road_arrays_and_cell_table_agree(self):
        road = np.load(MODEL/'static/road_mask.npy')
        valid = np.load(MODEL/'static/valid_mask.npy')
        anchor = np.load(MODEL/'static/node_anchor_mask.npy')
        lower = np.load(MODEL/'static/road_lowering_mask.npy')
        elevation = np.load(MODEL/'static/elevation.npy')
        terrain = np.load(MODEL/'static/terrain.npy')
        resistance = np.load(MODEL/'static/resistance.npy')
        cells = pd.read_csv(MODEL/'static/cells.csv')
        self.assertTrue(np.array_equal(lower,road & ~anchor))
        np.testing.assert_allclose((elevation-terrain)[lower],-.1,atol=5e-5)
        np.testing.assert_allclose(resistance[road],.9)
        self.assertTrue(np.array_equal(cells.is_road,road[valid]))
        np.testing.assert_allclose(cells.elevation,elevation[valid])


if __name__=='__main__':
    unittest.main()
