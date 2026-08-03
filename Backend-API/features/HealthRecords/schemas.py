from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, model_validator

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


class VitalBilanCreateRequest(BaseModel):
    systolic: int | None = None
    diastolic: int | None = None
    glycemia_g_l: float | None = None
    heart_rate_bpm: int | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate(self):
        if (self.systolic is None) != (self.diastolic is None):
            raise ValueError("systolic and diastolic must be provided together")
        if (
            self.systolic is None
            and self.glycemia_g_l is None
            and self.heart_rate_bpm is None
        ):
            raise ValueError(
                "at least one of tension, glycemia_g_l or heart_rate_bpm is required"
            )
        return self


class VitalBilanUpdateRequest(BaseModel):
    systolic: int | None = None
    diastolic: int | None = None
    glycemia_g_l: float | None = None
    heart_rate_bpm: int | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate(self):
        if (self.systolic is None) != (self.diastolic is None):
            raise ValueError("systolic and diastolic must be provided together")
        return self
