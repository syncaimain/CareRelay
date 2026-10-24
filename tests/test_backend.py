import json
import asyncio
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import ai
from backend.main import app
from backend.schemas import Extraction, SuggestedItem
from backend.db import connect
from backend.import_jobs import prepare_import, save_import


@pytest.fixture
def client(monkeypatch):
    # pytest's mode-0700 temporary directories are inaccessible to this Windows
    # sandbox token. Use unique files under an inherited-permission data folder.
    path = Path('data') / ('test-' + uuid.uuid4().hex + '.sqlite3')
    path.parent.mkdir(exist_ok=True)
    monkeypatch.setenv('CARERELAY_DB', str(path))
    monkeypatch.setenv('CARERELAY_DEMO', 'true')
    monkeypatch.setenv('CARERELAY_IMPORT_ENGINE', 'inline')
    with TestClient(app) as client:
        yield client
    path.unlink(missing_ok=True)


def circle(client):
    return client.post('/api/demo').json()['profiles']


def auth(profile):
    return {'Authorization': 'Bearer ' + profile['token']}


def suggestion(source_id=1, **updates):
    values = {'source_id': source_id, 'quote': 'Alex will book transport on 2026-10-26 at 09:00.',
              'title': 'Book transport', 'kind': 'transport', 'due_at': '2026-10-26T09:00:00+05:00',
              'owner': 'Alex', 'location': None, 'uncertainty': None}
    values.update(updates)
    return SuggestedItem(**values)


def install_extractor(monkeypatch, **updates):
    async def extract(source, caregivers, existing):
        return Extraction(items=[suggestion(source_id=source['id'], **updates)])
    monkeypatch.setattr(ai, 'extract', extract)


def imported(client, profile, **updates):
    payload = {'text': 'Alex will book transport on 2026-10-26 at 09:00.',
               'reference_at': '2026-10-24T09:00:00+05:00'}
    payload.update(updates)
    response = client.post('/api/imports', json=payload, headers=auth(profile))
    assert response.status_code == 202, response.text
    return response.json()


def state(client, profile):
    response = client.get('/api/state', headers=auth(profile))
    assert response.status_code == 200
    return response.json()


def approve(client, profile, task, **updates):
    body = {'decision': 'approve', 'title': task['title'], 'due_at': task['due_at'],
            'owner_id': task['owner_id'], 'location': task['location'], 'uncertainty': '',
            'acknowledge_uncertainty': True, 'version': task['version']}
    body.update(updates)
    return client.post(f"/api/tasks/{task['id']}/review", json=body, headers=auth(profile))


def test_requires_auth(client):
    assert client.get('/api/state').status_code == 401
    assert client.get('/api/state', headers={'Authorization': 'Bearer invalid'}).status_code == 401


def test_end_to_end_approval_consent_and_completion(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    imported(client, alex)
    initial = state(client, alex)
    task = initial['tasks'][0]
    assert task['status'] == 'suggested'
    assert task['quote'] in initial['sources'][0]['text']
    assert approve(client, alex, task).status_code == 200
    approved = state(client, alex)
    assert approved['tasks'][0]['accepted'] == 0
    assert approved['conflicts'][0]['type'] == 'transport'
    assert client.post(f"/api/tasks/{task['id']}/done", headers=auth(alex)).status_code == 403
    assert client.post(f"/api/tasks/{task['id']}/accept", headers=auth(alex)).status_code == 200
    assert state(client, alex)['conflicts'] == []
    assert client.post(f"/api/tasks/{task['id']}/done", headers=auth(alex)).status_code == 200
    assert state(client, alex)['tasks'][0]['status'] == 'done'


def test_duplicate_import_does_not_repeat_model_call(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    first = imported(client, alex)
    second = imported(client, alex)
    assert second['duplicate'] is True
    assert first['job_id'] == second['job_id']
    assert len(state(client, alex)['tasks']) == 1


def test_invalid_quote_fails_atomically(client, monkeypatch):
    install_extractor(monkeypatch, quote='This quote is not in the source.')
    alex = circle(client)[0]
    job = imported(client, alex)
    assert state(client, alex)['tasks'] == []
    result = client.get('/api/jobs/' + job['job_id'], headers=auth(alex)).json()
    assert result['status'] == 'failed'
    assert 'unverifiable' in result['error']


def test_private_sources_and_jobs_do_not_leak(client, monkeypatch):
    install_extractor(monkeypatch)
    alex, maya, *_ = circle(client)
    job = imported(client, alex, visibility='private')
    assert len(state(client, alex)['tasks']) == 1
    assert state(client, maya)['tasks'] == []
    assert state(client, maya)['sources'] == []
    assert state(client, maya)['audit'] == []
    assert client.get('/api/jobs/' + job['job_id'], headers=auth(maya)).status_code == 404


def test_circle_boundary(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    other = circle(client)[0]
    imported(client, alex)
    assert state(client, other)['tasks'] == []
    task = state(client, alex)['tasks'][0]
    assert approve(client, other, task).status_code == 404


def test_nonreviewer_and_wrong_owner_cannot_act(client, monkeypatch):
    install_extractor(monkeypatch)
    alex, maya, *_ = circle(client)
    imported(client, alex)
    task = state(client, alex)['tasks'][0]
    assert approve(client, maya, task).status_code == 403
    assert approve(client, alex, task).status_code == 200
    assert client.post(f"/api/tasks/{task['id']}/accept", headers=auth(maya)).status_code == 403


def test_review_requires_acknowledgement_and_current_version(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    imported(client, alex)
    task = state(client, alex)['tasks'][0]
    assert approve(client, alex, task, acknowledge_uncertainty=False).status_code == 422
    assert approve(client, alex, task).status_code == 200
    assert approve(client, alex, task).status_code == 409


def test_availability_conflicts(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    imported(client, alex)
    task = state(client, alex)['tasks'][0]
    assert approve(client, alex, task).status_code == 200
    response = client.post('/api/availability', headers=auth(alex), json={
        'start_at': '2026-10-26T08:00:00+05:00', 'end_at': '2026-10-26T11:00:00+05:00'})
    assert response.status_code == 200
    assert any(c['type'] == 'availability' for c in state(client, alex)['conflicts'])


def test_reschedule_cancels_original_and_resets_consent(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    imported(client, alex)
    first = state(client, alex)['tasks'][0]
    assert approve(client, alex, first).status_code == 200
    client.post(f"/api/tasks/{first['id']}/accept", headers=auth(alex))
    install_extractor(monkeypatch, quote='Move transport to 2026-10-27 at 09:00.',
                      change='reschedule', related_task_id=first['id'], due_at='2026-10-27T09:00:00+05:00', owner=None)
    imported(client, alex, text='Move transport to 2026-10-27 at 09:00.')
    second = state(client, alex)['tasks'][0]
    assert approve(client, alex, second).status_code == 200
    tasks = state(client, alex)['tasks']
    assert tasks[1]['status'] == 'cancelled'
    assert tasks[0]['status'] == 'confirmed'
    assert tasks[0]['accepted'] == 0


def test_handoff_is_grounded_and_stale_plan_cannot_be_approved(client, monkeypatch):
    from backend.schemas import DraftSelection
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    imported(client, alex)
    task = state(client, alex)['tasks'][0]
    approve(client, alex, task)
    async def select(tasks, day):
        return DraftSelection(task_ids=[tasks[0]['id']])
    monkeypatch.setattr(ai, 'select_brief_tasks', select)
    response = client.post('/api/drafts', json={'day': '2026-10-26'}, headers=auth(alex))
    assert response.status_code == 200, response.text
    draft = response.json()
    assert f"source #{task['source_id']}" in draft['text']
    assert 'not accepted' in draft['text']
    assert 'Unresolved' in draft['text']
    client.post(f"/api/tasks/{task['id']}/accept", headers=auth(alex))
    assert client.post(f"/api/drafts/{draft['id']}/approve", headers=auth(alex)).status_code == 409


def test_timezone_required_and_unknown_owner_stays_unassigned():
    source = {'id': 1, 'text': 'Alex will book transport on 2026-10-26 at 09:00.', 'reference_at': '2026-10-24T09:00:00+05:00'}
    item = suggestion(due_at=datetime(2026, 10, 26, 9), owner='Sam')
    result = ai.validate_evidence(item, source, [{'id': 1, 'name': 'Alex'}, {'id': 2, 'name': 'Sam'}], [])
    assert result['due_at'] is None
    assert result['owner_id'] is None


def test_model_timezone_drift_requires_manual_correction():
    source = {'id': 1, 'text': 'Alex will book transport on 2026-10-26 at 09:00.', 'reference_at': '2026-10-24T09:00:00+05:00'}
    result = ai.validate_evidence(suggestion(due_at='2026-10-26T09:00:00+00:00'), source, [{'id': 1, 'name': 'Alex'}], [])
    assert result['due_at'] is None
    assert 'timezone differs' in result['uncertainty']


def test_reviewer_can_correct_model_category(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    imported(client, alex)
    task = state(client, alex)['tasks'][0]
    assert approve(client, alex, task, kind='confirmation').status_code == 200
    assert state(client, alex)['tasks'][0]['kind'] == 'confirmation'


def test_permission_revocation(client, monkeypatch):
    install_extractor(monkeypatch)
    alex, maya, *_ = circle(client)
    assert client.patch(f"/api/caregivers/{maya['id']}/permissions", headers=auth(alex), json={
        'can_import': False, 'can_review': False, 'can_brief': False}).status_code == 200
    assert client.post('/api/imports', headers=auth(maya), json={
        'text': 'Book a taxi tomorrow.', 'reference_at': '2026-10-24T09:00:00+05:00'}).status_code == 403


def test_demo_disabled(client, monkeypatch):
    monkeypatch.setenv('CARERELAY_DEMO', 'false')
    assert client.post('/api/demo').status_code == 403


def test_cancellation_preserves_history(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    imported(client, alex)
    first = state(client, alex)['tasks'][0]
    assert approve(client, alex, first).status_code == 200
    install_extractor(monkeypatch, quote='Cancel transport on 2026-10-26 at 09:00.',
                      change='cancel', related_task_id=first['id'], owner=None)
    imported(client, alex, text='Cancel transport on 2026-10-26 at 09:00.')
    cancel = state(client, alex)['tasks'][0]
    assert approve(client, alex, cancel).status_code == 200
    tasks = state(client, alex)['tasks']
    assert len(tasks) == 2
    assert all(t['status'] == 'cancelled' for t in tasks)
    assert tasks[0]['related_task_id'] == first['id']
    assert tasks[1]['quote'] == first['quote']


def test_private_change_cannot_cancel_shared_task(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    imported(client, alex)
    first = state(client, alex)['tasks'][0]
    assert approve(client, alex, first).status_code == 200
    install_extractor(monkeypatch, quote='Cancel transport on 2026-10-26 at 09:00.',
                      change='cancel', related_task_id=first['id'], owner=None)
    imported(client, alex, text='Cancel transport on 2026-10-26 at 09:00.', visibility='private')
    cancel = state(client, alex)['tasks'][0]
    assert approve(client, alex, cancel).status_code == 422
    assert state(client, alex)['tasks'][1]['status'] == 'confirmed'


def test_other_circle_owner_is_rejected(client, monkeypatch):
    install_extractor(monkeypatch)
    alex = circle(client)[0]
    other = circle(client)[0]
    imported(client, alex)
    task = state(client, alex)['tasks'][0]
    assert approve(client, alex, task, owner_id=other['id']).status_code == 422
    assert approve(client, alex, task, owner_id=0).status_code == 422
    assert state(client, alex)['tasks'][0]['status'] == 'suggested'


def test_inaccessible_model_reference_is_rejected_before_writing(client, monkeypatch):
    install_extractor(monkeypatch, change='cancel', related_task_id=99999)
    alex = circle(client)[0]
    job = imported(client, alex)
    assert state(client, alex)['tasks'] == []
    result = client.get('/api/jobs/' + job['job_id'], headers=auth(alex)).json()
    assert result['status'] == 'failed'


def test_temporal_outbox_survives_service_outage_and_dispatch_gap(client, monkeypatch):
    from types import SimpleNamespace
    from temporalio.client import WorkflowExecutionStatus
    from temporalio.exceptions import WorkflowAlreadyStartedError
    from backend.temporal_dispatch import dispatch_once
    monkeypatch.setenv('CARERELAY_IMPORT_ENGINE', 'temporal')
    alex = circle(client)[0]
    job_id = imported(client, alex)['job_id']
    job = client.get('/api/jobs/' + job_id, headers=auth(alex)).json()
    assert job['status'] == 'queued' and job['dispatched'] == 0
    assert imported(client, alex)['job_id'] == job_id

    class Unavailable:
        async def start_workflow(self, *args, **kwargs):
            raise ConnectionError('offline')

    asyncio.run(dispatch_once(Unavailable()))
    assert client.get('/api/jobs/' + job_id, headers=auth(alex)).json()['status'] == 'queued'
    calls = []

    class AcceptedBeforeCrash:
        async def start_workflow(self, name, argument, **kwargs):
            calls.append((name, argument, kwargs['id']))
            raise WorkflowAlreadyStartedError(kwargs['id'], name)

        def get_workflow_handle(self, workflow_id):
            return self

        async def describe(self, **kwargs):
            return SimpleNamespace(status=WorkflowExecutionStatus.RUNNING)

    asyncio.run(dispatch_once(AcceptedBeforeCrash()))
    recovered = client.get('/api/jobs/' + job_id, headers=auth(alex)).json()
    assert recovered['dispatched'] == 1
    assert calls == [('CareRelayImport', job_id, 'carerelay-import-' + job_id)]
    assert alex['token'] not in str(calls)
    assert 'Alex will book' not in str(calls)


def test_temporal_attempt_fencing_and_commit_are_idempotent(client, monkeypatch):
    monkeypatch.setenv('CARERELAY_IMPORT_ENGINE', 'temporal')
    alex = circle(client)[0]
    job_id = imported(client, alex)['job_id']
    first = prepare_import(job_id, 1)
    second = prepare_import(job_id, 2)
    result = Extraction(items=[suggestion(source_id=first[1]['id'])])
    assert save_import(job_id, first, result, 1) == 0
    assert state(client, alex)['tasks'] == []
    assert save_import(job_id, second, result, 2) == 1
    assert save_import(job_id, second, result, 2) == 1
    assert prepare_import(job_id, 3) is None
    data = state(client, alex)
    assert len(data['tasks']) == 1
    assert len([x for x in data['audit'] if x['action'] == 'extraction_completed']) == 1


def test_temporal_rechecks_permission_before_commit(client, monkeypatch):
    monkeypatch.setenv('CARERELAY_IMPORT_ENGINE', 'temporal')
    alex, maya, *_ = circle(client)
    job_id = imported(client, maya)['job_id']
    context = prepare_import(job_id, 1)
    assert client.patch(f"/api/caregivers/{maya['id']}/permissions", headers=auth(alex), json={
        'can_import': False, 'can_review': False, 'can_brief': True}).status_code == 200
    with pytest.raises(ValueError, match='revoked'):
        save_import(job_id, context, Extraction(items=[suggestion(source_id=context[1]['id'])]), 1)
    assert state(client, alex)['tasks'] == []


def test_temporal_jobs_survive_api_restart_and_keep_private_access(client, monkeypatch):
    import backend.temporal_dispatch as dispatch
    monkeypatch.setenv('CARERELAY_IMPORT_ENGINE', 'temporal')
    alex, maya, *_ = circle(client)
    job_id = imported(client, alex, visibility='private')['job_id']
    prepare_import(job_id, 1)
    async def idle():
        await asyncio.Event().wait()
    monkeypatch.setattr(dispatch, 'dispatch_forever', idle)
    with TestClient(app) as restarted:
        job = restarted.get('/api/jobs/' + job_id, headers=auth(alex)).json()
        assert job['status'] == 'processing' and job['attempts'] == 1
        assert restarted.get('/api/jobs/' + job_id, headers=auth(maya)).status_code == 404
        assert state(restarted, maya)['sources'] == []


def test_temporal_invalid_evidence_is_non_retryable(client, monkeypatch):
    from temporalio.exceptions import ApplicationError
    from temporalio.testing import ActivityEnvironment
    from backend.temporal_worker import extract_import
    monkeypatch.setenv('CARERELAY_IMPORT_ENGINE', 'temporal')
    install_extractor(monkeypatch, quote='A fabricated quote that does not exist in the source.')
    alex = circle(client)[0]
    job_id = imported(client, alex)['job_id']
    with pytest.raises(ApplicationError) as failure:
        asyncio.run(ActivityEnvironment().run(extract_import, job_id))
    assert failure.value.non_retryable
    assert failure.value.type == 'ImportValidationError'
    assert state(client, alex)['tasks'] == []
    assert client.get('/api/jobs/' + job_id, headers=auth(alex)).json()['status'] == 'failed'
