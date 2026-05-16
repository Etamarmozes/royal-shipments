"""Gmail OAuth + sync service.

Responsibilities:
- OAuth2 authorization flow (Authorization Code with PKCE-equivalent state)
- Token persistence + refresh
- Listing recent messages from Gmail
- Extracting metadata (sender, subject, body, attachments) — NO parsing/matching here
- Persisting raw EmailUpdate rows with status='fetched'

Parsing/matching happens in a separate step (email_parser_service / email_sync_service.process_email).
That separation is intentional per the spec: "אל תבנה עדיין parsing — רק חיבור ומשיכת מיילים."
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from ..config import (
    GMAIL_CREDENTIALS_FILE,
    GMAIL_FRONTEND_RETURN_URL,
    GMAIL_PREFER_UNREAD,
    GMAIL_REDIRECT_URI,
    GMAIL_SCOPES,
    GMAIL_SYNC_DAYS,
    GMAIL_SYNC_MAX_MESSAGES,
    GMAIL_TOKEN_FILE,
)
from ..models import EmailUpdate, EmailAttachment
from . import event_service, document_service

log = logging.getLogger("gmail")
log.setLevel(logging.INFO)


# =====================================================================
# OAuth flow
# =====================================================================

def _ensure_credentials_file() -> None:
    if not Path(GMAIL_CREDENTIALS_FILE).exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"credentials.json לא נמצא ב-{GMAIL_CREDENTIALS_FILE}. "
                "הורד את הקובץ מ-Google Cloud Console → APIs & Services → Credentials, "
                "ושים אותו בתיקיית backend/."
            ),
        )


def _build_flow(state: Optional[str] = None) -> Flow:
    _ensure_credentials_file()
    flow = Flow.from_client_secrets_file(
        str(GMAIL_CREDENTIALS_FILE),
        scopes=GMAIL_SCOPES,
        state=state,
    )
    flow.redirect_uri = GMAIL_REDIRECT_URI
    return flow


def get_authorization_url() -> Tuple[str, str, Optional[str]]:
    """Returns (authorization_url, state, code_verifier).

    PKCE is enabled by default in google_auth_oauthlib. The library generates
    a `code_verifier` on the flow object during `authorization_url()`. We MUST
    keep that verifier and supply it back when exchanging the code, otherwise
    Google rejects with "Missing code verifier".
    """
    log.info("Gmail OAuth: building authorization URL")
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    code_verifier = getattr(flow, "code_verifier", None)
    log.info(
        "Gmail OAuth: state=%s, has_verifier=%s",
        state[:8] + "…", bool(code_verifier),
    )
    return auth_url, state, code_verifier


def exchange_code_for_token(
    code: str,
    state: Optional[str] = None,
    code_verifier: Optional[str] = None,
) -> Credentials:
    log.info(
        "Gmail OAuth: exchanging authorization code for token (has_verifier=%s)",
        bool(code_verifier),
    )
    flow = _build_flow(state=state)
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials
    _save_credentials(creds)
    log.info(
        "Gmail OAuth: token stored — has_refresh=%s, expiry=%s",
        bool(creds.refresh_token), creds.expiry,
    )
    return creds


def _save_credentials(creds: Credentials) -> None:
    Path(GMAIL_TOKEN_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(GMAIL_TOKEN_FILE).write_text(creds.to_json(), encoding="utf-8")


def _load_credentials() -> Optional[Credentials]:
    if not Path(GMAIL_TOKEN_FILE).exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_FILE), GMAIL_SCOPES)
    except Exception as e:
        log.warning("Gmail OAuth: failed to load saved token: %s", e)
        return None
    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            log.info("Gmail OAuth: token expired, refreshing")
            creds.refresh(GoogleAuthRequest())
            _save_credentials(creds)
        except Exception as e:
            log.warning("Gmail OAuth: refresh failed: %s", e)
            return None
    return creds


def is_connected() -> bool:
    creds = _load_credentials()
    return bool(creds and creds.valid)


def get_connection_status() -> Dict[str, Any]:
    creds = _load_credentials()
    return {
        "connected": bool(creds and creds.valid),
        "token_file_exists": Path(GMAIL_TOKEN_FILE).exists(),
        "credentials_file_exists": Path(GMAIL_CREDENTIALS_FILE).exists(),
        "expiry": creds.expiry.isoformat() if creds and creds.expiry else None,
        "scopes": list(creds.scopes) if creds and creds.scopes else [],
    }


def get_debug_info() -> Dict[str, Any]:
    """Full diagnostic snapshot — used by GET /gmail/debug."""
    creds = _load_credentials()
    from ..config import (
        GMAIL_SYNC_DAYS, GMAIL_SYNC_MAX_MESSAGES, GMAIL_PREFER_UNREAD,
        GMAIL_REDIRECT_URI, GMAIL_SCOPES,
    )
    from . import dashboard_service
    last_sync_at = dashboard_service.get_last_email_sync()
    return {
        "connected": bool(creds and creds.valid),
        "token": {
            "file_exists": Path(GMAIL_TOKEN_FILE).exists(),
            "valid": bool(creds and creds.valid),
            "expired": bool(creds and creds.expired),
            "has_refresh": bool(creds and creds.refresh_token),
            "expires_at": creds.expiry.isoformat() if creds and creds.expiry else None,
            "scopes": list(creds.scopes) if creds and creds.scopes else [],
        },
        "credentials_file_exists": Path(GMAIL_CREDENTIALS_FILE).exists(),
        "credentials_file_path": str(GMAIL_CREDENTIALS_FILE),
        "config": {
            "days": GMAIL_SYNC_DAYS,
            "max_messages": GMAIL_SYNC_MAX_MESSAGES,
            "prefer_unread_default": GMAIL_PREFER_UNREAD,
            "redirect_uri": GMAIL_REDIRECT_URI,
            "scopes": GMAIL_SCOPES,
        },
        "default_query": _build_query(),
        "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
        "last_sync_result": get_last_sync_result(),
    }


def disconnect() -> None:
    if Path(GMAIL_TOKEN_FILE).exists():
        Path(GMAIL_TOKEN_FILE).unlink()
        log.info("Gmail OAuth: token file deleted")


def get_frontend_return_url() -> str:
    return GMAIL_FRONTEND_RETURN_URL


# =====================================================================
# Gmail API client
# =====================================================================

def _gmail_client():
    creds = _load_credentials()
    if not creds or not creds.valid:
        raise HTTPException(
            status_code=401,
            detail="Gmail אינו מחובר. פתח /gmail/connect כדי לחבר חשבון.",
        )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _build_query(*, days: Optional[int] = None, unread_only: Optional[bool] = None) -> str:
    """Gmail search query: last N days + optionally only unread.

    Args:
        days: override GMAIL_SYNC_DAYS
        unread_only: override GMAIL_PREFER_UNREAD
    """
    d = days if days is not None else GMAIL_SYNC_DAYS
    u = unread_only if unread_only is not None else GMAIL_PREFER_UNREAD
    parts = [f"newer_than:{d}d"]
    if u:
        parts.append("is:unread")
    parts.append("-in:spam")
    parts.append("-in:trash")
    return " ".join(parts)


# Last sync result is cached on disk so /gmail/debug can display it
def _last_sync_result_path():
    from ..config import DATA_DIR
    p = DATA_DIR / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p / "last_gmail_sync.json"


def _save_last_sync(result: Dict[str, Any]) -> None:
    import json
    try:
        _last_sync_result_path().write_text(
            json.dumps(result, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning("failed to persist last sync result: %s", e)


def get_last_sync_result() -> Optional[Dict[str, Any]]:
    import json
    p = _last_sync_result_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# =====================================================================
# Message extraction
# =====================================================================

def _decode_b64url(data: str) -> bytes:
    if not data:
        return b""
    # Gmail uses URL-safe base64 with no padding
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _walk_parts(part: Dict[str, Any]):
    """Yield every part (including nested) of a Gmail message payload."""
    yield part
    for sub in part.get("parts", []) or []:
        yield from _walk_parts(sub)


def _extract_body_and_attachments(payload: Dict[str, Any]) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Returns (text_body, html_body, attachments_metadata)."""
    text_body = ""
    html_body = ""
    attachments: List[Dict[str, Any]] = []

    for part in _walk_parts(payload):
        mime = part.get("mimeType", "")
        filename = part.get("filename") or ""
        body_data = (part.get("body") or {}).get("data")
        body_size = (part.get("body") or {}).get("size", 0)
        attachment_id = (part.get("body") or {}).get("attachmentId")

        if filename:
            attachments.append({
                "filename": filename,
                "mime_type": mime,
                "size": body_size,
                "attachment_id": attachment_id,
                "part_id": part.get("partId"),
            })
            continue

        if mime == "text/plain" and body_data and not text_body:
            try:
                text_body = _decode_b64url(body_data).decode("utf-8", errors="replace")
            except Exception as e:
                log.warning("decode text/plain failed: %s", e)
        elif mime == "text/html" and body_data and not html_body:
            try:
                html_body = _decode_b64url(body_data).decode("utf-8", errors="replace")
            except Exception as e:
                log.warning("decode text/html failed: %s", e)

    return text_body, html_body, attachments


def _strip_html(html: str) -> str:
    """Cheap HTML→text stripping (for body_excerpt). No external deps."""
    if not html:
        return ""
    import re
    text = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _header(headers: List[Dict[str, str]], name: str) -> Optional[str]:
    name_low = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_low:
            return h.get("value")
    return None


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo:
            d = d.astimezone(timezone.utc).replace(tzinfo=None)
        return d
    except Exception:
        return None


# =====================================================================
# Sync
# =====================================================================

def _list_message_ids(service, query: str, *, max_messages: int = GMAIL_SYNC_MAX_MESSAGES) -> List[str]:
    """List message IDs matching the query, paginated up to max_messages."""
    ids: List[str] = []
    page_token: Optional[str] = None
    while True:
        resp = (
            service.users().messages()
            .list(
                userId="me",
                q=query,
                pageToken=page_token,
                maxResults=min(100, max_messages - len(ids)),
            )
            .execute()
        )
        msgs = resp.get("messages") or []
        ids.extend(m["id"] for m in msgs)
        page_token = resp.get("nextPageToken")
        if not page_token or len(ids) >= max_messages:
            break
    return ids[:max_messages]


def _fetch_message(service, message_id: str) -> Dict[str, Any]:
    return (
        service.users().messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )


# Limit per-attachment size to keep things sane
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_MIME_PREFIXES = ("application/pdf", "image/", "application/msword",
                        "application/vnd.openxml", "application/vnd.ms-excel",
                        "text/plain", "text/csv")


def _safe_filename(name: str) -> str:
    name = name or "attachment"
    name = re.sub(r"[^A-Za-z0-9._\-]", "_", name)
    return name[:200] or "attachment"


def download_attachment_to_disk(
    service,
    *,
    gmail_message_id: str,
    gmail_attachment_id: str,
    filename: str,
    mime_type: str,
    eu_id: int,
) -> Optional[Path]:
    """Download a Gmail attachment by ID and save to uploads/documents.
    Returns the on-disk path, or None if skipped (e.g. unsupported type).
    """
    if mime_type and not any(mime_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        log.info("skip attachment (mime not allowed): %s %s", filename, mime_type)
        return None
    try:
        att = (
            service.users().messages().attachments()
            .get(userId="me", messageId=gmail_message_id, id=gmail_attachment_id)
            .execute()
        )
    except HttpError as e:
        log.error("attachment fetch failed: %s", e)
        return None

    data = att.get("data") or ""
    if not data:
        return None
    raw = _decode_b64url(data)
    if len(raw) > MAX_ATTACHMENT_BYTES:
        log.warning("attachment %s exceeds %d bytes — saving truncated", filename, MAX_ATTACHMENT_BYTES)
        raw = raw[:MAX_ATTACHMENT_BYTES]

    safe = _safe_filename(filename)
    out_path = document_service.DOCS_DIR / f"eu{eu_id}_{safe}"
    out_path.write_bytes(raw)
    log.info("saved attachment to %s (%d bytes)", out_path.name, len(raw))
    return out_path


# Need re for _safe_filename
import re


def _message_to_email_update_kwargs(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Map a Gmail message resource into kwargs for EmailUpdate(**kwargs)."""
    payload = msg.get("payload") or {}
    headers = payload.get("headers") or []

    sender = _header(headers, "From") or ""
    subject = _header(headers, "Subject") or ""
    date_hdr = _header(headers, "Date")
    received_at = _parse_date(date_hdr)
    if not received_at:
        # fallback to internalDate (epoch ms)
        try:
            received_at = datetime.utcfromtimestamp(int(msg["internalDate"]) / 1000.0)
        except Exception:
            received_at = datetime.utcnow()

    text_body, html_body, attachments = _extract_body_and_attachments(payload)
    body = text_body or _strip_html(html_body)

    return {
        "email_message_id": msg.get("id"),
        "email_thread_id": msg.get("threadId"),
        "sender": sender,
        "subject": subject,
        "received_at": received_at,
        "body_excerpt": body[:500],
        "full_body_text": body,
        "attachment_names": [a["filename"] for a in attachments],
        "detected_fields_json": None,
        "detection_type": None,
        "confidence_score": None,
        "status": "fetched",  # raw, not yet parsed/matched
    }


def sync_inbox(
    db: Session,
    *,
    days: Optional[int] = None,
    unread_only: Optional[bool] = None,
    max_messages: Optional[int] = None,
) -> Dict[str, Any]:
    """Fetch recent messages from Gmail and persist as EmailUpdate rows.

    Does NOT invoke parser/matching — just stores raw email metadata.
    Dedup is by Gmail message_id, so re-running sync is idempotent.

    Args:
        days: window override (default GMAIL_SYNC_DAYS=7)
        unread_only: filter override (default GMAIL_PREFER_UNREAD=False).
            Set True to fetch only unread emails. Note: filtering to unread
            misses emails the user already opened in Gmail.
        max_messages: cap on messages fetched per call.
    """
    started_at = datetime.utcnow()
    log.info("Gmail SYNC start  (days=%s unread_only=%s)", days, unread_only)

    # Pre-flight: token check
    creds = _load_credentials()
    if not creds:
        msg = "No Gmail token saved. Visit /gmail/connect first."
        log.warning("Gmail SYNC abort: %s", msg)
        result = _make_sync_result(
            query=None, days=days, unread_only=unread_only,
            matched=0, inserted=0, skipped_existing=0, errors=[],
            ok=False, message=msg, started_at=started_at,
        )
        _save_last_sync(result)
        return result
    if not creds.valid:
        msg = "Gmail token expired and could not be refreshed."
        log.warning("Gmail SYNC abort: %s", msg)
        result = _make_sync_result(
            query=None, days=days, unread_only=unread_only,
            matched=0, inserted=0, skipped_existing=0, errors=[],
            ok=False, message=msg, started_at=started_at,
        )
        _save_last_sync(result)
        return result

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    query = _build_query(days=days, unread_only=unread_only)
    log.info("Gmail SYNC: query=%r", query)

    cap = max_messages if max_messages is not None else GMAIL_SYNC_MAX_MESSAGES
    try:
        msg_ids = _list_message_ids(service, query, max_messages=cap)
    except HttpError as e:
        log.error("Gmail SYNC: list HttpError: %s", e)
        result = _make_sync_result(
            query=query, days=days, unread_only=unread_only,
            matched=0, inserted=0, skipped_existing=0,
            errors=[{"phase": "list", "error": str(e)}],
            ok=False, message=f"Gmail list error: {e}", started_at=started_at,
        )
        _save_last_sync(result)
        return result

    log.info("Gmail SYNC: %d messages match query (cap=%d)", len(msg_ids), cap)

    inserted = 0
    skipped_existing = 0
    errors: List[Dict[str, str]] = []

    for i, mid in enumerate(msg_ids, 1):
        # Dedupe — don't reprocess emails we've already stored
        existing = (
            db.query(EmailUpdate)
            .filter(EmailUpdate.email_message_id == mid)
            .first()
        )
        if existing:
            skipped_existing += 1
            continue

        try:
            log.info("Gmail SYNC: fetching message %d/%d id=%s", i, len(msg_ids), mid)
            msg = _fetch_message(service, mid)
            kwargs = _message_to_email_update_kwargs(msg)
            eu = EmailUpdate(**kwargs)
            db.add(eu)
            db.flush()
            event_service.log_event(
                db,
                entity_type="email_update",
                entity_id=eu.id,
                action_type="gmail_fetched",
                new_value=kwargs.get("subject"),
                changed_by="system",
                source="email_import",
                note=f"sender={kwargs.get('sender')}",
            )

            # Download attachments to disk (PDF / images / docs)
            payload = msg.get("payload") or {}
            _, _, attachments_meta = _extract_body_and_attachments(payload)
            for a in attachments_meta:
                if not a.get("attachment_id"):
                    continue
                fpath = download_attachment_to_disk(
                    service,
                    gmail_message_id=mid,
                    gmail_attachment_id=a["attachment_id"],
                    filename=a.get("filename") or "attachment",
                    mime_type=a.get("mime_type") or "",
                    eu_id=eu.id,
                )
                if fpath:
                    doc_type = document_service.guess_document_type(
                        filename=a.get("filename"),
                        subject=eu.subject,
                        body=eu.body_excerpt,
                    )
                    db.add(EmailAttachment(
                        email_update_id=eu.id,
                        filename=a.get("filename"),
                        file_type=a.get("mime_type"),
                        file_size=a.get("size") or len(fpath.read_bytes()) if fpath.exists() else None,
                        file_path=f"documents/{fpath.name}",
                        document_type=doc_type,
                        gmail_attachment_id=a["attachment_id"],
                    ))
            # Detect Drive links in body and store as link-only attachments
            links = document_service.find_drive_links(eu.full_body_text)
            for link in links:
                exists = db.query(EmailAttachment).filter(
                    EmailAttachment.email_update_id == eu.id,
                    EmailAttachment.source_url == link,
                ).first()
                if exists:
                    continue
                db.add(EmailAttachment(
                    email_update_id=eu.id,
                    filename=f"Drive link",
                    file_type="text/uri-list",
                    file_path=None,
                    source_url=link,
                    document_type=document_service.guess_doc_type_from_link(link),
                ))
            db.flush()
            inserted += 1
        except HttpError as e:
            log.error("Gmail SYNC: HttpError on %s: %s", mid, e)
            errors.append({"id": mid, "error": str(e)})
        except Exception as e:
            log.exception("Gmail SYNC: unexpected error on %s", mid)
            errors.append({"id": mid, "error": str(e)})

    db.commit()
    from . import dashboard_service
    dashboard_service.set_last_email_sync()

    if inserted == 0 and skipped_existing == 0 and not errors:
        message = "No new emails found"
    elif inserted == 0 and skipped_existing > 0:
        message = f"No new emails — {skipped_existing} already in DB"
    else:
        message = f"{inserted} new emails inserted ({skipped_existing} already in DB)"

    log.info(
        "Gmail SYNC done — matched=%d inserted=%d skipped_existing=%d errors=%d | %s",
        len(msg_ids), inserted, skipped_existing, len(errors), message,
    )
    result = _make_sync_result(
        query=query, days=days, unread_only=unread_only,
        matched=len(msg_ids), inserted=inserted,
        skipped_existing=skipped_existing, errors=errors,
        ok=True, message=message, started_at=started_at,
    )
    _save_last_sync(result)
    return result


def backfill_attachments(db: Session) -> Dict[str, Any]:
    """Retroactively download attachments for already-synced emails that have
    `attachment_names` set but no `EmailAttachment` rows on disk.

    Also tries to auto-link each downloaded attachment to a shipment/container
    based on the email's already-classified `detected_fields_json`.
    """
    started_at = datetime.utcnow()
    log.info("Gmail BACKFILL start")

    creds = _load_credentials()
    if not creds or not creds.valid:
        return {
            "ok": False, "message": "Gmail not connected",
            "scanned": 0, "downloaded": 0, "linked": 0,
        }
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # Pass 1: detect Drive links in any EU body that doesn't have them yet
    drive_added = 0
    for eu in db.query(EmailUpdate).filter(EmailUpdate.full_body_text.isnot(None)).all():
        links = document_service.find_drive_links(eu.full_body_text)
        for link in links:
            exists = db.query(EmailAttachment).filter(
                EmailAttachment.email_update_id == eu.id,
                EmailAttachment.source_url == link,
            ).first()
            if exists:
                continue
            db.add(EmailAttachment(
                email_update_id=eu.id,
                filename="Drive link",
                file_type="text/uri-list",
                file_path=None,
                source_url=link,
                document_type=document_service.guess_doc_type_from_link(link),
            ))
            drive_added += 1
    if drive_added:
        db.flush()
        log.info("Backfill: %d Drive links detected", drive_added)

    # Find EUs that claim to have attachments but no EmailAttachment rows yet
    eus = db.query(EmailUpdate).filter(
        EmailUpdate.email_message_id.isnot(None),
        EmailUpdate.attachment_names.isnot(None),
    ).all()
    targets: List[EmailUpdate] = []
    for eu in eus:
        names = eu.attachment_names or []
        if not names:
            continue
        existing = db.query(EmailAttachment).filter(
            EmailAttachment.email_update_id == eu.id
        ).count()
        if existing == 0:
            targets.append(eu)
    log.info("Backfill: %d EUs need attachment download", len(targets))

    downloaded = 0
    linked = 0
    errors: List[Dict[str, Any]] = []

    for eu in targets:
        try:
            msg = _fetch_message(service, eu.email_message_id)
            payload = msg.get("payload") or {}
            _, _, attachments_meta = _extract_body_and_attachments(payload)
            for meta in attachments_meta:
                if not meta.get("attachment_id"):
                    continue
                fpath = download_attachment_to_disk(
                    service,
                    gmail_message_id=eu.email_message_id,
                    gmail_attachment_id=meta["attachment_id"],
                    filename=meta.get("filename") or "attachment",
                    mime_type=meta.get("mime_type") or "",
                    eu_id=eu.id,
                )
                if not fpath:
                    continue
                doc_type = document_service.guess_document_type(
                    filename=meta.get("filename"),
                    subject=eu.subject,
                    body=eu.body_excerpt,
                )
                att = EmailAttachment(
                    email_update_id=eu.id,
                    filename=meta.get("filename"),
                    file_type=meta.get("mime_type"),
                    file_size=meta.get("size") or fpath.stat().st_size,
                    file_path=f"documents/{fpath.name}",
                    document_type=doc_type,
                    gmail_attachment_id=meta["attachment_id"],
                )
                db.add(att)
                db.flush()
                downloaded += 1

                # Auto-link via parsed fields + filename scan
                ship_id, cont_id = document_service.attempt_link_to_shipment(
                    db, parsed_fields=eu.detected_fields_json,
                    sender=eu.sender,
                    filename=meta.get("filename"),
                )
                # Fallback: if EU itself was matched to a shipment via classify
                if not ship_id and eu.detected_shipment_id:
                    ship_id = eu.detected_shipment_id
                if not cont_id and eu.detected_container_id:
                    cont_id = eu.detected_container_id

                if ship_id:
                    att.linked_shipment_id = ship_id
                    if cont_id:
                        att.linked_container_id = cont_id
                    linked += 1
                    db.flush()
                    log.info("Backfill: linked %s → shipment#%s", att.filename, ship_id)
        except Exception as e:
            log.exception("Backfill failed for EU#%s", eu.id)
            errors.append({"eu_id": eu.id, "error": str(e)})

    db.commit()
    finished_at = datetime.utcnow()
    log.info("Gmail BACKFILL done: scanned=%d downloaded=%d linked=%d errors=%d",
             len(targets), downloaded, linked, len(errors))
    return {
        "ok": True,
        "message": f"{downloaded} files downloaded, {linked} auto-linked",
        "scanned": len(targets),
        "downloaded": downloaded,
        "linked": linked,
        "errors": errors,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }


def _make_sync_result(
    *, query, days, unread_only, matched, inserted, skipped_existing,
    errors, ok, message, started_at,
) -> Dict[str, Any]:
    finished_at = datetime.utcnow()
    return {
        "ok": ok,
        "message": message,
        "query": query,
        "days": days if days is not None else GMAIL_SYNC_DAYS,
        "unread_only": (
            unread_only if unread_only is not None else GMAIL_PREFER_UNREAD
        ),
        "matched": matched,
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "errors": errors,
        "started_at": started_at.isoformat(),
        "synced_at": finished_at.isoformat(),
        "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
    }
