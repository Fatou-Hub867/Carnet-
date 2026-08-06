from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, EmailStr

from features.Auth.models import DoctorStatus, Gender


class DoctorPublicOut(BaseModel):
    """What a patient sees when searching for a doctor to book with."""

    id: int
    first_name: str
    last_name: str
    specialty: str
    practice_name: str
    city: str
    consultation_fee: float
    photo_url: str | None
    is_available: bool

    model_config = {"from_attributes": True}


class DoctorProfileOut(DoctorPublicOut):
    date_of_birth: date
    place_of_birth: str
    email: EmailStr
    phone_number: str
    country_of_residence: str
    gender: Gender
    license_number: str
    status: DoctorStatus
    suspended_until: datetime | None
    has_diploma: bool


class DoctorProfileUpdateRequest(BaseModel):
    phone_number: str | None = None
    practice_name: str | None = None
    consultation_fee: float | None = None
    is_available: bool | None = None


class DoctorDashboardOut(BaseModel):
    consultations_today: int
    pending_appointments: int
    consultations_this_month: int
    revenue_this_month: float


class DoctorPatientOut(BaseModel):
    """A patient this doctor has an accepted relationship with (confirmed or
    completed appointment) — used to populate patient pickers that shouldn't
    require an existing messaging conversation, e.g. chronic-care follow-ups."""

    patient_id: int
    patient_name: str
