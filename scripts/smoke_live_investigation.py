"""One explicit live investigation attempt, retaining provider output for review.

Does not simulate, expand evidence, run verification, or publish a report.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow_agents.investigation import advance_investigation, SYSTEM_PROMPT, serialize_prompt
from workflow_agents.state import resolve_run_root


async def run(args):
    if not args.live:
        raise ValueError('Use --live only after confirming this external model call')
    from autogen_core.models import SystemMessage, UserMessage
    from llm import deepseek_flash, deepseek_model, deepseek_base_url
    root = resolve_run_root(args.model, args.run_id)
    if len(args.task_id) != 32 or any(c not in '0123456789abcdef' for c in args.task_id):
        raise ValueError('Invalid task ID')
    folder = root / 'diagnosis_tasks' / args.task_id
    if not (folder / 'task.json').exists():
        raise FileNotFoundError('Prepare the task first')
    attempt_path = folder / f'live_attempt_{uuid4().hex}.json'
    audit = {'task_id': args.task_id, 'model': deepseek_model, 'provider': deepseek_base_url,
             'status': 'started', 'network_call_started': False}
    def save():
        attempt_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    async def complete(prompt):
        audit['network_call_started'] = True
        audit['request_characters'] = len(SYSTEM_PROMPT) + len(serialize_prompt(prompt))
        audit['request_character_scope'] = 'system_and_serialized_user_prompt'
        save()
        response = await deepseek_flash.create(
            [SystemMessage(content=SYSTEM_PROMPT),
             UserMessage(content=serialize_prompt(prompt), source='user')],
            json_output=True)
        audit['raw_response'] = response.content
        audit['finish_reason'] = response.finish_reason
        audit['usage'] = {'prompt_tokens': response.usage.prompt_tokens,
                          'completion_tokens': response.usage.completion_tokens}
        save()
        if not isinstance(response.content, str):
            raise ValueError('Expected text JSON')
        return json.loads(response.content)
    start = time.monotonic()
    try:
        state = await advance_investigation(args.model, args.run_id, 'diagnose', args.task_id, complete=complete)
        audit.update(status='completed', next_state=state['state'], revision=state['revision'],
                     claim_count=len(state['diagnosis']['claims']),
                     evidence_request_count=len(state['diagnosis']['evidence_requests']))
    except Exception as exc:
        # Do not log arbitrary SDK exception text: it can contain endpoint payloads.
        audit.update(status='failed', error_type=type(exc).__name__)
        if isinstance(exc, (ValueError, json.JSONDecodeError)):
            audit['validation_error'] = str(exc)
    finally:
        audit['elapsed_seconds'] = round(time.monotonic() - start, 3)
        save()
        await deepseek_flash.close()
    print(json.dumps({k: v for k, v in audit.items() if k != 'raw_response'}, ensure_ascii=True))
    print('audit_file=' + str(attempt_path.resolve()))
    return 0 if audit['status'] == 'completed' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--live', action='store_true')
    sys.exit(asyncio.run(run(parser.parse_args())))
