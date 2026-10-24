import json
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import ai
from backend.main import app
from backend.schemas import Extraction, SuggestedItem


@pytest.fixture
def client(monkeypatch):
    # pytest's mode-0700 temporary directories are inaccessible to this Windows
    # sandbox token. Use unique files under an inherited-permission data folder.
    path = Path('data') / ('test-' + uuid.uuid4().hex + '.sqlite3')
    path.parent.mkdir(exist_ok=True)
    monkeypatch.setenv('CARERELAY_DB', str(path))
    monkeypatch.setenv('CARERELAY_DEMO', 'true')
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
