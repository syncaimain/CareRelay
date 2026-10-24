"""Real Temporal/Ollama recovery checks using only new synthetic local data.

Start the persistent local Temporal service first. This script owns and restarts
only the API/worker child processes it creates, using an isolated SQLite DB and
task queue. Existing CareRelay services and other projects are untouched.
"""
import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
from google.protobuf.json_format import MessageToDict
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

ROOT = Path(__file__).resolve().parent.parent
RUN = uuid.uuid4().hex[:12]
DATA = ROOT / 'data' / ('temporal-verification-' + RUN)
DATA.mkdir(parents=True)
PORT = int(os.getenv('TEMPORAL_VERIFY_API_PORT', '8106'))
ADDRESS = os.getenv('TEMPORAL_ADDRESS', '127.0.0.1:7233')
QUEUE = 'carerelay-verification-' + RUN
PROCESSES = []
LOGS = []
ENV = {**os.environ, 'CARERELAY_DB': str(DATA / 'app.sqlite3'),
       'CARERELAY_DEMO': 'true', 'CARERELAY_IMPORT_ENGINE': 'temporal',
       'TEMPORAL_ADDRESS': ADDRESS, 'TEMPORAL_TASK_QUEUE': QUEUE}


def start(kind, **extra_env):
    log = (DATA / f'{kind}-{len(LOGS)}.log').open('w', encoding='utf-8')
    LOGS.append(log)
    command = ([sys.executable, '-m', 'backend.temporal_worker'] if kind == 'worker' else
               [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', str(PORT)])
    process = subprocess.Popen(command, cwd=ROOT, env={**ENV, **extra_env},
                               stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    PROCESSES.append(process)
    return process


def stop(process):
    if process.poll() is None:
        process.kill()
        process.wait(timeout=10)


async def wait_for(check, message, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = await check()
            if value:
                return value
        except (httpx.HTTPError, ConnectionError):
            pass
        await asyncio.sleep(0.05)
    raise AssertionError(message)


def payloads(value):
    if isinstance(value, dict):
        if 'metadata' in value and 'data' in value:
            yield base64.b64decode(value['data']).decode('utf-8', errors='replace')
        for child in value.values():
            yield from payloads(child)
    elif isinstance(value, list):
        for child in value:
            yield from payloads(child)


async def main():
    started = time.monotonic()
    client = await Client.connect(ADDRESS, identity='carerelay-recovery-check')
    report = {'synthetic': True, 'model': ENV.get('OLLAMA_MODEL', 'ministral-3:14b'),
              'sdk': '1.34.0', 'task_queue': QUEUE}
    api_process = start('api')
    async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{PORT}', timeout=10, trust_env=False) as http:
        async def ready():
            return (await http.get('/openapi.json')).status_code == 200
        await wait_for(ready, 'Verification API did not start.')
        response = await http.post('/api/demo'); response.raise_for_status()
        profiles = response.json()['profiles']; alex, maya = profiles[:2]
        headers = {'Authorization': 'Bearer ' + alex['token']}
        source = 'Alex will book transport to Oak Clinic on 2026-10-26 at 09:00.'

        async def submit(text, label):
            response = await http.post('/api/imports', headers=headers, json={
                'text': text, 'label': label, 'reference_at': '2026-10-24T09:00:00+05:00',
                'visibility': 'private', 'synthetic': True})
            response.raise_for_status()
            return response.json()['job_id']

        async def job(job_id):
            r = await http.get('/api/jobs/' + job_id, headers=headers); r.raise_for_status()
            return r.json()

        async def status_matches(job_id, predicate):
            value = await job(job_id)
            if value['status'] == 'failed':
                raise AssertionError(value['error'])
            return value if predicate(value) else None

        print('Checking durable queue and API restart before a worker exists...', flush=True)
        first = await submit(source, 'Synthetic transient-failure check')
        await wait_for(lambda: status_matches(first, lambda j: j['dispatched'] == 1), 'Outbox did not dispatch.')
        before = await job(first)
        assert before['status'] == 'queued'
        stop(api_process); api_process = start('api')
        await wait_for(ready, 'API did not recover after restart.')
        after = await job(first)
        assert after['workflow_id'] == before['workflow_id'] and after['status'] == 'queued'
        report['queued_import_survived_api_restart'] = True

        print('Forcing a real connection failure, then restoring Ollama...', flush=True)
        worker = start('worker', OLLAMA_URL='http://127.0.0.1:1')
        await wait_for(lambda: status_matches(first, lambda j: bool(j['error']) and j['attempts'] >= 1),
                       'Transient inference failure was not recorded.')
        stop(worker); worker = start('worker')
        recovered = await wait_for(lambda: status_matches(first, lambda j: j['status'] == 'completed'),
                                   'Transient failure did not recover.', timeout=300)
        assert recovered['attempts'] >= 2 and recovered['item_count'] >= 1
        report['transient_failure_recovered_with_real_ollama'] = True
        report['transient_failure_attempts'] = recovered['attempts']

        print('Crashing the worker and API during an active extraction Activity...', flush=True)
        second_source = ('The clinic appointment is on 2026-10-27 at 10:00 at Oak Clinic.\n'
                         'Maya will drive to Oak Clinic on 2026-10-27 at 09:00.\n'
                         'Robin will collect the library books on 2026-10-28 at 15:00.')
        second = await submit(second_source, 'Synthetic worker-crash recovery')
        active = await wait_for(lambda: status_matches(second, lambda j: j['status'] == 'processing'),
                                'Second extraction did not start.')
        stop(worker)
        assert (await job(second))['status'] != 'completed', 'Worker finished before the crash; rerun the check.'
        stop(api_process); api_process = start('api')
        await wait_for(ready, 'API did not recover during active extraction.')
        restored = await job(second)
        assert restored['workflow_id'] == active['workflow_id'] and restored['status'] == 'processing'
        worker = start('worker')
        completed = await wait_for(lambda: status_matches(second, lambda j: j['status'] == 'completed'),
                                   'Crashed extraction did not resume.', timeout=300)
        assert completed['attempts'] >= 2
        report['worker_and_api_crash_recovered'] = True
        report['worker_crash_attempts'] = completed['attempts']
        report['recovered_job_id'] = second
        report['recovered_workflow_id'] = completed['workflow_id']

        handle = client.get_workflow_handle(completed['workflow_id'])
        assert await handle.result(rpc_timeout=timedelta(seconds=30)) == completed['item_count']
        history = await handle.fetch_history()
        events = [MessageToDict(e, preserving_proto_field_name=True) for e in history.events]
        event_types = [e['event_type'] for e in events]
        starts = [e['activity_task_started_event_attributes'] for e in events
                  if 'activity_task_started_event_attributes' in e]
        assert any(a.get('attempt', 1) >= 2 and a.get('last_failure', {}).get(
            'timeout_failure_info', {}).get('timeout_type') == 'TIMEOUT_TYPE_HEARTBEAT' for a in starts)
        assert event_types[-1] == 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED'
        report['temporal_history_event_types'] = event_types
        report['history_confirms_heartbeat_timeout_and_retry'] = True
        report['activity_retry_evidence'] = [{'attempt': a.get('attempt', 1),
                                             'last_failure': a.get('last_failure')} for a in starts]
        history_text = '\n'.join(payloads(events))
        assert source not in history_text and second_source not in history_text
        assert all(p['token'] not in history_text for p in profiles)
        assert 'Oak Clinic' not in history_text
        report['history_excludes_source_text_and_credentials'] = True

        try:
            await client.start_workflow('CareRelayImport', second, id=completed['workflow_id'],
                                        task_queue=QUEUE, id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        except WorkflowAlreadyStartedError:
            report['duplicate_workflow_start_rejected'] = True
        else:
            raise AssertionError('Duplicate workflow execution was accepted.')
        response = await http.post('/api/imports', headers=headers, json={
            'text': second_source, 'reference_at': '2026-10-24T09:00:00+05:00',
            'visibility': 'private', 'synthetic': True})
        assert response.json()['job_id'] == second and response.json()['duplicate']
        data = (await http.get('/api/state', headers=headers)).json()
        tasks = data['tasks']
        keys = [(t['source_id'], t['quote'], t['kind'], t['title']) for t in tasks]
        assert len(keys) == len(set(keys))
        assert all(t['status'] == 'suggested' and not t['accepted'] for t in tasks)
        assert all(t['quote'] in next(s['text'] for s in data['sources'] if s['id'] == t['source_id']) for t in tasks)
        assert (await http.get('/api/jobs/' + second, headers={'Authorization':'Bearer ' + maya['token']})).status_code == 404
        report.update({'duplicate_tasks': 0, 'all_results_require_human_review': True,
                       'source_quotes_validated': True, 'private_job_access_enforced': True,
                       'task_count': len(tasks), 'seconds': round(time.monotonic() - started, 2), 'passed': True})
        target = ROOT / 'docs' / 'temporal-verification.json'
        target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        (DATA / 'history.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        for process in PROCESSES:
            stop(process)
        for log in LOGS:
            log.close()
