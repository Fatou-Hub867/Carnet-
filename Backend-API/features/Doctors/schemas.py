from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr

from features.Auth.models import Gender


class DoctorPublicOut(BaseModel):
    """What a patient sees when searching for a doctor to book with."""

    id: int
    first_name: str
    last_name: str
    specialty: str
    practice_name: str
    city: str
    consultation_fee: float

    model_config = {"from_attributes": True}


class DoctorProfileOut(DoctorPublicOut):
    date_of_birth: date
    place_of_birth: str
    email: EmailStr
    phone_number: str
    country_of_residence: str
    gender: Gender
    license_number: str


class DoctorProfileUpdateRequest(BaseModel):
    phone_number: str | None = None
    practice_name: str | None = None
    consultation_fee: float | None = None


class DoctorDashboardOut(BaseModel):
    consultations_today: int
    pending_appointments: int
    consultations_this_month: int
    revenue_this_month: float
