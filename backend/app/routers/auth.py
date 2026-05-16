"""Auth endpoints — login, me, change password, logout."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services import auth_service
from ..services.auth_service import (
    get_current_user, authenticate, hash_password, verify_password,
    create_access_token, has_permission,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _user_dict(u: User) -> dict:
    is_active = u.is_active if u.is_active is not None else u.active
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name or u.name,
        "email": u.email,
        "phone": u.phone,
        "role": u.role,
        "is_active": bool(is_active),
        "must_change_password": bool(u.must_change_password),
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, payload.username.strip(), payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="שם משתמש או קוד שגויים",
        )
    # Persist last_login_at only for real DB users — emergency admin (id=-1)
    # is synthetic and must not touch the DB.
    if user.id and user.id > 0:
        user.last_login_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
    token = create_access_token(user)
    return LoginResponse(access_token=token, user=_user_dict(user))


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    """Stateless JWT — actual revocation happens by client deleting the token.
    This endpoint exists so the client can confirm it's authenticated."""
    return {"ok": True, "message": "נותקת"}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {**_user_dict(user), "permissions": _user_permission_set(user)}


def _user_permission_set(user: User) -> list[str]:
    """Return a list of permission strings the user has — used by frontend
    to hide buttons without re-implementing the permission table client-side."""
    out = []
    for action in auth_service.PERMISSIONS:
        if has_permission(user, action):
            out.append(action)
    return out


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="הסיסמה הנוכחית שגויה")
    new = payload.new_password.strip()
    if len(new) < 4:
        raise HTTPException(status_code=400, detail="סיסמה קצרה מדי (לפחות 4 תווים)")
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": "הסיסמה שונתה"}
