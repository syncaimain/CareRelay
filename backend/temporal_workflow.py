"""Deterministic orchestration. Only opaque job IDs and counts enter history."""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError


@workflow.defn(name='CareRelayImport')
class ImportWorkflow:
    @workflow.run
    async def run(self, job_id: str) -> int:
        try:
            return await workflow.execute_activity(
                'extract_import', job_id, result_type=int,
                start_to_close_timeout=timedelta(minutes=5),
                schedule_to_close_timeout=timedelta(minutes=15),
                heartbeat_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1),
                                         maximum_interval=timedelta(seconds=15), maximum_attempts=5),
            )
        except ActivityError:
            await workflow.execute_activity(
                'fail_import', job_id, start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            # Keep a failed execution visible in Temporal as well as the UI.
            raise ApplicationError('Import could not be completed; see its local review status.',
                                   type='ImportFailed', non_retryable=True) from None
