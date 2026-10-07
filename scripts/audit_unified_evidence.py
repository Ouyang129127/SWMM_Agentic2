"""Rebuild two recorded runs in temporary copies; never simulate or call a model."""
import argparse
import asyncio
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow_agents.evidence_builder import build_evidence_for_run
from workflow_agents.evidence_package import load_package
from workflow_agents.evidence_selection import EVENT_GROUPS
from workflow_agents.event_packages import _table, read_saved_binary
from workflow_agents.investigation import advance_investigation, build_diagnosis_prompt, serialize_prompt, SYSTEM_PROMPT
from workflow_agents.reference_checks import sha256_file

PROJECT = Path(__file__).resolve().parents[1]
RUNS = ('chicago_single_event__baseline__20260927_192515', 'chicago_triple_event__baseline__20260927_203812')


async def audit():
    results = []
    for run_id in RUNS:
        original = PROJECT / 'models/urban_drainage/runs' / run_id
        watched = [p for folder in ('evidence', 'diagnosis_tasks') for p in (original / folder).rglob('*') if p.is_file()]
        raw_names = ['summary.json', 'swmm/model_with_event.inp', 'swmm/model.out', 'swmm/nodes.tsv',
                     'swmm/links.tsv', 'ca2d/surface_depth.tsv', 'rainfall_event.txt']
        watched.extend(original / name for name in raw_names if (original / name).is_file())
        before = {str(p.relative_to(original)): sha256_file(p) for p in watched}
        # Historical files are read for regression comparison only. Runtime has no legacy reader.
        old_events = json.loads((original / 'evidence/first_pass_evidence.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='swmm-unified-audit-') as temp:
            root = Path(temp) / 'urban_drainage/runs' / run_id
            for name in raw_names:
                source = original / name
                if source.is_file():
                    destination = root / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
            with patch('workflow_agents.evidence_builder.resolve_run_root', return_value=root):
                built = build_evidence_for_run('urban_drainage', run_id)
            package = load_package(root, verify_sources=True)
            event_rows = [r for r in package['evidence_rows'] if r.get('event_id')]
            old_values = {(r['event_id'], r['metric_name']): r['value'] for r in old_events['evidence_rows']}
            new_values = {(r['event_id'], r['metric_name']): r['value'] for r in event_rows}
            assert set(new_values) == set(old_values)
            raw_nodes = _table(root / 'swmm/nodes.tsv', 'node_id', ['depth_m', 'flooding_Ls'])
            raw_links = _table(root / 'swmm/links.tsv', 'link_id', ['flow_Ls', 'depth_m'])
            required = {n for r in event_rows if r['metric_name'] == 'local_structure' for n in r['value']['nodes']}
            native, _ = read_saved_binary(root / 'swmm/model.out', required)
            scopes = []
            for index in package['packages']:
                assert {r['metric_name'] for r in event_rows if r['evidence_id'] in index['evidence_ids']} == EVENT_GROUPS
                event_id = index['event_id']
                for metric in ('event_context', 'direct_source_composition', 'surface_association'):
                    assert new_values[event_id, metric] == old_values[event_id, metric]
                structure = new_values[event_id, 'local_structure']
                for kind in ('nodes', 'links'):
                    for key, value in old_values[event_id, 'local_structure'][kind].items():
                        assert structure[kind][key] == value
                old_series = old_values[event_id, 'local_process_series']['series']
                new_series = new_values[event_id, 'local_process_series']['series']
                assert [r['time'] for r in new_series] == [r['time'] for r in old_series]
                for old, new in zip(old_series, new_series):
                    for kind in ('nodes', 'links'):
                        for key, values in old[kind].items():
                            for field, value in values.items():
                                assert new[kind][key][field] == value
                    for key in ('signed_towards_node_Ls', 'positive_source_sum_Ls', 'source_sum_minus_total_Ls'):
                        assert new[key] == old[key]
                    assert set(new['nodes']) == set(structure['nodes'])
                    assert set(new['links']) == set(structure['links'])
                    for key, values in new['nodes'].items():
                        saved = raw_nodes.get(key, {}).get(new['time'], {})
                        assert values['depth_m'] == saved.get('depth_m')
                        assert values['flooding_Ls'] == saved.get('flooding_Ls')
                        for field in ('total_inflow_Ls', 'lateral_inflow_Ls'):
                            assert values[field] == native.get(key, {}).get(new['time'], {}).get(field)
                        head = native.get(key, {}).get(new['time'], {}).get('head_m')
                        if head is None and saved.get('depth_m') is not None and structure['nodes'][key] is not None:
                            invert = structure['nodes'][key]['invert_elevation']
                            head = invert + saved['depth_m'] if invert is not None else None
                        assert values['head_m'] == head
                    for key, values in new['links'].items():
                        saved = raw_links.get(key, {}).get(new['time'], {})
                        assert values['signed_model_flow_Ls'] == saved.get('flow_Ls')
                        assert values['depth_m'] == saved.get('depth_m')
                        link = structure['links'][key]
                        a, b = new['nodes'][link['from_node']]['head_m'], new['nodes'][link['to_node']]['head_m']
                        assert values['from_minus_to_head_m'] == (a - b if a is not None and b is not None else None)
                scope = structure['topology_scope']
                scopes.append({'event_id': event_id, 'node_id': index['node_id'],
                               'old_node_count': len(old_values[event_id, 'local_structure']['nodes']),
                               'old_link_count': len(old_values[event_id, 'local_structure']['links']),
                               'new_node_count': len(structure['nodes']), 'new_link_count': len(structure['links']),
                               'boundary_nodes': scope['boundary_nodes'], 'traces': scope['traces'],
                               'status': scope['status']})
            prompts = []
            for question in ('全局洪涝诊断', '分析P6', '分析P6:E001'):
                if question.endswith(':E001') and not package['overview']['event_count']:
                    continue
                with patch('workflow_agents.investigation.resolve_run_root', return_value=root):
                    state = await advance_investigation('urban_drainage', run_id, question=question)
                folder = root / 'diagnosis_tasks' / state['task_id']
                snapshot = json.loads((folder / 'evidence_snapshot.json').read_text(encoding='utf-8'))
                prompt = build_diagnosis_prompt(state, snapshot)
                assert json.dumps({r['evidence_id']: r for r in prompt['visible_evidence']}, sort_keys=True) == json.dumps({
                    r['evidence_id']: r for r in snapshot if r['evidence_id'] in state['visible_ids']}, sort_keys=True)
                sent_rows = prompt['visible_evidence']
                source = {r['evidence_id']: r for r in snapshot}
                sample_count = 0
                for sent in sent_rows:
                    if sent['metric_name'] == 'local_process_series':
                        series = sent['value']['series']
                        assert isinstance(series, list)
                        assert series == source[sent['evidence_id']]['value']['series']
                        sample_count += len(series)
                prompts.append({'question': question, 'visible_rows': len(sent_rows),
                                'request_characters': len(SYSTEM_PROMPT) + len(serialize_prompt(prompt)),
                                'component_characters': {k: len(serialize_prompt(v)) for k, v in prompt.items()},
                                'transport_status': 'no_application_limit',
                                'transport_format': 'original_json_rows',
                                'selected_records_equal_to_snapshot': True,
                                'event_count': len(state['evidence_selection']['event_coverage']),
                                'process_sample_count': sample_count,
                                'rainfall_visible': 'CTX_RAINFALL' in state['visible_ids']})
            p6 = {r['metric_name']: r['value'] for r in package['evidence_rows'] if r['object_type'] == 'node' and r['object_id'] == 'P6' and not r.get('event_id')}
            results.append({'run_id': run_id, 'package_rows': len(package['evidence_rows']),
                            'event_count': built['event_count'], 'overflow_node_count': built['overflow_node_count'],
                            'event_facts_and_direct_composition_unchanged': True,
                            'historical_local_process_preserved': True,
                            'expanded_process_matches_saved_outputs': True, 'topology_scopes': scopes,
                            'evidence_files': sorted(p.name for p in (root / 'evidence').iterdir()),
                            'P6_scalar_facts': p6, 'prompts': prompts})
        assert before == {str(p.relative_to(original)): sha256_file(p) for p in watched}
        results[-1]['original_files_unchanged'] = True
    return {'external_llm_calls': 0, 'simulations': 0, 'cases': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = asyncio.run(audit())
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': args.output, 'cases': [
        {k: case[k] for k in ('run_id', 'event_count', 'original_files_unchanged', 'prompts')}
        for case in result['cases']]}, ensure_ascii=False))
