"""Authentication + RBAC.

- Passwords: bcrypt via passlib (never stored plain).
- Tokens: JWT (HS256) via python-jose, with sub=user_id, role, exp.
- Token TTL: 24h.

Use `get_current_user` as a FastAPI dependency on protected routers.
Use `require_role(...)` to gate specific routes.
Use `has_permission(user, action)` from anywhere for fine-grained checks.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Iterable

import bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from ..config import (
    AUTH_SECRET, AUTH_TOKEN_TTL_HOURS,
    AUTH_BOOTSTRAP_USERNAME, AUTH_BOOTSTRAP_PASSWORD,
    EMERGENCY_ADMIN_USERNAME, EMERGENCY_ADMIN_PASSWORD,
)
from ..database import get_db
from ..models import User
from ..models.user import VALID_ROLES

# Sentinel id for the env-var emergency admin. Never written to the DB.
EMERGENCY_ADMIN_ID = -1

log = logging.getLogger("auth")

# OAuth2PasswordBearer auto-extracts Bearer token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# =====================================================================
# Password hashing — bcrypt directly (passlib 1.7.4 doesn't support bcrypt 5.x)
# =====================================================================

def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("password cannot be empty")
    # bcrypt has a 72-byte input limit — truncate if longer (standard practice)
    pw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: Optional[str]) -> bool:
    if not hashed or not plain:
        return False
    try:
        pw = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except Exception as e:
        log.warning("verify_password error: %s", e)
        return False


# =====================================================================
# JWT
# =====================================================================

def create_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=AUTH_TOKEN_TTL_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, AUTH_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, AUTH_SECRET, algorithms=["HS256"])


# =====================================================================
# Login + lookup
# =====================================================================

def find_by_username(db: Session, username: str) -> Optional[User]:
    if not username:
        return None
    return db.query(User).filter(User.username == username).first()


def _emergency_admin() -> Optional[User]:
    """Build a synthetic in-memory admin User from env vars.
    Never persisted. Used as a break-glass when the DB is unavailable
    or the real admin row is gone."""
    if not EMERGENCY_ADMIN_USERNAME or not EMERGENCY_ADMIN_PASSWORD:
        return None
    u = User(
        id=EMERGENCY_ADMIN_ID,
        username=EMERGENCY_ADMIN_USERNAME,
        full_name="Emergency Admin",
        name="Emergency Admin",
        email="emergency@local",
        role="admin",
        password_hash="(env)",  # placeholder, never compared
        is_active=True,
        active=True,
        must_change_password=False,
    )
    return u


def authenticate(db: Session, username: str, password: str) -> Optional[User]:
    # 1. Emergency env-var admin — checked FIRST so the app stays usable
    #    even if the database is empty / locked / corrupt.
    if (EMERGENCY_ADMIN_USERNAME and EMERGENCY_ADMIN_PASSWORD
            and username == EMERGENCY_ADMIN_USERNAME
            and password == EMERGENCY_ADMIN_PASSWORD):
        log.warning("Emergency admin login used (username=%s)", username)
        return _emergency_admin()

    # 2. Normal DB-backed user lookup
    try:
        user = find_by_username(db, username)
    except Exception as e:
        log.error("DB lookup failed during login: %s", e)
        return None
    if not user:
        return None
    if not (user.is_active if user.is_active is not None else user.active):
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# =====================================================================
# FastAPI dependencies
# =====================================================================

class AuthError(HTTPException):
    def __init__(self, detail: str = "אינך מורשה"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: require a valid Bearer token, return the User row."""
    if not token:
        raise AuthError("נדרש אימות")
    try:
        payload = decode_access_token(token)
    except JWTError as e:
        raise AuthError(f"טוקן לא תקין: {e}")
    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("טוקן ללא משתמש")
    uid = int(user_id)

    # Emergency admin: synthetic, never in DB
    if uid == EMERGENCY_ADMIN_ID:
        u = _emergency_admin()
        # Token must match current env (rotation safety): if env was wiped
        # since the token was issued, reject.
        if not u or payload.get("username") != u.username:
            raise AuthError("מצב חירום: טוקן לא תואם למשתמש החירום הנוכחי")
        return u

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise AuthError("המשתמש לא נמצא")
    is_active = user.is_active if user.is_active is not None else user.active
    if not is_active:
        raise AuthError("המשתמש מושבת")
    return user


def require_role(*roles: str):
    """FastAPI dependency factory: only allow users whose role is in `roles`."""
    role_set = set(roles)

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in role_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"נדרשת הרשאה: {', '.join(sorted(role_set))}",
            )
        return user
    return _check


# =====================================================================
# Permissions matrix — used by both backend gates and UI
# =====================================================================

# action → set of allowed roles
PERMISSIONS = {
    # data writes
    "shipment.create":         {"admin", "import_manager"},
    "shipment.update":         {"admin", "import_manager"},
    "shipment.delete":         {"admin"},
    "shipment.update_eta":     {"admin", "import_manager"},  # warehouse can NOT
    "container.create":        {"admin", "import_manager"},
    "container.update":        {"admin", "import_manager"},
    "container.delete":        {"admin", "import_manager"},
    "extra_work.write":        {"admin", "import_manager"},

    # email + pending decisions (manager/admin only)
    "email.approve":           {"admin", "import_manager"},
    "email.reject":            {"admin", "import_manager"},
    "email.process":           {"admin", "import_manager"},
    "pending.approve":         {"admin", "import_manager"},
    "pending.reject":          {"admin", "import_manager"},
    "gmail.sync":              {"admin", "import_manager"},
    "gmail.connect":           {"admin"},

    # warehouse-friendly
    "document.upload":         {"admin", "import_manager", "warehouse"},
    "document.assign":         {"admin", "import_manager", "warehouse"},
    "document.delete":         {"admin", "import_manager"},
    "receiving.update":        {"admin", "import_manager", "warehouse"},
    "product_image.upload":    {"admin", "import_manager", "warehouse"},
    "alert.resolve":           {"admin", "import_manager"},

    # admin-only
    "users.manage":            {"admin"},
    "shipment.archive":        {"admin", "import_manager"},
    "category.manage":         {"admin", "import_manager"},

    # everyone authenticated can read
    "shipment.read":           {"admin", "import_manager", "warehouse", "viewer"},
    "container.read":          {"admin", "import_manager", "warehouse", "viewer"},
    "document.read":           {"admin", "import_manager", "warehouse", "viewer"},
    "ai.ask":                  {"admin", "import_manager", "warehouse", "viewer"},
}


def has_permission(user: User, action: str) -> bool:
    if not user:
        return False
    allowed = PERMISSIONS.get(action)
    if allowed is None:
        # Unknown action — default deny except admin
        return user.role == "admin"
    return user.role in allowed


def require_permission(action: str):
    """FastAPI dependency factory: require a specific permission."""
    def _check(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"אין הרשאה לפעולה: {action}",
            )
        return user
    return _check


# =====================================================================
# Bootstrap admin
# =====================================================================

def bootstrap_admin(db: Session) -> None:
    """Ensure at least one admin user exists. Creates 'admin/123456' with
    must_change_password=true if there are no users in the system."""
    existing = db.query(User).filter(
        (User.username.isnot(None)) & (User.password_hash.isnot(None))
    ).count()
    if existing > 0:
        log.info("auth bootstrap: %d users already exist, skipping", existing)
        return
    admin = User(
        username=AUTH_BOOTSTRAP_USERNAME,
        full_name="מנהל ראשי",
        name="מנהל ראשי",
        email="admin@royallinen.local",
        role="admin",
        password_hash=hash_password(AUTH_BOOTSTRAP_PASSWORD),
        is_active=True,
        active=True,
        must_change_password=True,
    )
    db.add(admin)
    db.commit()
    log.info("auth bootstrap: created admin user '%s' (must change password on first login)",
             AUTH_BOOTSTRAP_USERNAME)
