from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel


class TreatmentLineRequest(BaseModel):
    medication_name: str
    dosage: str
    start_date: date
    end_date: date
    intake_times: list[time]


class PrescriptionCreateRequest(BaseModel):
    appointment_id: int
    notes: str | None = None
    treatments: list[TreatmentLineRequest]


class TreatmentLineOut(BaseModel):
    medication_name: str
    dosage: str
    start_date: date
    end_date: date


class PrescriptionOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    doctor_name: str
    appointment_id: int
    notes: str | None
    created_at: datetime
    treatments: list[TreatmentLineOut]

    model_config = {"from_attributes": True}


class TreatmentIntakeConfirmRequest(BaseModel):
    treatment_schedule_id: int
    date: date
