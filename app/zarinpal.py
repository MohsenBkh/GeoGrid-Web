# -*- coding: utf-8 -*-
"""
zarinpal.py
============
Thin client for ZarinPal's REST payment API (v4). Two calls:

  1. request_payment() -- before redirecting the user to pay. Returns
     an "authority" token and the URL to send them to.
  2. verify_payment() -- after ZarinPal redirects back to our callback
     URL. Confirms the payment actually succeeded server-to-server
     (never trust the callback query params alone -- a user could
     forge a "success" redirect).

Docs: https://docs.zarinpal.com/paymentGateway/
"""
import requests

from . import settings


class ZarinPalError(Exception):
    pass


def request_payment(amount_rials: int, description: str, callback_url: str, mobile: str = "") -> tuple:
    """Returns (authority, pay_url)."""
    payload = {
        "merchant_id": settings.ZARINPAL_MERCHANT_ID,
        "amount": amount_rials,
        "description": description,
        "callback_url": callback_url,
    }
    if mobile:
        payload["metadata"] = {"mobile": mobile}

    try:
        resp = requests.post(settings.ZARINPAL_REQUEST_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise ZarinPalError(f"ZarinPal request failed: {e}") from e

    result = data.get("data", {})
    errors = data.get("errors", {})
    if errors:
        raise ZarinPalError(f"ZarinPal rejected the payment request: {errors}")

    authority = result.get("authority")
    if not authority:
        raise ZarinPalError(f"ZarinPal returned no authority: {data}")

    pay_url = settings.ZARINPAL_STARTPAY_URL.format(authority=authority)
    return authority, pay_url


def verify_payment(amount_rials: int, authority: str) -> str:
    """Returns the ZarinPal ref_id on success. Raises ZarinPalError on
    any failure (declined, already verified, wrong amount, etc.)."""
    payload = {
        "merchant_id": settings.ZARINPAL_MERCHANT_ID,
        "amount": amount_rials,
        "authority": authority,
    }
    try:
        resp = requests.post(settings.ZARINPAL_VERIFY_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise ZarinPalError(f"ZarinPal verify failed: {e}") from e

    result = data.get("data", {})
    errors = data.get("errors", {})
    if errors:
        raise ZarinPalError(f"ZarinPal verification rejected: {errors}")

    # code 100 = freshly verified, 101 = already verified (also a success,
    # can happen if the user refreshes the callback page).
    code = result.get("code")
    if code not in (100, 101):
        raise ZarinPalError(f"ZarinPal verification returned unexpected code: {data}")

    return str(result.get("ref_id", ""))
