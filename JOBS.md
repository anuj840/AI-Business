# Background Jobs

Implements spec sections 39-41: `/analyze` no longer blocks the request while
crawling + calling the AI model. It enqueues a job and returns immediately;
a separate worker process does the actual work.

## Architecture

```
POST /api/businesses/{id}/analyze
        │
        ▼
Creates a Job row (status=QUEUED) in Postgres
        │
        ▼
Enqueues analyze_business_task via ARQ (Redis-backed queue)
        │
        ▼
Returns {"job_id": "...", "status": "QUEUED"} immediately  (HTTP 202)
        │
        │  ... meanwhile, in a separate worker process ...
        ▼
ARQ worker picks up the job
        │
        ▼
analyze_business_task (app/worker/tasks.py):
  1. Job.status = RUNNING
  2. run_full_pipeline(business)       <- same pipeline as before, unchanged
  3. persist_pipeline_result(...)      <- same persistence, unchanged
  4. Job.status = COMPLETED (or FAILED, with .error set, on any exception)
```

`GET /api/jobs/{job_id}` polls status. `GET /api/businesses/{id}/analysis`
fetches the persisted result once the job is `COMPLETED` — this endpoint
already existed before jobs did and needed no changes.

## Why a real `jobs` table instead of relying on ARQ/Redis alone

ARQ tracks its own internal job state in Redis, but that's ephemeral (gone on
a Redis flush/restart) and not easily queryable/joinable with the rest of the
app's data. The `jobs` table (spec section 4/39-40) is the durable source of
truth the API and UI read from; ARQ is purely the execution/queueing
mechanism underneath it.

## Running the worker

```bash
cd backend
source .venv/bin/activate
arq app.worker.settings.WorkerSettings
```

Or via Docker Compose, the `worker` service runs this automatically.

## Job states

`QUEUED → RUNNING → COMPLETED` (happy path) or `→ FAILED` (with `error` set)
on any unhandled exception, per spec section 40. `RETRYING`/`CANCELLED` are
modeled but not yet wired to actual retry/cancel logic — `JOB_MAX_RETRIES`
(default 1) is currently just passed to ARQ's own `max_tries`; a failed
attempt within that budget is retried by ARQ automatically, but the `jobs`
row does not yet reflect an intermediate `RETRYING` state during that.

## A real bug found and fixed while building this

Python 3.14 removed the implicit "create an event loop for me" behavior that
`asyncio.get_event_loop()` used to fall back on. `arq==0.26.3`'s `Worker.__init__`
still called that pattern directly and crashed on startup with `RuntimeError:
There is no current event loop`. Fixed by pinning `arq==0.28.0`, which
doesn't hit this path.

## Verified end-to-end

Against a live stack (Postgres + Redis + Ollama + a real `arq` worker
process, not mocked): created a business via the actual UI, clicked "Run
Analysis," watched the button show "Queued…" then "Analyzing…", confirmed
via direct SQL that the job transitioned `QUEUED → RUNNING → COMPLETED` in
the `jobs` table, and confirmed the frontend picked up completion via
polling and rendered the full audit + outreach draft — all without the
browser blocking on a single long HTTP request.

A real frontend bug was found and fixed in this process: an `unmountedRef`
guard was set to `true` on cleanup but never reset to `false` on remount,
so React 18 Strict Mode's dev-only mount→cleanup→mount cycle permanently
"unmounted" the component from the poll loop's perspective before it ever
ran — the UI would sit on "Queued…" forever in `npm run dev`, invisible in
a production build where Strict Mode's double-invoke doesn't happen. This
is exactly the kind of bug Strict Mode exists to catch, once you notice the
symptom instead of dismissing it as "must be a backend timing issue."
