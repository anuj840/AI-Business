"""ARQ worker configuration.

Run with:  arq app.worker.settings.WorkerSettings

All knobs (retries, timeout) come from app config, not hard-coded here, per
the project's configuration-over-hard-coding rule.
"""
from __future__ import annotations

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.worker.tasks import _shutdown, _startup, analyze_business_task

settings = get_settings()
configure_logging()


class WorkerSettings:
    functions = [analyze_business_task]
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_tries = settings.JOB_MAX_RETRIES + 1
    job_timeout = settings.JOB_TIMEOUT_SECONDS
