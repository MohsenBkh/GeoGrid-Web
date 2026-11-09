# -*- coding: utf-8 -*-
"""
uploads.py
===========
Handles the user's uploaded .zip of shapefile layers:

  * Size/type validation BEFORE extraction (a zip bomb is a real risk
    for a public upload endpoint).
  * Safe extraction (guards against zip-slip path traversal -- a
    malicious entry name like "../../etc/passwd" must not escape the
    job's own directory).
  * Basic sanity check that at least one .shp file is present.

This does NOT validate that the shapefile layers match GeoGrid's
expected naming convention (ELW*) -- that happens naturally inside
Converter.build(), which already logs "layer missing" per layer and
continues; invalid/empty input just produces a near-empty DGS output,
which is a correctness concern, not a security one.
"""
import os
import zipfile
from pathlib import Path

from fastapi import UploadFile

from . import settings


class UploadError(Exception):
    pass


def _safe_extract(zf: zipfile.ZipFile, dest: Path):
    dest = dest.resolve()
    for member in zf.infolist():
        member_path = (dest / member.filename).resolve()
        if not str(member_path).startswith(str(dest)):
            raise UploadError("Invalid archive contents (path traversal attempt).")
    zf.extractall(dest)


def save_and_extract(upload: UploadFile, job_dir: Path) -> Path:
    """Saves the uploaded zip, extracts it safely, and returns the
    directory containing the extracted shapefile layers."""
    job_dir.mkdir(parents=True, exist_ok=True)

    filename = (upload.filename or "").lower()
    if not filename.endswith(".zip"):
        raise UploadError("Please upload a single .zip file containing your shapefile layers (.shp/.shx/.dbf/.prj).")

    zip_path = job_dir / "upload.zip"
    size = 0
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    with open(zip_path, "wb") as out:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                out.close()
                zip_path.unlink(missing_ok=True)
                raise UploadError(f"File too large (max {settings.MAX_UPLOAD_MB} MB).")
            out.write(chunk)

    extract_dir = job_dir / "shp"
    extract_dir.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Reject absurd compression ratios (zip bomb heuristic):
            # total uncompressed size shouldn't be wildly larger than
            # what a legitimate shapefile set would produce.
            total_uncompressed = sum(i.file_size for i in zf.infolist())
            if total_uncompressed > max_bytes * 20:
                raise UploadError("Archive contents too large after extraction.")
            _safe_extract(zf, extract_dir)
    except zipfile.BadZipFile:
        raise UploadError("The uploaded file is not a valid .zip archive.")

    # Shapefiles are sometimes nested one level deep (a folder inside
    # the zip) -- flatten if so, so Converter finds .shp files directly.
    shp_files = list(extract_dir.rglob("*.shp"))
    if not shp_files:
        raise UploadError("No .shp files found in the uploaded archive.")

    # If every .shp lives in one common subdirectory, use that as the
    # effective shapefile directory (Converter expects a flat folder).
    common_dirs = {p.parent for p in shp_files}
    if len(common_dirs) == 1 and next(iter(common_dirs)) != extract_dir:
        return next(iter(common_dirs))

    return extract_dir
