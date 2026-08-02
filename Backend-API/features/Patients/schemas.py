from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, EmailStr

from features.Appointments.models import AppointmentMode
from features.Auth.models import Gender


class PatientProfileOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    date_of_birth: date
    place_of_birth: str
    address: str
    phone_number: str
    country_of_residence: str
    gender: Gender
    city: str
    email: EmailStr
    blood_type: str | None
    allergies: str | None
    weight_kg: float | None
    photo_url: str | None

    model_config = {"from_attributes": True}


class PatientProfileUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    address: str | None = None
    phone_number: str | None = None
    country_of_residence: str | None = None
    city: str | None = None
    blood_type: str | None = None
    allergies: str | None = None
    weight_kg: float | None = None


class TreatmentSummary(BaseModel):
    """One active treatment shown in the dashboard's ongoing-treatments table."""

    treatment_id: int
    medication_name: str
    dosage: str
    start_date: date
    end_date: date
    times_of_day: list[time]


class DoseReminder(BaseModel):
    """A single intake due today, with whether the patient already logged it."""

    treatment_id: int
    medication_name: str
    dosage: str
    time_of_day: time
    taken: bool


class UpcomingAppointment(BaseModel):
    appointment_id: int
    doctor_name: str
    specialty: str
    date: date
    start_time: time
    mode: AppointmentMode


class PatientDashboardOut(BaseModel):
    active_treatments: list[TreatmentSummary]
    today_doses: list[DoseReminder]
    upcoming_appointments: list[UpcomingAppointment]
