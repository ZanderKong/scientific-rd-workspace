"""Diagnostic reproductions: assertions confirm current defects, not desired behavior.

Run from api with PYTHONPATH=.:tests and an explicitly isolated TEST_DATABASE_URL.
The imported repository fixture drops that test database's public schema for each test.
Do not add these assertions unchanged to the normal regression suite.
"""

import uuid

from conftest import client, db, override_db  # noqa: F401


def post(c, path, payload):
    r = c.post('/api/v1' + path, json=payload, headers={'Idempotency-Key': str(uuid.uuid4())})
    assert r.status_code < 300, r.text
    return r.json()


def project(c):
    return post(c, '/project-records', {'project': {'title': 'audit project'}})['project']['id']


def obj(c, scope, title='audit object'):
    return post(c, '/objects', {'kind': 'research_object', 'title': title, 'project_scope_id': scope})


def setup_record(c, scope):
    definition = post(c, '/process-definitions', {'title': 'audit process', 'project_scope_id': scope})
    target = obj(c, scope)
    p, o = str(uuid.uuid4()), str(uuid.uuid4())
    payload = {'project_scope_id': scope, 'sample': {'title': 'audit sample', 'tags': ['sample']},
      'document': {'schema_version': 1, 'blocks': [{'type': 'paragraph', 'content': [
        {'type': 'processRef', 'props': {'occurrenceId': p}},
        {'type': 'objectRef', 'props': {'occurrenceId': o}}]}]},
      'occurrences': [
        {'occurrence_id': p, 'kind': 'process', 'target_id': definition['process_definition']['id'],
         'process_definition_version_id': definition['current_version']['id'], 'field_definitions': {}, 'values': {}},
        {'occurrence_id': o, 'kind': 'object', 'target_id': target['id'], 'field_definitions': {}, 'values': {},
         'binding': {'process_occurrence_id': p, 'direction': 'input', 'role': 'subject'}}]}
    record = post(c, '/sample-records', payload)
    return payload, record, target


def update(c, record, payload):
    return c.put('/api/v1/samples/' + record['sample']['id'] + '/record',
        headers={'If-Match': record['record_sha256']},
        json={'document': payload['document'], 'occurrences': payload['occurrences'],
              'base_record_sha256': record['record_sha256']})


def test_unbound_object_crosses_project(client):
    p1, p2 = project(client), project(client)
    target = obj(client, p2)
    o = str(uuid.uuid4())
    result = post(client, '/sample-records', {'project_scope_id': p1, 'sample': {'title': 'cross scope'},
        'document': {'schema_version': 1, 'blocks': [{'type': 'paragraph', 'content': [{'type': 'objectRef', 'props': {'occurrenceId': o}}]}]},
        'occurrences': [{'occurrence_id': o, 'kind': 'object', 'target_id': target['id']}]})
    assert result['occurrences'][0]['object']['project_scope_id'] == p2


def test_replace_object_keeps_wrong_binding_target(client):
    scope = project(client)
    payload, record, target = setup_record(client, scope)
    replacement = obj(client, scope, 'replacement')
    payload['occurrences'][1]['target_id'] = replacement['id']
    r = update(client, record, payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['occurrences'][1]['target_id'] == replacement['id']
    assert body['occurrences'][0]['execution']['object_bindings'][0]['research_object_id'] == target['id']


def test_restore_saved_deleted_process_hits_unique_constraint(client):
    scope = project(client)
    payload, record, target = setup_record(client, scope)
    empty = {'document': {'schema_version': 1, 'blocks': []}, 'occurrences': []}
    r = update(client, record, empty)
    assert r.status_code == 200, r.text
    restored = update(client, r.json(), payload)
    assert restored.status_code >= 400, restored.text
    print('restore response:', restored.status_code, restored.text[:350])


def test_related_rename_changes_sample_token_without_sample_revision(client):
    scope = project(client)
    payload, record, target = setup_record(client, scope)
    sample_path = '/api/v1/objects/' + record['sample']['id'] + '/revisions'
    old_revisions = client.get(sample_path).json()
    r = client.patch('/api/v1/objects/' + target['id'], json={'title': 'renamed elsewhere'})
    assert r.status_code == 200, r.text
    current = client.get('/api/v1/samples/' + record['sample']['id'] + '/record').json()
    assert current['record_sha256'] != record['record_sha256']
    assert client.get(sample_path).json() == old_revisions


def test_generic_patch_breaks_document_occurrence_alignment(client):
    scope = project(client)
    payload, record, target = setup_record(client, scope)
    r = client.patch('/api/v1/objects/' + record['sample']['id'], json={'content_document': []})
    assert r.status_code == 200, r.text
    current = client.get('/api/v1/samples/' + record['sample']['id'] + '/record').json()
    assert current['document']['blocks'] == []
    assert len(current['occurrences']) == 2


def test_view_accepts_representation_absent_from_pinned_revision(client):
    scope = project(client)
    data = post(client, '/data-records', {'project_scope_id': scope, 'data': {'title': 'source'}})
    old_revision = client.get('/api/v1/objects/' + data['data']['id'] + '/revisions').json()[-1]
    rep = post(client, '/data/' + data['data']['id'] + '/representations',
        {'kind': 'description', 'name': 'new observation', 'inline_payload_jsonb': {'text': 'later'}})
    assert all(item['id'] != rep['id'] for item in old_revision['snapshot_jsonb']['representations'])
    view = post(client, '/views', {'project_scope_id': scope, 'title': 'inconsistent manifest',
        'data_refs': [{'data_id': data['data']['id'], 'data_revision_id': old_revision['id'], 'representation_ids': [rep['id']]}]})
    assert view['data_refs'][0]['representation_ids'] == [rep['id']]


def test_view_update_does_not_require_revision_token(client):
    scope = project(client)
    view = post(client, '/views', {'project_scope_id': scope, 'title': 'view'})
    r = client.put('/api/v1/views/' + view['view']['id'], json={'title': 'unconditional overwrite'})
    assert r.status_code == 200, r.text


def test_removing_process_leaves_object_binding_unsaveable(client):
    scope = project(client)
    payload, record, target = setup_record(client, scope)
    payload['document']['blocks'][0]['content'] = payload['document']['blocks'][0]['content'][1:]
    payload['occurrences'] = payload['occurrences'][1:]
    r = update(client, record, payload)
    assert r.status_code >= 400, r.text
    print('dangling binding response:', r.status_code, r.text[:350])


def test_old_view_source_can_be_deleted_after_repin(client):
    scope = project(client)
    data = post(client, '/data-records', {'project_scope_id': scope, 'data': {'title': 'historical source'}})
    revision = client.get('/api/v1/objects/' + data['data']['id'] + '/revisions').json()[-1]
    view = post(client, '/views', {'project_scope_id': scope, 'title': 'view history',
        'data_refs': [{'data_id': data['data']['id'], 'data_revision_id': revision['id']}]})
    r = client.put('/api/v1/views/' + view['view']['id'], json={'data_refs': []}, headers={'If-Match': view['record_sha256']})
    assert r.status_code == 200, r.text
    deleted = client.delete('/api/v1/objects/' + data['data']['id'])
    assert deleted.status_code == 204, deleted.text
    revisions = client.get('/api/v1/views/' + view['view']['id'] + '/revisions').json()
    assert revisions[0]['snapshot_jsonb']['data_refs'][0]['data_revision_id'] == revision['id']
    assert client.get('/api/v1/objects/' + data['data']['id']).status_code == 404


def test_data_finalize_has_no_producer_readback(client):
    scope = project(client)
    payload, sample, target = setup_record(client, scope)
    draft = post(client, '/data-drafts', {'project_scope_id': scope, 'content': {
        'title': 'acquisition', 'document': payload['document'], 'occurrences': payload['occurrences']}})
    result = post(client, '/data-drafts/' + draft['id'] + '/finalize', {'base_record_sha256': draft['record_sha256']})
    assert len(result['data']['content_document']) == 1
    assert 'occurrences' not in result
    executions = client.get('/api/v1/data/' + result['data']['id'] + '/process-executions').json()
    assert executions == []


def test_empty_slots_missing_from_table_catalog(client):
    scope = project(client)
    payload, sample, target = setup_record(client, scope)
    payload['occurrences'][0]['field_definitions'] = {'fields': [{'key': 'reading', 'label': 'Reading', 'value_type': 'number'}]}
    r = update(client, sample, payload)
    assert r.status_code == 200, r.text
    result = post(client, '/record-tables/query', {'project_scope_id': scope, 'record_kind': 'sample'})
    assert result['total'] == 1 and result['columns'] == []


def test_changeset_applied_result_cannot_be_replayed(client):
    scope = project(client)
    cs = post(client, '/change-sets/propose', {'project_scope_id': scope,
        'operation_kind': 'create_research_object', 'source_client_name': 'audit',
        'request_payload_jsonb': {'kind': 'research_object', 'title': 'replay', 'project_scope_id': scope}})
    r = client.post('/api/v1/change-sets/' + cs['id'] + '/apply')
    assert r.status_code == 200, r.text
    replay = client.post('/api/v1/change-sets/' + cs['id'] + '/apply')
    assert replay.status_code >= 400, replay.text
    print('ChangeSet replay response:', replay.status_code, replay.text[:350])


def test_measure_100_refs_20_fields_read_queries(client, db):
    import time
    from sqlalchemy import event

    scope = project(client)
    fields = {'fields': [{'key': f'value_{i}', 'label': f'Value {i}', 'value_type': 'number'} for i in range(20)]}
    definition = post(client, '/process-definitions', {'title': 'stress process', 'project_scope_id': scope,
        'execution_field_definitions': fields})
    ids = [str(uuid.uuid4()) for _ in range(100)]
    payload = {'project_scope_id': scope, 'sample': {'title': '100 refs', 'tags': ['sample']},
        'document': {'schema_version': 1, 'blocks': [{'type': 'paragraph', 'content': [
            {'type': 'processRef', 'props': {'occurrenceId': identity}} for identity in ids]}]},
        'occurrences': [{'occurrence_id': identity, 'kind': 'process',
            'target_id': definition['process_definition']['id'],
            'process_definition_version_id': definition['current_version']['id'],
            'field_definitions': fields, 'values': {f'value_{i}': i for i in range(20)}} for identity in ids]}
    record = post(client, '/sample-records', payload)
    statements = []
    def count(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
    db.expire_all()
    event.listen(db.bind, 'before_cursor_execute', count)
    started = time.perf_counter()
    try:
        r = client.get('/api/v1/samples/' + record['sample']['id'] + '/record')
    finally:
        elapsed = time.perf_counter() - started
        event.remove(db.bind, 'before_cursor_execute', count)
    assert r.status_code == 200, r.text
    print(f'100 Ref x 20 fields GET: {len(statements)} SQL statements, {elapsed:.3f}s, {len(r.content)} bytes; diagnostic only, not fixed-environment p95')
