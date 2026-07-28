from __future__ import annotations

from datetime import date, time

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


class DoctorCalendarEntryOut(BaseModel):
    """A day's consultation as shown on the doctor's calendar: the slot time and
    patient name that a raw AppointmentOut can't carry without a join."""

    appointment_id: int
    patient_name: str
    date: date
    start_time: time
    mode: AppointmentMode
    status: AppointmentStatus
