"""Prepare beta inputs and a disclosed synthetic CA2D surface, without simulations.

Never modify beta.inp. Unit conversion is explicitly scoped to its actual
sections; unexpected sections, shapes or curve types fail closed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFilter

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
SOURCE = PROJECT / 'beta.inp'
FT = .3048
FT2 = FT ** 2
FT3 = FT ** 3
CFS_LPS = FT3 * 1000
ACRE_HA = .40468564224
INCH_MM = 25.4
CELL = 5.0
EPOCH = datetime(2016, 10, 8)
SCENARIOS = ('baseline', 'free_outfall', 'tide_base00')
EVENTS = tuple(f'chicago_like_{shape}_4h_{depth}mm_5min.txt'
               for shape in ('single', 'double', 'triple') for depth in (80, 120, 160))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sections(path):
    result, name = {}, ''
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        line = line.split(';', 1)[0].strip()
        if not line:
            continue
        if line.startswith('['):
            name = line.strip('[]').upper()
            result.setdefault(name, [])
        else:
            result[name].append(line.split())
    return result


def number(value):
    return f'{value:.12g}'


def multiply(row, factors):
    for index, factor in factors.items():
        if index < len(row):
            row[index] = number(float(row[index]) * factor)


def coordinate_transform(source):
    """One isotropic, length-informed synthetic scale, not GIS reconstruction."""
    coords = {r[0]: np.array(r[1:3], float) for r in source['COORDINATES']}
    ratios = []
    records = []
    for row in source['CONDUITS']:
        distance = float(np.linalg.norm(coords[row[1]] - coords[row[2]]))
        length = float(row[3]) * FT
        ratio = length / distance if distance > 1e-9 else None
        if ratio is not None:
            ratios.append(ratio)
        records.append({'link_id': row[0], 'source_xy_distance': distance,
                        'hydraulic_length_m': length, 'm_per_source_unit': ratio})
    scale = float(np.median(ratios))
    origin = np.vstack(list(coords.values())).min(axis=0)
    local = {key: (value - origin) * scale + 60 for key, value in coords.items()}
    audit = pd.DataFrame(records)
    audit['synthetic_xy_distance_m'] = audit.source_xy_distance * scale
    audit['synthetic_distance_to_hydraulic_length_ratio'] = audit.synthetic_xy_distance_m / audit.hydraulic_length_m
    return local, audit, {'method': 'median hydraulic conduit length / nonzero anonymous endpoint distance',
                         'metres_per_anonymous_unit': scale, 'source_origin': origin.tolist(),
                         'target_translation_m': [60, 60],
                         'nonzero_distance_conduits': len(ratios),
                         'scale_quantiles_m_per_unit': np.quantile(ratios, [0, .1, .5, .9, 1]).tolist(),
                         'status': 'synthetic scale assumption; no recovered CRS, roads or surveyed geometry'}


def convert_to_si(source, coords):
    result = copy.deepcopy(source)
    supported = {'TITLE', 'OPTIONS', 'EVAPORATION', 'RAINGAGES', 'SUBCATCHMENTS',
                 'SUBAREAS', 'INFILTRATION', 'JUNCTIONS', 'OUTFALLS', 'STORAGE',
                 'CONDUITS', 'PUMPS', 'ORIFICES', 'WEIRS', 'XSECTIONS', 'CONTROLS',
                 'CURVES', 'TIMESERIES', 'REPORT', 'TAGS', 'MAP', 'COORDINATES',
                 'VERTICES', 'POLYGONS', 'SYMBOLS'}
    if set(result) - supported or result['CONTROLS']:
        raise ValueError('Unexpected section or controls: audit conversion first')
    if any(result.get(k) for k in ('VERTICES', 'POLYGONS', 'SYMBOLS')):
        raise ValueError('Unexpected spatial records: audit transformation first')
    options = dict(result['OPTIONS'])
    if options['FLOW_UNITS'] != 'CFS' or options['INFILTRATION'] != 'HORTON' or options['LINK_OFFSETS'] != 'DEPTH':
        raise ValueError('Unexpected source units/infiltration/offsets')
    for row in result['OPTIONS']:
        if row[0] == 'FLOW_UNITS': row[1] = 'LPS'
        if row[0] == 'REPORT_STEP': row[1] = '00:01:00'
        if row[0] == 'MIN_SURFAREA': multiply(row, {1: FT2})
        if row[0] == 'HEAD_TOLERANCE': multiply(row, {1: FT})
    for row in result['EVAPORATION']:
        if row[0] == 'CONSTANT': multiply(row, {1: INCH_MM})
    rules = {
        'SUBCATCHMENTS': {3: ACRE_HA, 5: FT, 7: FT},
        'SUBAREAS': {3: INCH_MM, 4: INCH_MM},
        'INFILTRATION': {1: INCH_MM, 2: INCH_MM, 5: INCH_MM},
        'JUNCTIONS': {1: FT, 2: FT, 3: FT, 4: FT, 5: FT2},
        'CONDUITS': {3: FT, 5: FT, 6: FT, 7: CFS_LPS, 8: CFS_LPS},
        'PUMPS': {5: FT, 6: FT},
        'ORIFICES': {4: FT},
    }
    for name, rule in rules.items():
        for row in result.get(name, []): multiply(row, rule)
    for row in result['OUTFALLS']:
        if row[2] != 'TIMESERIES': raise ValueError('Unexpected outfall type')
        multiply(row, {1: FT})
    for row in result['STORAGE']:
        if row[4] != 'FUNCTIONAL': raise ValueError('Unexpected storage law')
        exponent = float(row[6])
        multiply(row, {1: FT, 2: FT, 3: FT, 5: FT2 / FT ** exponent, 7: FT2})
        if len(row) > 10: raise ValueError('Audit optional storage infiltration fields')
    for row in result['WEIRS']:
        if row[3] != 'TRANSVERSE': raise ValueError('Unexpected weir type')
        multiply(row, {4: FT, 5: math.sqrt(FT), 8: math.sqrt(FT)})
    for row in result['XSECTIONS']:
        if row[1] == 'CIRCULAR': multiply(row, {2: FT})
        elif row[1] in ('HORIZ_ELLIPSE', 'RECT_OPEN', 'RECT_CLOSED'):
            multiply(row, {2: FT, 3: FT})
            if row[1] == 'HORIZ_ELLIPSE' and float(row[4]) != 0:
                raise ValueError('Standard ellipse size code needs dedicated conversion')
        else: raise ValueError(f'Unexpected shape: {row[1]}')
    curve_type = None
    for row in result['CURVES']:
        if len(row) == 4:
            curve_type = row[1].upper()
            if curve_type != 'PUMP1': raise ValueError('Unexpected pump curve type')
            multiply(row, {2: FT3, 3: CFS_LPS})
        else:
            if curve_type != 'PUMP1': raise ValueError('Unspecified curve type')
            multiply(row, {1: FT3, 2: CFS_LPS})
    rain_names = {r[-1] for r in source['RAINGAGES']}
    tide_names = {r[0] for r in source['TIMESERIES'] if r[0].startswith('base_')}
    # Also convert the two unused design-rain series, not only the active one.
    rain_names |= {r[0] for r in source['TIMESERIES'] if r[0].endswith('yr12hr')}
    for row in result['TIMESERIES']:
        if row[0] in rain_names: multiply(row, {len(row)-1: INCH_MM})
        elif row[0] in tide_names: multiply(row, {len(row)-1: FT})
        else: raise ValueError(f'Unclassified series {row[0]}')
    # Explicitly hold the final hourly stage to midnight: no invented cyclic tide.
    for name in sorted(tide_names):
        last = [r for r in result['TIMESERIES'] if r[0] == name][-1]
        result['TIMESERIES'].append([name, '10/09/2016', '0:00', last[-1]])
    result['COORDINATES'] = [[name, number(x), number(y)] for name, (x, y) in coords.items()]
    points = np.vstack(list(coords.values()))
    result['MAP'] = [['DIMENSIONS', '0', '0', number(points[:, 0].max()+60), number(points[:, 1].max()+60)], ['Units', 'Meters']]
    return result


def write_inp(path, data, comment):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = '; Derived beta input. Original beta.inp is preserved.\n; ' + comment + '\n'
    text += '\n'.join('[' + name + ']\n' + '\n'.join(' '.join(r) for r in rows) + '\n' for name, rows in data.items())
    path.write_text(text, encoding='utf-8')


def distance_segment(xx, yy, a, b):
    dx, dy = b-a
    den = dx*dx + dy*dy
    t = np.clip(((xx-a[0])*dx+(yy-a[1])*dy)/den, 0, 1) if den else 0
    return np.hypot(xx-a[0]-t*dx, yy-a[1]-t*dy)


def convex_hull(points):
    ordered = sorted(set(map(tuple, points)))
    def cross(o,a,b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    def half(seq):
        result=[]
        for p in seq:
            while len(result)>=2 and cross(result[-2],result[-1],p)<=0: result.pop()
            result.append(p)
        return result
    return half(ordered)[:-1]+half(ordered[::-1])[:-1]


def dilate(mask,size):
    return np.array(Image.fromarray(mask.astype(np.uint8)).filter(ImageFilter.MaxFilter(size)),dtype=bool)


def build_surface(si, coords, transform):
    points = np.vstack(list(coords.values()))
    nx, ny = (np.ceil((points.max(axis=0)+60)/CELL)).astype(int)
    xx, yy = np.meshgrid((np.arange(nx)+.5)*CELL, (ny-np.arange(ny)-.5)*CELL)
    # Convex hull plus 30 m margin is a disclosed synthetic surface domain.
    hull = convex_hull(points)
    image = Image.new('L',(int(nx),int(ny)),0)
    ImageDraw.Draw(image).polygon([(round(x/CELL-.5),round(ny-y/CELL-.5)) for x,y in hull],fill=1)
    valid = dilate(np.array(image),13)
    valid[[0,-1],:] = False; valid[:,[0,-1]] = False
    road = np.zeros_like(valid)
    streets = []
    for section in ('CONDUITS', 'PUMPS', 'ORIFICES', 'WEIRS'):
        for r in si[section]:
            a, b = coords[r[1]], coords[r[2]]
            road |= distance_segment(xx, yy, a, b) <= 5
            streets.append({'street_id': 'synthetic_'+r[0], 'width_m': 10,
                            'vertices_m': json.dumps([a.tolist(), b.tolist()]),
                            'assumption': 'hypothetical corridor along anonymous network layout; not surveyed road'})
    road &= valid
    forbidden = dilate(road,3) | ~valid
    for x,y in points: forbidden |= np.hypot(xx-x, yy-y) <= 8
    building = np.zeros_like(valid)
    buildings = []
    for r in range(5, ny-5, 10):
        for c in range(5, nx-5, 10):
            w,h = ((3,3),(4,3),(5,4),(3,4))[(r+c)%4]
            r0,r1,c0,c1 = r-h//2,r-h//2+h,c-w//2,c-w//2+w
            if forbidden[r0:r1,c0:c1].any() or building[r0:r1,c0:c1].any(): continue
            building[r0:r1,c0:c1] = True
            buildings.append({'building_id': f'B{len(buildings)+1:04d}',
                              'row_min': r0, 'row_max': r1-1, 'col_min': c0, 'col_max': c1-1,
                              'width_m': w*CELL, 'depth_m': h*CELL, 'raise_m': 15,
                              'n_cells': w*h, 'assumption': 'deterministic synthetic footprint; no original-city identity'})
    flow = valid & ~building
    nodes = {}
    for sec,kind in [('JUNCTIONS','JUNCTION'),('STORAGE','STORAGE'),('OUTFALLS','OUTFALL')]:
        for r in si[sec]:
            nodes[r[0]] = {'kind': kind, 'invert': float(r[1]),
                          'max_depth': float(r[2]) if kind != 'OUTFALL' else None,
                          'surface': float(r[1])+float(r[2]) if kind != 'OUTFALL' else None}
    controls = np.array([(*coords[n], d['surface']) for n,d in nodes.items() if d['surface'] is not None])
    queries = np.column_stack([xx.ravel(),yy.ravel()])
    ground = np.empty(len(queries),float)
    for start in range(0,len(queries),4096):
        q=queries[start:start+4096]
        d2=((q[:,None,:]-controls[None,:,:2])**2).sum(axis=2)
        index=np.argpartition(d2,7,axis=1)[:,:8]
        weights=1/np.maximum(np.take_along_axis(d2,index,axis=1),.25)
        ground[start:start+len(q)]=(weights*controls[index,2]).sum(axis=1)/weights.sum(axis=1)
    terrain = ground.reshape((ny,nx)).astype(np.float32)
    fr,fc = np.where(flow)
    flow_points = np.column_stack([xx[flow], yy[flow]])
    anchor_values = defaultdict(list)
    positions = {}
    for name,d in nodes.items():
        distances=np.linalg.norm(flow_points-coords[name],axis=1)
        i=int(np.argmin(distances)); dist=distances[i]; r,c = int(fr[i]),int(fc[i])
        positions[name] = (r,c,float(dist))
        if d['surface'] is not None: anchor_values[(r,c)].append(d['surface'])
    anchor = np.zeros_like(valid)
    for (r,c),z in anchor_values.items():
        terrain[r,c] = np.median(z); anchor[r,c] = True
    lowering_mask = road & ~anchor
    elevation = terrain.copy()
    elevation[lowering_mask] -= .1
    elevation[building] += 15
    elevation[~valid] = 0; terrain[~valid] = 0
    ids = np.full(valid.shape,-1,np.int32); ids[valid] = np.arange(valid.sum())
    smids = np.where(valid,ids+1,0).astype(np.int32)
    resistance = np.where(flow,.62,0).astype(np.float32); resistance[road] = .9
    arrays = dict(terrain=terrain,elevation=elevation,valid_mask=valid,domain_mask=valid,
                  flow_mask=flow,building_mask=building,road_mask=road,node_anchor_mask=anchor,
                  road_lowering_mask=lowering_mask,cell_id_grid=ids,smid_grid=smids,resistance=resistance)
    records = []
    for i,(name,d) in enumerate(nodes.items(),1):
        r,c,dist = positions[name]
        error = float(elevation[r,c]-d['surface']) if d['surface'] is not None else None
        records.append(dict(node_smid=i,node_id=name,node_type=d['kind'],node_x=float(coords[name][0]),
                            node_y=float(coords[name][1]),invert_elevation_m=d['invert'],
                            max_depth_m=d['max_depth'],surface_elevation_m=d['surface'],
                            cell_id=int(ids[r,c]),smid=int(smids[r,c]),cell_row=r,cell_col=c,
                            cell_x=float(xx[r,c]),cell_y=float(yy[r,c]),cell_elevation=float(elevation[r,c]),
                            distance_m=dist,weight=1.,rim_cell_difference_m=error,
                            surface_anchor_status='not a surveyed surface level' if error is None else
                            ('shared_cell_rim_conflict' if abs(error)>.02 else 'model_rim_anchored')))
    mapping = pd.DataFrame(records)
    static = PROJECT/'static'; static.mkdir(exist_ok=True)
    for name,a in arrays.items(): np.save(static/f'{name}.npy',a)
    for directory in (static,PROJECT/'mapping'):
        directory.mkdir(exist_ok=True); mapping.to_csv(directory/'node_to_cell_mapping.csv',index=False)
    pd.DataFrame(buildings).to_csv(static/'synthetic_buildings.csv',index=False)
    pd.DataFrame(streets).to_csv(static/'synthetic_streets.csv',index=False)
    vr,vc = np.where(valid)
    pd.DataFrame(dict(cell_id=ids[valid],smid=smids[valid],row=vr,col=vc,x=xx[valid],y=yy[valid],
                      area_m2=CELL**2,elevation=elevation[valid],terrain=terrain[valid],
                      is_road=road[valid],is_building=building[valid],is_flow=flow[valid],is_valid=True)).to_csv(static/'cells.csv',index=False)
    config = dict(cell_size=CELL,grid_shape=[int(ny),int(nx)],bounds=[0,0,int(nx)*CELL,int(ny)*CELL],crs=None,
                  spatial_units='metre',source_map_units='anonymous display units',
                  source_elevation_units='feet, converted to metre',coordinate_transform=transform,
                  source_inp='swmm/scenarios/baseline/model.inp',
                  n_nodes=len(mapping),n_mapped_nodes=len(mapping),n_valid_cells=int(valid.sum()),
                  n_flow_cells=int(flow.sum()),n_building_cells=int(building.sum()),
                  n_road_cells=int(road.sum()),n_buildings=len(buildings),n_streets=len(streets),
                  node_mapping_distance_max=float(mapping.distance_m.max()),
                  shared_cell_rim_conflicts=int((mapping.surface_anchor_status=='shared_cell_rim_conflict').sum()),
                  domain_method='convex hull of scaled anonymous coordinates with 30 m margin; synthetic, not a watershed boundary',
                  terrain_method='8-nearest IDW of model junction rims and storage tops; mapped cells anchored to median rim',
                  road_method='hypothetical 10 m corridors along network layout, lowered by 0.10 m except rim anchors',
                  building_method='deterministic synthetic footprints raised by 15 m and excluded from flow',
                  assumption_status='technical-validation surface; not original-city DEM/roads/buildings',
                  domain_area_ha=float(valid.sum()*CELL**2/10000),
                  rainfall_catchment_area_ha=sum(float(r[3]) for r in si['SUBCATCHMENTS']),
                  building_raise_m=15,road_lowering_m=.1,building_node_clearance_m=8,
                  land_conveyance_coefficient=.62,road_conveyance_coefficient=.9,
                  coupling='one-way SWMM node overflow to surface; no rainfall or tidal water injected directly into CA2D',
                  surface_boundary='closed invalid-domain perimeter; solver outermost raster ring inactive')
    (static/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    fig,axes = plt.subplots(1,2,figsize=(14,7),layout='constrained')
    extent = (0,nx*CELL,0,ny*CELL)
    im=axes[0].imshow(np.ma.masked_where(~valid,terrain),origin='upper',extent=extent,cmap='terrain')
    fig.colorbar(im,ax=axes[0],shrink=.7,label='Synthetic ground elevation (m)')
    for ax in axes:
        ax.imshow(np.ma.masked_where(~road,road),origin='upper',extent=extent,cmap=ListedColormap(['#d5ab64']),alpha=.9)
        ax.imshow(np.ma.masked_where(~building,building),origin='upper',extent=extent,cmap=ListedColormap(['#555b68']))
        ax.scatter(mapping.node_x,mapping.node_y,s=7,color='#2365a5',zorder=5)
        ax.set(xlabel='Synthetic local X (m)',ylabel='Synthetic local Y (m)',aspect='equal')
    axes[0].set_title('Model-rim-informed synthetic terrain')
    axes[1].set_title(f'CA2D: 5 m cells / {len(mapping)} nodes / {len(buildings)} hypothetical buildings')
    fig.suptitle('Pystorms beta: constructed technical-validation surface, NOT a real-city flood map',fontsize=11)
    fig.savefig(static/'ca2d_layout_preview.png',dpi=160); plt.close(fig)
    return config


def main():
    if (PROJECT/'model.yaml').exists():
        raise FileExistsError('Already prepared: inspect or verify existing outputs; no automatic overwrite')
    original_hash = digest(SOURCE)
    source = sections(SOURCE)
    coords,audit,transform = coordinate_transform(source)
    si = convert_to_si(source,coords)
    for folder in ('raw','static','swmm','mapping','events','runs','validation','boundaries'):
        (PROJECT/folder).mkdir(exist_ok=True)
    # Immutable original snapshot; the root original remains unchanged too.
    (PROJECT/'raw/beta_original.inp').write_bytes(SOURCE.read_bytes())
    audit.to_csv(PROJECT/'mapping/coordinate_scale_audit.csv',index=False)
    for name in SCENARIOS:
        variant = copy.deepcopy(si)
        if name == 'free_outfall': variant['OUTFALLS'][0] = ['OUT0',variant['OUTFALLS'][0][1],'FREE','YES']
        if name == 'tide_base00': variant['OUTFALLS'][0][3] = 'base_00'
        write_inp(PROJECT/f'swmm/scenarios/{name}/model.inp',variant,f'scenario={name}; hydraulic settings preserved, report step=1 minute')
    for name in sorted({r[0] for r in si['TIMESERIES'] if r[0].startswith('base_')}):
        rows=[r for r in si['TIMESERIES'] if r[0]==name]
        pd.DataFrame([{'timestamp':datetime.strptime(r[1]+' '+r[2],'%m/%d/%Y %H:%M').isoformat(sep=' '),
                       'stage_m':float(r[-1])} for r in rows]).to_csv(PROJECT/f'boundaries/{name}.csv',index=False)
    inventory=[]
    for filename in EVENTS:
        src=ROOT/'models/urban_drainage/events'/filename
        df=pd.read_csv(src); times=pd.to_datetime(df.timestamp)
        df.timestamp=[(EPOCH+(t-times.iloc[0]).to_pytimedelta()).strftime('%Y-%m-%d %H:%M:%S') for t in times]
        target=PROJECT/'events'/filename; df.to_csv(target,index=False,float_format='%.3f')
        intensity=df.value.to_numpy(float)
        dt=pd.to_datetime(df.timestamp).diff().iloc[1:].dt.total_seconds().to_numpy()/3600
        if not np.allclose(dt,5/60) or intensity[-1]!=0: raise ValueError('Unexpected matrix event')
        inventory.append(dict(event_file='events/'+filename,source_file=str(src.relative_to(ROOT)).replace('\\','/'),
                              source_sha256=digest(src),event_sha256=digest(target),
                              total_rain_mm=float(np.dot(intensity[:-1],dt)),peak_mm_h=float(intensity.max()),
                              start=df.timestamp.iloc[0],rain_end=df.timestamp.iloc[-1],
                              simulation_end='2016-10-09 00:00:00',date_change_only=True,
                              status='prepared_not_simulated',rain_gage_name='RG1'))
    (PROJECT/'events/manifest.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf-8')
    timing=dict(swmm_save_interval_minutes=1.,boundary_interval_minutes=5.,ca2d_save_interval_minutes=5.,
                post_rainfall_hours=20.,boundary_method='interval_mean',rainfall_time_convention='interval_start',
                rationale='4 h matrix rain plus 20 h recovery gives 24 h boundary window; not proven sufficient for storage drainage')
    (PROJECT/'simulation_timing.json').write_text(json.dumps(timing,indent=2)+'\n',encoding='utf-8')
    config=build_surface(si,coords,transform)
    yaml='''name: pystorms_beta
type: swmm_2d
description: Pystorms beta with full CFS-to-LPS conversion and a disclosed constructed CA2D surface.
source_repository: https://github.com/kLabUM/pystorms
source_path: pystorms/networks/beta.inp
case_class: adapted_public_benchmark_with_synthetic_surface
license_status: source_project_GPL_3_0_review_before_redistribution
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
    boundary: original_base_30_stage_with_explicit_one_hour_endpoint_hold
  free_outfall:
    swmm_inp: swmm/scenarios/free_outfall/model.inp
    boundary: idealized_free_outfall_flap_gate_retained
  tide_base00:
    swmm_inp: swmm/scenarios/tide_base00/model.inp
    boundary: base_tide_without_added_sea_level_rise_NOT_without_tide
rain_gage_name: RG1
ca2d:
  static_model: static
  node_to_cell_mapping: static/node_to_cell_mapping.csv
  source_config: static/config.json
  default_dt_seconds: 10.0
  default_boundary_interval_minutes: 5.0
  default_save_interval_minutes: 5.0
notes:
  - Surface is synthetic; anonymous coordinates are length-informed scaled, not georeferenced.
  - Original 1-foot catchment widths, 100-percent slopes and pump settings are preserved in equivalent units.
  - Fullness-derived link evidence currently covers circular pipes only; other shapes need explicit limits.
  - No SWMM event, coupled storm or LLM diagnosis has been run by this preparation.
'''
    (PROJECT/'model.yaml').write_text(yaml,encoding='utf-8')
    manifest=dict(prepared_on='2026-10-12',source_file='beta.inp',source_sha256=original_hash,
                  original_snapshot_sha256=digest(PROJECT/'raw/beta_original.inp'),
                  formal_runs_executed=False,coordinate_transform=transform,
                  conversion_factors=dict(length_ft_to_m=FT,area_ft2_to_m2=FT2,volume_ft3_to_m3=FT3,
                                         flow_cfs_to_lps=CFS_LPS,catchment_acre_to_ha=ACRE_HA,rain_inch_to_mm=INCH_MM,
                                         transverse_weir_coefficient_factor=math.sqrt(FT)),
                  pump_curve_semantics='PUMP1: x inlet volume ft3->m3; y CFS->LPS, not a head curve',
                  original_rainfall_format='CUMULATIVE, 6 minutes; preserved in scenario sources',
                  matrix_rainfall_format='INTENSITY mm/h, 5-minute interval start; replaces RG1 at runtime',
                  tidal_endpoint='hold 23:00 stage until 24:00, explicitly added to every base series',
                  warnings=['No true DEM/road/building data or original coordinate reference system',
                            'Unusual source catchment width/slope retained; no rainfall-runoff calibration claim',
                            'Pump/depth controls and storage retained; M5/M6 not claimed as fully diagnosed',
                            'No spin-up added; initial depths remain zero as original; boundary transient needs examination',
                            '24 h window not verified as complete basin drainage; no future auto-extension of tide',
                            'Reference checks do not themselves establish diagnostic causal correctness'],
                  scenarios=list(SCENARIOS),prepared_matrix_events=len(inventory),surface=config)
    (PROJECT/'preparation_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert digest(SOURCE)==original_hash
    print(json.dumps({'status':'PREPARED_NOT_SIMULATED','scenarios':SCENARIOS,'events':len(inventory),
                      'grid_shape':config['grid_shape'],'valid_cells':config['n_valid_cells'],
                      'nodes':config['n_mapped_nodes'],'buildings':config['n_buildings'],
                      'rim_conflicts':config['shared_cell_rim_conflicts']},indent=2))


if __name__=='__main__':
    main()
