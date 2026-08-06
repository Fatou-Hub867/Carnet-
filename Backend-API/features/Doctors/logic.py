"""Doctor profile management, public search and dashboard aggregation."""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_file_url
from features.Appointments.models import Appointment, AppointmentStatus, Availability
from features.Auth.models import Doctor, DoctorStatus, Patient
from features.Doctors.schemas import (
    DoctorDashboardOut,
    DoctorPatientOut,
    DoctorProfileOut,
    DoctorProfileUpdateRequest,
    DoctorPublicOut,
)

# Appointments that actually count as consultations (a pending or refused/cancelled
# one is neither billable nor a real visit). Also the relationship rule used
# to decide which patients a doctor "knows" — same criterion as
# HealthRecords._authorize_doctor_for_patient.
_ACTIVE_STATUSES = (AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED)


def build_public_out(doctor: Doctor) -> DoctorPublicOut:
    return DoctorPublicOut(
        id=doctor.id,
        first_name=doctor.first_name,
        last_name=doctor.last_name,
        specialty=doctor.specialty,
        practice_name=doctor.practice_name,
        city=doctor.city,
        consultation_fee=float(doctor.consultation_fee),
        photo_url=get_file_url(doctor.photo_file_key)
        if doctor.photo_file_key
        else None,
        is_available=doctor.is_available,
    )


def build_profile_out(doctor: Doctor) -> DoctorProfileOut:
    return DoctorProfileOut(
        **build_public_out(doctor).model_dump(),
        date_of_birth=doctor.date_of_birth,
        place_of_birth=doctor.place_of_birth,
        email=doctor.email,
        phone_number=doctor.phone_number,
        country_of_residence=doctor.country_of_residence,
        gender=doctor.gender,
        license_number=doctor.license_number,
        status=doctor.status,
        suspended_until=doctor.suspended_until,
        has_diploma=doctor.diploma_file_key is not None,
    )


async def search_doctors(
    db: AsyncSession, specialty: str | None, city: str | None
) -> list[DoctorPublicOut]:
    """Only returns doctors with status=validated, never pending/suspended/deleted ones."""
    query = select(Doctor).where(Doctor.status == DoctorStatus.VALIDATED)
    if specialty:
        query = query.where(Doctor.specialty.ilike(f"%{specialty}%"))
    if city:
        query = query.where(Doctor.city.ilike(f"%{city}%"))
    query = query.order_by(Doctor.last_name, Doctor.first_name)
    doctors = (await db.scalars(query)).all()
    return [build_public_out(d) for d in doctors]


async def get_doctor_profile(db: AsyncSession, doctor_id: int) -> DoctorPublicOut:
    """Public lookup of a single doctor. A patient must not be able to reach a
    doctor that was never validated, so anything but VALIDATED is a 404."""
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None or doctor.status != DoctorStatus.VALIDATED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    return build_public_out(doctor)


async def update_doctor_profile(
    db: AsyncSession, doctor: Doctor, data: DoctorProfileUpdateRequest
) -> DoctorProfileOut:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(doctor, field, value)
    await db.commit()
    await db.refresh(doctor)
    return build_profile_out(doctor)


async def update_doctor_photo(
    db: AsyncSession, doctor: Doctor, file_key: str
) -> DoctorProfileOut:
    doctor.photo_file_key = file_key
    await db.commit()
    await db.refresh(doctor)
    return build_profile_out(doctor)


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
            .where(
                Appointment.doctor_id == doctor_id,
                Appointment.status.in_(_ACTIVE_STATUSES),
            )
        )

    consultations_today = await db.scalar(
        dated_query(func.count()).where(Availability.date == today)
    )
    consultations_this_month = await db.scalar(
        dated_query(func.count()).where(Availability.date >= month_start)
    )
    revenue_this_month = await db.scalar(
        dated_query(func.coalesce(func.sum(Appointment.amount), 0)).where(
            Availability.date >= month_start
        )
    )
    pending_appointments = await db.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.PENDING,
        )
    )

    return DoctorDashboardOut(
        consultations_today=consultations_today or 0,
        pending_appointments=pending_appointments or 0,
        consultations_this_month=consultations_this_month or 0,
        revenue_this_month=float(revenue_this_month or 0),
    )


async def list_my_patients(db: AsyncSession, doctor_id: int) -> list[DoctorPatientOut]:
    """Distinct patients this doctor has an accepted relationship with, so
    frontend patient pickers (e.g. starting a chronic-care follow-up) aren't
    limited to patients the doctor already has a messaging conversation
    with — a presentiel-only patient is just as legitimate."""
    rows = (
        await db.execute(
            select(Patient.id, Patient.first_name, Patient.last_name)
            .join(Appointment, Appointment.patient_id == Patient.id)
            .where(
                Appointment.doctor_id == doctor_id,
                Appointment.status.in_(_ACTIVE_STATUSES),
            )
            .distinct()
            .order_by(Patient.last_name, Patient.first_name)
        )
    ).all()
    return [
        DoctorPatientOut(patient_id=pid, patient_name=f"{first} {last}")
        for pid, first, last in rows
    ]
