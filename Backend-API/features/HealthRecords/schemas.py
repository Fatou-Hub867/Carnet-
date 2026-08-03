from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from features.HealthRecords.models import DocumentAddedBy, DocumentSourceType


class HealthRecordDocumentOut(BaseModel):
    id: int
    source_type: DocumentSourceType
    added_by: DocumentAddedBy
    original_filename: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthRecordSummaryOut(BaseModel):
    first_name: str
    last_name: str
    blood_type: str | None
    allergies: str | None
    weight_kg: float | None
    document_count: int


class TensionValueOut(BaseModel):
    systolic: int
    diastolic: int
    recorded_at: datetime


class NumericVitalValueOut(BaseModel):
    value: float
    recorded_at: datetime


class VitalsSummaryOut(BaseModel):
    tension: TensionValueOut | None
    glycemia: NumericVitalValueOut | None
    heart_rate: NumericVitalValueOut | None
    weight: NumericVitalValueOut | None
