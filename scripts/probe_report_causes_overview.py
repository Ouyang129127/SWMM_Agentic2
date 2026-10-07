"""Probe chapter-five overview writing without changing an existing report/task."""
import argparse
import asyncio
import copy
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflow_agents.reporting.materials import assert_sources_current
from workflow_agents.reporting.narrative import SYSTEM_PROMPT, expand, make_prompt, validate
from workflow_agents.reporting.pipeline import producer_hashes


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


async def run(args):
    from autogen_core.models import SystemMessage, UserMessage
    from llm import deepseek_flash

    source=Path(args.source_report).resolve()
    output=Path(args.output_dir).resolve()
    output.mkdir(parents=True,exist_ok=False)
    materials=json.loads((source/'report_materials.json').read_text(encoding='utf-8'))
    original=json.loads((source/'narrative.json').read_text(encoding='utf-8'))
    assert_sources_current(materials)
    producer=producer_hashes()
    prompt,facts=make_prompt(materials)
    known=set()
    for event in materials['events']:
        known.add(event['node_id']);known.update(event['incident_links'])
        for edge in event['incident_links'].values():
            known.update((edge['from_node'],edge['to_node']))
    system=SYSTEM_PROMPT+'''
本次只试写第五章开头的总体成因判断，不生成其他章节或逐节点正文。
使用上述“第五章开头”的专门写法与案例，当前事实以materials为准。
只返回合法JSON：{"paragraphs":["第一个自然段","第二个自然段"]}。
不要返回整篇报告结构、解释写作方法或复述内部判断状态。
'''
    user={'materials':prompt['materials'],'fact_text':facts,
          'previous_overview':original['sections']['causes'],
          'instruction':'重新组织共同成因、节点差异和下游影响，不照抄旧段落。无需在此展开管线连接清单或重复过程数字。'}
    save(output/'prompt.json',{'system':system,'input':user,'producer_hashes':producer,
                             'source_report':str(source),'generated_at':datetime.now().astimezone().isoformat()})
    for attempt in range(1,4):
        result=await deepseek_flash.create([SystemMessage(content=system),
            UserMessage(content=json.dumps(user,ensure_ascii=False),source='user')],json_output=True)
        audit={'attempt':attempt,'source':'configured_model','raw_response':result.content,
               'finish_reason':getattr(result,'finish_reason',None)}
        usage=getattr(result,'usage',None)
        audit['usage']={'prompt_tokens':getattr(usage,'prompt_tokens',None),
                        'completion_tokens':getattr(usage,'completion_tokens',None)}
        try:
            response=json.loads(result.content)
            paragraphs=response['paragraphs']
            if not isinstance(paragraphs,list) or not paragraphs or any(not isinstance(p,str) or not p.strip() for p in paragraphs):
                raise ValueError('Overview paragraphs must be nonempty strings')
            combined=copy.deepcopy(original);combined['sections']['causes']=paragraphs
            validate(combined,materials,facts,known)
            assert_sources_current(materials)
            if producer_hashes()!=producer:
                raise ValueError('Producer files changed during the probe')
            audit['status']='passed';save(output/f'attempt_{attempt}.json',audit)
            save(output/'overview.json',response)
            prose=[expand(p,facts) for p in paragraphs]
            (output/'第五章总体成因_试写.md').write_text('\n\n'.join(prose)+'\n',encoding='utf-8')
            save(output/'probe_result.json',{'status':'completed','source_report':str(source),
                'excerpt_file':str(output/'第五章总体成因_试写.md'),'producer_hashes':producer,
                'scope':'chapter-five overview only; original HTML and task state remain unchanged'})
            print(json.dumps({'status':'completed','excerpt_file':str(output/'第五章总体成因_试写.md'),
                              'paragraphs':prose},ensure_ascii=False))
            return
        except (ValueError,KeyError,TypeError) as exc:
            audit.update(status='failed',error=str(exc));save(output/f'attempt_{attempt}.json',audit)
            if attempt==3:
                raise
            user=dict(user,repair={'error':str(exc),'previous_response':result.content,
                                  'instruction':'修订所指出的问题，直接给出诊断解释，保留原判断力度。'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-report',required=True)
    parser.add_argument('--output-dir',required=True)
    asyncio.run(run(parser.parse_args()))
