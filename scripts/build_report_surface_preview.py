"""Preview the verified surface figures and fixed opening, retaining accepted prose."""
import argparse
import copy
import hashlib
import html
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from workflow_agents.reporting.materials import assert_sources_current, prepare_materials
from workflow_agents.reporting.narrative import assemble_fixed_sections, expand, make_prompt, validate
from workflow_agents.reporting.pipeline import producer_hashes
from workflow_agents.reporting.plots import make_plots
from workflow_agents.reporting.surface import BASIS, VERSION


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def hashes(paths):
    return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def run(args):
    material_file=Path(args.materials).resolve()
    narrative_file=Path(args.narrative_source).resolve()
    materials=read(material_file);baseline=read(narrative_file)
    assert_sources_current(materials)
    root=next(Path(path).parent for path in materials['source_hashes'] if Path(path).name=='rainfall_event.txt')
    task=root/'diagnosis_tasks'/materials['task_id']
    protected=[material_file,narrative_file,task/'task.json']
    source_report=Path(args.source_report).resolve()
    protected.extend(source_report.glob('*.html'))
    protected.extend([source_report/'report_materials.json',source_report/'narrative.json'])
    before=hashes(protected);producer=producer_hashes()
    current,data=prepare_materials(root,task,read(task/'task.json'))
    if current['source_hashes']!=materials['source_hashes'] or current['surface']!=materials['surface']:
        raise ValueError('Current surface materials differ from accepted source')
    prompt,facts=make_prompt(materials)
    validate(baseline,materials,facts,data['known_ids'])
    scoped=dict(prompt,fixed_sections={})
    combined=assemble_fixed_sections(baseline,scoped)
    # Remove the old field-like threshold preamble while retaining all result facts.
    old=combined['sections']['surface'][1]
    preamble='地表统计分为一般积水与重点关注区域。'
    if old.startswith(preamble):
        split=old.find('从峰值看，')
        if split>=0:
            combined['sections']['surface'][1]=old[split:]
    validate(combined,materials,facts,data['known_ids'])
    expected=copy.deepcopy(baseline);expected['sections']['surface']=combined['sections']['surface']
    if expected!=combined:
        raise ValueError('Another report section changed')
    output=Path(args.output_dir).resolve();output.mkdir(parents=True,exist_ok=False)
    media,layouts=make_plots(materials,data,output/'assets')
    paragraphs=[expand(p,facts) for p in combined['sections']['surface']]
    (output/'地表积水_开场与配色预览.md').write_text(paragraphs[0]+'\n',encoding='utf-8')
    sources='；'.join(f'<a href="{html.escape(row["url"],quote=True)}">{html.escape(row["title"])}</a>' for row in BASIS['sources'])
    content='<p>'+html.escape(paragraphs[0])+'</p><p class="sources">分级依据：'+sources+'</p>'
    for key in ('surface_maps','surface_process','surface_stages'):
        name=Path(media[key]['path']).name
        content+=f'<figure><img src="assets/{name}"><figcaption>{html.escape(media[key]["caption"])}</figcaption></figure>'
    document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>地表积水预览</title><style>body{background:#edf2ed;margin:0;color:#223d35;font:16px/1.9 "Microsoft YaHei",sans-serif}main{max-width:1100px;background:white;padding:40px;margin:30px auto}h1{font-size:25px}figure{margin:28px 0}img{width:100%;height:auto}figcaption,.sources{font-size:12px;color:#64776e}a{color:#087b72}</style><main><h1>地表淹没情况与演变</h1>'+content+'</main></html>'
    preview=output/'地表积水_预览.html';preview.write_text(document,encoding='utf-8')
    assert_sources_current(materials)
    if before!=hashes(protected) or producer_hashes()!=producer:
        raise ValueError('Protected inputs or producer changed during preview')
    audit={'status':'completed','source':'program_template_and_plots','version':VERSION,
        'scope':'surface opening and palette; remaining surface prose awaits further refinement',
        'source_hashes':before,'producer_hashes':producer,'basis':BASIS,'preview':str(preview)}
    for name,value in [('combined_narrative.json',combined),('fact_text.json',facts),('report_materials.json',materials),
                       ('map_label_layout.json',layouts),('preview_result.json',audit)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'completed','opening':paragraphs[0],'preview':str(preview)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--materials',required=True)
    parser.add_argument('--narrative-source',required=True)
    parser.add_argument('--source-report',required=True)
    parser.add_argument('--output-dir',required=True)
    run(parser.parse_args())
