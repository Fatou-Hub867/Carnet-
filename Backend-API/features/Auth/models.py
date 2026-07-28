from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


class PatientStatus(str, enum.Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class DoctorStatus(str, enum.Enum):
    PENDING_VALIDATION = "pending_validation"
    VALIDATED = "validated"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    DELETED = "deleted"


# A doctor can authenticate in any of these statuses (e.g. to see a "pending"
# or "suspended" notice screen); REJECTED and DELETED cannot log in at all.
# Shared between Auth/logic.py and core/deps.py so the rule lives in one place.
DOCTOR_LOGIN_ALLOWED_STATUSES = frozenset(
    {DoctorStatus.PENDING_VALIDATION, DoctorStatus.VALIDATED, DoctorStatus.SUSPENDED}
)


class UserType(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)
    place_of_birth: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str] = mapped_column(String(30))
    country_of_residence: Mapped[str] = mapped_column(String(100))
    gender: Mapped[Gender] = mapped_column(Enum(Gender))
    city: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    blood_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    allergies: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[PatientStatus] = mapped_column(Enum(PatientStatus), default=PatientStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)
    place_of_birth: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(30))
    country_of_residence: Mapped[str] = mapped_column(String(100))
    gender: Mapped[Gender] = mapped_column(Enum(Gender))
    city: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    specialty: Mapped[str] = mapped_column(String(150))
    license_number: Mapped[str] = mapped_column(String(100), unique=True)
    practice_name: Mapped[str] = mapped_column(String(255))
    # Nullable: the diploma is uploaded in a second call right after registration
    # (a JSON body and a file upload cannot share a single multipart request cleanly).
    diploma_file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consultation_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[DoctorStatus] = mapped_column(Enum(DoctorStatus), default=DoctorStatus.PENDING_VALIDATION)
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_type: Mapped[UserType] = mapped_column(Enum(UserType))
    user_id: Mapped[int]
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
