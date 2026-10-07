"""Build a reviewable report specimen from one saved run. Does not change agents."""
from pathlib import Path
import base64
import hashlib
import json
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
from matplotlib.patches import Patch

PROJECT = Path(__file__).resolve().parents[1]
RUN = PROJECT / 'models/urban_drainage/runs/chicago_like_single_4h_80mm_5min__baseline__20261003_150049'
STATIC = PROJECT / 'models/urban_drainage/static'
TASK = RUN / 'diagnosis_tasks/837a05e8c66a49e08d5fad9e37ea12a8'
OUT = RUN / 'report_preview_v1'
OUT.mkdir(exist_ok=True)
ASSETS = OUT / 'assets'
ASSETS.mkdir(exist_ok=True)
THRESHOLD = .01
SOURCES = [RUN/'summary.json', RUN/'rainfall_event.txt', RUN/'ca2d/surface_depth.tsv',
           RUN/'ca2d/ca2d_animation.gif', RUN/'swmm/nodes.tsv', STATIC/'cells.csv',
           STATIC/'config.json', STATIC/'node_to_cell_mapping.csv', TASK/'task.json',
           TASK/'diagnosis.json', TASK/'evidence_snapshot.json']
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
before = {str(p.relative_to(PROJECT)): sha(p) for p in SOURCES}
summary = json.loads((RUN/'summary.json').read_text(encoding='utf-8'))
task = json.loads((TASK/'task.json').read_text(encoding='utf-8'))
facts = sorted([e['facts'] for e in task['event_manifest']], key=lambda e: -e['estimated_volume_m3'])
rows = json.loads((TASK/'evidence_snapshot.json').read_text(encoding='utf-8'))
if isinstance(rows, dict):
    rows = rows['evidence_rows']
cells = pd.read_csv(STATIC/'cells.csv').sort_values('smid')
cfg = json.loads((STATIC/'config.json').read_text(encoding='utf-8'))
shape = tuple(cfg['grid_shape'])
mapping = pd.read_csv(STATIC/'node_to_cell_mapping.csv')
rain = pd.read_csv(RUN/'rainfall_event.txt')
rain['timestamp'] = pd.to_datetime(rain.timestamp)
dt_h = rain.timestamp.diff().shift(-1).dt.total_seconds().fillna(0).to_numpy()/3600
rain_amounts = rain.value.to_numpy()*dt_h
total_rain = float(rain_amounts.sum())
cumulative = np.r_[0, np.cumsum(rain_amounts[:-1])]
rain_peak_idx = rain.value.idxmax()
rain_peak = rain.loc[rain_peak_idx, 'timestamp']
minutes = (rain.timestamp-rain.timestamp.iloc[0]).dt.total_seconds().to_numpy()/60
max30_idx = int(np.argmax(np.convolve(rain_amounts[:-1], np.ones(6), mode='valid')))
max30 = float(rain_amounts.iloc[max30_idx:max30_idx+6].sum()) if isinstance(rain_amounts,pd.Series) else float(rain_amounts[max30_idx:max30_idx+6].sum())
surface = pd.read_csv(RUN/'ca2d/surface_depth.tsv', sep='\t')
surface['timestamp'] = pd.to_datetime(surface.Date+' '+surface.Time)
pivot = surface.pivot(index='timestamp', columns='Smid', values='Depth').reindex(columns=cells.smid)
assert not pivot.isna().any().any(), 'Missing surface samples'
times = pivot.index
depth = pivot.to_numpy().reshape((len(times), *shape))
flow = cells.is_flow.to_numpy().reshape(shape)
valid = cells.is_valid.to_numpy().reshape(shape)
road = (cells.is_road & cells.is_flow).to_numpy().reshape(shape)
building = (cells.is_building & cells.is_valid).to_numpy().reshape(shape)
green = flow & ~road
assert not (road & building).any()
wet = (depth >= THRESHOLD) & flow[None,:,:]
area_cell = cfg['cell_size']**2
area = wet.sum(axis=(1,2))*area_cell
road_area = (wet & road[None,:,:]).sum(axis=(1,2))*area_cell
green_area = (wet & green[None,:,:]).sum(axis=(1,2))*area_cell
maxdepth_series = np.where(flow[None,:,:],depth,0).max(axis=(1,2))
peak_area_i = int(area.argmax())
peak_depth_i = int(maxdepth_series.argmax())
first_i = int(np.flatnonzero(area>0)[0])
max_grid = depth.max(axis=0)
ever_wet = wet.any(axis=0)
duration = wet[:-1].sum(axis=0)*5
max_duration = float(duration.max())
neighbor = np.zeros(shape,dtype=bool)
padded = np.pad(building,1)
for dr in range(3):
    for dc in range(3):
        neighbor |= padded[dr:dr+shape[0],dc:dc+shape[1]]
neighbor &= flow
building_near_area = (wet & neighbor[None,:,:]).sum(axis=(1,2))*area_cell
nodes = pd.read_csv(RUN/'swmm/nodes.tsv',sep='\t')
nodes['timestamp'] = pd.to_datetime(nodes.date+' '+nodes.time)
raw_positive = set(nodes.loc[nodes.flooding_Ls>1e-9,'node_id'])
assert raw_positive == {e['node_id'] for e in facts}, 'Event coverage differs from raw node results'
raw_volume = float((nodes.sort_values(['node_id','timestamp']).assign(
    seconds=lambda d: (d.groupby('node_id').timestamp.shift(-1)-d.timestamp).dt.total_seconds().fillna(0)
).eval('flooding_Ls * seconds').sum())/1000)
total_volume = math.fsum(e['estimated_volume_m3'] for e in facts)
assert math.isclose(raw_volume,total_volume,rel_tol=1e-7,abs_tol=1e-6)
def process(node):
    return next(e for e in rows if e.get('metric_name')=='local_process_series' and e.get('object_id')==node)['value']['series']
p6series = process('P6')
p6peak = next(s for s in p6series if s['time']==facts[0]['peak_time'])
p6in = p6peak['nodes']['P6']['total_inflow_Ls']
p6out = p6peak['links']['G6']['signed_model_flow_Ls']
p6flood = p6peak['nodes']['P6']['flooding_Ls']
assert abs(p6in-p6out-p6flood)<.05
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,
    'font.size':11,'axes.spines.top':False,'axes.spines.right':False,
    'axes.edgecolor':'#ced9d7','axes.labelcolor':'#485f59','xtick.color':'#60756f',
    'ytick.color':'#60756f','figure.facecolor':'white','axes.facecolor':'white',
    'savefig.facecolor':'white'})
TEAL='#087b72'
ORANGE='#d78034'
def save(fig,name):
    fig.savefig(ASSETS/name,dpi=160,bbox_inches='tight')
    plt.close(fig)
def format_time(t):
    return pd.Timestamp(t).strftime('%H:%M')
def nice_axis(ax):
    ax.grid(axis='y',color='#e7eeeb',linewidth=.8)
    ax.set_axisbelow(True)

# Rainfall: interval-average intensities and accumulated rainfall share elapsed time.
fig,ax=plt.subplots(figsize=(10.2,3.15))
ax.bar(minutes[:-1],rain.value.iloc[:-1],width=4.2,align='edge',color=TEAL,alpha=.84)
ax.set(xlim=(0,240),ylim=(0,175),xlabel='降雨开始后的时间（分钟）',ylabel='5分钟平均雨强（毫米/小时）')
ax.set_xticks(np.arange(0,241,30)); nice_axis(ax)
ax.annotate(f'雨峰 {format_time(rain_peak)}\n{rain.value.max():.2f} 毫米/小时',
            xy=(minutes[rain_peak_idx]+2,rain.value.max()),xytext=(130,157),
            fontsize=10,color=TEAL,arrowprops={'arrowstyle':'-','color':TEAL})
ax2=ax.twinx(); ax2.plot(minutes,cumulative,color=ORANGE,lw=2)
ax2.set(ylabel='累计雨量（毫米）',ylim=(0,95)); ax2.spines['right'].set_visible(False)
ax2.tick_params(axis='y',colors=ORANGE); ax2.yaxis.label.set_color(ORANGE)
save(fig,'rainfall.png')

# Area and depth: distinguish peak timing instead of conflating both peaks.
fig,(ax,ax2)=plt.subplots(2,1,figsize=(10.2,4.2),sharex=True,gridspec_kw={'hspace':.17})
tmins=np.array((times-times[0]).total_seconds()/60)
ax.fill_between(tmins,area,color=TEAL,alpha=.13); ax.plot(tmins,area,color=TEAL,lw=2,label='全部积水')
ax.plot(tmins,road_area,color='#6b8d87',lw=1.3,ls='--',label='道路积水')
ax.set(ylabel='积水面积（平方米）',ylim=(0,float(area.max())*1.28)); nice_axis(ax)
ax.annotate(f'{format_time(times[peak_area_i])} · {area.max():,.0f} 平方米',
    (tmins[peak_area_i],area.max()),xytext=(tmins[peak_area_i]+27,area.max()*1.08),
    fontsize=10,color=TEAL,arrowprops={'arrowstyle':'-','color':TEAL})
ax.legend(frameon=False,loc='upper right',ncol=2,fontsize=9)
ax2.plot(tmins,maxdepth_series*100,color=ORANGE,lw=2)
ax2.set(ylabel='最大水深（厘米）',xlabel='模拟时间',ylim=(0,maxdepth_series.max()*125)); nice_axis(ax2)
ax2.annotate(f'{format_time(times[peak_depth_i])} · {maxdepth_series.max()*100:.1f} 厘米',
    (tmins[peak_depth_i],maxdepth_series.max()*100),xytext=(tmins[peak_depth_i]+32,maxdepth_series.max()*102),
    fontsize=10,color=ORANGE,arrowprops={'arrowstyle':'-','color':ORANGE})
ax2.set_xticks(np.arange(0,421,60),[f'{h:02d}:00' for h in range(8)])
for a in (ax,ax2):
    a.axvline(240,color='#9daaa4',ls=':',lw=1)
ax2.text(245,maxdepth_series.max()*75,'04:00 雨停',color='#7c8c84',fontsize=9)
save(fig,'surface_process.png')

# Draw native grid outputs as publication-style figures, with declared land categories.
base=np.full(shape,np.nan);base[green]=0;base[road]=1;base[building]=2
land_cmap=ListedColormap(['#e5eee1','#c6d0d0','#556468'])
water_cmap=LinearSegmentedColormap.from_list('water_depth',['#fff0bc','#ffc46c','#ed9143','#c55d32','#913833'])
def drawmap(ax,arr,label,mark_nodes=False):
    ax.imshow(np.ma.masked_invalid(base),cmap=land_cmap,vmin=0,vmax=2,interpolation='nearest')
    im=ax.imshow(np.ma.masked_where((arr<THRESHOLD)|(~flow),arr),cmap=water_cmap,
                 vmin=THRESHOLD,vmax=.22,interpolation='nearest')
    ax.contour(valid.astype(float),levels=[.5],colors=['#7a8c86'],linewidths=.55)
    if mark_nodes:
        offsets={'P6':(10,10),'P7':(-25,-12),'P42':(10,5),'P43':(20,12),
                 'P44':(-33,-8),'P46':(-30,3),'P48':(-30,3)}
        for e in facts:
            m=mapping[mapping.node_id==e['node_id']].iloc[0]
            ax.scatter(m.cell_col,m.cell_row,s=11,color='#183f3b',edgecolor='white',linewidth=.5,zorder=5)
            ax.annotate(e['node_id'],(m.cell_col,m.cell_row),xytext=offsets[e['node_id']],
                textcoords='offset points',fontsize=8,color='#153d36',
                bbox={'facecolor':'white','alpha':.9,'edgecolor':'none','pad':1.8},
                arrowprops={'arrowstyle':'-','lw':.6,'color':'#54726b'})
    ax.set_title(label,fontsize=12,pad=13,color='#234b43')
    ax.set_xticks([]);ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    return im
fig,axs=plt.subplots(1,2,figsize=(10.2,6.7))
drawmap(axs[0],max_grid,'模拟过程中各位置的最大水深',True)
im=drawmap(axs[1],depth[-1],f'模拟结束时的水深 · {format_time(times[-1])}')
fig.legend(handles=[Patch(color='#e5eee1',label='绿地'),Patch(color='#c6d0d0',label='道路'),
                    Patch(color='#556468',label='建筑物')],loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,.025),fontsize=10)
fig.subplots_adjust(bottom=.10,right=.89,wspace=.12)
cax=fig.add_axes([.92,.19,.016,.59]);cb=fig.colorbar(im,cax=cax);cb.set_label('水深（米）',fontsize=10)
save(fig,'surface_maps.png')
selected_i=[first_i,peak_area_i,int(np.argmin(abs(tmins-240))),len(times)-1]
fig,axs=plt.subplots(1,4,figsize=(11.7,4.6))
for ax,i in zip(axs,selected_i): im=drawmap(ax,depth[i],f'{format_time(times[i])}\n积水 {area[i]:,.0f} 平方米')
fig.subplots_adjust(wspace=.13,right=.91)
cax=fig.add_axes([.93,.24,.013,.48]);cb=fig.colorbar(im,cax=cax);cb.set_label('水深（米）',fontsize=9)
save(fig,'surface_stages.png')

# Event volumes and actual P6 process.
fig,(ax,ax2)=plt.subplots(1,2,figsize=(10.2,3.5),gridspec_kw={'width_ratios':[.85,1.35],'wspace':.32})
names=[e['node_id'] for e in facts]; vols=[e['estimated_volume_m3'] for e in facts]
ax.barh(names[::-1],vols[::-1],color=[TEAL if n in ('P6','P7') else '#9cb5ad' for n in names[::-1]],height=.58)
for i,v in enumerate(vols[::-1]):ax.text(v+.16,i,f'{v:.2f}',va='center',fontsize=9,color='#415e55')
ax.set(xlabel='累计冒溢量（立方米）',xlim=(0,max(vols)*1.25));ax.set_title('各节点冒溢量',fontsize=11,pad=15); nice_axis(ax)
pt=pd.to_datetime([s['time'] for s in p6series]); pm=(pt-pt[0]).total_seconds()/60
pin=[s['nodes']['P6']['total_inflow_Ls'] for s in p6series]
pout=[s['links']['G6']['signed_model_flow_Ls'] for s in p6series]
pf=[s['nodes']['P6']['flooding_Ls'] for s in p6series]
ax2.plot(pm,pin,color=TEAL,label='P6总入流',lw=2)
ax2.plot(pm,pout,color='#637e89',label='G6出流',lw=2)
ax2.plot(pm,pf,color=ORANGE,label='P6冒溢',lw=2)
ax2.set(ylabel='流量（升/秒）',xlabel='模拟时间');ax2.set_xticks(pm,[format_time(t) for t in pt],rotation=35)
ax2.legend(frameon=False,fontsize=8,ncol=3,loc='upper center',bbox_to_anchor=(.5,1.19))
nice_axis(ax2);save(fig,'overflow_process.png')

metrics={
    'rain_total_mm':total_rain,'rain_peak_mm_h':float(rain.value.max()),'rain_peak_time':str(rain_peak),
    'wet_threshold_m':THRESHOLD,'surface_saved_times':len(times),'max_simultaneous_area_m2':float(area.max()),
    'max_area_time':str(times[peak_area_i]),'max_saved_depth_m':float(maxdepth_series.max()),
    'max_solver_depth_m':summary['ca2d']['max_depth_m'],'max_depth_time':str(times[peak_depth_i]),
    'final_area_m2':float(area[-1]),'final_max_depth_m':float(maxdepth_series[-1]),
    'first_saved_ponding_time':str(times[first_i]),'ever_wet_area_m2':float(ever_wet.sum()*area_cell),
    'max_ponding_duration_min':max_duration,'road_peak_area_m2':float(road_area.max()),
    'road_peak_time':str(times[road_area.argmax()]),'green_peak_area_m2':float(green_area.max()),
    'green_peak_time':str(times[green_area.argmax()]),'road_area_at_total_peak_m2':float(road_area[peak_area_i]),
    'green_area_at_total_peak_m2':float(green_area[peak_area_i]),'final_road_area_m2':float(road_area[-1]),
    'final_green_area_m2':float(green_area[-1]),'building_adjacent_peak_area_m2':float(building_near_area.max()),
    'road_share_at_total_peak_percent':float(road_area[peak_area_i]/area[peak_area_i]*100),
    'road_ever_wet_area_m2':float((ever_wet&road).sum()*area_cell),
    'green_ever_wet_area_m2':float((ever_wet&green).sum()*area_cell),
    'total_flooding_volume_m3':total_volume,'raw_volume_m3':raw_volume,'events':facts,
    'p6_peak_inflow_Ls':p6in,'p6_peak_outflow_Ls':p6out,'p6_peak_flooding_Ls':p6flood,
    'p6_p7_volume_share_percent':float((vols[0]+vols[1])/total_volume*100),
    'wet_at_04_00_m2':float(area[selected_i[2]]),'max_30min_rain_mm':max30,
    'max_30min_start':str(rain.timestamp.iloc[max30_idx]),
}
metrics['area_process']=[{'time':str(t),'area_m2':float(a),'road_area_m2':float(b),'green_area_m2':float(c),'max_depth_m':float(d)}
                         for t,a,b,c,d in zip(times,area,road_area,green_area,maxdepth_series)]
(OUT/'report_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
after={str(p.relative_to(PROJECT)):sha(p) for p in SOURCES}
assert before==after,'Saved source artifacts changed during report build'
provenance={'source_hashes':before,'source_files_unchanged':True,
 'calculation_choices':{'ponding_depth_threshold_m':THRESHOLD,'area':'simultaneous wet valid flow cells times 9 m2',
 'green':'valid flow cells excluding roads','building_surroundings':'one-cell adjacent valid flow cells',
 'event_volume':'frozen event_manifest cross-checked against native saved node flooding left-interval integration'},
 'purpose':'First human-facing report specimen; not an agent workflow change.'}
(OUT/'report_provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')

def embed(p):
    mime='image/gif' if p.suffix=='.gif' else 'image/png'
    return f'data:{mime};base64,'+base64.b64encode(p.read_bytes()).decode()
def figure(name,caption,cls=''):
    return f'<figure class="{cls}"><img src="{embed(ASSETS/name)}" alt="{caption}" loading="lazy"><figcaption>{caption}</figcaption></figure>'
event_table=''.join(f'<tr><td><b>{e["node_id"]}</b></td><td>{format_time(e["start"])}—{format_time(e["end"])}</td><td>{e["duration_minutes"]:.0f}</td><td>{e["estimated_volume_m3"]:.2f}</td><td>{e["peak_flooding_Ls"]:.2f}</td></tr>' for e in facts)
near_buildings = ('建筑物周边出现局部积水，呈零散小片分布。'
                  if building_near_area.max()>0 else '积水主要分布在道路及部分绿地，未延伸至建筑物紧邻地表。')
flood_share=(vols[0]+vols[1])/total_volume*100
gpeak=int(green_area.argmax())
rpeak=int(road_area.argmax())
html=f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>UrbanDrainage · 单峰降雨情景模拟诊断报告</title>
<style>
:root{{--ink:#203b35;--muted:#6b7e76;--accent:#087b72;--rule:#e1e8e3;--paper:#fff;--wash:#f3f6f2;--gold:#bd7433}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--wash);color:var(--ink);font-family:'Microsoft YaHei','PingFang SC','Segoe UI',sans-serif;line-height:1.85;-webkit-font-smoothing:antialiased}}
.layout{{max-width:1330px;margin:0 auto;display:grid;grid-template-columns:164px minmax(0,1fr);gap:38px;padding:42px 28px 60px}}
aside{{position:sticky;top:32px;align-self:start;font-size:12px;padding-top:10px}}.brand{{font-weight:700;letter-spacing:2px;color:var(--accent);font-size:13px;margin-bottom:34px}}.nav-label{{color:#8a9890;font-size:10px;letter-spacing:2px;margin-bottom:12px}}
nav a{{display:block;text-decoration:none;color:var(--muted);padding:10px 0;border-bottom:1px solid #e3e9e4;line-height:1.5}}nav a:hover{{color:var(--accent)}}nav span{{display:inline-block;width:25px;font-size:10px;color:#94a59b}}.aside-foot{{margin-top:30px;color:#8a9890;font-size:10px;line-height:1.9}}
main{{background:var(--paper);border:1px solid var(--rule);padding:54px 60px 30px;min-width:0;box-shadow:0 10px 42px #24443808}}
.eyebrow{{font-size:11px;letter-spacing:2px;color:var(--accent);font-weight:600;margin:0 0 17px}}h1{{font-size:38px;line-height:1.35;letter-spacing:1px;font-weight:650;margin:0 0 20px}}.subtitle{{font-size:14px;color:var(--muted);margin:0 0 25px}}
.meta{{display:flex;gap:23px;flex-wrap:wrap;font-size:11px;color:var(--muted);padding:16px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}}.meta b{{color:var(--ink);font-weight:500;margin-left:7px}}
.intro{{font-size:15px;margin:25px 0 28px}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:25px 0 7px}}.metric{{padding:16px 15px;background:#f4f8f5;border-top:2px solid #b4cec3}}.metric span{{font-size:11px;color:var(--muted);display:block}}.metric strong{{display:block;font-size:27px;font-weight:600;color:var(--accent);line-height:1.7}}.metric small{{font-size:11px;color:var(--muted)}}
section{{padding-top:34px;margin-top:34px;border-top:1px solid var(--rule);scroll-margin-top:24px}}h2{{font-size:23px;font-weight:600;line-height:1.4;margin:0 0 22px;display:flex;align-items:center;gap:16px}}h2 span{{font-family:Georgia,serif;font-size:30px;font-weight:400;color:#a2b9aa}}h3{{font-size:16px;margin:25px 0 9px;font-weight:600}}p{{font-size:14px;margin:0 0 16px}}.lead{{font-size:16px;line-height:1.9}}strong{{font-weight:600}}figure{{margin:22px 0 25px}}figure img{{display:block;width:100%;height:auto;border:1px solid #edf1ed;background:white}}figcaption{{font-size:11px;color:var(--muted);line-height:1.7;margin-top:10px}}.map figcaption{{text-align:center}}
.finding{{background:#f1f7f3;border-left:3px solid var(--accent);padding:18px 22px;margin:23px 0;font-size:14px}}.finding b{{color:var(--accent)}}.statline{{display:flex;gap:32px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-bottom:18px}}.statline b{{font-size:18px;color:var(--ink);margin-left:5px}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:16px 0 20px;font-variant-numeric:tabular-nums}}th{{text-align:left;font-weight:500;color:var(--muted);background:#f5f7f4;padding:12px 10px;white-space:nowrap}}td{{padding:12px 10px;border-bottom:1px solid var(--rule)}}th:nth-child(n+3),td:nth-child(n+3){{text-align:right}}tbody tr:hover{{background:#fafbf8}}
.animation{{background:#f5f7f4;padding:20px 24px 16px;position:relative}}.animation img{{max-height:550px;width:auto;max-width:100%;margin:0 auto;border:0}}.animation-head{{display:flex;align-items:center;justify-content:space-between;font-size:12px;margin-bottom:14px;color:var(--muted)}}button{{border:1px solid #bdccc1;border-radius:3px;background:white;color:var(--accent);font:inherit;font-size:11px;cursor:pointer;padding:6px 12px}}button:hover{{background:#e9f2ec}}
.conclusions{{counter-reset:c;margin:0;padding:0;list-style:none}}.conclusions li{{counter-increment:c;display:grid;grid-template-columns:26px 1fr;gap:13px;padding:17px 0;border-bottom:1px solid var(--rule);font-size:14px}}.conclusions li:before{{content:counter(c,decimal-leading-zero);font-family:Georgia,serif;color:var(--accent);font-size:18px}}.conclusions b{{display:block;margin-bottom:4px}}footer{{margin-top:40px;padding-top:17px;border-top:1px solid var(--rule);display:flex;justify-content:space-between;gap:16px;font-size:10px;color:#87968b}}.print-button{{margin-top:22px}}
@media(max-width:1000px){{.layout{{grid-template-columns:1fr;max-width:980px;padding:20px;gap:15px}}aside{{position:static;padding:0}}.brand{{margin:0 0 10px}}.nav-label,.aside-foot{{display:none}}nav{{display:flex;flex-wrap:wrap;gap:8px 16px}}nav a{{border:0;padding:3px 0;font-size:11px}}main{{padding:35px 32px}}}}
@media(max-width:600px){{.layout{{padding:12px}}main{{padding:26px 20px}}h1{{font-size:28px}}h2{{font-size:20px;gap:10px}}.metrics{{grid-template-columns:repeat(2,1fr)}}.metric strong{{font-size:25px}}.meta{{gap:8px 16px}}p{{font-size:13px}}.lead{{font-size:14px}}.animation{{padding:14px}}.statline{{gap:12px}}footer{{flex-direction:column}}}}
@media print{{body{{background:white}}.layout{{display:block;padding:0}}aside,.print-button,button{{display:none}}main{{border:0;box-shadow:none;padding:15px}}section{{break-before:auto}}figure,.finding,table,.metrics{{break-inside:avoid}}.animation{{display:none}}h2,h3{{break-after:avoid}}.metrics{{grid-template-columns:repeat(4,1fr)}}}}
</style></head><body><div class="layout">
<aside><div class="brand">SWMM · AGENTIC</div><div class="nav-label">报告目录</div><nav>
<a href="#scene"><span>01</span>模拟基本场景</a><a href="#rain"><span>02</span>降雨特征</a>
<a href="#surface"><span>03</span>地表淹没与演变</a><a href="#network"><span>04</span>管网冒溢与地表联系</a>
<a href="#causes"><span>05</span>原因分析</a><a href="#conclusion"><span>06</span>主要结论与关注重点</a>
</nav><div class="aside-foot">UrbanDrainage<br>单峰降雨 · 基准方案<br>模拟时长 7小时</div></aside>
<main><header><p class="eyebrow">URBAN DRAINAGE / SIMULATION REPORT</p>
<h1>单峰降雨情景<br>模拟诊断报告</h1><p class="subtitle">UrbanDrainage区域 · 基准方案 · 4小时80毫米降雨</p>
<div class="meta"><span>模拟时段<b>2024年1月1日 00:00—07:00</b></span><span>计算日期<b>2026年10月3日</b></span></div>
<p class="intro">本场降雨的雨峰较为集中，管网冒溢发生在雨峰后的短时间内。地表积水以道路为主，先出现局部较深积水，随后积水范围扩大；雨停后，部分路段仍有积水。</p>
<div class="metrics"><div class="metric"><span>累计降雨量</span><strong>{total_rain:.0f}</strong><small>毫米 / 历时4小时</small></div>
<div class="metric"><span>冒溢节点</span><strong>{len(facts)}</strong><small>个 / 总冒溢量{total_volume:.2f}立方米</small></div>
<div class="metric"><span>最大地表水深</span><strong>{maxdepth_series.max():.2f}</strong><small>米 / 出现在{format_time(times[peak_depth_i])}</small></div>
<div class="metric"><span>最大同时积水面积</span><strong>{area.max():,.0f}</strong><small>平方米 / 出现在{format_time(times[peak_area_i])}</small></div></div></header>

<section id="scene"><h2><span>01</span>模拟基本场景</h2>
<p>本次模拟针对UrbanDrainage区域的基准方案，采用历时4小时、累计雨量80毫米的单峰降雨。模拟从00:00开始，降雨于04:00结束，计算继续至07:00，覆盖降雨期间及雨停后3小时的管网和地表变化。</p>
<p>报告依次呈现降雨过程、地表积水分布与演变、管网冒溢及其地表联系，并结合节点来水与相邻管段的流量变化解释主要现象。</p></section>

<section id="rain"><h2><span>02</span>降雨特征</h2>
<p class="lead">本场降雨呈明显单峰形态，雨峰出现在01:35，最大5分钟平均雨强约为{rain.value.max():.2f}毫米/小时。</p>
<p>降雨前段逐渐增强，在中前段形成集中雨峰，随后逐步减弱。雨量最多的连续30分钟为{format_time(rain.timestamp.iloc[max30_idx])}—{format_time(rain.timestamp.iloc[max30_idx]+pd.Timedelta(minutes=30))}，累计雨量约{max30:.1f}毫米，占整场降雨的{max30/total_rain*100:.0f}%。本场降雨的突出特点，是较多雨量集中在较短时间内。</p>
{figure('rainfall.png','图1　单峰降雨过程。绿色柱表示5分钟平均雨强，橙色曲线表示累计雨量。')}
</section>

<section id="surface"><h2><span>03</span>地表淹没情况与演变</h2>
<h3>整体情况与空间分布</h3>
<p>本次地表积水呈道路带状分布与局部积水点并存的形态。最大同时积水面积约为{area.max():,.0f}平方米，最大水深约为{maxdepth_series.max():.2f}米。较连续的积水带位于图示左侧及下部，道路交汇附近出现局部较深积水；中部至上部还分布着若干较小积水点。</p>
{figure('surface_maps.png','图2　各位置的最大水深与07:00结束时刻水深对照。左图汇集各位置在模拟过程中达到的最大水深；右图表示结束时刻的同时分布。','map')}
<h3>道路、绿地与建筑物周边</h3>
<p>积水面积最大时，道路积水约为{road_area[peak_area_i]:,.0f}平方米，占同时积水面积的{road_area[peak_area_i]/area[peak_area_i]*100:.0f}%；绿地积水约为{green_area[peak_area_i]:,.0f}平方米。道路是本次积水分布的主体，绿地积水则在后续阶段逐步增加。{near_buildings}</p>
<div class="table-wrap"><table><thead><tr><th>地表类型</th><th>最大同时积水面积</th><th>出现时刻</th><th>07:00积水面积</th></tr></thead><tbody>
<tr><td>道路</td><td>{road_area.max():,.0f}平方米</td><td>{format_time(times[rpeak])}</td><td>{road_area[-1]:,.0f}平方米</td></tr>
<tr><td>绿地</td><td>{green_area.max():,.0f}平方米</td><td>{format_time(times[gpeak])}</td><td>{green_area[-1]:,.0f}平方米</td></tr>
</tbody></table></div>
<h3>从局部加深到范围扩展</h3>
<p>地表时序在{format_time(times[first_i])}开始出现明显积水，同一时刻局部水深达到本次最大值，约为{maxdepth_series.max()*100:.1f}厘米。此后最大水深总体下降，积水范围则在波动中扩大，在{format_time(times[peak_area_i])}达到约{area.max():,.0f}平方米。水深峰值与面积峰值相隔{(times[peak_area_i]-times[peak_depth_i]).total_seconds()/60:.0f}分钟，说明本次过程经历了先局部加深、后扩大分布范围的变化。</p>
<p>04:00雨停时，积水面积约为{area[selected_i[2]]:,.0f}平方米。至07:00，积水面积约为{area[-1]:,.0f}平方米，最大水深约为{maxdepth_series[-1]*100:.1f}厘米，剩余积水主要位于道路。其中道路积水约{road_area[-1]:,.0f}平方米，绿地积水约{green_area[-1]:,.0f}平方米。</p>
{figure('surface_process.png','图3　地表积水面积与最大水深的时间变化。积水面积按水深达到1厘米的地表网格统计。')}
{figure('surface_stages.png','图4　积水出现、范围最大、雨停及模拟结束四个阶段的水深分布。')}
<figure class="animation"><div class="animation-head"><span>地表积水演变 · 00:00—07:00</span><button type="button" id="replay">重新播放</button></div>
<img id="surface-animation" src="{embed(RUN/'ca2d/ca2d_animation.gif')}" alt="00:00至07:00的地表积水演变动画" loading="lazy">
<figcaption>图5　地表积水演变动画。画面标题显示模拟时刻，观察积水的出现、扩展和后期变化。</figcaption></figure>
</section>

<section id="network"><h2><span>04</span>管网冒溢情况与地表联系</h2>
<p class="lead">本次共有7个节点发生冒溢，每个节点各发生1次，总冒溢量约为{total_volume:.2f}立方米，事件集中在01:37—01:42。</p>
<p>P6和P7最早开始冒溢，均持续约5分钟；随后P43、P44、P46、P42和P48陆续出现冒溢，各持续约1—3分钟。P6冒溢量最大，约{vols[0]:.2f}立方米，P7次之，约{vols[1]:.2f}立方米，两者合计占总冒溢量的{flood_share:.0f}%。</p>
<div class="table-wrap"><table><thead><tr><th>节点</th><th>冒溢时段</th><th>持续（分钟）</th><th>冒溢量（立方米）</th><th>峰值（升/秒）</th></tr></thead><tbody>{event_table}</tbody></table></div>
<h3>雨峰后的集中冒溢</h3>
<p>雨强在01:35达到峰值，最早冒溢发生在2分钟后。P6、P7和P46的冒溢峰值均出现在01:40附近，之后逐步减弱。节点位置在图2中标出，主要形成P6—P7与P42—P48两组空间分布。</p>
<h3>冒溢进入地表后的变化</h3>
<p>本次管网冒溢向地表输入的水量约为{total_volume:.2f}立方米。冒溢集中发生的01:37—01:42，与地表在01:40开始出现明显积水的阶段衔接。节点冒溢停止后，地表积水范围仍继续扩大，至{format_time(times[peak_area_i])}达到最大，呈现短时冒溢输入之后地表水继续重新分布的过程。</p>
</section>

<section id="causes"><h2><span>05</span>原因分析</h2>
<h3>集中来水与出流变化共同构成冒溢过程</h3>
<p>以P6为例，冒溢前节点水位快速上升。01:40，总入流约为{p6in:.1f}升/秒，G6出流约为{p6out:.1f}升/秒，冒溢流量约为{p6flood:.1f}升/秒。冒溢高峰附近，来水保持较高水平，而G6的出流变化较小，多出的来水通过节点冒溢进入地表。</p>
{figure('overflow_process.png','图6　各节点冒溢量及P6事件过程。右图对照同一时段的节点总入流、G6出流和冒溢流量。')}
<p>P6的来水由上游G4、G5及节点侧向来水共同组成；P7则同时接收G6来水和节点侧向来水。两节点的冒溢开始和结束时刻一致，峰值也均位于01:40，表现出同一轮来水高峰下的连续响应。另一组节点在随后几分钟陆续冒溢，同样体现出集中来水期间的短时入流与出流不匹配。</p>
<h3>地表水深与积水面积呈不同的峰值过程</h3>
<p>地表最大水深出现在冒溢集中输入的初期；随后，即使节点冒溢已停止，积水仍从较集中的位置向周边重新分布。局部最大水深总体下降，而达到积水统计水深的区域增多，因此面积峰值出现在水深峰值之后。</p>
<p>道路积水在最大同时积水面积和结束时刻均占主要份额，表明道路空间是本次地表水分布与存留的重要位置。较深积水点、较连续积水带以及后期保留积水的路段，构成了本次地表分析的关注重点。</p>
</section>

<section id="conclusion"><h2><span>06</span>主要结论与关注重点</h2>
<ol class="conclusions"><li><div><b>冒溢集中发生在雨峰之后。</b>雨峰出现在01:35，7个节点在01:37—01:42冒溢，总冒溢量约{total_volume:.2f}立方米。P6和P7是主要冒溢节点，合计贡献约{flood_share:.0f}%的冒溢量。</div></li>
<li><div><b>地表经历了先局部加深、后范围扩大的过程。</b>{format_time(times[peak_depth_i])}出现约{maxdepth_series.max():.2f}米的最大水深；{format_time(times[peak_area_i])}积水面积达到约{area.max():,.0f}平方米。局部水深与积水范围具有不同的变化节奏。</div></li>
<li><div><b>道路是主要积水位置，也是后期关注重点。</b>最大同时积水面积时，道路约占{road_area[peak_area_i]/area[peak_area_i]*100:.0f}%。至07:00，道路仍有约{road_area[-1]:,.0f}平方米积水，重点关注图示左侧、下部积水路段及相关道路交汇位置。</div></li></ol>
</section><footer><span>UrbanDrainage · 单峰降雨情景 · 基准方案</span><span>报告日期：2026年10月4日</span></footer>
<button type="button" class="print-button" onclick="window.print()">打印 / 保存静态版</button>
</main></div><script>
document.getElementById('replay').addEventListener('click',()=>{{const img=document.getElementById('surface-animation');const src=img.src;img.src='';requestAnimationFrame(()=>{{img.src=src}})}});
</script></body></html>'''
(OUT/'模拟诊断报告_v1.html').write_text(html,encoding='utf-8')
print(json.dumps({'report':str(OUT/'模拟诊断报告_v1.html'),'size_bytes':len(html.encode('utf-8')),
    'metrics':{k:v for k,v in metrics.items() if k not in ('events','area_process')}},ensure_ascii=False,indent=2))
