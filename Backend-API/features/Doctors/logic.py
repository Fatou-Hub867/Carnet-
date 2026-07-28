"""Doctor profile management, public search and dashboard aggregation."""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from features.Appointments.models import Appointment, AppointmentStatus, Availability
from features.Auth.models import Doctor, DoctorStatus
from features.Doctors.schemas import DoctorDashboardOut, DoctorProfileUpdateRequest

# Appointments that actually count as consultations (a pending or refused/cancelled
# one is neither billable nor a real visit).
_ACTIVE_STATUSES = (AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED)


async def search_doctors(db: AsyncSession, specialty: str | None, city: str | None) -> list[Doctor]:
    """Only returns doctors with status=validated, never pending/suspended/deleted ones."""
    query = select(Doctor).where(Doctor.status == DoctorStatus.VALIDATED)
    if specialty:
        query = query.where(Doctor.specialty.ilike(f"%{specialty}%"))
    if city:
        query = query.where(Doctor.city.ilike(f"%{city}%"))
    query = query.order_by(Doctor.last_name, Doctor.first_name)
    return list((await db.scalars(query)).all())


async def get_doctor_profile(db: AsyncSession, doctor_id: int) -> Doctor:
    """Public lookup of a single doctor. A patient must not be able to reach a
    doctor that was never validated, so anything but VALIDATED is a 404."""
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None or doctor.status != DoctorStatus.VALIDATED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    return doctor


async def update_doctor_profile(db: AsyncSession, doctor: Doctor, data: DoctorProfileUpdateRequest) -> Doctor:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(doctor, field, value)
    await db.commit()
    await db.refresh(doctor)
    return doctor


async def get_doctor_dashboard(db: AsyncSession, doctor_id: int) -> DoctorDashboardOut:
    today = date.today()
    month_start = today.replace(day=1)

    # Appointment carries no date of its own; the slot date lives on Availability,
    # so every date filter joins through it. This helper factors that join out.
    def dated_query(agg):
        return (
            select(agg)
            .select_from(Appointment)
            .join(Availability, Appointment.availability_id == Availability.id)
            .where(Appointment.doctor_id == doctor_id, Appointment.status.in_(_ACTIVE_STATUSES))
        )

    consultations_today = await db.scalar(dated_query(func.count()).where(Availability.date == today))
    consultations_this_month = await db.scalar(dated_query(func.count()).where(Availability.date >= month_start))
    revenue_this_month = await db.scalar(
        dated_query(func.coalesce(func.sum(Appointment.amount), 0)).where(Availability.date >= month_start)
    )
    pending_appointments = await db.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.doctor_id == doctor_id, Appointment.status == AppointmentStatus.PENDING)
    )

    return DoctorDashboardOut(
        consultations_today=consultations_today or 0,
        pending_appointments=pending_appointments or 0,
        consultations_this_month=consultations_this_month or 0,
        revenue_this_month=float(revenue_this_month or 0),
    )
