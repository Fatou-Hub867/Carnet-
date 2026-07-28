from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class FollowUpStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CarePlanStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ChronicFollowUp(Base):
    """One row per doctor + condition (confirmed in brainstorming): a patient
    can have several concurrent follow-ups with different doctors."""

    __tablename__ = "chronic_follow_ups"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    condition_name: Mapped[str] = mapped_column(String(255))
    start_date: Mapped[date] = mapped_column(Date)
    status: Mapped[FollowUpStatus] = mapped_column(Enum(FollowUpStatus), default=FollowUpStatus.ACTIVE)
    # The displayed alert combines this manual flag with an automatic
    # computation (missed doses / missed follow-up appointment) done at
    # query time — see ChronicCare/logic.py.
    manual_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_alert_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CarePlan(Base):
    __tablename__ = "care_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    chronic_follow_up_id: Mapped[int] = mapped_column(ForeignKey("chronic_follow_ups.id"))
    description: Mapped[str] = mapped_column(String(2000))
    status: Mapped[CarePlanStatus] = mapped_column(Enum(CarePlanStatus), default=CarePlanStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
