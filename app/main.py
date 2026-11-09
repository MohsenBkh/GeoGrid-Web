# -*- coding: utf-8 -*-
"""
main.py
========
GeoGrid Web -- FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload --port 8000
Run in prod:  see docs/deployment.md (gunicorn + nginx + systemd)
"""
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, settings, worker
from .uploads import save_and_extract, UploadError
from .zarinpal import request_payment, verify_payment, ZarinPalError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("geogrid_web")

app = FastAPI(title="GeoGrid Web")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

db.init_db()


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.post("/api/jobs")
def create_job(file: UploadFile = File(...)):
    """Step 1: upload the shapefile zip. Returns a job_id and the price
    to pay -- no conversion happens yet."""
    job_id = uuid.uuid4().hex
    job_dir = settings.UPLOADS_DIR / job_id

    try:
        shp_dir = save_and_extract(file, job_dir)
    except UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.create_job(
        job_id=job_id,
        upload_path=str(shp_dir),
        original_filename=file.filename or "shapefile.zip",
        price_rials=settings.PRICE_RIALS,
    )
    return {"job_id": job_id, "price_rials": settings.PRICE_RIALS}


@app.post("/api/jobs/{job_id}/pay")
def start_payment(job_id: str, request: Request):
    """Step 2: create a ZarinPal payment request and return the URL to
    redirect the user to."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] not in ("uploaded", "payment_failed"):
        raise HTTPException(status_code=400, detail=f"Job is not payable (status={job['status']}).")

    callback_url = f"{settings.SITE_BASE_URL}/api/payment/callback?job_id={job_id}"
    try:
        authority, pay_url = request_payment(
            amount_rials=job["price_rials"],
            description=f"GeoGrid conversion - job {job_id[:8]}",
            callback_url=callback_url,
        )
    except ZarinPalError as e:
        logger.error("job %s: payment request failed: %s", job_id, e)
        raise HTTPException(status_code=502, detail="Could not start payment. Please try again shortly.")

    db.update_job(job_id, status="payment_pending", zarinpal_authority=authority)
    return {"pay_url": pay_url}


@app.get("/api/payment/callback")
def payment_callback(job_id: str, Authority: str = "", Status: str = ""):
    """ZarinPal redirects the user's browser here after they pay (or
    cancel). We verify server-to-server before trusting it."""
    job = db.get_job(job_id)
    if not job:
        return RedirectResponse(f"/?error=job_not_found")

    if Status != "OK":
        db.update_job(job_id, status="payment_failed")
        return RedirectResponse(f"/?job_id={job_id}&payment=cancelled")

    try:
        ref_id = verify_payment(amount_rials=job["price_rials"], authority=Authority)
    except ZarinPalError as e:
        logger.error("job %s: payment verify failed: %s", job_id, e)
        db.update_job(job_id, status="payment_failed", error_message=str(e))
        return RedirectResponse(f"/?job_id={job_id}&payment=failed")

    download_token = db.generate_download_token()
    db.update_job(job_id, status="paid", zarinpal_ref_id=ref_id, download_token=download_token)

    # Payment confirmed -- kick off the actual conversion now, not before.
    shp_dir = Path(job["upload_path"])
    output_path = settings.OUTPUTS_DIR / f"{job_id}.xlsx"
    worker.submit_conversion(job_id, shp_dir, output_path)

    return RedirectResponse(f"/?job_id={job_id}&payment=success")


@app.get("/api/jobs/{job_id}/status")
def job_status(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    result = {
        "job_id": job_id,
        "status": job["status"],
        "price_rials": job["price_rials"],
        "original_filename": job["original_filename"],
    }
    if job["status"] == "failed":
        result["error_message"] = "Conversion failed. Please check your shapefile and try again."
    if job["status"] == "done":
        result["download_token"] = job["download_token"]
    return result


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str, token: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail="This job is not ready for download yet.")
    if not token or token != job["download_token"]:
        raise HTTPException(status_code=403, detail="Invalid download link.")

    output_path = Path(job["output_path"])
    if not output_path.exists():
        raise HTTPException(status_code=410, detail="This file has expired. Please submit a new job.")

    download_name = Path(job["original_filename"]).stem + "_GeoGrid.xlsx"
    return FileResponse(
        path=str(output_path),
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
