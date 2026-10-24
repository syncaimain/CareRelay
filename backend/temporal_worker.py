"""Run with: python -m backend.temporal_worker."""
import asyncio
import logging
import os
from contextlib import suppress
from datetime import timedelta

from dotenv import load_dotenv
from temporalio import activity
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from . import ai
from .db import connect, initialize
from .import_jobs import fail_import, prepare_import, save_import
from .temporal_workflow import ImportWorkflow


async def heartbeat():
    while True:
        activity.heartbeat()
        await asyncio.sleep(2)


@activity.defn(name='extract_import')
async def extract_import(job_id: str) -> int:
    attempt = activity.info().attempt
    pulse = asyncio.create_task(heartbeat())
    try:
        context = prepare_import(job_id, attempt)
        if context is None:
            with connect() as db:
                return db.execute('SELECT item_count FROM jobs WHERE id=?', (job_id,)).fetchone()['item_count']
        _, source, caregivers, existing = context
        result = await ai.extract(source, caregivers, existing)
        return save_import(job_id, context, result, attempt)
    except ValueError as exc:
        fail_import(job_id, str(exc), attempt)
        # Validation errors contain only our generic messages; never export
        # Pydantic inputs or source text into Temporal failure payloads.
        raise ApplicationError('Source validation or import authorization failed.',
                               type='ImportValidationError', non_retryable=True) from None
    except Exception:
        with connect() as db:
            db.execute("UPDATE jobs SET error=? WHERE id=? AND status='processing' AND attempts=?",
                       ('Local inference was interrupted; Temporal will retry automatically.', job_id, attempt))
        raise ApplicationError('Local extraction is temporarily unavailable.', type='InferenceUnavailable') from None
    finally:
        pulse.cancel()
        with suppress(asyncio.CancelledError):
            await pulse


@activity.defn(name='fail_import')
async def mark_failed(job_id: str) -> None:
    fail_import(job_id, 'Import could not complete after retries. Check the local services and submit again.')


async def main():
    load_dotenv()
    initialize()
    client = await Client.connect(os.getenv('TEMPORAL_ADDRESS', '127.0.0.1:7233'),
                                  namespace=os.getenv('TEMPORAL_NAMESPACE', 'default'),
                                  identity='carerelay-local-worker')
    async with Worker(client, task_queue=os.getenv('TEMPORAL_TASK_QUEUE', 'carerelay-imports'),
                      workflows=[ImportWorkflow], activities=[extract_import, mark_failed],
                      max_concurrent_activities=1, max_heartbeat_throttle_interval=timedelta(seconds=2)):
        logging.getLogger(__name__).info('CareRelay Temporal worker ready.')
        await asyncio.Event().wait()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
