"""Exercise the genuine local-model P0 workflow in-process, without server sockets."""
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['CARERELAY_DB'] = str(ROOT / 'data' / ('api-smoke-' + uuid.uuid4().hex + '.sqlite3'))
os.environ['CARERELAY_DEMO'] = 'true'

from fastapi.testclient import TestClient
from backend.main import app
from backend.ai import model_name


def main():
    started = time.perf_counter()
    source = 'Alex will book transport to Oak Clinic on 2026-10-26 at 09:00.'
    with TestClient(app) as client:
        result = client.post('/api/demo')
        assert result.status_code == 200, result.text
        profile = result.json()['profiles'][0]
        headers = {'Authorization': 'Bearer ' + profile['token']}
        result = client.post('/api/imports', headers=headers, json={
            'text': source, 'reference_at': '2026-10-24T09:00:00+05:00', 'synthetic': True})
        assert result.status_code == 202, result.text
        job = client.get('/api/jobs/' + result.json()['job_id'], headers=headers).json()
        assert job['status'] == 'completed', job
        state = client.get('/api/state', headers=headers).json()
        assert state['tasks'], state
        task = next(t for t in state['tasks'] if t['kind'] == 'transport')
        assert task['quote'] in source
        extracted_date_correct = task['due_at'] == '2026-10-26T09:00:00+05:00'
        assert task['owner_id'] == profile['id'], task
        result = client.post(f"/api/tasks/{task['id']}/review", headers=headers, json={
            # Human review explicitly confirms the source's local date/time.
            'decision': 'approve', 'title': task['title'], 'due_at': '2026-10-26T09:00:00+05:00',
            'owner_id': task['owner_id'], 'location': task['location'], 'uncertainty': '',
            'acknowledge_uncertainty': True, 'version': task['version']})
        assert result.status_code == 200, result.text
        state = client.get('/api/state', headers=headers).json()
        assert not state['tasks'][0]['accepted']
        assert state['conflicts'], 'Unaccepted travel must be flagged.'
        result = client.post(f"/api/tasks/{task['id']}/accept", headers=headers)
        assert result.status_code == 200, result.text
        result = client.post('/api/drafts', headers=headers, json={'day': '2026-10-26'})
        assert result.status_code == 200, result.text
        draft = result.json()
        assert f"source #{task['source_id']}" in draft['text']
        result = client.post(f"/api/drafts/{draft['id']}/approve", headers=headers)
        assert result.status_code == 200, result.text
    report = {'model': model_name(), 'synthetic': True, 'passed': True,
              'transport_quote_verified': True, 'extracted_due_timestamp_correct': extracted_date_correct,
              'human_reviewed_due_timestamp': '2026-10-26T09:00:00+05:00',
              'owner_attribution_correct': True, 'review_and_consent_verified': True,
              'handoff_approved': True, 'seconds': round(time.perf_counter()-started, 3)}
    (ROOT / 'docs/api-smoke-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
