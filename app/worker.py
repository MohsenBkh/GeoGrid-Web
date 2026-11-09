# -*- coding: utf-8 -*-
"""
worker.py
==========
Runs the actual shapefile -> DGS conversion for a paid job, using the
exact same shp2dgs.core.converter.Converter class the desktop app
uses (vendored under shp2dgs/, see project root).

MVP concurrency model: a small ThreadPoolExecutor. Converter is CPU/IO
heavy pure Python (no GIL-released native work for the open-source
build), so a thread pool gives real concurrency limits -- good enough
for an initial deployment. If conversion volume grows, swap this for
a proper task queue (Celery/RQ with a Redis broker) without changing
anything else; the job's lifecycle (status column in db.py) already
models that.
"""
import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import db, settings
from shp2dgs.core.converter import Converter
from shp2dgs.core.config_io import load_json

logger = logging.getLogger("geogrid_web.worker")

# Cap concurrent conversions so one burst of paid jobs can't exhaust
# server memory/CPU. Tune based on your server's actual resources.
_executor = ThreadPoolExecutor(max_workers=2)

_CONFIG = load_json(str(settings.ENGINE_CONFIG_PATH))
_TEMPLATE = load_json(str(settings.ENGINE_TEMPLATE_PATH))


def submit_conversion(job_id: str, shp_dir: Path, output_path: Path):
    _executor.submit(_run_conversion, job_id, shp_dir, output_path)


def _run_conversion(job_id: str, shp_dir: Path, output_path: Path):
    db.update_job(job_id, status="converting")
    logger.info("job %s: conversion started", job_id)
    t0 = time.time()
    try:
        conv = Converter(
            str(shp_dir), _CONFIG, _TEMPLATE,
            make_graphics=True, generate_gps=True, gps_line_vertices=True,
        )
        conv.build()
        conv.emit()
        conv.write(str(output_path))

        record_count = sum(
            len(getattr(conv, attr, []) or [])
            for attr in ("elm_terms", "elm_lines") if hasattr(conv, attr)
        ) or None

        db.update_job(
            job_id,
            status="done",
            output_path=str(output_path),
            record_count=record_count,
            error_message=None,
        )
        logger.info("job %s: conversion done in %.1fs", job_id, time.time() - t0)
    except Exception as e:
        logger.exception("job %s: conversion FAILED", job_id)
        db.update_job(
            job_id,
            status="failed",
            error_message=f"{type(e).__name__}: {e}",
        )
