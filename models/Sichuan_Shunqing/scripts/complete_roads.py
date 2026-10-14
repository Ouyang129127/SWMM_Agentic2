"""Add continuous pipe-aligned roads to the existing Shunqing surface.

Preserve terrain, buildings, domain, cell IDs and source hydraulics; archive the
old inputs before changing road-dependent arrays. No rainfall or LLM execution.
"""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from prepare_shunqing import PROJECT, ROOT, read_sections, digest, save_json
sys.path.insert(0, str(ROOT))
from ca2d import load_model, add_inflow, diffuse_one_step, render_depth

VERSION = 'pipe_aligned_continuous_roads_v2'


def pipe_cells(a, b, cell_size, shape):
    """Grid supercover of a line, with orthogonal bridges at diagonal transitions.

    Split at every grid crossing, not at arbitrary drawing/sample intervals.
    Each pipe is a four-neighbor connected road-cell path, including endpoints.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    ts = [0., 1.]
    for axis in (0, 1):
        delta = b[axis]-a[axis]
        if abs(delta)<1e-12:
            continue
        lo, hi = sorted((a[axis], b[axis]))
        crossings = np.arange(np.floor(lo/cell_size)+1, np.ceil(hi/cell_size))*cell_size
        ts.extend(((crossings-a[axis])/delta).tolist())
    ts = sorted(set(t for t in ts if 0<=t<=1))
    sample_t = [0.]+[(x+y)/2 for x,y in zip(ts,ts[1:])]+[1.]
    points = a+(b-a)*np.array(sample_t)[:, None]
    cc = np.floor(points[:, 0]/cell_size).astype(int)
    rr = shape[0]-1-np.floor(points[:, 1]/cell_size).astype(int)
    cells = set()
    previous = None
    for r,c in zip(rr,cc):
        r,c = int(r),int(c)
        if not (0<=r<shape[0] and 0<=c<shape[1]):
            raise ValueError('Pipe path outside model grid')
        cells.add((r,c))
        if previous is not None:
            pr,pc = previous
            if abs(pr-r)>1 or abs(pc-c)>1:
                raise ValueError('Missed grid crossing')
            if pr!=r and pc!=c:
                cells.update(((pr,c),(r,pc)))
        previous = r,c
    return sorted(cells)


def connected(cells):
    unseen = set(cells)
    if not unseen:
        return False
    stack = [unseen.pop()]
    while stack:
        r,c = stack.pop()
        for neighbor in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)):
            if neighbor in unseen:
                unseen.remove(neighbor)
                stack.append(neighbor)
    return not unseen


def preview(arrays, config, mapping):
    cell = float(config['cell_size'])
    ny,nx = arrays['road_mask'].shape
    extent = (0,nx*cell,0,ny*cell)
    valid, road, building = (arrays[k] for k in ('valid_mask','road_mask','building_mask'))
    fig,axes = plt.subplots(1,2,figsize=(12,9),layout='constrained')
    im = axes[0].imshow(np.ma.masked_where(~valid,arrays['terrain']),extent=extent,origin='upper',cmap='terrain')
    fig.colorbar(im,ax=axes[0],shrink=.6,label='Constructed ground elevation (m)')
    axes[1].imshow(np.ma.masked_where(~valid,valid),extent=extent,origin='upper',cmap=ListedColormap(['#d4dfc6']))
    for ax in axes:
        ax.imshow(np.ma.masked_where(~road,road),extent=extent,origin='upper',interpolation='nearest',cmap=ListedColormap(['#e3e5e7']))
        ax.contour(road.astype(float),levels=[.5],extent=extent,origin='upper',colors='#89929b',linewidths=.4)
        ax.imshow(np.ma.masked_where(~building,building),extent=extent,origin='upper',cmap=ListedColormap(['#555b68']))
        ax.scatter(mapping.node_x,mapping.node_y,s=7,color='#2365a5',zorder=6)
        ax.set(xlabel='Local X (m)',ylabel='Local Y (m)',aspect='equal')
    axes[0].set_title('Constructed terrain with continuous roads')
    axes[1].set_title('Roads follow every pipe / nodes at road junctions')
    axes[1].legend(handles=[Patch(facecolor='#e3e5e7',edgecolor='#89929b',label='Pipe-aligned road'),
                            Patch(facecolor='#555b68',label='Synthetic obstacle')],loc='upper left',fontsize=8)
    fig.suptitle('Shunqing SWMM-CA2D: assumed roads above pipes; constructed surface',fontsize=11)
    for name in ('ca2d_layout_preview.png','ca2d_roads_completed.png'):
        fig.savefig(PROJECT/'static'/name,dpi=180)
    plt.close(fig)


def main():
    folder = PROJECT/'validation/road_upgrade_20261013_v2'
    if folder.exists():
        raise FileExistsError('Road upgrade already attempted; refusing overwrite')
    if any((PROJECT/'runs').iterdir()):
        raise ValueError('Existing rainfall runs require an explicitly separate surface version')
    static = PROJECT/'static'
    cfg = json.loads((static/'config.json').read_text(encoding='utf-8'))
    data = read_sections(PROJECT/'swmm/scenarios/baseline/model.inp')
    coords = {r[0]:np.array(r[1:3],float) for r in data['COORDINATES']}
    arrays = {p.stem:np.load(p) for p in static.glob('*.npy')}
    mapping = pd.read_csv(static/'node_to_cell_mapping.csv')
    original_road = arrays['road_mask'].copy()
    road = original_road.copy()
    audits,streets = [],[]
    for row in data['CONDUITS']:
        a,b = coords[row[1]],coords[row[2]]
        cells = pipe_cells(a,b,cfg['cell_size'],road.shape)
        assert connected(cells)
        rr,cc = np.array(cells).T
        assert arrays['valid_mask'][rr,cc].all(), 'Road would expand valid domain'
        assert not arrays['building_mask'][rr,cc].any(), 'Road would intersect existing obstacle'
        road[rr,cc] = True
        audits.append(dict(link_id=row[0],from_node=row[1],to_node=row[2],path_cells=len(cells),
                           previously_uncovered_cells=int((~original_road[rr,cc]).sum()),
                           four_neighbor_connected=True,all_path_cells_road=True))
        streets.append(dict(street_id='synthetic_'+row[0],link_id=row[0],from_node=row[1],to_node=row[2],
                            width_m=20.,vertices_m=json.dumps([a.tolist(),b.tolist()]),
                            path_cell_count=len(cells),raster_method='20 m nominal corridor plus connected centreline supercover',
                            assumption='pipe buried beneath assumed road; raster width varies at coarse-grid bends'))
    road[mapping.cell_row.to_numpy(int),mapping.cell_col.to_numpy(int)] = True
    assert not (road & arrays['building_mask']).any()
    assert not (road & ~arrays['flow_mask']).any()
    # Archive only this model's prior prepared artifacts, before the first write.
    before = folder/'before'
    before.mkdir(parents=True)
    shutil.copytree(static,before/'static')
    for name in ('preparation_manifest.json','README.md','validation/preflight_report.json',
                 'validation/preparation_execution.json','mapping/node_to_cell_mapping.csv'):
        src = PROJECT/name
        if src.exists():
            dest = before/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dest)
    unchanged = {str(p.relative_to(PROJECT)):digest(p) for p in
                 [PROJECT/'shunqing.inp',PROJECT/'swmm/scenarios/baseline/model.inp',
                  static/'terrain.npy',static/'building_mask.npy',static/'flow_mask.npy',static/'valid_mask.npy',
                  static/'cell_id_grid.npy',static/'smid_grid.npy']}
    lowered = road & ~arrays['node_anchor_mask']
    elevation = arrays['terrain'].copy()
    elevation[lowered] -= .1
    elevation[arrays['building_mask']] += 15
    resistance = np.where(arrays['flow_mask'],.62,0).astype(np.float32)
    resistance[road] = .9
    arrays.update(road_mask=road,road_lowering_mask=lowered,elevation=elevation,resistance=resistance)
    for name in ('road_mask','road_lowering_mask','elevation','resistance'):
        np.save(static/(name+'.npy'),arrays[name])
    # Keep the exact float32-array value as a Python/CSV float64, rather than
    # pandas' shortened float32 text representation (e.g. 277.17).
    mapping.cell_elevation = elevation[mapping.cell_row,mapping.cell_col].astype(np.float64)
    junctions = mapping.node_type=='JUNCTION'
    mapping.loc[junctions,'rim_cell_difference_m'] = mapping.loc[junctions,'cell_elevation']-mapping.loc[junctions,'surface_elevation_m']
    for path in (static/'node_to_cell_mapping.csv',PROJECT/'mapping/node_to_cell_mapping.csv'):
        mapping.to_csv(path,index=False)
    frame = pd.read_csv(static/'cells.csv')
    frame.is_road = road[arrays['valid_mask']]
    frame.elevation = elevation[arrays['valid_mask']]
    frame.to_csv(static/'cells.csv',index=False)
    pd.DataFrame(streets).to_csv(static/'synthetic_streets.csv',index=False)
    pd.DataFrame(audits).to_csv(folder/'pipe_road_coverage.csv',index=False)
    cfg.update(n_road_cells=int(road.sum()),road_version=VERSION,
               road_method='assume pipes buried below roads: nominal 20 m corridors plus 4-neighbor connected grid supercover and mapped road junctions; lowered 0.10 m except rim anchors',
               road_raster_resolution_note='20 m grid may depict 20-40 m stepped road coverage; this is raster continuity, not surveyed road width')
    save_json(static/'config.json',cfg)
    manifest = json.loads((PROJECT/'preparation_manifest.json').read_text(encoding='utf-8'))
    manifest.update(surface=cfg,road_version=VERSION,road_upgrade_record=str(folder.relative_to(PROJECT)).replace('\\','/'))
    save_json(PROJECT/'preparation_manifest.json',manifest)
    model = load_model(static)
    depth = np.zeros_like(elevation)
    jm = mapping[junctions]
    rr,cc = jm.cell_row.to_numpy(int),jm.cell_col.to_numpy(int)
    q = np.full(len(jm),.002)
    volume = 0.
    for _ in range(60):
        volume += add_inflow(depth,rr,cc,q,10.,cfg['cell_size'])
        diffuse_one_step(depth,elevation,resistance,arrays['flow_mask'],10.,cfg['cell_size'])
    stored = float(depth.sum(dtype=np.float64)*cfg['cell_size']**2)
    error = abs(stored-volume)/volume
    assert error<1e-5 and np.isfinite(depth).all() and (depth>=0).all()
    assert not depth[~arrays['flow_mask']].any()
    assert all(digest(PROJECT/name)==sha for name,sha in unchanged.items())
    preview(arrays,cfg,mapping)
    render_depth(depth,elevation,arrays['flow_mask'],arrays['building_mask'],static/'ca2d_smoke_test.png',
                 '顺庆：连续道路人工注水验收（非降雨结果）',**model['display_layers'])
    report = dict(status='PASS',version=VERSION,date='2026-10-13',assumption='pipes buried under assumed roads',
                  previous_road_cells=int(original_road.sum()),current_road_cells=int(road.sum()),
                  added_road_cells=int((road & ~original_road).sum()),pipes_checked=len(audits),
                  pipes_with_old_gaps=sum(x['previously_uncovered_cells']>0 for x in audits),
                  pipes_with_current_gaps=0,nodes_on_roads=int(road[mapping.cell_row,mapping.cell_col].sum()),
                  old_nodes_off_road=int((~original_road[mapping.cell_row,mapping.cell_col]).sum()),
                  mapping_rim_conflicts=int((mapping.loc[junctions,'rim_cell_difference_m'].abs()>.02).sum()),
                  buildings_removed=0,domain_changed=False,baseline_inp_changed=False,
                  unchanged_inputs_sha256=unchanged,backup_directory=str(before.relative_to(PROJECT)).replace('\\','/'),
                  artificial_injection=dict(duration_seconds=600,flow_lps_per_junction=2,input_volume_m3=volume,
                      stored_volume_m3=stored,relative_mass_error=error,wet_cells=int((depth>1e-6).sum()),
                      maximum_depth_m=float(depth.max())),rainfall_runs=0,llm_calls=0)
    preflight = json.loads((PROJECT/'validation/preflight_report.json').read_text(encoding='utf-8'))
    preflight.update(road_version=VERSION,road_upgrade_record=str((folder/'report.json').relative_to(PROJECT)).replace('\\','/'),
                     artificial_injection=report['artificial_injection'])
    save_json(PROJECT/'validation/preflight_report.json',preflight)
    report['current_artifact_sha256'] = {str(p.relative_to(PROJECT)).replace('\\','/'):digest(p)
                                        for p in list(static.iterdir())+[PROJECT/'preparation_manifest.json',PROJECT/'validation/preflight_report.json'] if p.is_file()}
    save_json(folder/'report.json',report)
    print(json.dumps({k:report[k] for k in ('status','previous_road_cells','current_road_cells','added_road_cells',
                                           'pipes_checked','pipes_with_current_gaps','nodes_on_roads','artificial_injection')},ensure_ascii=False))


if __name__=='__main__':
    main()
