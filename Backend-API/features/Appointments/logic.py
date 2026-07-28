"""Availability slots and appointment booking/acceptance workflow."""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from features.Appointments.models import (
    Appointment,
    AppointmentStatus,
    Availability,
    AvailabilityStatus,
)
from features.Appointments.schemas import (
    AppointmentCreateRequest,
    AvailabilityCreateRequest,
    DoctorCalendarEntryOut,
)
from features.Auth.models import Doctor, Patient


async def create_availability(db: AsyncSession, doctor_id: int, data: AvailabilityCreateRequest) -> Availability:
    if data.end_time <= data.start_time:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "end_time must be after start_time")
    if data.date < date.today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot open a slot in the past")

    # Reject a slot that overlaps an existing one for the same doctor/day:
    # two overlap iff each starts before the other ends.
    overlap = (
        await db.scalars(
            select(Availability).where(
                Availability.doctor_id == doctor_id,
                Availability.date == data.date,
                Availability.start_time < data.end_time,
                Availability.end_time > data.start_time,
            )
        )
    ).first()
    if overlap is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot overlaps an existing availability")

    availability = Availability(
        doctor_id=doctor_id,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
    )
    db.add(availability)
    await db.commit()
    await db.refresh(availability)
    return availability


async def list_doctor_availabilities(db: AsyncSession, doctor_id: int, from_date: date) -> list[Availability]:
    """Free slots only, from `from_date` onward — this is what a patient browses to book."""
    return list(
        (
            await db.scalars(
                select(Availability)
                .where(
                    Availability.doctor_id == doctor_id,
                    Availability.status == AvailabilityStatus.FREE,
                    Availability.date >= from_date,
                )
                .order_by(Availability.date, Availability.start_time)
            )
        ).all()
    )


async def book_appointment(db: AsyncSession, patient_id: int, data: AppointmentCreateRequest) -> Appointment:
    """Marks the availability as booked and creates the appointment as pending."""
    # Lock the slot row so two patients can't book it concurrently (no-op on
    # SQLite, enforced on Postgres); re-check FREE after acquiring the lock.
    availability = (
        await db.scalars(
            select(Availability).where(Availability.id == data.availability_id).with_for_update()
        )
    ).first()
    if availability is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Availability not found")
    if availability.status != AvailabilityStatus.FREE:
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot is no longer available")
    if availability.date < date.today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This slot is in the past")

    availability.status = AvailabilityStatus.BOOKED
    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=availability.doctor_id,
        availability_id=availability.id,
        mode=data.mode,
        status=AppointmentStatus.PENDING,
        reason=data.reason,
    )
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    return appointment


async def _get_owned_pending_appointment(db: AsyncSession, doctor_id: int, appointment_id: int) -> Appointment:
    appointment = await db.get(Appointment, appointment_id)
    if appointment is None or appointment.doctor_id != doctor_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    if appointment.status != AppointmentStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a pending appointment can be decided")
    return appointment


async def confirm_appointment(db: AsyncSession, doctor_id: int, appointment_id: int) -> Appointment:
    """Snapshots Doctor.consultation_fee into Appointment.amount."""
    appointment = await _get_owned_pending_appointment(db, doctor_id, appointment_id)
    doctor = await db.get(Doctor, doctor_id)
    appointment.status = AppointmentStatus.CONFIRMED
    appointment.amount = doctor.consultation_fee
    await db.commit()
    await db.refresh(appointment)
    return appointment


async def refuse_appointment(db: AsyncSession, doctor_id: int, appointment_id: int) -> Appointment:
    """Frees the availability back up so another patient can book it."""
    appointment = await _get_owned_pending_appointment(db, doctor_id, appointment_id)
    appointment.status = AppointmentStatus.REFUSED
    availability = await db.get(Availability, appointment.availability_id)
    if availability is not None:
        availability.status = AvailabilityStatus.FREE
    await db.commit()
    await db.refresh(appointment)
    return appointment


async def complete_appointment(db: AsyncSession, doctor_id: int, appointment_id: int) -> Appointment:
    """Marks a confirmed consultation as done. This is the gate for prescribing:
    a doctor can only write a prescription once the appointment is completed."""
    appointment = await db.get(Appointment, appointment_id)
    if appointment is None or appointment.doctor_id != doctor_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    if appointment.status != AppointmentStatus.CONFIRMED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a confirmed appointment can be completed")
    appointment.status = AppointmentStatus.COMPLETED
    await db.commit()
    await db.refresh(appointment)
    return appointment


async def list_pending_appointments(db: AsyncSession, doctor_id: int) -> list[Appointment]:
    return list(
        (
            await db.scalars(
                select(Appointment)
                .where(Appointment.doctor_id == doctor_id, Appointment.status == AppointmentStatus.PENDING)
                .order_by(Appointment.created_at)
            )
        ).all()
    )


async def get_doctor_calendar(db: AsyncSession, doctor_id: int, day: date) -> list[DoctorCalendarEntryOut]:
    """Confirmed consultations for a given day, with slot time and patient name."""
    rows = (
        await db.execute(
            select(
                Appointment.id,
                Patient.first_name,
                Patient.last_name,
                Availability.date,
                Availability.start_time,
                Appointment.mode,
                Appointment.status,
            )
            .join(Availability, Appointment.availability_id == Availability.id)
            .join(Patient, Appointment.patient_id == Patient.id)
            .where(
                and_(
                    Appointment.doctor_id == doctor_id,
                    Appointment.status == AppointmentStatus.CONFIRMED,
                    Availability.date == day,
                )
            )
            .order_by(Availability.start_time)
        )
    ).all()

    return [
        DoctorCalendarEntryOut(
            appointment_id=appt_id,
            patient_name=f"{first_name} {last_name}",
            date=appt_date,
            start_time=start_time,
            mode=mode,
            status=appt_status,
        )
        for appt_id, first_name, last_name, appt_date, start_time, mode, appt_status in rows
    ]
