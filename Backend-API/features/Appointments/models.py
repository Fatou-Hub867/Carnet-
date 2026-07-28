from __future__ import annotations

import enum
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class AvailabilityStatus(str, enum.Enum):
    FREE = "free"
    BOOKED = "booked"


class AppointmentMode(str, enum.Enum):
    IN_PERSON = "in_person"
    MESSAGE = "message"


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REFUSED = "refused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Availability(Base):
    """A slot the doctor opened up. Booking it does not auto-confirm the
    appointment — the doctor still has to accept it explicitly."""

    __tablename__ = "availabilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[AvailabilityStatus] = mapped_column(Enum(AvailabilityStatus), default=AvailabilityStatus.FREE)


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    availability_id: Mapped[int] = mapped_column(ForeignKey("availabilities.id"))
    mode: Mapped[AppointmentMode] = mapped_column(Enum(AppointmentMode))
    status: Mapped[AppointmentStatus] = mapped_column(Enum(AppointmentStatus), default=AppointmentStatus.PENDING)
    # Snapshotted from Doctor.consultation_fee at confirmation time, so a later
    # fee change never affects an already-confirmed appointment's revenue.
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
