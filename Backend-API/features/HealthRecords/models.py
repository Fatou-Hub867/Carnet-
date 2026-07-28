from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
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
    prescription_id: Mapped[int | None] = mapped_column(ForeignKey("prescriptions.id"), nullable=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
