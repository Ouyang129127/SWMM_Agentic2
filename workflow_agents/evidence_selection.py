"""Task-scoped evidence selection and lossless transport, never top-N selection.

All source rows stay local. Global scalar statistics have their own IDs and
reproducible selectors; citing one does not mark its source rows as read.
"""
import copy
import hashlib
import json
import math
from collections import defaultdict


SELECTION_VERSION = 'task_evidence_v2'
EVENT_GROUPS = frozenset({
    'event_context', 'local_structure', 'local_process_series',
    'direct_source_composition', 'facilities_and_storage', 'surface_association',
})
SUMMARY_KEYS = ('object_type', 'metric_name', 'unit', 'calculation_method', 'threshold')


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _ordered(rows):
    return sorted(rows, key=lambda r: (r.get('object_type', ''), r.get('object_id', ''),
                                      r.get('event_id', ''), r['metric_name'], r['evidence_id']))


def _global_summaries(rows, model_name, run_id):
    groups = defaultdict(list)
    for row in rows:
        # Event facts are delivered directly with their event, not mixed with
        # whole-run indicators. Structured packages are not numerical scalars.
        if not row.get('event_id') and not isinstance(row.get('value'), (dict, list)):
            groups[tuple(row.get(key, '') for key in SUMMARY_KEYS)].append(row)
    summaries = []
    for group, sources in sorted(groups.items()):
        sources = _ordered(sources)
        numbers = [_number(r.get('value')) for r in sources]
        valid = [n for n in numbers if n is not None]
        selector = dict(zip(SUMMARY_KEYS, group))
        selector['event_id'] = ''
        # Exact source rows can be recovered from the frozen local snapshot.
        # The digest binds values as well as IDs; do not ship thousands of IDs.
        lineage = {'source': 'evidence_snapshot.json', 'selector': selector,
                   'source_rows_sha256': _digest(sources)}
        value = {'status': 'complete' if len(valid) == len(sources) else 'partial',
                 'source_metric': selector['metric_name'], 'source_object_type': selector['object_type'],
                 'source_row_count': len(sources),
                 'object_count': len({r['object_id'] for r in sources}),
                 'valid_count': len(valid), 'missing_or_nonfinite_count': len(sources) - len(valid),
                 'minimum': min(valid) if valid else None, 'maximum': max(valid) if valid else None,
                 'positive_value_count': sum(n > 0 for n in valid),
                 'zero_value_count': sum(n == 0 for n in valid),
                 'negative_value_count': sum(n < 0 for n in valid),
                 'interpretation': 'Counts describe this metric, not event counts or mechanism support.'}
        # Existing scalar timestamps sometimes denote an object's peak and
        # sometimes its observation interval. Preserve every distinct window
        # as a separate stratum, in a compact table rather than hundreds of
        # repeated evidence-row envelopes. Never sum or imply simultaneity.
        windows = defaultdict(list)
        for source in sources:
            windows[(source.get('time_start', ''), source.get('time_end', ''))].append(source)
        strata = []
        for (start, end), members in sorted(windows.items()):
            values = [_number(r.get('value')) for r in members]
            finite = [n for n in values if n is not None]
            strata.append([start, end, len(members), len({r['object_id'] for r in members}),
                           len(finite), len(members) - len(finite),
                           min(finite) if finite else None, max(finite) if finite else None,
                           sum(n > 0 for n in finite), sum(n == 0 for n in finite), sum(n < 0 for n in finite)])
        value['by_source_window'] = {
            'columns': ['start', 'end', 'rows', 'objects', 'valid', 'missing', 'minimum', 'maximum',
                        'positive', 'zero', 'negative'], 'records': strata}
        value['time_interpretation'] = (
            'Overall statistics compare saved scalar values across objects and their own source windows; '
            'not a simultaneous state or a common-event integral. Per-window statistics are retained below.')
        row = {'source_model': model_name, 'run_id': run_id, 'object_type': 'run',
               'object_id': run_id, 'event_id': '',
               'metric_name': f"summary:{selector['object_type']}:{selector['metric_name']}",
               'unit': selector['unit'],
               'calculation_method': 'grouped_scalar_min_max_counts_v1',
               'source_calculation_method': selector['calculation_method'],
               'source_threshold': selector['threshold'],
               'value': value, 'derivation': lineage}
        row['evidence_id'] = 'SUM_' + _digest(row)[:24]
        summaries.append(row)
    return summaries


def select_initial_evidence(rows, scope, model_name, run_id):
    """Return new summary rows, selected IDs, and explicit coverage/missingness.

    Selection is by task objects, event identity and hydraulic adjacency, never
    row count/order/rank. An oversized complete selection is refused at the
    request boundary rather than silently truncated here.
    """
    node, event = scope.get('node_id'), scope.get('event_id')
    event_rows = [r for r in rows if r.get('event_id')
                  and (not node or (r['object_type'] == 'node' and r['object_id'] == node))
                  and (not event or r['event_id'] == event)]
    events = sorted({r['event_id'] for r in event_rows})
    related_nodes, related_links = ({node} if node else set()), set()
    for row in event_rows:
        if row['metric_name'] == 'local_structure' and isinstance(row.get('value'), dict):
            related_nodes.update(row['value'].get('nodes', {}))
            related_links.update(row['value'].get('links', {}))

    # The builder emits the same event facts both in event_context and as CSV
    # scalars. Use the full event context only when identity, value and units
    # agree exactly. Conflicting or unavailable facts must remain visible.
    contexts = {(r['object_id'], r['event_id']): r['value'].get('event', {})
                for r in event_rows if r['metric_name'] == 'event_context' and isinstance(r.get('value'), dict)}
    duplicated, selected = [], []
    event_fields = {'event_peak_flooding': ('peak_flooding_Ls', 'L/s'),
                    'event_duration': ('duration_minutes', 'min'),
                    'event_estimated_volume': ('estimated_volume_m3', 'm3')}
    for r in event_rows:
        field, unit = event_fields.get(r['metric_name'], ('', ''))
        context = contexts.get((r['object_id'], r['event_id']), {})
        value = _number(r.get('value'))
        if (field and value is not None and value == _number(context.get(field))
                and r.get('unit') == unit
                and r.get('time_start') == context.get('start')
                and r.get('time_end') == context.get('end')
                and r.get('calculation_method') == context.get('integration_method')):
            duplicated.append(r['evidence_id'])
        else:
            selected.append(r)
    derived = []
    if node:
        for row in rows:
            if row.get('event_id'):
                continue
            if (row['object_type'] == 'node' and row['object_id'] in related_nodes
                    or row['object_type'] == 'link' and row['object_id'] in related_links):
                selected.append(row)
    else:
        derived = _global_summaries(rows, model_name, run_id)
        selected.extend(derived)
        # Preserve any run-level structured background already built.
        selected.extend(r for r in rows if not r.get('event_id')
                        and r['object_type'] == 'run' and isinstance(r.get('value'), dict))

    coverage = []
    for event_id in events:
        groups = {r['metric_name'] for r in event_rows if r['event_id'] == event_id}
        coverage.append({'event_id': event_id, 'missing_groups': sorted(EVENT_GROUPS - groups)})
    manifest = {
        'policy': SELECTION_VERSION, 'selection_basis': 'task_scope_and_event_hydraulic_context',
        'scope': scope['scope'], 'event_coverage': coverage,
        'duplicate_scalar_ids_available_on_request': sorted(duplicated),
        'related_nodes': sorted(related_nodes), 'related_links': sorted(related_links),
        'background_scope': 'Whole-run statistics remain background; do not substitute them for event values.',
        'limitations': ['Local packages cover only their saved process window; missing values remain unknown.',
                        'Global statistics are not individual-object or causal diagnosis.'],
    }
    if not events:
        manifest['limitations'].append(
            'No event evidence in the selected snapshot scope. Check event-count evidence/overview; '
            'absence of a package alone does not prove absence of flooding.')
    if node and not related_links:
        manifest['limitations'].append('No local connection package available; adjacent processes are not supplied.')
    return derived, sorted({r['evidence_id'] for r in selected}), manifest


def lookup_evidence(rows, request):
    allowed = {'tool', 'object_type', 'object_id', 'metric_name', 'event_id',
               'evidence_id', 'offset', 'reason'}
    if set(request) - allowed:
        raise ValueError('Unsupported evidence lookup parameters')
    offset = request.get('offset', 0)
    if type(offset) is not int or offset != 0:
        raise ValueError('Row offsets are no longer supported; query objects, events or metrics')
    filters = {key: request[key] for key in
               ('object_type', 'object_id', 'metric_name', 'event_id', 'evidence_id') if request.get(key)}
    if any(not isinstance(value, str) for value in filters.values()):
        raise ValueError('Evidence query filters must be strings')
    if request.get('tool') != 'unavailable' and not any(key in filters for key in ('object_id', 'event_id', 'metric_name', 'evidence_id')):
        raise ValueError('Evidence queries require an object, event, metric or evidence ID, not a whole-library scan')
    selected = _ordered([r for r in rows if all(r.get(k) == v for k, v in filters.items())])
    return {'rows': selected, 'total_matches': len(selected), 'selection': filters,
            'complete_match_set': True}


def _flatten(value, path=()):
    if isinstance(value, dict) and value:
        result = {}
        for key, item in value.items():
            result.update(_flatten(item, path + (key,)))
        return result
    return {path: value}


def encode_series(series):
    """Lossless field-path matrix: no temporal sampling or numerical rounding."""
    if not series:
        return series
    flat = [_flatten(record) for record in series]
    paths = sorted({path for record in flat for path in record})
    # A key may disappear or become a dictionary in irregular inputs. Retain
    # such inputs unchanged rather than risk an ambiguous path reconstruction.
    if any(path[:i] in paths for path in paths for i in range(1, len(path))):
        return series
    constants, varying = [], []
    for path in paths:
        if all(path in record and record[path] == flat[0].get(path) for record in flat):
            constants.append([list(path), flat[0][path]])
        else:
            varying.append(path)
    records = []
    for record in flat:
        records.append({'values': [record.get(path) for path in varying],
                        'absent': [i for i, path in enumerate(varying) if path not in record]})
    encoded = {'encoding': 'lossless_field_path_matrix_v1', 'fields': [list(p) for p in varying],
               'constants': constants, 'records': records}
    return encoded if len(_json(encoded)) < len(_json(series)) else series


def decode_series(value):
    """Reference decoder used to verify transport equivalence."""
    if isinstance(value, list):
        return copy.deepcopy(value)
    result = []
    for record in value['records']:
        tree = {}
        items = list(value['constants']) + [(path, record['values'][i])
                 for i, path in enumerate(value['fields']) if i not in record['absent']]
        for path, item in items:
            current = tree
            for key in path[:-1]:
                current = current.setdefault(key, {})
            current[path[-1]] = copy.deepcopy(item)
        result.append(tree)
    return result


def transport_evidence(rows):
    """Keep IDs and every value; only repeated process-series keys are factored."""
    result = copy.deepcopy(_ordered(rows))
    for row in result:
        if row['metric_name'] == 'local_process_series' and isinstance(row.get('value'), dict):
            series = row['value'].get('series')
            if isinstance(series, list):
                row['value']['series'] = encode_series(series)
    return result
