"""Background job status API (spec sections 39-40, 50).

  GET /api/jobs/{job_id}   poll a job's status/result metadata
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.job import Job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "id": str(job.id),
        "job_type": job.job_type.value,
        "status": job.status.value,
        "business_id": str(job.business_id) if job.business_id else None,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error": job.error,
        "retry_count": job.retry_count,
        "metadata": job.job_metadata,
    }
