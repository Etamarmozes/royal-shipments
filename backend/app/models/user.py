from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime

from ..database import Base


class User(Base):
    """Users + RBAC.

    Roles (used by services/auth_service.has_permission):
    - admin           — full access
    - import_manager  — full shipping ops; approve email updates; manage data
    - warehouse       — read-only on shipments; receiving + doc upload only
    - viewer          — read-only

    Backward-compat note: 'name' and 'active' are kept (nullable) because the
    pre-auth seed populated them; new code reads `full_name` and `is_active`.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # NEW fields (auth)
    username = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    must_change_password = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Existing (kept for compat — older seed populated these)
    name = Column(String, nullable=True)
    email = Column(String, index=True, nullable=True)
    role = Column(String, default="viewer")
    password_hash = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


VALID_ROLES = {"admin", "import_manager", "warehouse", "viewer"}
