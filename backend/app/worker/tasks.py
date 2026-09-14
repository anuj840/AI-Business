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
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

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


async def _shutdown(ctx: dict) -> None:
    logger.info("worker.shutdown")
