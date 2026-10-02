"""Global/node report without adding causes or selecting an unrelated point."""
import csv
import json
import re

from .reference_checks import sha256_file
from .schemas import artifacts_for_run
from .state import resolve_run_root


def select_scope(message, node_ids, node_id=None, event_id=None):
    if node_id is not None and node_id not in node_ids:
        raise ValueError(f'Unknown node: {node_id}')
    # Chinese text commonly touches identifiers, e.g. 分析P6; do not use \w here.
    mentioned = [n for n in sorted(node_ids) if re.search(r'(?<![A-Za-z0-9_-])' + re.escape(n) + r'(?![A-Za-z0-9_-])', message)]
    if node_id:
        mentioned = [node_id]
    if len(mentioned) > 1:
        raise ValueError('Multiple nodes specified; please select a node or request a global report')
    if not mentioned and re.search(r'(?:节点|node)\s*[:：]?\s*[A-Za-z0-9_-]+', message, re.I):
        raise ValueError('Requested node could not be matched; specify a valid node ID')
    selected = mentioned[0] if mentioned else None
    found = re.findall(r'([A-Za-z0-9_-]+:E\d+)', message)
    if len(set(found)) > 1:
        raise ValueError('Multiple events specified')
    event_id = event_id or (found[0] if found else None)
    if event_id:
        event_node = event_id.rsplit(':E', 1)[0]
        if event_node not in node_ids or (selected and selected != event_node):
            raise ValueError('Event and node do not match')
        selected = event_node
    if selected is None and any(x in message for x in ('该节点', '这个节点', '该点', '这一点', '该事件', '这次冒溢')):
        raise ValueError('Specify the node/event referenced by this follow-up')
    return {'scope': 'event' if event_id else 'node' if selected else 'global',
            'node_id': selected, 'event_id': event_id, 'original_question': message}


def build_scoped_report(model_name, run_id, message='', node_id=None, event_id=None):
    root = resolve_run_root(model_name, run_id)
    a = artifacts_for_run(root)
    diagnosis = json.loads(a.diagnosis_claims.read_text(encoding='utf-8'))
    verification = json.loads(a.verification_report.read_text(encoding='utf-8'))
    if verification.get('verification_scope') != 'reference_traceability_only':
        raise ValueError('Please rerun reference verification; legacy checks are not this report contract')
    for data in (diagnosis, verification):
        if data.get('run_id') != root.name or data.get('model_name') != root.parents[1].name:
            raise ValueError('Report inputs belong to another model/run')
    hashes = verification.get('input_hashes', {})
    for key, path in [('evidence_table', a.evidence_table), ('diagnosis_claims', a.diagnosis_claims)]:
        if hashes.get(key) != sha256_file(path):
            raise ValueError('Evidence or diagnosis changed; rerun reference verification')
    with a.evidence_table.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    catalog_path = root / 'evidence' / 'overflow_events.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.exists() else None
    if catalog and (catalog.get('run_id') != root.name or catalog.get('model_name') != root.parents[1].name):
        raise ValueError('Event catalog belongs to another run')
    nodes = {r['object_id'] for r in rows if r['object_type'] == 'node'}
    task = select_scope(message, nodes, node_id, event_id)
    events = catalog['events'] if catalog else []
    events = [e for e in events if not task['node_id'] or e['node_id'] == task['node_id']]
    if task['event_id']:
        events = [e for e in events if e['event_id'] == task['event_id']]
        if not events:
            raise ValueError('Event not found in this run catalog')
    statuses = {c['claim_id']: c['verification_status'] for c in verification['claim_checks']}
    claims = [c for c in diagnosis.get('claims', []) if statuses.get(c['claim_id']) == 'references_verified']
    if task['node_id']:
        claims = [c for c in claims if c.get('object_type') == 'node' and str(c.get('object_id')) == task['node_id']]
    if task['event_id']:
        claims = [c for c in claims if c.get('event_id') == task['event_id']]
    title = '全局模拟评估报告' if task['scope'] == 'global' else f"节点 {task['node_id']} 分析报告"
    lines = [f'# {title}', '', f'运行：`{root.name}`', f"原问题：{message or '全局评估'}", '',
             '核查范围：EvidenceID引用可追溯性；不代表水力解释或因果关系已验证。', '',
             '## 冒溢事件（保存时序精度）', '']
    if catalog is None:
        lines.append('尚未生成逐次事件目录，请先更新证据构建；不据此判断没有冒溢。')
    elif not events:
        lines.append('所选范围内，保存记录未识别到正溢流段。')
    for e in events:
        lines.append(f"- {e['event_id']}：{e['start']} 至 {e['end']}；持续 {e['duration_minutes']:.3g} min；"
                     f"峰值 {e['peak_flooding_Ls']:.4g} L/s；左端采样积分估计 {e['estimated_volume_m3']:.4g} m³。"
                     + ('末端截断，终止时间未被完整观察。' if e['right_censored'] else ''))
    lines += ['', '## 诊断记录（仅引用核查通过项）', '']
    if not claims:
        lines.append('当前范围没有可发布的已核查诊断记录，需要DiagnosisAgent补充或修订；不替换为其他对象。')
    for c in claims:
        lines.append(f"- [{c['claim_id']}] {c['claim_text']}（EvidenceID：{', '.join(c['evidence_ids'])}）")
    lines += ['', '## 已有指标摘要', '']
    selected_rows = [r for r in rows if (not task['node_id'] or (r['object_type'] == 'node' and r['object_id'] == task['node_id']))]
    if task['event_id']:
        lines.append('不将全程指标代入单次事件；本事件事实见上方事件目录。')
    else:
        for kind, metric in [('cell', 'max_depth'), ('node', 'total_flooding_volume'), ('link', 'max_fullness')]:
            candidates = [r for r in selected_rows if r['object_type'] == kind and r['metric_name'] == metric]
            candidates.sort(key=lambda r: float(r['value']), reverse=True)
            for r in candidates[:5]:
                lines.append(f"- {kind} {r['object_id']}：{metric}={r['value']} {r['unit']} [{r['evidence_id']}]；按该指标降序展示前5项，不代表因果排名。")
    needs_diagnosis = not claims or any(x in message for x in ('为什么', '主因', '次因', '原因', '削减', '扩容'))
    if needs_diagnosis:
        lines += ['', '后续请求：请DiagnosisAgent结合原问题调查或确认上述记录是否足以回答；本报告不新增原因或措施效果。']
    return {'schema_name': 'swmm_ca2d_report', 'schema_version': '0.2', 'model_name': root.parents[1].name,
            'run_id': root.name, 'task_context': task, 'report_type': task['scope'],
            'next_action': 'diagnosis_review_requested' if needs_diagnosis else 'await_user',
            'markdown': '\n'.join(lines)}
