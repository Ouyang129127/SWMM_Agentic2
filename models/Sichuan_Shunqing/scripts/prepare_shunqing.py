"""Prepare an additive, reproducible Shunqing SWMM–CA2D project.

Only model display coordinates and baseline REPORT_STEP change. No calibration,
rainfall simulation or model/API request is performed. Never overwrite a build.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.path import Path as PolygonPath
import numpy as np
import pandas as pd
from PIL import Image, ImageFilter

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
SOURCE = PROJECT / 'shunqing.inp'
CELL = 20.0
ROAD_WIDTH = 20.0
MARGIN = 80.0
EPOCH = datetime(2020, 7, 15)


def timing_policy():
    """Keep regenerated builds at the requested three-hour post-rain window."""
    return dict(swmm_save_interval_minutes=1., boundary_interval_minutes=5.,
                ca2d_save_interval_minutes=5., post_rainfall_hours=3.,
                boundary_method='interval_mean', rainfall_time_convention='interval_start',
                rationale='Rainfall end plus 3 h, per user instruction; 4 h synthetic events run for 7 h and the 25 h source event for 28 h; fixed observation window, not validated as complete drainage')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_sections(path):
    result, current = {}, None
    for raw in Path(path).read_text(encoding='utf-8-sig').splitlines():
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            current = line.strip('[]').upper()
            result.setdefault(current, [])
        elif current:
            result[current].append(line.split())
    return result


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def polygons_of(data):
    result = defaultdict(list)
    for name, x, y in data['POLYGONS']:
        result[name].append((float(x), float(y)))
    return {name: np.array(points) for name, points in result.items()}


def polygon_area(points):
    p = points-points[0]
    return abs(np.dot(p[:, 0], np.roll(p[:, 1], -1))-
               np.dot(p[:, 1], np.roll(p[:, 0], -1)))/2


def dilate(mask, size):
    return np.array(Image.fromarray(mask.astype(np.uint8)).filter(ImageFilter.MaxFilter(size)), dtype=bool)


def segment_distance(xx, yy, a, b):
    dx, dy = b-a
    denominator = dx*dx+dy*dy
    t = np.clip(((xx-a[0])*dx+(yy-a[1])*dy)/denominator, 0, 1) if denominator else 0
    return np.hypot(xx-a[0]-t*dx, yy-a[1]-t*dy)


def localize(source):
    data = copy.deepcopy(source)
    all_points = np.array([r[1:3] for key in ('COORDINATES', 'POLYGONS', 'SYMBOLS')
                           for r in source.get(key, [])], dtype=float)
    origin = np.floor((all_points.min(axis=0)-MARGIN)/CELL)*CELL
    for key in ('COORDINATES', 'POLYGONS', 'SYMBOLS'):
        for row in data.get(key, []):
            row[1:3] = [format(float(v)-origin[i], '.9f') for i, v in enumerate(row[1:3])]
    for row in data['OPTIONS']:
        if row[0] == 'REPORT_STEP':
            row[1] = '00:01:00'
    extent = np.ceil((all_points.max(axis=0)-origin+MARGIN)/CELL)*CELL
    data['MAP'] = [['DIMENSIONS', '0', '0', str(extent[0]), str(extent[1])], ['Units', 'Meters']]
    transform = dict(operation='translation_only', scale=1.0, source_origin=origin.tolist(),
                     formula='local_xy = source_xy - source_origin', crs=None,
                     coordinate_units_basis='metres inferred from pipe endpoint distance and hydraulic length agreement',
                     source_map_units='None', georeference_status='CRS not provided; no EPSG asserted')
    return data, transform


def source_audit(source):
    coords = {r[0]: np.array(r[1:3], float) for r in source['COORDINATES']}
    invert = {r[0]: float(r[1]) for key in ('JUNCTIONS', 'OUTFALLS') for r in source[key]}
    records = []
    for row in source['CONDUITS']:
        distance = float(np.linalg.norm(coords[row[1]]-coords[row[2]]))
        length = float(row[3])
        slope = (invert[row[1]]+float(row[5])-invert[row[2]]-float(row[6]))/length
        records.append(dict(link_id=row[0], from_node=row[1], to_node=row[2],
                            hydraulic_length_m=length, coordinate_distance=distance,
                            length_to_coordinate_ratio=length/distance if distance else None,
                            invert_slope=slope, adverse_slope=slope < 0))
    return pd.DataFrame(records)


def build_surface(data, transform):
    coords = {r[0]: np.array(r[1:3], float) for r in data['COORDINATES']}
    polygons = polygons_of(data)
    extent = np.array(data['MAP'][0][3:5], float)
    nx, ny = np.rint(extent/CELL).astype(int)
    xx, yy = np.meshgrid((np.arange(nx)+.5)*CELL, (ny-np.arange(ny)-.5)*CELL)
    queries = np.column_stack([xx.ravel(), yy.ravel()])
    catchment = np.zeros((ny, nx), dtype=bool)
    for points in polygons.values():
        if len(points) < 3:
            raise ValueError('Invalid source subcatchment polygon')
        # Cell-centre membership; original polygons are not treated as surveyed DEM.
        box = ((queries >= points.min(axis=0)).all(axis=1) &
               (queries <= points.max(axis=0)).all(axis=1))
        indices = np.flatnonzero(box)
        catchment.ravel()[indices] |= PolygonPath(points).contains_points(queries[indices], radius=1e-7)
    road = np.zeros_like(catchment)
    streets = []
    for row in data['CONDUITS']:
        a, b = coords[row[1]], coords[row[2]]
        road |= segment_distance(xx, yy, a, b) <= ROAD_WIDTH/2
        streets.append(dict(street_id='synthetic_'+row[0], width_m=ROAD_WIDTH,
                            vertices_m=json.dumps([a.tolist(), b.tolist()]),
                            assumption='grid-resolved hypothetical corridor; not a surveyed street'))
    node_neighborhood = np.zeros_like(catchment)
    for point in coords.values():
        node_neighborhood |= np.hypot(xx-point[0], yy-point[1]) <= CELL*1.5
    valid = dilate(catchment | road | node_neighborhood, 5)
    valid[[0, -1], :] = False
    valid[:, [0, -1]] = False
    road &= valid
    forbidden = dilate(road, 3) | node_neighborhood | ~valid
    building = np.zeros_like(valid)
    blocks = []
    for r in range(5, ny-5, 10):
        for c in range(5, nx-5, 10):
            w, h = ((2, 2), (3, 2), (2, 3), (3, 3))[(r//10+c//10)%4]
            r0, r1, c0, c1 = r-h//2, r-h//2+h, c-w//2, c-w//2+w
            if forbidden[r0:r1, c0:c1].any():
                continue
            building[r0:r1, c0:c1] = True
            blocks.append(dict(building_id=f'B{len(blocks)+1:04d}', row_min=r0, row_max=r1-1,
                               col_min=c0, col_max=c1-1, width_m=w*CELL, depth_m=h*CELL,
                               raise_m=15, n_cells=w*h, assumption='synthetic obstacle block; not individual-building validation'))
    flow = valid & ~building
    nodes = {r[0]: dict(kind='JUNCTION', invert=float(r[1]), max_depth=float(r[2]),
                         surface=float(r[1])+float(r[2])) for r in data['JUNCTIONS']}
    nodes.update({r[0]: dict(kind='OUTFALL', invert=float(r[1]), max_depth=None, surface=None)
                  for r in data['OUTFALLS']})
    controls = np.array([(*coords[name], d['surface']) for name, d in nodes.items() if d['surface'] is not None])
    ground = np.zeros((ny, nx), dtype=np.float64)
    idx = np.flatnonzero(valid)
    for start in range(0, len(idx), 4096):
        ids = idx[start:start+4096]
        q = queries[ids]
        dist2 = ((q[:, None, :]-controls[None, :, :2])**2).sum(axis=2)
        nearest = np.argpartition(dist2, 7, axis=1)[:, :8]
        weights = 1/np.maximum(np.take_along_axis(dist2, nearest, axis=1), .25)
        ground.ravel()[ids] = (weights*controls[nearest, 2]).sum(axis=1)/weights.sum(axis=1)
    terrain = ground.astype(np.float32)
    fr, fc = np.where(flow)
    flow_points = np.column_stack([xx[flow], yy[flow]])
    positions, anchors = {}, defaultdict(list)
    for name, d in nodes.items():
        distances = np.linalg.norm(flow_points-coords[name], axis=1)
        i = int(np.argmin(distances))
        positions[name] = (int(fr[i]), int(fc[i]), float(distances[i]))
        if d['surface'] is not None:
            anchors[positions[name][:2]].append(d['surface'])
    anchor = np.zeros_like(valid)
    for (r, c), values in anchors.items():
        terrain[r, c] = np.median(values)
        anchor[r, c] = True
    lowered = road & ~anchor
    elevation = terrain.copy()
    elevation[lowered] -= .1
    elevation[building] += 15
    ids = np.full(valid.shape, -1, np.int32)
    ids[valid] = np.arange(valid.sum())
    smids = np.where(valid, ids+1, 0).astype(np.int32)
    resistance = np.where(flow, .62, 0).astype(np.float32)
    resistance[road] = .9
    arrays = dict(terrain=terrain, elevation=elevation, valid_mask=valid, domain_mask=valid,
                  catchment_mask=catchment, flow_mask=flow, road_mask=road, building_mask=building,
                  node_anchor_mask=anchor, road_lowering_mask=lowered,
                  cell_id_grid=ids, smid_grid=smids, resistance=resistance)
    static = PROJECT/'static'
    for name, array in arrays.items():
        np.save(static/(name+'.npy'), array)
    mapping = []
    for i, (name, d) in enumerate(nodes.items(), 1):
        r, c, distance = positions[name]
        error = float(elevation[r, c]-d['surface']) if d['surface'] is not None else None
        mapping.append(dict(node_smid=i, node_id=name, node_type=d['kind'],
                            node_x=float(coords[name][0]), node_y=float(coords[name][1]),
                            invert_elevation_m=d['invert'], max_depth_m=d['max_depth'],
                            surface_elevation_m=d['surface'], cell_id=int(ids[r, c]), smid=int(smids[r, c]),
                            cell_row=r, cell_col=c, cell_x=float(xx[r, c]), cell_y=float(yy[r, c]),
                            cell_elevation=float(elevation[r, c]), distance_m=distance, weight=1.,
                            rim_cell_difference_m=error,
                            surface_anchor_status='no_surface_rim_for_outfall' if error is None else
                            ('shared_cell_rim_conflict' if abs(error)>.02 else 'model_rim_anchored')))
    mapping = pd.DataFrame(mapping)
    for directory in (static, PROJECT/'mapping'):
        mapping.to_csv(directory/'node_to_cell_mapping.csv', index=False)
    pd.DataFrame(blocks).to_csv(static/'synthetic_buildings.csv', index=False)
    pd.DataFrame(streets).to_csv(static/'synthetic_streets.csv', index=False)
    vr, vc = np.where(valid)
    pd.DataFrame(dict(cell_id=ids[valid], smid=smids[valid], row=vr, col=vc, x=xx[valid], y=yy[valid],
                      area_m2=CELL**2, elevation=elevation[valid], terrain=terrain[valid],
                      is_road=road[valid], is_building=building[valid], is_flow=flow[valid], is_valid=True)).to_csv(static/'cells.csv', index=False)
    polygon_records = [dict(subcatchment_id=name, vertices_m=json.dumps(p.tolist()),
                            polygon_area_ha=polygon_area(p)/10000) for name, p in polygons.items()]
    pd.DataFrame(polygon_records).to_csv(PROJECT/'mapping/source_subcatchment_polygons.csv', index=False)
    config = dict(cell_size=CELL, grid_shape=[int(ny), int(nx)], bounds=[0, 0, float(nx*CELL), float(ny*CELL)],
                  crs=None, spatial_units='metre', coordinate_transform=transform,
                  source_inp='swmm/scenarios/baseline/model.inp', source_elevation_units='metre (LPS SWMM)',
                  n_nodes=len(mapping), n_mapped_nodes=len(mapping), n_valid_cells=int(valid.sum()),
                  n_flow_cells=int(flow.sum()), n_building_cells=int(building.sum()), n_road_cells=int(road.sum()),
                  n_buildings=len(blocks), n_streets=len(streets), domain_area_ha=float(valid.sum()*CELL**2/10000),
                  rainfall_catchment_area_ha=sum(float(r[3]) for r in data['SUBCATCHMENTS']),
                  node_mapping_distance_max=float(mapping.distance_m.max()),
                  shared_cell_rim_conflicts=int((mapping.surface_anchor_status=='shared_cell_rim_conflict').sum()),
                  domain_method='union of original subcatchment polygon cell centres, hypothetical corridors and node neighborhoods; 40 m square-grid dilation',
                  terrain_method='8-nearest IDW from 105 model junction rims; mapped junction cells anchored; not surveyed DEM',
                  road_method='hypothetical 20 m corridors along pipe endpoints, lowered by 0.10 m except rim anchors',
                  building_method='deterministic 40-60 m synthetic obstacle blocks raised by 15 m and excluded from flow',
                  assumption_status='regional technical-validation surface; not a real-city flood prediction',
                  resolution_scope='20 m grid cannot validate narrow street/individual-building inundation; no resolution-convergence test yet',
                  surface_boundary='closed invalid-domain perimeter, with inactive outermost raster ring',
                  coupling='one-way node overflow injection only; no surface-to-sewer exchange, no direct surface rainfall',
                  infiltration_evaporation_on_surface=False, building_raise_m=15, road_lowering_m=.1,
                  land_conveyance_coefficient=.62, road_conveyance_coefficient=.9)
    save_json(static/'config.json', config)
    fig, axes = plt.subplots(1, 2, figsize=(12, 9), layout='constrained')
    display_extent = (0, nx*CELL, 0, ny*CELL)
    im = axes[0].imshow(np.ma.masked_where(~valid, terrain), extent=display_extent, origin='upper', cmap='terrain')
    fig.colorbar(im, ax=axes[0], shrink=.6, label='Constructed ground elevation (m)')
    for ax in axes:
        ax.imshow(np.ma.masked_where(~road, road), extent=display_extent, origin='upper', cmap=ListedColormap(['#d5ab64']))
        ax.imshow(np.ma.masked_where(~building, building), extent=display_extent, origin='upper', cmap=ListedColormap(['#555b68']))
        ax.scatter(mapping.node_x, mapping.node_y, s=5, color='#2365a5')
        ax.set(xlabel='Local X (m)', ylabel='Local Y (m)', aspect='equal')
    axes[0].set_title('Model-rim-informed constructed terrain')
    axes[1].set_title('20 m grid / hypothetical corridors and obstacle blocks')
    fig.suptitle('Shunqing: constructed SWMM-CA2D technical-validation surface, not a surveyed flood map', fontsize=10)
    fig.savefig(static/'ca2d_layout_preview.png', dpi=150)
    plt.close(fig)
    return config


def prepare_events(source):
    inventory = []
    for shape in ('single', 'double', 'triple'):
        for total in (20, 40, 60, 80, 120, 160):
            reference_total = total if total >= 80 else 80
            name = f'chicago_like_{shape}_4h_{total}mm_5min.txt'
            src = ROOT/'models/urban_drainage/events'/f'chicago_like_{shape}_4h_{reference_total}mm_5min.txt'
            frame = pd.read_csv(src)
            times = pd.to_datetime(frame.timestamp)
            frame.timestamp = [(EPOCH+(t-times.iloc[0]).to_pytimedelta()).strftime('%Y-%m-%d %H:%M:%S') for t in times]
            if total < 80:
                units = np.rint(frame.value.to_numpy(float)*total/80*1000).astype(int)
                units[int(units.argmax())] += total*12000-int(units.sum())
                frame.value = units/1000
            assert len(frame)==49 and float(frame.value.iloc[-1])==0
            assert np.isclose(float(frame.value.sum())/12, total, atol=1e-9)
            target = PROJECT/'events'/name
            frame.to_csv(target, index=False, float_format='%.3f')
            inventory.append(dict(event_file='events/'+name, event_sha256=digest(target),
                                  source_file=str(src.relative_to(ROOT)).replace('\\', '/'), source_sha256=digest(src),
                                  total_rain_mm=float(frame.value.sum()/12), peak_mm_h=float(frame.value.max()),
                                  start=str(frame.timestamp.iloc[0]), rain_end=str(frame.timestamp.iloc[-1]),
                                  simulation_end=(datetime.fromisoformat(str(frame.timestamp.iloc[-1])) +
                                                  timedelta(hours=timing_policy()['post_rainfall_hours'])).isoformat(sep=' '),
                                  rain_gage_name='RainGage',
                                  purpose='screening_candidate' if total < 80 else 'shared_cross_model_candidate',
                                  formal_matrix_frozen=False, date_change_only=total>=80, status='PREPARED_NOT_SIMULATED'))
    rows = [r for r in source['TIMESERIES'] if r[0]=='bpswmm_2413']
    frame = pd.DataFrame([dict(timestamp=datetime.strptime(r[1]+' '+r[2], '%m/%d/%Y %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S'), value=float(r[3])) for r in rows])
    target = PROJECT/'events/source_20200715_hourly.txt'
    frame.to_csv(target, index=False, float_format='%.3f')
    inventory.append(dict(event_file='events/'+target.name, event_sha256=digest(target),
                          source_file='shunqing.inp [TIMESERIES] bpswmm_2413', total_rain_mm=float(frame.value.iloc[:-1].sum()),
                          peak_mm_h=float(frame.value.max()), start=frame.timestamp.iloc[0], rain_end=frame.timestamp.iloc[-1],
                          simulation_end=(datetime.fromisoformat(str(frame.timestamp.iloc[-1])) +
                                          timedelta(hours=timing_policy()['post_rainfall_hours'])).isoformat(sep=' '),
                          interval_minutes=60, rain_gage_name='RainGage', purpose='original_input_rainfall',
                          origin_status='source INP series, observational provenance unverified',
                          formal_matrix_frozen=False, status='PREPARED_NOT_SIMULATED'))
    save_json(PROJECT/'events/manifest.json', inventory)
    return inventory


def main():
    for path in ('model.yaml', 'preparation_manifest.json', 'static/config.json', 'swmm/scenarios/baseline/model.inp', 'events/manifest.json'):
        if (PROJECT/path).exists():
            raise FileExistsError('Already prepared or partial build exists; refusing overwrite: '+path)
    source_hash = digest(SOURCE)
    source = read_sections(SOURCE)
    assert dict(source['OPTIONS'])['FLOW_UNITS']=='LPS'
    assert dict(source['OPTIONS'])['FLOW_ROUTING']=='DYNWAVE'
    assert all(r[2]=='FREE' for r in source['OUTFALLS'])
    assert all(r[1]=='CIRCULAR' for r in source['XSECTIONS'])
    for directory in ('raw', 'static', 'swmm/scenarios/baseline', 'mapping', 'events', 'runs', 'validation'):
        (PROJECT/directory).mkdir(parents=True, exist_ok=True)
    snapshot = PROJECT/'raw/shunqing_original.inp'
    if snapshot.exists():
        raise FileExistsError('Immutable snapshot already exists')
    snapshot.write_bytes(SOURCE.read_bytes())
    data, transform = localize(source)
    # Preserve original comments and all untouched section text.
    text = SOURCE.read_text(encoding='utf-8-sig')
    lines, current, output, emitted = text.splitlines(), None, [], set()
    replaced = {'COORDINATES', 'POLYGONS', 'SYMBOLS', 'MAP'}
    for line in lines:
        stripped = line.split(';', 1)[0].strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            current = stripped.strip('[]').upper()
            output.append(line)
            if current in replaced:
                output.extend(' '.join(row) for row in data[current])
                emitted.add(current)
            continue
        if current in replaced:
            continue
        if current=='OPTIONS' and stripped.split()[:1]==['REPORT_STEP']:
            output.append('REPORT_STEP          00:01:00')
        else:
            output.append(line)
    (PROJECT/'swmm/scenarios/baseline/model.inp').write_text('; Prepared Shunqing baseline: translated display coordinates; 1-minute reports; hydraulic parameters unchanged.\n'+'\n'.join(output)+'\n', encoding='utf-8')
    audit = source_audit(source)
    audit.to_csv(PROJECT/'mapping/coordinate_and_slope_audit.csv', index=False)
    config = build_surface(data, transform)
    inventory = prepare_events(source)
    save_json(PROJECT/'simulation_timing.json', timing_policy())
    yaml = '''name: Sichuan_Shunqing
type: swmm_2d
description: Shunqing LPS dynamic-wave network with a constructed regional CA2D surface.
case_class: user_supplied_network_with_constructed_surface
source_provenance: user_local_INP; source author/title marker DSDAConvertToSwmmTools EcoVista
license_status: unverified; confirm before redistributing source data
paths:
  raw: raw
  static: static
  swmm: swmm
  mapping: mapping
  events: events
  runs: runs
default_scenario: baseline
scenarios:
  baseline:
    swmm_inp: swmm/scenarios/baseline/model.inp
    boundary: original_eight_free_outfalls
rain_gage_name: RainGage
ca2d:
  static_model: static
  node_to_cell_mapping: static/node_to_cell_mapping.csv
  source_config: static/config.json
  default_dt_seconds: 10.0
  default_boundary_interval_minutes: 5.0
  default_save_interval_minutes: 5.0
notes:
  - Original LPS hydraulic and hydrologic parameters are unchanged; display coordinates translated only.
  - Source CRS is unspecified; coordinate metric scale is supported by pipe lengths, not an EPSG claim.
  - Twenty-metre surface is constructed, not surveyed DEM; corridors and obstacle blocks are hypothetical.
  - Candidate event library is not a frozen formal evaluation matrix.
  - No coupled rainfall run, LLM diagnosis or report is performed during preparation.
'''
    (PROJECT/'model.yaml').write_text(yaml, encoding='utf-8')
    save_json(PROJECT/'preparation_manifest.json', dict(prepared_on='2026-10-13', source_file='shunqing.inp',
              source_sha256=source_hash, original_snapshot_sha256=digest(snapshot), source_license='UNVERIFIED',
              source_counts={k:len(v) for k,v in source.items()}, source_area_ha=config['rainfall_catchment_area_ha'],
              coordinate_transform=transform, surface=config, candidate_event_count=len(inventory),
              formal_matrix_frozen=False, formal_runs_executed=False, source_hydraulic_parameters_changed=False,
              source_changes=['REPORT_STEP 30 min -> 1 min', 'display coordinates, polygons, symbols translated; MAP relabelled metres on explicit scale inference'],
              adverse_slope_links=audit[audit.adverse_slope][['link_id','invert_slope']].to_dict('records'),
              boundaries='original eight FREE outfalls preserved; no imposed tide or river stage',
              warnings=['No surveyed DEM, road or building data provided', 'No grid-convergence, rainfall-runoff calibration or physical flood validation',
                        'Original four adverse slopes retained; no automatic correction', 'No pump/gate/storage mechanism assessment possible from absent source facilities',
                        'Regional grid and closed, one-way surface do not resolve real-city recession or individual-building flooding']))
    assert digest(SOURCE)==source_hash
    print(json.dumps(dict(status='PREPARED_NOT_SIMULATED', nodes=config['n_nodes'], pipes=131,
                         grid_shape=config['grid_shape'], valid_cells=config['n_valid_cells'],
                         candidates=len(inventory), rim_conflicts=config['shared_cell_rim_conflicts']), ensure_ascii=False), flush=True)


if __name__=='__main__':
    main()
