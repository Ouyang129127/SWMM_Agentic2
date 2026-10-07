"""Generate/reuse HTML for a verified diagnosis, without rerunning simulation."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow_agents.investigation import advance_investigation
from workflow_agents.investigation_flow import load_active_task


async def run(args):
    state=load_active_task(args.model,args.run,args.task)
    if state is None:raise ValueError('No active diagnosis task')
    action='report' if state['state']=='ready_for_report' else 'display_report'
    result=await advance_investigation(args.model,args.run,action,state['task_id'])
    report=result['display_report']
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']=='completed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True);parser.add_argument('--run',required=True)
    parser.add_argument('--task',default='')
    sys.exit(asyncio.run(run(parser.parse_args())))
