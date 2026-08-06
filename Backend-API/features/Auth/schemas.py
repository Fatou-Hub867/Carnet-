from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr, Field, model_validator

from features.Auth.models import Gender


class PatientRegisterRequest(BaseModel):
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
    password: str = Field(min_length=10)
    password_confirmation: str

    @model_validator(mode="after")
    def passwords_match(self) -> "PatientRegisterRequest":
        if self.password != self.password_confirmation:
            raise ValueError("password and password_confirmation must match")
        return self


class PatientOut(BaseModel):
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

    model_config = {"from_attributes": True}


class DoctorRegisterRequest(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    place_of_birth: str
    email: EmailStr
    phone_number: str
    country_of_residence: str
    gender: Gender
    city: str
    password: str = Field(min_length=10)
    password_confirmation: str
    specialty: str
    license_number: str
    practice_name: str
    consultation_fee: float

    @model_validator(mode="after")
    def passwords_match(self) -> "DoctorRegisterRequest":
        if self.password != self.password_confirmation:
            raise ValueError("password and password_confirmation must match")
        return self


class DoctorRegisterResponse(BaseModel):
    id: int
    status: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10)
    new_password_confirmation: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.new_password_confirmation:
            raise ValueError("new_password and new_password_confirmation must match")
        return self


class ConfirmEmailRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)
    new_password_confirmation: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.new_password_confirmation:
            raise ValueError("new_password and new_password_confirmation must match")
        return self
