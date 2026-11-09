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
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://localhost:8000")

# --- Storage ---------------------------------------------------------------
STORAGE_DIR = ROOT_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
DB_PATH = STORAGE_DIR / "db" / "geogrid_web.sqlite3"

for d in (UPLOADS_DIR, OUTPUTS_DIR, DB_PATH.parent):
    d.mkdir(parents=True, exist_ok=True)

# --- Limits ------------------------------------------------------------
MAX_UPLOAD_MB = int(os.environ.get("GEOGRID_MAX_UPLOAD_MB", "100"))
JOB_RETENTION_HOURS = int(os.environ.get("GEOGRID_JOB_RETENTION_HOURS", "48"))

# --- Engine resource files (bundled config/template, see shp2dgs.core.config_io) ---
ENGINE_CONFIG_PATH = ROOT_DIR / "config.json"
ENGINE_TEMPLATE_PATH = ROOT_DIR / "dgs_template.json"
