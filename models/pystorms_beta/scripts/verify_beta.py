"""Offline input/static acceptance, initialization only, and artificial CA2D injection.

No SWMM time step, design-storm simulation, LLM call or diagnosis is executed.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from prepare_beta import PROJECT, ROOT, SOURCE, sections, digest, SCENARIOS, FT, FT2, FT3, CFS_LPS, ACRE_HA

sys.path.insert(0,str(ROOT))
from ca2d import load_model, add_inflow, diffuse_one_step, render_depth
from simulation_timing import load_timing
from tools import (_replace_swmm_event_inputs, _parse_datetime_value_file,
                   _validate_model_event, check_swmm_2d_project)


def scaled_equal(a,b,factor):
    assert np.isclose(float(b),float(a)*factor,rtol=1e-9,atol=1e-9),(a,b,factor)


def main():
    manifest=json.loads((PROJECT/'preparation_manifest.json').read_text(encoding='utf-8'))
    assert digest(SOURCE)==manifest['source_sha256']==digest(PROJECT/'raw/beta_original.inp')
    source=sections(SOURCE); si=sections(PROJECT/'swmm/scenarios/baseline/model.inp')
    assert dict(si['OPTIONS'])['FLOW_UNITS']=='LPS'
    assert dict(si['OPTIONS'])['ROUTING_STEP']==dict(source['OPTIONS'])['ROUTING_STEP']
    assert dict(si['OPTIONS'])['INERTIAL_DAMPING']==dict(source['OPTIONS'])['INERTIAL_DAMPING']
    rules={'SUBCATCHMENTS':{3:ACRE_HA,5:FT,7:FT},'SUBAREAS':{3:25.4,4:25.4},
           'INFILTRATION':{1:25.4,2:25.4,5:25.4},'JUNCTIONS':{1:FT,2:FT,3:FT,4:FT,5:FT2},
           'CONDUITS':{3:FT,5:FT,6:FT,7:CFS_LPS,8:CFS_LPS},'PUMPS':{5:FT,6:FT},'ORIFICES':{4:FT}}
    for sec,rule in rules.items():
        assert len(source[sec])==len(si[sec])
        for a,b in zip(source[sec],si[sec]):
            assert a[0]==b[0]
            for i,f in rule.items():
                if i<len(a):scaled_equal(a[i],b[i],f)
    for a,b in zip(source['STORAGE'],si['STORAGE']):
        for i,f in {1:FT,2:FT,3:FT,5:FT2/FT**float(a[6]),7:FT2}.items():scaled_equal(a[i],b[i],f)
    for a,b in zip(source['WEIRS'],si['WEIRS']):
        for i,f in {4:FT,5:FT**.5,8:FT**.5}.items():scaled_equal(a[i],b[i],f)
    for a,b in zip(source['XSECTIONS'],si['XSECTIONS']):
        assert a[:2]==b[:2]
        scaled_equal(a[2],b[2],FT)
        if a[1]!='CIRCULAR':scaled_equal(a[3],b[3],FT)
    for a,b in zip(source['CURVES'],si['CURVES']):
        x,y=(2,3) if len(a)==4 else (1,2)
        scaled_equal(a[x],b[x],FT3); scaled_equal(a[y],b[y],CFS_LPS)
    for a,b in zip(source['TIMESERIES'],si['TIMESERIES']):
        assert a[:-1]==b[:-1]
        scaled_equal(a[-1],b[-1],FT if a[0].startswith('base_') else 25.4)
    scaled_equal(dict(source['OPTIONS'])['MIN_SURFAREA'],dict(si['OPTIONS'])['MIN_SURFAREA'],FT2)
    scaled_equal(dict(source['OPTIONS'])['HEAD_TOLERANCE'],dict(si['OPTIONS'])['HEAD_TOLERANCE'],FT)
    scaled_equal(source['OUTFALLS'][0][1],si['OUTFALLS'][0][1],FT)
    for name in SCENARIOS:
        data=sections(PROJECT/f'swmm/scenarios/{name}/model.inp')
        assert all(data[k]==si[k] for k in si if k!='OUTFALLS')
        assert data['OUTFALLS'][0][-1]=='YES'
    timing=load_timing(PROJECT,required=True)
    inventory=json.loads((PROJECT/'events/manifest.json').read_text())
    assert len(inventory)==9
    prepared=[]
    engine_files={}
    for item in inventory:
        path=PROJECT/item['event_file']; entries=_parse_datetime_value_file(path)
        assert _validate_model_event(PROJECT,path,entries)['ok']
        assert digest(path)==item['event_sha256']
        original=pd.read_csv(ROOT/item['source_file'])
        np.testing.assert_allclose([v for _,v in entries],original.value,rtol=0,atol=0)
        assert entries[0][0]==datetime(2016,10,8) and entries[-1][0]==datetime(2016,10,8,4)
        assert all((b[0]-a[0]).total_seconds()==300 for a,b in zip(entries,entries[1:]))
        for name in SCENARIOS:
            target=PROJECT/'validation/event_inputs'/name/(path.stem+'.inp')
            result=_replace_swmm_event_inputs(PROJECT/f'swmm/scenarios/{name}/model.inp',target,
                                             entries,timing=timing)
            data=sections(target)
            before=[r for r in si['TIMESERIES'] if r[0].startswith('base_')]
            after=[r for r in data['TIMESERIES'] if r[0].startswith('base_')]
            assert before==after,'Tide series changed/disappeared during rainfall replacement'
            assert data['RAINGAGES'][0][:3]==['RG1','INTENSITY','0:05']
            end=datetime.fromisoformat(result['simulation_end'])
            assert end==datetime(2016,10,9)
            if name!='free_outfall':
                tide=data['OUTFALLS'][0][3]
                rows=[r for r in data['TIMESERIES'] if r[0]==tide]
                assert datetime.strptime(rows[0][1]+' '+rows[0][2],'%m/%d/%Y %H:%M')<=entries[0][0]
                assert datetime.strptime(rows[-1][1]+' '+rows[-1][2],'%m/%d/%Y %H:%M')>=end
            prepared.append({'event':path.name,'scenario':name,'status':'INPUT_READY_NOT_RUN',
                             'simulation_end':result['simulation_end'],'rain_gage':'RG1'})
            engine_files.setdefault(name,target)
    # Load and initialize each representative file; never call swmm_step/next.
    from pyswmm import Simulation,Nodes,Links
    initialized=[]
    for name,inp in engine_files.items():
        folder=PROJECT/'validation/engine_preflight'/name;folder.mkdir(parents=True,exist_ok=True)
        with Simulation(str(inp),str(folder/'initialize_only.rpt'),str(folder/'initialize_only.out')) as sim:
            sim.start()
            assert sim.current_time==sim.start_time
            assert sim.flow_units=='LPS'
            assert len(list(Nodes(sim)))==210 and len(list(Links(sim)))==211
            initialized.append({'scenario':name,'status':'INITIALIZED_NO_TIME_STEPS','steps_executed':0})
    model=load_model(PROJECT/'static');a={p.stem:np.load(p) for p in (PROJECT/'static').glob('*.npy')}
    config=model['config'];mapping=model['node_mapping'];valid=a['valid_mask'];flow=a['flow_mask'];building=a['building_mask']
    assert all(v.shape==tuple(config['grid_shape']) for v in a.values())
    assert np.array_equal(flow,valid&~building)
    assert np.array_equal(valid,a['domain_mask'])
    assert not (building&a['road_mask']).any()
    assert building.any() and a['road_mask'].any()
    assert not flow[[0,-1],:].any() and not flow[:,[0,-1]].any()
    assert np.isfinite(a['elevation']).all() and np.isfinite(a['terrain']).all()
    delta=a['elevation']-a['terrain']
    np.testing.assert_allclose(delta[building],15,atol=2e-6)
    np.testing.assert_allclose(delta[a['road_lowering_mask']],-.1,atol=2e-6)
    assert np.array_equal(a['smid_grid'][valid],np.arange(1,valid.sum()+1))
    cells=pd.read_csv(PROJECT/'static/cells.csv')
    assert len(cells)==valid.sum()
    np.testing.assert_allclose(cells.elevation,a['elevation'][valid])
    pd.testing.assert_frame_equal(mapping,pd.read_csv(PROJECT/'mapping/node_to_cell_mapping.csv'))
    coords={r[0]:np.array(r[1:3],float) for r in si['COORDINATES']}
    assert len(mapping)==210 and mapping.node_id.is_unique
    for r in mapping.itertuples():
        assert flow[r.cell_row,r.cell_col]
        assert r.smid==a['smid_grid'][r.cell_row,r.cell_col]
        assert r.cell_id==a['cell_id_grid'][r.cell_row,r.cell_col]
        assert np.isclose(r.cell_elevation,a['elevation'][r.cell_row,r.cell_col])
        np.testing.assert_allclose([r.node_x,r.node_y],coords[r.node_id])
        np.testing.assert_allclose([r.cell_x,r.cell_y],[(r.cell_col+.5)*config['cell_size'],
                                                      (a['elevation'].shape[0]-r.cell_row-.5)*config['cell_size']])
        assert r.distance_m<=config['cell_size']/2**.5+1e-6
    conflicts=mapping[mapping.surface_anchor_status=='shared_cell_rim_conflict']
    assert len(conflicts)==config['shared_cell_rim_conflicts']
    depth=np.zeros_like(a['elevation']);inflow=mapping[mapping.node_type=='JUNCTION']
    rows=inflow.cell_row.to_numpy(int);cols=inflow.cell_col.to_numpy(int)
    q=np.full(len(inflow),.002);volume=0.
    for _ in range(60):
        volume+=add_inflow(depth,rows,cols,q,10.,config['cell_size'])
        diffuse_one_step(depth,a['elevation'],a['resistance'],flow,10.,config['cell_size'])
    stored=float(depth.sum(dtype=np.float64)*config['cell_size']**2)
    mass_error=abs(stored-volume)/volume
    assert mass_error<1e-5 and np.isfinite(depth).all() and (depth>=0).all()
    assert not depth[building].any() and not depth[~flow].any()
    assert np.count_nonzero(depth>1e-6)>len(inflow)
    render_depth(depth,model['elevation'],flow,building,PROJECT/'static/ca2d_smoke_test.png',
                 'Beta 人工注水验收（不是降雨模拟结果）',**model['display_layers'])
    report=dict(status='PASS_WITH_DISCLOSED_SURFACE_WARNINGS',checked_on='2026-10-12',
                original_source_unchanged=True,unit_conversion='all populated hydraulic/hydrologic fields checked',
                project_layout=json.loads(check_swmm_2d_project('pystorms_beta')),
                prepared_inputs=len(prepared),engine_initialization=initialized,
                formal_rainfall_simulations_executed=0,diagnoses_executed=0,
                rain_gage_integration='generic rain1 default resolves the sole source gage RG1; verified for all 27 inputs',
                static_shape=config['grid_shape'],mapped_nodes=len(mapping),
                shared_cell_rim_conflicts=conflicts[['node_id','rim_cell_difference_m']].to_dict('records'),
                surface_spatial_truth='synthetic only; these 6 conflicting nodes are not precise rim-validation targets',
                artificial_injection=dict(duration_seconds=600,flow_lps_per_junction=2,input_volume_m3=volume,
                                          stored_volume_m3=stored,relative_mass_error=mass_error,
                                          wet_cells=int(np.count_nonzero(depth>1e-6)),maximum_depth_m=float(depth.max())),
                prepared_scenarios=prepared)
    assert report['project_layout']['ready']
    (PROJECT/'validation/preflight_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert digest(SOURCE)==manifest['source_sha256']
    print(json.dumps({k:report[k] for k in ('status','prepared_inputs','engine_initialization',
                                          'mapped_nodes','shared_cell_rim_conflicts','artificial_injection')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
