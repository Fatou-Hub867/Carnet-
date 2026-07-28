from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class PendingDoctorOut(BaseModel):
    """A doctor awaiting validation, with a presigned link so the admin can
    review the uploaded diploma before deciding."""

    id: int
    first_name: str
    last_name: str
    email: EmailStr
    specialty: str
    license_number: str
    practice_name: str
    diploma_url: str | None


class ReviewCreateRequest(BaseModel):
    doctor_id: int
    appointment_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class ComplaintCreateRequest(BaseModel):
    doctor_id: int
    reason: str
    description: str


class DoctorValidationDecision(BaseModel):
    approve: bool
    rejection_reason: str | None = None


class AccountDeletionRequest(BaseModel):
    reason: str | None = None
