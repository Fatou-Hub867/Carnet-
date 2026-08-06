from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_doctor, get_current_patient
from features.Appointments import logic
from features.Appointments.schemas import (
    AppointmentCreateRequest,
    AppointmentDecisionRequest,
    AppointmentOut,
    AvailabilityCreateRequest,
    AvailabilityOut,
    AwaitingPrescriptionOut,
    DoctorCalendarEntryOut,
    PendingAppointmentOut,
)
from features.Auth.models import Doctor, Patient

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post(
    "/availabilities",
    response_model=AvailabilityOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability(
    data: AvailabilityCreateRequest,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.create_availability(db, current_doctor.id, data)


@router.get("/doctors/{doctor_id}/availabilities", response_model=list[AvailabilityOut])
async def list_doctor_availabilities(
    doctor_id: int, from_date: date, db: AsyncSession = Depends(get_db)
):
    return await logic.list_doctor_availabilities(db, doctor_id, from_date)


@router.delete(
    "/availabilities/{availability_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_availability(
    availability_id: int,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    await logic.delete_availability(db, current_doctor.id, availability_id)


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def book_appointment(
    data: AppointmentCreateRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    return await logic.book_appointment(db, current_patient.id, data)


@router.post("/{appointment_id}/decision", response_model=AppointmentOut)
async def decide_appointment(
    appointment_id: int,
    decision: AppointmentDecisionRequest,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    if decision.approve:
        return await logic.confirm_appointment(db, current_doctor.id, appointment_id)
    return await logic.refuse_appointment(db, current_doctor.id, appointment_id)


@router.post("/{appointment_id}/complete", response_model=AppointmentOut)
async def complete_appointment(
    appointment_id: int,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.complete_appointment(db, current_doctor.id, appointment_id)


@router.get("/pending", response_model=list[PendingAppointmentOut])
async def list_pending_appointments(
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_pending_appointments(db, current_doctor.id)


@router.get(
    "/completed-awaiting-prescription", response_model=list[AwaitingPrescriptionOut]
)
async def list_completed_awaiting_prescription(
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_completed_awaiting_prescription(db, current_doctor.id)


@router.get("/calendar", response_model=list[DoctorCalendarEntryOut])
async def get_doctor_calendar(
    day: date,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.get_doctor_calendar(db, current_doctor.id, day)


@router.get("/confirmed", response_model=list[DoctorCalendarEntryOut])
async def list_confirmed_appointments(
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_confirmed_appointments(db, current_doctor.id)
