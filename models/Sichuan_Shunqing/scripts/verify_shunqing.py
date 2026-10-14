"""Acceptance: provenance, input compatibility, zero-step engine initialization,
and a small artificial surface-injection test. No design-storm or LLM execution.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from prepare_shunqing import PROJECT, ROOT, SOURCE, CELL, digest, read_sections, polygons_of, polygon_area

sys.path.insert(0, str(ROOT))
from ca2d import load_model, add_inflow, diffuse_one_step, render_depth
from simulation_timing import load_timing
from tools import _replace_swmm_event_inputs, _parse_datetime_value_file, _validate_model_event, check_swmm_2d_project


def main():
    target_report = PROJECT/'validation/preflight_report.json'
    if target_report.exists():
        raise FileExistsError('Acceptance already recorded; use a new version to rerun')
    manifest = json.loads((PROJECT/'preparation_manifest.json').read_text(encoding='utf-8'))
    source = read_sections(SOURCE)
    baseline = read_sections(PROJECT/'swmm/scenarios/baseline/model.inp')
    assert digest(SOURCE)==manifest['source_sha256']==digest(PROJECT/'raw/shunqing_original.inp')
    origin = np.array(manifest['coordinate_transform']['source_origin'])
    changed_display = {'COORDINATES', 'POLYGONS', 'SYMBOLS', 'MAP'}
    assert set(source)==set(baseline)
    for key in source:
        if key not in changed_display | {'OPTIONS'}:
            assert source[key]==baseline[key], 'Unintended source change: '+key
    options_a, options_b = dict(source['OPTIONS']), dict(baseline['OPTIONS'])
    assert options_b.pop('REPORT_STEP')=='00:01:00'
    options_a.pop('REPORT_STEP')
    assert options_a==options_b
    for key in ('COORDINATES', 'POLYGONS', 'SYMBOLS'):
        for old, new in zip(source[key], baseline[key]):
            assert old[0]==new[0]
            np.testing.assert_allclose(np.array(old[1:3], float)-origin, np.array(new[1:3], float), atol=1e-8, rtol=0)
    polygons = polygons_of(source)
    polygon_areas = {name:polygon_area(p)/10000 for name,p in polygons.items()}
    polygon_area_audit = []
    for row in source['SUBCATCHMENTS']:
        points = polygons[row[0]]
        perimeter = np.linalg.norm(points-np.roll(points,-1,axis=0),axis=1).sum()
        # Source XY is rounded to .001 units. A .0005 displacement per axis
        # permits area error bounded by perimeter*delta + n*delta**2.
        delta = np.sqrt(2)*.0005
        bound_ha = float((perimeter*delta+len(points)*delta**2)/10000)
        difference_ha = polygon_areas[row[0]]-float(row[3])
        assert abs(difference_ha)<=bound_ha+1e-9, (row[0],difference_ha,bound_ha)
        polygon_area_audit.append(dict(subcatchment_id=row[0],difference_ha=difference_ha,
                                       coordinate_rounding_bound_ha=bound_ha))
    assert all(row[2]=='FREE' for row in baseline['OUTFALLS'])
    timing = load_timing(PROJECT, required=True)
    inventory = json.loads((PROJECT/'events/manifest.json').read_text(encoding='utf-8'))
    assert len(inventory)==19
    inputs = []
    representative = {}
    for item in inventory:
        path = PROJECT/item['event_file']
        entries = _parse_datetime_value_file(path)
        assert digest(path)==item['event_sha256']
        assert _validate_model_event(PROJECT, path, entries)['ok']
        dt = (entries[1][0]-entries[0][0]).total_seconds()/3600
        assert all((b[0]-a[0]).total_seconds()/3600==dt for a,b in zip(entries, entries[1:]))
        assert np.isclose(sum(v for _,v in entries[:-1])*dt, item['total_rain_mm'], atol=1e-8)
        assert entries[-1][1]==0
        if item['purpose']!='original_input_rainfall':
            assert len(entries)==49 and dt==5/60
            src = pd.read_csv(ROOT/item['source_file'])
            if item['date_change_only']:
                np.testing.assert_allclose([v for _,v in entries], src.value, rtol=0, atol=0)
        inp = PROJECT/'validation/event_inputs'/(path.stem+'.inp')
        meta = _replace_swmm_event_inputs(PROJECT/'swmm/scenarios/baseline/model.inp', inp, entries, timing=timing)
        prepared = read_sections(inp)
        assert meta['rain_gage_name']=='RainGage' and len(prepared['RAINGAGES'])==1
        assert prepared['RAINGAGES'][0][-1]=='bpswmm_2413'
        assert all(row[1]=='RainGage' for row in prepared['SUBCATCHMENTS'])
        before = [r for r in baseline['TIMESERIES'] if r[0]!='bpswmm_2413']
        after = [r for r in prepared['TIMESERIES'] if r[0]!='bpswmm_2413']
        assert before==after
        assert prepared['OUTFALLS']==source['OUTFALLS']
        for key in ('SUBCATCHMENTS','SUBAREAS','INFILTRATION','JUNCTIONS','CONDUITS','XSECTIONS','EVAPORATION'):
            assert prepared[key]==source[key]
        if item['purpose']!='original_input_rainfall':
            assert meta['rainfall_end']=='2020-07-15 04:00:00'
            assert meta['simulation_end']=='2020-07-15 07:00:00'
        representative.setdefault(item['purpose'], inp)
        inputs.append(dict(event=path.name, simulation_end=meta['simulation_end'], status='INPUT_READY_NOT_RUN'))
    from pyswmm import Simulation, Nodes, Links
    initialized = []
    for purpose, inp in representative.items():
        directory = PROJECT/'validation/engine_preflight'/purpose
        directory.mkdir(parents=True, exist_ok=False)
        with Simulation(str(inp), str(directory/'initialize_only.rpt'), str(directory/'initialize_only.out')) as sim:
            sim.start()
            assert sim.current_time==sim.start_time and sim.flow_units=='LPS'
            assert len(list(Nodes(sim)))==113 and len(list(Links(sim)))==131
            initialized.append(dict(purpose=purpose, steps_executed=0, status='INITIALIZED_NO_TIME_STEPS'))
    model = load_model(PROJECT/'static')
    arrays = {p.stem:np.load(p) for p in (PROJECT/'static').glob('*.npy')}
    config, mapping = model['config'], model['node_mapping']
    valid, flow, building = arrays['valid_mask'], arrays['flow_mask'], arrays['building_mask']
    assert all(a.shape==tuple(config['grid_shape']) for a in arrays.values())
    assert np.array_equal(valid, arrays['domain_mask'])
    assert np.array_equal(flow, valid & ~building)
    assert not (building & arrays['road_mask']).any()
    assert not flow[[0,-1],:].any() and not flow[:,[0,-1]].any()
    assert np.isfinite(arrays['elevation']).all() and np.isfinite(arrays['terrain']).all()
    delta = arrays['elevation']-arrays['terrain']
    np.testing.assert_allclose(delta[building], 15, atol=5e-5)
    np.testing.assert_allclose(delta[arrays['road_lowering_mask']], -.1, atol=5e-5)
    assert np.array_equal(arrays['smid_grid'][valid], np.arange(1, valid.sum()+1))
    assert len(mapping)==113 and mapping.node_id.is_unique
    pd.testing.assert_frame_equal(mapping, pd.read_csv(PROJECT/'mapping/node_to_cell_mapping.csv'))
    cells = pd.read_csv(PROJECT/'static/cells.csv')
    assert len(cells)==valid.sum()
    np.testing.assert_allclose(cells.elevation, arrays['elevation'][valid])
    coords = {r[0]:np.array(r[1:3], float) for r in baseline['COORDINATES']}
    for row in mapping.itertuples():
        assert flow[row.cell_row, row.cell_col]
        assert row.smid==arrays['smid_grid'][row.cell_row,row.cell_col]
        assert row.cell_id==arrays['cell_id_grid'][row.cell_row,row.cell_col]
        np.testing.assert_allclose([row.node_x,row.node_y],coords[row.node_id],atol=1e-8)
        assert row.distance_m<=CELL/np.sqrt(2)+1e-7
    conflicts = mapping[mapping.surface_anchor_status=='shared_cell_rim_conflict']
    assert len(conflicts)==config['shared_cell_rim_conflicts']
    # Artificial two-litre/second injection at every junction for ten minutes.
    depth = np.zeros_like(arrays['elevation'])
    junctions = mapping[mapping.node_type=='JUNCTION']
    rr, cc = junctions.cell_row.to_numpy(int), junctions.cell_col.to_numpy(int)
    q = np.full(len(junctions), .002)
    volume = 0.
    for _ in range(60):
        volume += add_inflow(depth,rr,cc,q,10.,CELL)
        diffuse_one_step(depth,arrays['elevation'],arrays['resistance'],flow,10.,CELL)
    stored = float(depth.sum(dtype=np.float64)*CELL**2)
    error = abs(stored-volume)/volume
    assert error<1e-5 and np.isfinite(depth).all() and (depth>=0).all()
    assert not depth[building].any() and not depth[~flow].any()
    assert np.count_nonzero(depth>1e-6)>len(junctions)
    render_depth(depth,model['elevation'],flow,building,PROJECT/'static/ca2d_smoke_test.png',
                 '顺庆 CA2D 人工注水验收（非降雨结果）',**model['display_layers'])
    layout = json.loads(check_swmm_2d_project('Sichuan_Shunqing'))
    assert layout['ready']
    warnings = []
    for rpt in (PROJECT/'validation').glob('**/*.rpt'):
        warnings.extend(dict(file=str(rpt.relative_to(PROJECT)),message=line.strip())
                        for line in rpt.read_text(encoding='utf-8',errors='replace').splitlines()
                        if line.strip().startswith(('WARNING','ERROR')))
    assert not any(row['message'].startswith('ERROR') for row in warnings)
    report = dict(status='PASS_WITH_DISCLOSED_SURFACE_AND_RESOLUTION_LIMITS', checked_on='2026-10-13',
                  original_unchanged=True, hydraulic_and_hydrologic_source_data_unchanged=True,
                  polygon_area_audit=polygon_area_audit,
                  project_layout=layout, prepared_inputs=inputs, engine_initialization=initialized,
                  rainfall_runs_executed=0, llm_calls=0, diagnoses_executed=0,
                  static_shape=config['grid_shape'], cell_size_m=CELL, mapped_nodes=len(mapping),
                  shared_cell_rim_conflicts=conflicts[['node_id','rim_cell_difference_m']].to_dict('records'),
                  engine_initialization_warnings=warnings,
                  artificial_injection=dict(duration_seconds=600,flow_lps_per_junction=2,
                  input_volume_m3=volume,stored_volume_m3=stored,relative_mass_error=error,
                  wet_cells=int(np.count_nonzero(depth>1e-6)),maximum_depth_m=float(depth.max())),
                  scope='input/static acceptance only; not numerical validation of rainfall simulations or physical flood prediction')
    target_report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert digest(SOURCE)==manifest['source_sha256']
    print(json.dumps({k:report[k] for k in ('status','mapped_nodes','engine_initialization','shared_cell_rim_conflicts','artificial_injection')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
