from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class DocumentSourceType(str, enum.Enum):
    MANUAL_UPLOAD = "manual_upload"
    PRESCRIPTION = "prescription"
    MESSAGE = "message"
    DOCTOR_UPLOAD = "doctor_upload"


class DocumentAddedBy(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    SYSTEM = "system"


class HealthRecordDocument(Base):
    """Fed by four sources (confirmed in brainstorming): manual patient
    upload, automatic on prescription creation, automatic when a doctor
    sends a messaging attachment, and direct doctor upload."""

    __tablename__ = "health_record_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    source_type: Mapped[DocumentSourceType] = mapped_column(Enum(DocumentSourceType))
    added_by: Mapped[DocumentAddedBy] = mapped_column(Enum(DocumentAddedBy))
    file_key: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    prescription_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescriptions.id"), nullable=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctors.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VitalSignBilan(Base):
    """One point-in-time measurement. Holds either a manual bilan (systolic +
    diastolic + glycemia_g_l + heart_rate_bpm, never weight_kg) or an automatic
    weight snapshot (only weight_kg, written inline by
    Patients.logic.update_patient_profile whenever the profile's weight_kg
    changes — the profile stays the only place a patient edits their weight;
    see the design spec for why one table serves both cases)."""

    __tablename__ = "vital_sign_bilans"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    systolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diastolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    glycemia_g_l: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    heart_rate_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Vaccination(Base):
    """A vaccine dose entered by the patient (free-text name, no catalog — see
    design spec). No status field: the "à jour/à faire" badge from the mockup
    was explicitly dropped, this is a plain history."""

    __tablename__ = "vaccinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    vaccine_name: Mapped[str] = mapped_column(String(255))
    dose_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    administered_at: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
