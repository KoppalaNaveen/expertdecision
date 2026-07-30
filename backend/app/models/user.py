from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
)

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(100), nullable=False)

    email = Column(String(100), unique=True, nullable=False)

    employee_id = Column(String(50), unique=True, index=True)

    password = Column(String(255), nullable=False)

    role_id = Column(Integer, ForeignKey("roles.id"), nullable = False)

    role = relationship( "Role", back_populates="users")

    team_id = Column(Integer, ForeignKey("teams.id"))
    team = relationship("Team", back_populates="users")

    designation = Column(String(100))

    phone = Column(String(20))

    is_active = Column(Boolean, default=True)

    email_verified = Column(Boolean, default=False)
    approved = Column(Boolean, default=False)
    status = Column(String(50), default="Pending Approval")

    approved_by = Column(String(100), nullable=True)
    approved_at = Column(String(50), nullable=True)
    rejected_by = Column(String(100), nullable=True)
    rejected_at = Column(String(50), nullable=True)

    created_at = Column(String(50), nullable=True)
    updated_at = Column(String(50), nullable=True)


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), index=True, nullable=False)
    code = Column(String(10), nullable=False)
    expires_at = Column(Integer, nullable=False)  # Unix timestamp
    purpose = Column(String(20), nullable=False)  # "register", "reset_password"