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

## Orphaned/zombie job protection

Found live, days into using this: a business's analyze job silently ran
**on its own, ~4 hours after the business was created**, with no one
having triggered it. Root cause: repeatedly killing and restarting the
worker process (e.g. to deploy new code) can leave ARQ's own job
bookkeeping in Redis inconsistent when a job was in-flight at the moment
of the kill. A later worker process can then redeliver and re-execute
that same job — sometimes much later, sometimes more than once. Confirmed
in the logs: one job was retried with a ~1417-second deferred delay,
completed once, then **completed again two hours later** re-running the
whole pipeline a second time unprompted, before eventually corrupting
into an internal `KeyError` in ARQ's Redis-side state.

Two defenses added to `app/worker/tasks.py`:

1. **Idempotency check.** `analyze_business_task` looks up the `Job` row
   first; if it's already `COMPLETED`/`FAILED`/`CANCELLED`, the task logs
   `worker.stale_redelivery_skipped` and returns immediately instead of
   re-running the pipeline and silently overwriting a business's current
   analysis with a second, unrequested one.
2. **Startup sweep.** `_startup` marks any `Job` row still `RUNNING` when
   a worker process boots as `FAILED` (`"Orphaned: ..."`) — a freshly
   started worker cannot have any job legitimately still running from
   itself, so a `RUNNING` row at boot must be left over from a previous
   process that was killed or crashed mid-job.

Verified live: restarting the worker with a genuinely orphaned `RUNNING`
job present correctly marked it `FAILED` on startup, and a stale
redelivery of that exact job arriving seconds later was correctly skipped
rather than re-executed — both logged (`worker.orphaned_jobs_cleaned_up`,
`worker.stale_redelivery_skipped`) and confirmed via direct SQL.

**Operational note for local dev**: this mitigates the *symptom* (a
business's data silently changing from a phantom re-run) but the
underlying cause — killing a worker mid-job — still wastes whatever work
was in flight. Prefer letting an in-flight job finish before restarting
the worker where practical; this isn't a concern in a normal deployment
where the worker process isn't being restarted every few minutes for
active development.
