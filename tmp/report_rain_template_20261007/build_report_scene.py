"""Build fixed scene prose and retain every other accepted report section."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflow_agents.reporting.materials import assert_sources_current
from workflow_agents.reporting.narrative import assemble_fixed_sections, expand, make_prompt, validate
from workflow_agents.reporting.pipeline import producer_hashes
from workflow_agents.reporting.scene import VERSION


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def hashes(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def run(args):
    source = Path(args.source_report).resolve()
    narrative_source = Path(args.narrative_source).resolve()
    output = Path(args.output_dir).resolve()
    material_file = source / 'report_materials.json'
    materials = json.loads(material_file.read_text(encoding='utf-8'))
    baseline = json.loads(narrative_source.read_text(encoding='utf-8'))
    assert_sources_current(materials)
    protected = [material_file, source / 'narrative.json', narrative_source]
    protected.extend(source.glob('*.html'))
    task_file = source.parents[2] / 'task.json'
    if task_file.is_file():
        protected.append(task_file)
    before = hashes(protected)
    producer = producer_hashes()
    prompt, facts = make_prompt(materials)
    known = set()
    for event in materials['events']:
        known.add(event['node_id'])
        known.update(event['incident_links'])
        for edge in event['incident_links'].values():
            known.update((edge['from_node'], edge['to_node']))
    validate(baseline, materials, facts, known)
    combined = assemble_fixed_sections(baseline, prompt)
    validate(combined, materials, facts, known)
    if combined['intro'] != baseline['intro'] or combined['events'] != baseline['events']:
        raise ValueError('Accepted intro or node analyses changed')
    if any(combined['sections'][key] != baseline['sections'][key]
           for key in baseline['sections'] if key != 'scene'):
        raise ValueError('Another section changed during scene assembly')
    assert_sources_current(materials)
    if hashes(protected) != before or producer_hashes() != producer:
        raise ValueError('Protected source or producer changed during assembly')
    output.mkdir(parents=True, exist_ok=False)
    paragraphs = [expand(text, facts) for text in combined['sections']['scene']]
    excerpt = output / '模拟基本场景_模板输出.md'
    excerpt.write_text('\n\n'.join(paragraphs) + '\n', encoding='utf-8')
    save(output / 'scene.json', {'paragraphs': paragraphs, 'source': 'program_template', 'version': VERSION})
    save(output / 'combined_narrative.json', combined)
    save(output / 'fact_text.json', facts)
    save(output / 'assembly_result.json', {'status': 'completed', 'source': 'program_template',
        'template_version': VERSION, 'excerpt_file': str(excerpt), 'source_report': str(source),
        'narrative_source': str(narrative_source), 'source_hashes': before, 'producer_hashes': producer,
        'scope': 'scene only; all other prose, original HTML and task state unchanged'})
    print(json.dumps({'status': 'completed', 'source': 'program_template',
                      'paragraphs': paragraphs, 'excerpt_file': str(excerpt)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', required=True)
    parser.add_argument('--narrative-source', required=True)
    parser.add_argument('--output-dir', required=True)
    run(parser.parse_args())
