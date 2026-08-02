from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel

from features.Appointments.models import AppointmentMode, AppointmentStatus


class AvailabilityCreateRequest(BaseModel):
    date: date
    start_time: time
    end_time: time


class AvailabilityOut(BaseModel):
    id: int
    date: date
    start_time: time
    end_time: time

    model_config = {"from_attributes": True}


class AppointmentCreateRequest(BaseModel):
    availability_id: int
    mode: AppointmentMode
    reason: str | None = None


class AppointmentDecisionRequest(BaseModel):
    approve: bool


class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    availability_id: int
    mode: AppointmentMode
    status: AppointmentStatus
    amount: float | None
    reason: str | None

    model_config = {"from_attributes": True}


class PendingAppointmentOut(BaseModel):
    """A pending request as shown on the doctor's dashboard — needs the
    patient's name, which a raw AppointmentOut can't carry without a join."""

    appointment_id: int
    patient_name: str
    reason: str | None
    mode: AppointmentMode
    created_at: datetime


class DoctorCalendarEntryOut(BaseModel):
    """A day's consultation as shown on the doctor's calendar: the slot time and
    patient name that a raw AppointmentOut can't carry without a join."""

    appointment_id: int
    patient_name: str
    date: date
    start_time: time
    mode: AppointmentMode
    status: AppointmentStatus


class AwaitingPrescriptionOut(BaseModel):
    """A completed consultation with no prescription yet — what the doctor
    picks from on the "créer une ordonnance" page."""

    appointment_id: int
    patient_id: int
    patient_name: str
    date: date
    start_time: time
