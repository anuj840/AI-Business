"""Background task functions run by the ARQ worker (spec sections 39-41).

Each task:
  1. marks its Job row RUNNING
  2. does the actual work
  3. marks the Job row COMPLETED or FAILED, with an error message on failure

A failed AI/crawl step never corrupts a business record -- persist_pipeline_result
still runs in one transaction (spec section 66) -- but a fully unhandled
exception in the task itself must still leave the Job row in a terminal
FAILED state rather than stuck QUEUED/RUNNING forever, so this wraps the
whole thing in try/except at the top level too.

Zombie/orphaned job protection (found via live debugging -- see JOBS.md):
killing a worker process mid-job (e.g. to deploy new code) can leave ARQ's
own bookkeeping in Redis inconsistent, and a *later* worker process can
re-deliver and re-execute that same job hours afterward, with no one
having asked for it -- observed live: a job silently re-ran a full
analysis, unprompted, about 4 hours after its business was created. Two
defenses below: an idempotency check (skip re-running a job that's already
in a terminal state) and a startup sweep (any job still RUNNING when a
worker boots must belong to a now-dead previous process, since this is the
only worker -- mark it FAILED rather than let it sit there for some future
redelivery to resurrect).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.business import Business
from app.models.job import Job, JobStatus
from app.services.pipeline import persist_pipeline_result, run_full_pipeline

logger = get_logger(__name__)


async def analyze_business_task(ctx: dict, job_id: str, business_id: str) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, uuid.UUID(job_id))
        if not job:
            logger.error("worker.job_not_found", job_id=job_id)
            return

        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            # A stale redelivery of a job that already reached a terminal
            # state -- do not re-run the pipeline and silently overwrite
            # whatever's there now with a second, unrequested analysis.
            logger.warning(
                "worker.stale_redelivery_skipped",
                job_id=job_id,
                business_id=business_id,
                existing_status=job.status.value,
            )
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            business = await db.get(Business, uuid.UUID(business_id))
            if not business:
                raise ValueError(f"Business {business_id} not found")

            result = await run_full_pipeline(business)
            await persist_pipeline_result(db, business, result)

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("worker.job_completed", job_id=job_id, business_id=business_id)

        except Exception as exc:  # noqa: BLE001 - job must reach a terminal state
            logger.error(
                "worker.job_failed", job_id=job_id, business_id=business_id, error=str(exc)
            )
            # Roll back any partial work from the failed attempt before
            # writing the failure status in a fresh transaction.
            await db.rollback()
            job = await db.get(Job, uuid.UUID(job_id))
            if job:
                job.status = JobStatus.FAILED
                job.error = str(exc)[:2000]
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()


async def _startup(ctx: dict) -> None:
    logger.info("worker.startup")
    await _clean_up_orphaned_jobs()


async def _clean_up_orphaned_jobs() -> None:
    """Any Job row still RUNNING when a worker boots cannot belong to a
    live task -- this process just started, so nothing could legitimately
    still be running from it, and it's the only worker. It must be left
    over from a previous worker process that was killed (or crashed)
    mid-job. Mark it FAILED with a clear reason rather than let it sit
    there indefinitely for some future ARQ redelivery to silently resume
    and resurrect hours later (see the module docstring)."""
    async with AsyncSessionLocal() as db:
        orphaned = (
            (await db.execute(select(Job).where(Job.status == JobStatus.RUNNING)))
            .scalars()
            .all()
        )
        if not orphaned:
            return

        for job in orphaned:
            job.status = JobStatus.FAILED
            job.error = (
                "Orphaned: still RUNNING when a new worker process started, meaning "
                "the previous worker was stopped or crashed mid-job. Re-run analysis "
                "for this business if you still want it."
            )
            job.completed_at = datetime.now(timezone.utc)
            db.add(job)

        await db.commit()
        logger.warning("worker.orphaned_jobs_cleaned_up", count=len(orphaned))


async def _shutdown(ctx: dict) -> None:
    logger.info("worker.shutdown")
