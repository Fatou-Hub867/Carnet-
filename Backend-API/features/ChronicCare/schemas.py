from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class ChronicFollowUpCreateRequest(BaseModel):
    patient_id: int
    condition_name: str
    start_date: date


class ManualAlertRequest(BaseModel):
    alert: bool
    reason: str | None = None


class CarePlanUpsertRequest(BaseModel):
    description: str
    status: str


class ChronicPatientListItemOut(BaseModel):
    patient_id: int
    first_name: str
    last_name: str
    condition_name: str
    next_appointment: date | None
    care_plan_active: bool
    is_in_alert: bool


class ChronicCareDashboardOut(BaseModel):
    followed_patients: int
    active_care_plans: int
    patients_in_alert: int
    appointments_this_week: int
