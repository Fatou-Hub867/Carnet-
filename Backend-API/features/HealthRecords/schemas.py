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
    document_count: int
