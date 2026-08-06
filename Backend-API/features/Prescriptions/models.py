from __future__ import annotations

import enum
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class TreatmentIntakeStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    TAKEN = "taken"
    MISSED = "missed"


class Prescription(Base):
    """One PDF, generated once at creation and stored in S3/MinIO — never
    regenerated, since it is a fixed medical/legal document."""

    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    # Null when the prescription was created straight from a conversation,
    # with no underlying appointment (see create_prescription).
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    pdf_file_key: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Treatment(Base):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"))
    medication_name: Mapped[str] = mapped_column(String(255))
    dosage: Mapped[str] = mapped_column(String(100))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TreatmentSchedule(Base):
    """One row per intake time per day (e.g. 08:00 / 14:00 / 20:00) — a
    treatment can have several."""

    __tablename__ = "treatment_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    treatment_id: Mapped[int] = mapped_column(ForeignKey("treatments.id"))
    time_of_day: Mapped[time] = mapped_column(Time)


class TreatmentIntake(Base):
    """Adherence log: lets the dashboard show which of today's doses are
    still upcoming, and feeds the ChronicCare automatic alert."""

    __tablename__ = "treatment_intakes"

    id: Mapped[int] = mapped_column(primary_key=True)
    treatment_schedule_id: Mapped[int] = mapped_column(
        ForeignKey("treatment_schedules.id")
    )
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[TreatmentIntakeStatus] = mapped_column(
        Enum(TreatmentIntakeStatus), default=TreatmentIntakeStatus.SCHEDULED
    )
    actual_time: Mapped[time | None] = mapped_column(Time, nullable=True)
