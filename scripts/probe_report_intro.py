"""Try just the opening overview, retaining the accepted node analyses."""
import argparse
import asyncio
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflow_agents.reporting.materials import assert_sources_current
from workflow_agents.reporting.narrative import SYSTEM_PROMPT, make_prompt, validate
from workflow_agents.reporting.pipeline import producer_hashes


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def hashes(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


async def run(args):
    from autogen_core.models import SystemMessage, UserMessage
    from llm import deepseek_flash

    source = Path(args.source_report).resolve()
    narrative_source = Path(args.narrative_source).resolve()
    output = Path(args.output_dir).resolve()
    material_file = source / 'report_materials.json'
    materials = json.loads(material_file.read_text(encoding='utf-8'))
    baseline = json.loads(narrative_source.read_text(encoding='utf-8'))
    assert_sources_current(materials)
    prompt, facts = make_prompt(materials)
    known = set()
    for event in materials['events']:
        known.add(event['node_id'])
        known.update(event['incident_links'])
        for edge in event['incident_links'].values():
            known.update((edge['from_node'], edge['to_node']))
    validate(baseline, materials, facts, known)
    protected = [material_file, narrative_source, source / 'narrative.json']
    protected.extend(source.glob('*.html'))
    task_file = source.parents[2] / 'task.json'
    if task_file.is_file():
        protected.append(task_file)
    before = hashes(protected)
    producer = producer_hashes()
    input_materials = {key: prompt['materials'][key] for key in ('scene', 'rain', 'surface', 'overflow', 'scope')}
    tokens = set(re.findall(r'\[\[(F\d+)\]\]', json.dumps(input_materials, ensure_ascii=False)))
    system = SYSTEM_PROMPT + '''
本次只试写报告开头的总述，不生成其他章节或逐节点分析。
严格返回JSON：{"intro":"一个简短自然段"}。
执行“报告开头总述intro”的专门要求和案例，概括主要现象及演变，不摆数据，不展开成因。
总述不使用数字或事实标记；实际现象及先后关系以当前材料为准。
'''
    user = {'materials': input_materials,
            'fact_text': {key: facts[key] for key in facts if key in tokens},
            'previous_intro': baseline['intro'],
            'instruction': '像参考案例一样直接概括本次结果，用两三句连贯文字交代降雨、冒溢时段和地表积水演变。'}
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'prompt.json', {'system': system, 'input': user,
        'source_hashes': before, 'producer_hashes': producer,
        'generated_at': datetime.now().astimezone().isoformat()})
    for attempt in range(1, 4):
        result = await deepseek_flash.create([
            SystemMessage(content=system),
            UserMessage(content=json.dumps(user, ensure_ascii=False), source='user')
        ], json_output=True)
        usage = getattr(result, 'usage', None)
        audit = {'attempt': attempt, 'source': 'configured_model', 'raw_response': result.content,
            'finish_reason': getattr(result, 'finish_reason', None),
            'usage': {'prompt_tokens': getattr(usage, 'prompt_tokens', None),
                      'completion_tokens': getattr(usage, 'completion_tokens', None)}}
        try:
            response = json.loads(result.content)
            intro = response['intro']
            if not isinstance(intro, str) or not intro.strip() or '\n' in intro:
                raise ValueError('Intro must be a nonempty single paragraph')
            if re.search(r'\d|\[\[', intro):
                raise ValueError('Intro should describe qualitative results without numeric statistics or fact tokens')
            relation = facts[prompt['materials']['overflow']['rain_peak_relation'][2:-2]] if prompt['materials']['overflow'].get('rain_peak_relation') else ''
            if '记录区间内' in relation and re.search(r'雨峰后|雨峰结束后|峰值之后|雨峰之后', intro):
                raise ValueError('Overflow began inside the rain-peak interval; summarize near the peak rather than after it')
            combined = copy.deepcopy(baseline)
            combined['intro'] = intro
            validate(combined, materials, facts, known)
            assert_sources_current(materials)
            if hashes(protected) != before or producer_hashes() != producer:
                raise ValueError('Protected source or producer changed during intro probe')
            audit['status'] = 'passed'
            save(output / f'attempt_{attempt}.json', audit)
            save(output / 'intro.json', response)
            save(output / 'combined_narrative.json', combined)
            excerpt = output / '报告总述_试写.md'
            excerpt.write_text(intro + '\n', encoding='utf-8')
            save(output / 'probe_result.json', {'status': 'completed', 'excerpt_file': str(excerpt),
                'source_report': str(source), 'narrative_source': str(narrative_source),
                'source_hashes': before, 'producer_hashes': producer,
                'scope': 'intro only; accepted chapter-five text, other sections, HTML and task state unchanged',
                'verification_scope': 'source identity, report contract, qualitative intro and rain-peak relation; editorial review remains separate'})
            print(json.dumps({'status': 'completed', 'intro': intro, 'excerpt_file': str(excerpt),
                              'attempt': attempt}, ensure_ascii=False))
            return
        except (ValueError, KeyError, TypeError) as exc:
            audit.update(status='failed', error=str(exc))
            save(output / f'attempt_{attempt}.json', audit)
            if attempt == 3:
                raise
            user = dict(user, repair={'error': str(exc), 'previous_response': result.content,
                'instruction': '修订指出的问题，保留简短自然的结果概述，重新输出intro。'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', required=True)
    parser.add_argument('--narrative-source', required=True)
    parser.add_argument('--output-dir', required=True)
    asyncio.run(run(parser.parse_args()))
