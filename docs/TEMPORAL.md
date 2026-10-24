# Durable imports with Temporal

Temporal is the default import engine. FastAPI commits the source and its queued job in one SQLite transaction. Its outbox dispatcher starts a `CareRelayImport` workflow using a stable ID. A separate worker runs genuine Ollama extraction in a heartbeating Activity, validates evidence, rechecks permissions, and commits suggestions atomically.

## Local Windows setup

From the project directory, activate the application environment and install dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python scripts/install_temporal.py
```

The installer verifies the pinned official Windows x64 CLI archive against its upstream SHA-256. For other platforms, install the CLI using [Temporal's official instructions](https://docs.temporal.io/cli/setup-cli).

Run each command in a separate terminal from the project directory, with the application environment activated for Python commands:

```powershell
.\.tools\temporal\temporal.exe server start-dev --ip 127.0.0.1 --port 7233 --ui-port 8233 --db-filename data/temporal.sqlite --ui-disable-news-fetch
```

```powershell
python -m backend.temporal_worker
```

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8104
```

```powershell
npm.cmd run dev
```

The app is at http://127.0.0.1:3104 and Temporal's workflow UI is at http://127.0.0.1:8233. Ollama must already serve `ministral-3:14b` at `127.0.0.1:11434`. `.env.example` lists the Temporal address, namespace, task queue and import engine. The API and worker must share the same SQLite file, namespace, queue and model configuration.

The development service is loopback-only and uses a persistent local database. Its default in-memory mode is deliberately avoided. This service and the app are for fictional local data, without production identity, encryption or network deployment guarantees.

## Failure behavior

- If Temporal is unavailable, the import stays saved in SQLite and dispatch retries automatically. A stable workflow ID with duplicate-start rejection covers the crash window between starting the workflow and committing its dispatch marker.
- If the API restarts, Temporal jobs retain their state and pending outbox records are dispatched again safely.
- If a worker dies during extraction, its ten-second heartbeat timeout allows another Activity attempt. A live model call may run again; inference is not claimed to execute exactly once.
- Transient inference failures retry up to five attempts, with exponential backoff starting at one second and capped at fifteen seconds. Each attempt allows five minutes; the Activity has a fifteen-minute overall limit, and the workflow a twenty-minute limit.
- Bad evidence and revoked permissions are non-retryable failures. Exhausted, cancelled or terminated executions become visible failures rather than unfinished jobs that look completed.
- The final SQLite transaction checks the current attempt and completed-job state. An old or repeated Activity cannot duplicate suggestions or overwrite a completed result. Import permission is checked again after inference.
- Returned tasks stay suggested and unaccepted. Temporal never approves evidence, assigns consent or sends a handoff.

Only opaque job IDs, counts and generic failures enter workflow payloads. Source text, caregiver tokens and extracted tasks stay in the application database. The worker loads them locally when the Activity executes.

## Reproduce the recovery check

With the persistent Temporal service and Ollama running:

```powershell
python scripts/verify_temporal.py
```

This creates an isolated synthetic SQLite database and task queue, then starts its own API on port 8106 and its own workers. It restarts a queued API, forces an actual unreachable Ollama endpoint, restores real inference, and kills both worker and API during another extraction. It verifies recovery, duplicate rejection, private-job access, exact quotes, unapproved results and payload privacy. Only child processes created by the script are stopped.

The successful run is recorded in `temporal-verification.json`. Temporal's final Activity-start event records attempt 2 and its prior heartbeat timeout; intermediate retries are compacted rather than listed as separate timeout events. The actual completed-workflow screenshot is `demo/assets/screenshots/08-temporal-recovery.png`.

The explicit `CARERELAY_IMPORT_ENGINE=inline` mode supports deterministic unit fixtures and the isolated in-process smoke script. It retains the original restart limitation. The optional, untested legacy Docker Compose file explicitly uses inline mode; the durable path verified here is the manual Temporal setup above.
