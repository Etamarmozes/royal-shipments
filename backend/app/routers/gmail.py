"""Gmail OAuth + sync endpoints.

Flow:
  1. User clicks "Connect Gmail" in frontend → opens GET /gmail/connect
  2. Backend redirects to Google's auth URL
  3. User grants permission in Google → Google redirects to GET /gmail/callback?code=...
  4. Backend exchanges code for tokens, persists them, redirects user back to frontend
  5. Frontend / scheduler can now POST /gmail/sync to pull new messages
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status as http_status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import GMAIL_DISABLED
from ..database import get_db
from ..services import gmail_service

router = APIRouter(prefix="/gmail", tags=["gmail"])

log = logging.getLogger("gmail")


def _check_enabled():
    """Short-circuit when the operator disabled Gmail (account suspended /
    OAuth credentials revoked / etc). All Gmail endpoints become 503 with a
    clear, translatable message — the rest of the app keeps working."""
    if GMAIL_DISABLED:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Gmail integration כבוי כרגע (GMAIL_DISABLED=true). "
                "ניתן להמשיך לעבוד ידנית — סנכרון אוטומטי של מיילים מושבת. "
                "להפעלה מחדש: בטל את ה-env var GMAIL_DISABLED והפעל מחדש את ה-backend."
            ),
        )


@router.get("/status")
def status():
    """Quick check of connection status — used by frontend to show 'Connect' vs 'Sync now' buttons.

    Always answers 200 (even when GMAIL_DISABLED) so the UI can render the
    correct state without hitting a 503."""
    base = gmail_service.get_connection_status()
    base["disabled"] = GMAIL_DISABLED
    if GMAIL_DISABLED:
        base["connected"] = False
        base["disabled_reason"] = (
            "Gmail מנותק זמנית ע״י המנהל (חשבון Google מושעה / לא זמין). "
            "מצב ידני בלבד."
        )
    return base


@router.get("/connect")
def connect(request: Request):
    """Start OAuth flow — redirect user to Google's consent screen."""
    _check_enabled()
    auth_url, state, code_verifier = gmail_service.get_authorization_url()
    log.info("Gmail /connect → redirecting to Google consent screen")
    response = RedirectResponse(auth_url, status_code=302)
    # Persist state + PKCE verifier in cookies to use on callback
    response.set_cookie(
        "gmail_oauth_state", state, httponly=True, max_age=600, samesite="lax"
    )
    if code_verifier:
        response.set_cookie(
            "gmail_oauth_verifier", code_verifier,
            httponly=True, max_age=600, samesite="lax",
        )
    return response


@router.get("/callback")
def callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """OAuth callback — exchange the authorization code for tokens."""
    _check_enabled()
    if error:
        log.warning("Gmail /callback error param: %s", error)
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="חסר code בכתובת ה-callback")

    expected_state = request.cookies.get("gmail_oauth_state")
    if expected_state and state and expected_state != state:
        log.warning("Gmail /callback: state mismatch (cookie=%s, query=%s)",
                    expected_state[:8], state[:8])
        raise HTTPException(status_code=400, detail="State mismatch — חשד ל-CSRF")

    code_verifier = request.cookies.get("gmail_oauth_verifier")
    if not code_verifier:
        log.warning("Gmail /callback: no code_verifier cookie present (PKCE)")

    gmail_service.exchange_code_for_token(
        code, state=state, code_verifier=code_verifier,
    )

    # Redirect back to frontend
    return_url = gmail_service.get_frontend_return_url() + "?gmail=connected"
    log.info("Gmail /callback → redirecting back to frontend: %s", return_url)
    response = RedirectResponse(return_url, status_code=302)
    response.delete_cookie("gmail_oauth_state")
    response.delete_cookie("gmail_oauth_verifier")
    return response


@router.post("/sync")
def sync(
    db: Session = Depends(get_db),
    days: Optional[int] = None,
    unread_only: Optional[bool] = None,
    max_messages: Optional[int] = None,
):
    """Pull recent messages from Gmail and store them in EmailUpdate (raw, no parsing).

    Query params (all optional, override config defaults):
    - days: how many days back to look (default 7)
    - unread_only: if true, only fetch unread emails. Default false — pulls
      read emails too (dedup prevents repeats). Setting true risks missing
      emails the user already opened in Gmail.
    - max_messages: cap on total fetched per call (default 100)
    """
    _check_enabled()
    from ..services.dashboard_service import get_last_email_sync
    try:
        return gmail_service.sync_inbox(
            db, days=days, unread_only=unread_only, max_messages=max_messages,
        )
    except HTTPException:
        raise
    except Exception as e:
        # Wrap Google API failures (suspended account, revoked token, network)
        # in a clear 503 instead of a confusing 500 stack trace.
        log.exception("Gmail sync failed: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Gmail sync נכשל: {e}. "
                "החשבון מושעה / מנותק / אין אינטרנט. "
                "ניתן להמשיך לעבוד ידנית. כדי לכבות את ה-sync האוטומטי "
                "ולהסיר את ההתראה הזו, הגדר GMAIL_DISABLED=true."
            ),
        )


@router.post("/backfill-attachments")
def backfill_attachments(db: Session = Depends(get_db)):
    """One-shot retroactive download of attachments for emails already in DB.
    Use this after upgrading the system, or whenever you suspect attachment
    rows are missing for synced emails."""
    _check_enabled()
    try:
        return gmail_service.backfill_attachments(db)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Gmail backfill failed: %s", e)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Backfill נכשל: {e}",
        )


@router.get("/debug")
def debug():
    """Diagnostic snapshot — connection state, token, config, last sync result."""
    return gmail_service.get_debug_info()


@router.post("/disconnect")
def disconnect():
    gmail_service.disconnect()
    return {"ok": True, "message": "Gmail מנותק. הטוקן נמחק."}
