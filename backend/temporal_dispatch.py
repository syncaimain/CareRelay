"""Dispatch committed SQLite jobs and reconcile terminal workflow states."""
import asyncio
import os
from datetime import timedelta

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from .db import connect
from .import_jobs import fail_import


async def dispatch_once(client):
    with connect() as db:
        pending = [dict(row) for row in db.execute("""SELECT * FROM jobs
            WHERE engine='temporal' AND dispatched=0 AND status IN ('queued','processing')
            ORDER BY created_at LIMIT 20""")]
    for job in pending:
        try:
            await client.start_workflow(
                'CareRelayImport', job['id'], id=job['workflow_id'],
                task_queue=os.getenv('TEMPORAL_TASK_QUEUE', 'carerelay-imports'),
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                execution_timeout=timedelta(minutes=20),
                rpc_timeout=timedelta(seconds=3),
            )
        except WorkflowAlreadyStartedError:
            # Covers a crash after Temporal accepted the start but before the
            # SQLite dispatch marker committed. Never start a second execution.
            pass
        except Exception:
            with connect() as db:
                db.execute("UPDATE jobs SET error=? WHERE id=? AND dispatched=0 AND status='queued'",
                           ('Waiting for the local workflow service; dispatch will retry automatically.', job['id']))
            return
        with connect() as db:
            db.execute('UPDATE jobs SET dispatched=1 WHERE id=?', (job['id'],))

    with connect() as db:
        active = [dict(row) for row in db.execute("""SELECT id,workflow_id FROM jobs
            WHERE engine='temporal' AND dispatched=1 AND status IN ('queued','processing')
            ORDER BY created_at LIMIT 50""")]
    failed = {WorkflowExecutionStatus.FAILED, WorkflowExecutionStatus.TIMED_OUT,
              WorkflowExecutionStatus.CANCELED, WorkflowExecutionStatus.TERMINATED}
    for job in active:
        try:
            description = await client.get_workflow_handle(job['workflow_id']).describe(
                rpc_timeout=timedelta(seconds=3))
        except Exception:
            return
        if description.status in failed:
            fail_import(job['id'], 'The import workflow stopped. Check local services and submit the source again.')


async def dispatch_forever():
    client = await Client.connect(os.getenv('TEMPORAL_ADDRESS', '127.0.0.1:7233'),
                                  namespace=os.getenv('TEMPORAL_NAMESPACE', 'default'),
                                  identity='carerelay-local-api', lazy=True)
    while True:
        try:
            await dispatch_once(client)
        except Exception:
            # Outbox entries stay committed and are picked up on the next poll.
            pass
        await asyncio.sleep(2)
