"""Health record (carnet de santé) document management.

Only the two manual sources (patient upload, doctor upload) live here. The two
automatic sources are written inline by their producer, which is the only place
that holds the file key, original filename and source in scope, and keeps the
carnet write atomic with the event that triggered it:
  - PRESCRIPTION: features/Prescriptions/logic.create_prescription
  - MESSAGE:      features/Messaging/logic.send_message (doctor attachment)
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_file_url
from features.Auth.models import Patient, PatientStatus
from features.HealthRecords.models import (
    DocumentAddedBy,
    DocumentSourceType,
    HealthRecordDocument,
)
from features.HealthRecords.schemas import HealthRecordSummaryOut


async def upload_document_from_patient(
    db: AsyncSession, patient_id: int, file_key: str, filename: str
) -> HealthRecordDocument:
    document = HealthRecordDocument(
        patient_id=patient_id,
        source_type=DocumentSourceType.MANUAL_UPLOAD,
        added_by=DocumentAddedBy.PATIENT,
        file_key=file_key,
        original_filename=filename,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def upload_document_from_doctor(
    db: AsyncSession, patient_id: int, doctor_id: int, file_key: str, filename: str
) -> HealthRecordDocument:
    patient = await db.get(Patient, patient_id)
    if patient is None or patient.status != PatientStatus.ACTIVE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")

    document = HealthRecordDocument(
        patient_id=patient_id,
        source_type=DocumentSourceType.DOCTOR_UPLOAD,
        added_by=DocumentAddedBy.DOCTOR,
        file_key=file_key,
        original_filename=filename,
        doctor_id=doctor_id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def get_health_record_summary(db: AsyncSession, patient_id: int) -> HealthRecordSummaryOut:
    patient = await db.get(Patient, patient_id)
    document_count = await db.scalar(
        select(func.count())
        .select_from(HealthRecordDocument)
        .where(HealthRecordDocument.patient_id == patient_id)
    )
    return HealthRecordSummaryOut(
        first_name=patient.first_name,
        last_name=patient.last_name,
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        document_count=document_count or 0,
    )


async def list_documents(db: AsyncSession, patient_id: int) -> list[HealthRecordDocument]:
    return list(
        (
            await db.scalars(
                select(HealthRecordDocument)
                .where(HealthRecordDocument.patient_id == patient_id)
                .order_by(HealthRecordDocument.created_at.desc())
            )
        ).all()
    )


async def get_document_url(db: AsyncSession, patient_id: int, document_id: int) -> str:
    document = await db.get(HealthRecordDocument, document_id)
    if document is None or document.patient_id != patient_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return get_file_url(document.file_key)
