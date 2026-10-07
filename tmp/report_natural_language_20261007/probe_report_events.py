"""Try per-event Report Agent prose, preserving the source HTML and task state."""
import argparse
import asyncio
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflow_agents.reporting.materials import assert_sources_current
from workflow_agents.reporting.narrative import SYSTEM_PROMPT, expand, make_prompt, validate
from workflow_agents.reporting.pipeline import producer_hashes


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def file_hashes(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


async def run(args):
    from autogen_core.models import SystemMessage, UserMessage
    from llm import deepseek_flash

    source = Path(args.source_report).resolve()
    overview = Path(args.overview_source).resolve()
    output = Path(args.output_dir).resolve()
    materials = json.loads((source / 'report_materials.json').read_text(encoding='utf-8'))
    original = json.loads((source / 'narrative.json').read_text(encoding='utf-8'))
    original['sections']['causes'] = json.loads(overview.read_text(encoding='utf-8'))['paragraphs']
    assert_sources_current(materials)
    prompt, facts = make_prompt(materials)
    known = set()
    for event in materials['events']:
        known.add(event['node_id'])
        known.update(event['incident_links'])
        for edge in event['incident_links'].values():
            known.update((edge['from_node'], edge['to_node']))
    # Validate the retained sections before spending a model call. The supplied
    # overview can be an earlier accepted overview-only experiment.
    validate(original, materials, facts, known)
    protected = [source / 'report_materials.json', source / 'narrative.json', overview]
    protected.extend(source.glob('*.html'))
    task_file = source.parents[2] / 'task.json'
    if task_file.is_file():
        protected.append(task_file)
    before = file_hashes(protected)
    producer = producer_hashes()
    output.mkdir(parents=True, exist_ok=False)
    system = SYSTEM_PROMPT + '''
本次只重新撰写当前任务全部逐节点分析，不生成其他章节。
输出合法JSON：{"events":[正式结构中的逐事件对象]}。
每个事件保留event_id、title、process、supported_mechanism_ids、supported_causes、candidate_mechanism_ids、candidate_influences。
学习成对教学案例的组织方法，采用当前事件事实和诊断；不要给全部节点套用P6的过程。
过程写变化，成因写具体作用，下游影响写完整的一句解释；不要复述判断状态或添加抽象总结句。
'''
    user = dict(prompt)
    user['instruction'] = '按照逐节点转写要求重新组织全部事件的过程和成因；保留具体诊断关系与节点差异，不用同一套起句和结尾。'
    save(output / 'prompt.json', {'system': system, 'input': user,
        'producer_hashes': producer, 'source_hashes': before,
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
            combined = copy.deepcopy(original)
            combined['events'] = response['events']
            validate(combined, materials, facts, known)
            assert_sources_current(materials)
            if producer_hashes() != producer:
                raise ValueError('Producer files changed during the probe')
            if file_hashes(protected) != before:
                raise ValueError('Source report or task changed during the probe')
            audit['status'] = 'passed'
            save(output / f'attempt_{attempt}.json', audit)
            save(output / 'events.json', response)
            save(output / 'combined_narrative.json', combined)
            text = []
            by_id = {event['event_id']: event for event in response['events']}
            for material in materials['events']:
                event = by_id[material['event_id']]
                text.append('## ' + event.get('title', material['node_id']))
                for field, heading in (('process', '发生过程'),
                                       ('supported_causes', '成因分析'),
                                       ('candidate_influences', '下游影响')):
                    if event[field]:
                        text.append('### ' + heading)
                        text.extend(expand(paragraph, facts) for paragraph in event[field])
            excerpt = output / '逐节点分析_试写.md'
            excerpt.write_text('\n\n'.join(text) + '\n', encoding='utf-8')
            save(output / 'probe_result.json', {'status': 'completed', 'source_report': str(source),
                'excerpt_file': str(excerpt), 'event_count': len(response['events']),
                'producer_hashes': producer, 'source_hashes': before,
                'scope': 'per-event text only; original HTML and task state unchanged',
                'verification_scope': 'structure, source identity, fact references and diagnosis status; prose needs editorial review'})
            print(json.dumps({'status': 'completed', 'excerpt_file': str(excerpt),
                              'event_count': len(response['events']), 'attempt': attempt}, ensure_ascii=False))
            return
        except (ValueError, KeyError, TypeError) as exc:
            audit.update(status='failed', error=str(exc))
            save(output / f'attempt_{attempt}.json', audit)
            if attempt == 3:
                raise
            user = dict(user, repair={'error': str(exc), 'previous_response': result.content,
                'instruction': '修订所指出的问题，保留具体作用解释和原判断力度，重新输出全部事件。'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report', required=True)
    parser.add_argument('--overview-source', required=True)
    parser.add_argument('--output-dir', required=True)
    asyncio.run(run(parser.parse_args()))
