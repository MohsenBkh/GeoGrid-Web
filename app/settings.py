# -*- coding: utf-8 -*-
"""
settings.py
============
All configuration comes from environment variables so the same code
runs in dev and production without edits. Copy .env.example to .env
and fill in real values before deploying.
"""
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv():
    """Load ROOT_DIR/.env if python-dotenv is available.

    Real environment variables always win, so the same code works on a VPS
    (systemd EnvironmentFile), on Render/Fly/Docker (plain env vars) and
    locally (just a .env file, nothing to export by hand).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT_DIR / ".env", override=False)


_load_dotenv()

# --- ZarinPal ---------------------------------------------------------
# Sandbox merchant id works out of the box for testing with NO real
# money and NO merchant account -- https://sandbox.zarinpal.com
ZARINPAL_MERCHANT_ID = os.environ.get("ZARINPAL_MERCHANT_ID", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
ZARINPAL_SANDBOX = os.environ.get("ZARINPAL_SANDBOX", "true").lower() in ("1", "true", "yes")

ZARINPAL_BASE = "https://sandbox.zarinpal.com" if ZARINPAL_SANDBOX else "https://payment.zarinpal.com"
ZARINPAL_REQUEST_URL = f"{ZARINPAL_BASE}/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = f"{ZARINPAL_BASE}/pg/v4/payment/verify.json"
ZARINPAL_STARTPAY_URL = (
    "https://sandbox.zarinpal.com/pg/StartPay/{authority}"
    if ZARINPAL_SANDBOX else
    "https://payment.zarinpal.com/pg/StartPay/{authority}"
)

# --- Pricing ------------------------------------------------------------
# Fixed price per conversion, in Iranian Rials (ZarinPal's API takes Rials).
PRICE_RIALS = int(os.environ.get("GEOGRID_PRICE_RIALS", "500000"))  # placeholder default

# --- Site ----------------------------------------------------------------
# Public base URL of this site (used to build the ZarinPal callback URL).
# MUST be a real https:// URL in production -- ZarinPal requires it.
# Precedence: explicit SITE_BASE_URL  ->  platform-provided URL
#             (RENDER_EXTERNAL_URL on Render)  ->  localhost for dev.
# That way a Render deploy works even if the env var is left blank, and a
# service name collision (geogrid-web-xxxx.onrender.com) can't silently
# break the payment callback.
SITE_BASE_URL = (
    os.environ.get("SITE_BASE_URL")
    or os.environ.get("RENDER_EXTERNAL_URL")
    or "http://localhost:8000"
).rstrip("/")

# --- Storage ---------------------------------------------------------------
# GEOGRID_STORAGE_DIR lets a platform point storage at a mounted disk
# (e.g. /data) without touching code. Defaults to <project>/storage.
STORAGE_DIR = Path(os.environ.get("GEOGRID_STORAGE_DIR") or (ROOT_DIR / "storage"))
UPLOADS_DIR = STORAGE_DIR / "uploads"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
DB_PATH = STORAGE_DIR / "db" / "geogrid_web.sqlite3"

for d in (UPLOADS_DIR, OUTPUTS_DIR, DB_PATH.parent):
    d.mkdir(parents=True, exist_ok=True)

# --- Limits ------------------------------------------------------------
MAX_UPLOAD_MB = int(os.environ.get("GEOGRID_MAX_UPLOAD_MB", "100"))
JOB_RETENTION_HOURS = int(os.environ.get("GEOGRID_JOB_RETENTION_HOURS", "48"))
# How often the in-app cleaner runs. Set to 0 to disable it (e.g. when an
# external cron/systemd timer already runs `python -m app.cleanup`).
CLEANUP_INTERVAL_HOURS = float(os.environ.get("GEOGRID_CLEANUP_INTERVAL_HOURS", "6"))

# --- Engine resource files (bundled config/template, see shp2dgs.core.config_io) ---
ENGINE_CONFIG_PATH = ROOT_DIR / "config.json"
ENGINE_TEMPLATE_PATH = ROOT_DIR / "dgs_template.json"
