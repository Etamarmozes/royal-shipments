"""
Application configuration.

Everything that varies between environments (dev / staging / production)
should come from environment variables. The defaults below are safe for
local development on a single machine.

Set these in `.env` (loaded by your process manager / shell) or as real
environment variables in production:

  DATABASE_URL              postgresql://user:pass@host:5432/db (default: sqlite local file)
  AUTH_SECRET               long random string — JWT signing key (REQUIRED in prod)
  AUTH_TOKEN_TTL_HOURS      JWT lifetime in hours (default 24)
  AUTH_BOOTSTRAP_USERNAME   first-time admin username (default "admin")
  AUTH_BOOTSTRAP_PASSWORD   first-time admin password (default "123456")
  CORS_ALLOWED_ORIGINS      comma-separated list of frontend origins
  FRONTEND_URL              public URL of the frontend (used for OAuth return)
  BACKEND_URL               public URL of the backend (used for OAuth redirect)
  GMAIL_CREDENTIALS_FILE    path to Google OAuth client_secrets.json
  GMAIL_REDIRECT_URI        full https URL Google should redirect back to
  FILE_STORAGE_PATH         absolute path for uploaded files (default ./uploads)
  EMAIL_SYNC_INTERVAL_MINUTES   background sync interval (default 60)
"""
import os
from pathlib import Path

# Optionally load a `.env` file at backend/.env (one level above this file).
# python-dotenv is a transitive dep of pydantic-settings (already in
# requirements.txt) so it's always available in the venv.  Falls back
# silently when dotenv isn't present so the app stays bootable.
try:
    from dotenv import load_dotenv
    _ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)   # don't clobber real env vars
except Exception:
    pass


def _env(key: str, default: str = "") -> str:
    """Read an env var, treating empty string as missing."""
    v = os.environ.get(key, default)
    return v if v != "" else default


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.environ.get(key, "")
    if not v:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# File storage path is configurable so production can mount a volume / S3 sync
UPLOADS_DIR = Path(_env("FILE_STORAGE_PATH", str(BASE_DIR / "uploads")))

DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Database — defaults to local SQLite, can be swapped for Postgres in prod
DATABASE_URL = _env("DATABASE_URL", f"sqlite:///{DATA_DIR / 'royal_linen.db'}")

# Background email-sync cadence (minutes)
EMAIL_SYNC_INTERVAL_MINUTES = _env_int("EMAIL_SYNC_INTERVAL_MINUTES", 60)

# Internal SHP id sequence
SHP_ID_PREFIX = "SHP-"
SHP_ID_START = 12
SHP_ID_PADDING = 3

# Frontend / backend public URLs (used to build redirect targets)
FRONTEND_URL = _env("FRONTEND_URL", "http://localhost:5173")
BACKEND_URL = _env("BACKEND_URL", "http://localhost:8000")

# CORS — comma separated list, plus a sensible local-dev default that includes
# the LAN IP (so the phone on the same Wi-Fi can hit the backend)
_default_origins = ",".join([
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    FRONTEND_URL,
])
ALLOWED_ORIGINS = [
    o.strip() for o in _env("CORS_ALLOWED_ORIGINS", _default_origins).split(",")
    if o.strip()
]

# ---- Gmail OAuth ----
GMAIL_CREDENTIALS_FILE = Path(_env(
    "GMAIL_CREDENTIALS_FILE", str(BASE_DIR / "credentials.json"),
))
GMAIL_TOKEN_FILE = DATA_DIR / "gmail_token.json"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]
GMAIL_REDIRECT_URI = _env("GMAIL_REDIRECT_URI", f"{BACKEND_URL}/gmail/callback")
# default sync window — last 7 days, ALL emails (read+unread), dedup handles repeats
GMAIL_SYNC_DAYS = _env_int("GMAIL_SYNC_DAYS", 7)
GMAIL_SYNC_MAX_MESSAGES = _env_int("GMAIL_SYNC_MAX_MESSAGES", 100)
# Set to True to ONLY fetch unread emails. Default False — read emails in
# the last N days are also pulled. Dedup by Gmail message_id prevents repeats.
GMAIL_PREFER_UNREAD = _env_bool("GMAIL_PREFER_UNREAD", False)
# After OAuth, redirect the user back to the frontend
GMAIL_FRONTEND_RETURN_URL = _env(
    "GMAIL_FRONTEND_RETURN_URL", f"{FRONTEND_URL}/email-updates"
)

# ---- Auth ----
# In production, AUTH_SECRET MUST come from env. The default below is for dev only.
AUTH_SECRET = _env(
    "AUTH_SECRET",
    "dev-secret-change-me-before-prod-7e9f4a2b1c8d6e5a3f0b9c2d4e6f8a1b",
)
AUTH_TOKEN_TTL_HOURS = _env_int("AUTH_TOKEN_TTL_HOURS", 24)
AUTH_BOOTSTRAP_USERNAME = _env("AUTH_BOOTSTRAP_USERNAME", "admin")
AUTH_BOOTSTRAP_PASSWORD = _env("AUTH_BOOTSTRAP_PASSWORD", "123456")

# ---- Emergency admin (bypasses the DB) ----
# These two env vars create a synthetic admin who can ALWAYS log in, even if
# the users table is empty / corrupted / locked / the bootstrap admin was
# deleted. Use only for break-glass recovery. Both must be set to enable.
# The synthetic admin has id = -1 and never touches the database.
EMERGENCY_ADMIN_USERNAME = _env("EMERGENCY_ADMIN_USERNAME", "")
EMERGENCY_ADMIN_PASSWORD = _env("EMERGENCY_ADMIN_PASSWORD", "")

# ---- Gmail integration kill-switch ----
# Set GMAIL_DISABLED=true to short-circuit every /gmail/* endpoint with a 503.
# Use this when your Google account is suspended / down / under investigation
# so the rest of the app stays up and the UI shows a clean "Gmail disabled"
# banner instead of confusing OAuth errors.
GMAIL_DISABLED = _env_bool("GMAIL_DISABLED", False)


def is_production() -> bool:
    """Heuristic: AUTH_SECRET must be overridden in production."""
    return AUTH_SECRET != "dev-secret-change-me-before-prod-7e9f4a2b1c8d6e5a3f0b9c2d4e6f8a1b"
