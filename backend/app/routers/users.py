"""User management — admin only."""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..models.user import VALID_ROLES
from ..services.auth_service import (
    get_current_user, hash_password, require_permission,
)
from ..services import event_service

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_permission("users.manage"))],
)


class UserCreate(BaseModel):
    username: str
    full_name: str
    password: str
    role: str = "viewer"
    email: Optional[str] = None
    phone: Optional[str] = None
    must_change_password: bool = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str
    must_change_password: bool = True


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
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


@router.get("")
def list_users(db: Session = Depends(get_db)):
    rows = db.query(User).filter(User.username.isnot(None)).order_by(User.id).all()
    return [_user_dict(u) for u in rows]


@router.post("")
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                actor: User = Depends(get_current_user)):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role לא חוקי: {payload.role}")
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="שם משתמש חובה")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="שם משתמש כבר קיים")
    if len(payload.password.strip()) < 4:
        raise HTTPException(status_code=400, detail="סיסמה קצרה מדי (לפחות 4 תווים)")

    # email column has a NOT NULL constraint in the original schema; supply
    # a placeholder if missing (the field stays optional in the API).
    email_value = payload.email or f"{username}@local"
    u = User(
        username=username,
        full_name=payload.full_name.strip(),
        name=payload.full_name.strip(),
        email=email_value,
        phone=payload.phone,
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_active=True,
        active=True,
        must_change_password=payload.must_change_password,
    )
    db.add(u)
    db.flush()
    event_service.log_event(
        db, entity_type="user", entity_id=u.id,
        action_type="create_user",
        new_value=f"{u.username} ({u.role})",
        changed_by=actor.username, source="manual",
    )
    db.commit()
    return _user_dict(u)


@router.put("/{user_id}")
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db),
                actor: User = Depends(get_current_user)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"role לא חוקי: {payload.role}")
        u.role = payload.role
    if payload.full_name is not None:
        u.full_name = payload.full_name
        u.name = payload.full_name
    if payload.email is not None:
        u.email = payload.email
    if payload.phone is not None:
        u.phone = payload.phone
    if payload.is_active is not None:
        # Prevent self-deactivation by the only admin
        if not payload.is_active and u.id == actor.id:
            raise HTTPException(status_code=400, detail="אסור להשבית את עצמך")
        u.is_active = payload.is_active
        u.active = payload.is_active
    u.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(u)
    event_service.log_event(
        db, entity_type="user", entity_id=u.id,
        action_type="update_user", changed_by=actor.username, source="manual",
        note=str(payload.model_dump(exclude_unset=True)),
    )
    db.commit()
    return _user_dict(u)


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, payload: PasswordReset, db: Session = Depends(get_db),
                   actor: User = Depends(get_current_user)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")
    if len(payload.new_password.strip()) < 4:
        raise HTTPException(status_code=400, detail="סיסמה קצרה מדי")
    u.password_hash = hash_password(payload.new_password)
    u.must_change_password = payload.must_change_password
    u.updated_at = datetime.utcnow()
    db.commit()
    event_service.log_event(
        db, entity_type="user", entity_id=u.id,
        action_type="reset_password", changed_by=actor.username, source="manual",
    )
    db.commit()
    return {"ok": True}


@router.get("/roles/list")
def list_roles():
    return {
        "roles": [
            {"id": "admin",          "label": "מנהל"},
            {"id": "import_manager", "label": "מנהל יבוא"},
            {"id": "warehouse",      "label": "מחסן"},
            {"id": "viewer",         "label": "צופה"},
        ]
    }
