"""Offline regression tests for beta preparation: no SWMM execution or API calls."""
import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from tools import _replace_swmm_event_inputs
from simulation_timing import load_timing

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'models/pystorms_beta'
spec=importlib.util.spec_from_file_location('beta_prepare',MODEL/'scripts/prepare_beta.py')
beta=importlib.util.module_from_spec(spec);spec.loader.exec_module(beta)


class BetaPreparationTests(unittest.TestCase):
    def test_pump1_volume_and_flow_units(self):
        source=beta.sections(MODEL/'beta.inp')
        coords,_,_=beta.coordinate_transform(source)
        si=beta.convert_to_si(source,coords)
        self.assertAlmostEqual(float(si['CURVES'][0][2]),11*.3048**3)
        self.assertAlmostEqual(float(si['CURVES'][0][3]),7.2*.3048**3*1000)
        self.assertAlmostEqual(float(si['WEIRS'][0][5]),3.33*.3048**.5)
        self.assertAlmostEqual(float(si['STORAGE'][0][5]),100000*.3048**2)

    def test_preserves_unusual_source_hydrology(self):
        source=beta.sections(MODEL/'beta.inp');coords,_,_=beta.coordinate_transform(source)
        si=beta.convert_to_si(source,coords)
        self.assertTrue(all(float(r[5])==.3048 and float(r[6])==100 for r in si['SUBCATCHMENTS']))
        self.assertEqual(source['OPTIONS'][2],si['OPTIONS'][2])

    def test_rain_replacement_keeps_tide_and_inflow_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source.inp';dst=Path(tmp)/'event.inp'
            src.write_text('[OPTIONS]\nFLOW_UNITS LPS\n[RAINGAGES]\nRG1 INTENSITY 0:05 1 TIMESERIES RAIN\n'
                           '[TIMESERIES]\nRAIN 10/08/2016 00:00 1\nRAIN 10/08/2016 00:05 2\n'
                           'TIDE 10/08/2016 00:00 1.4\nINFLOW 10/08/2016 00:00 10\n'
                           'TIDE 10/09/2016 00:00 1.5\n',encoding='utf-8')
            _replace_swmm_event_inputs(src,dst,[(datetime(2016,10,8),8),
                                               (datetime(2016,10,8,0,5),0)],rain_gage_name='RG1')
            data=beta.sections(dst)['TIMESERIES']
            self.assertEqual([r for r in data if r[0]=='TIDE'],[['TIDE','10/08/2016','00:00','1.4'],
                                                              ['TIDE','10/09/2016','00:00','1.5']])
            self.assertEqual(len([r for r in data if r[0]=='INFLOW']),1)
            self.assertEqual(len([r for r in data if r[0]=='RAIN']),2)
            self.assertEqual(float(next(r for r in data if r[0]=='RAIN')[-1]),8)

    def test_prepared_beta_event_covers_tidal_boundary_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst=Path(tmp)/'event.inp'
            entries=[(datetime(2016,10,8)+timedelta(minutes=5*i),10 if i<48 else 0)
                     for i in range(49)]
            metadata=_replace_swmm_event_inputs(MODEL/'swmm/scenarios/baseline/model.inp',dst,
                entries,timing=load_timing(MODEL))
            data=beta.sections(dst)
            self.assertEqual(metadata['rain_gage_name'],'RG1')
            self.assertEqual(metadata['simulation_end'],'2016-10-09 00:00:00')
            self.assertEqual(data['RAINGAGES'][0][0],'RG1')
            self.assertEqual(len(data['RAINGAGES']),1)
            tide=[r for r in data['TIMESERIES'] if r[0]=='base_30']
            self.assertEqual(len(tide),25)
            self.assertEqual(datetime.strptime(' '.join(tide[-1][1:3]),'%m/%d/%Y %H:%M'),
                             datetime(2016,10,9))

    def test_existing_default_gage_is_not_redirected(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source.inp';dst=Path(tmp)/'event.inp'
            src.write_text('[RAINGAGES]\nrain1 INTENSITY 0:05 1 TIMESERIES RAIN\n'
                           'RG1 INTENSITY 0:05 1 TIMESERIES OTHER\n'
                           '[TIMESERIES]\nRAIN 10/08/2016 00:00 1\n'
                           'OTHER 10/08/2016 00:00 2\n',encoding='utf-8')
            metadata=_replace_swmm_event_inputs(src,dst,[(datetime(2016,10,8),8),
                                                        (datetime(2016,10,8,0,5),0)])
            self.assertEqual(metadata['rain_gage_name'],'rain1')
            self.assertIn(['OTHER','10/08/2016','00:00','2'],beta.sections(dst)['TIMESERIES'])


if __name__=='__main__':
    unittest.main()
