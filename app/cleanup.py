# -*- coding: utf-8 -*-
"""
cleanup.py
===========
Deletes uploaded shapefiles and converted outputs older than
JOB_RETENTION_HOURS (default 48h). Run periodically (cron or a
systemd timer) -- NOT on every request.

Usage:
    python -m app.cleanup
"""
import logging
import shutil
from pathlib import Path

from . import db, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("geogrid_web.cleanup")


def run():
    cutoff_seconds = settings.JOB_RETENTION_HOURS * 3600
    stale = db.list_stale_jobs(cutoff_seconds)
    logger.info("Found %d job(s) older than %dh", len(stale), settings.JOB_RETENTION_HOURS)

    for job in stale:
        job_id = job["id"]
        upload_dir = settings.UPLOADS_DIR / job_id
        output_path = settings.OUTPUTS_DIR / f"{job_id}.xlsx"

        if upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)
        if output_path.exists():
            output_path.unlink(missing_ok=True)

        db.delete_job(job_id)
        logger.info("Cleaned up job %s", job_id)


if __name__ == "__main__":
    run()
