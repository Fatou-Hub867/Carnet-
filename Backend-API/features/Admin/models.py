from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ComplaintStatus(str, enum.Enum):
    # A complaint counts toward the suspension threshold while ACTIVE. When the
    # threshold fires, the triggering batch is marked RESOLVED so the next
    # suspension cycle starts from a clean count (see Admin/logic.submit_complaint).
    ACTIVE = "active"
    RESOLVED = "resolved"


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    reason: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2000))
    status: Mapped[ComplaintStatus] = mapped_column(Enum(ComplaintStatus), default=ComplaintStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
