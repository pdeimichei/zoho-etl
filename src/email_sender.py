"""Plain-text email via Microsoft Graph API (Modern Auth).

Uses the OAuth2 Client Credentials flow — no user interaction required.
Requires an Azure AD app registration with Mail.Send application permission.
"""

import time
from datetime import date

import requests

from config import AppConfig

# Module-level token cache (lives for the process lifetime)
_token_cache: dict = {"access_token": None, "expires_at": 0.0}
_TOKEN_EXPIRY_BUFFER = 60  # seconds before actual expiry to refresh


def _get_access_token(cfg: AppConfig) -> str:
    """Acquire a bearer token via OAuth2 client credentials flow.

    Returns a cached token if it has not expired yet.

    Raises
    ------
    RuntimeError  with a human-readable message on any auth failure.
    """
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    url = (
        f"https://login.microsoftonline.com/"
        f"{cfg.tenant_id}/oauth2/v2.0/token"
    )
    payload = {
        "grant_type":    "client_credentials",
        "client_id":     cfg.client_id,
        "client_secret": cfg.client_secret,
        "scope":         "https://graph.microsoft.com/.default",
    }

    try:
        resp = requests.post(url, data=payload, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Microsoft login timed out. Check your network connection."
        )
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Cannot reach Microsoft login endpoint: {exc}"
        )
    except requests.exceptions.HTTPError:
        try:
            detail = resp.json().get("error_description", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(
            f"Token request failed ({resp.status_code}): {detail}"
        )

    data = resp.json()
    expires_in = int(data.get("expires_in", 3600))
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + expires_in - _TOKEN_EXPIRY_BUFFER
    return _token_cache["access_token"]


def send_summary_email(cfg: AppConfig, body: str) -> None:
    """Send the order summary to all configured recipients via Graph API.

    Parameters
    ----------
    cfg  : AppConfig instance (must have Azure AD and recipient fields set)
    body : plain-text email body produced by quote_processor

    Raises
    ------
    ValueError    if recipients list is empty
    RuntimeError  on any auth or delivery failure
    """
    if not cfg.recipients:
        raise ValueError("No recipients configured.")

    token = _get_access_token(cfg)

    subject = f"{cfg.subject_prefix} – {date.today().strftime('%Y-%m-%d')}"

    message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": body,
            },
            "toRecipients": [
                {"emailAddress": {"address": addr}}
                for addr in cfg.recipients
            ],
        },
        "saveToSentItems": "false",
    }

    url = (
        f"https://graph.microsoft.com/v1.0/users/"
        f"{cfg.from_address}/sendMail"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    try:
        resp = requests.post(url, json=message, headers=headers, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("Graph API timed out while sending email.")
    except requests.exceptions.HTTPError:
        try:
            detail = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(
            f"Graph API send failed ({resp.status_code}): {detail}"
        )
