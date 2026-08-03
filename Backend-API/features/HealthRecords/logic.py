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
    VitalSignBilan,
)
from features.HealthRecords.schemas import (
    HealthRecordSummaryOut,
    NumericVitalValueOut,
    TensionValueOut,
    VitalsSummaryOut,
)


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


async def get_health_record_summary(
    db: AsyncSession, patient_id: int
) -> HealthRecordSummaryOut:
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
        weight_kg=float(patient.weight_kg) if patient.weight_kg is not None else None,
        document_count=document_count or 0,
    )


async def list_documents(
    db: AsyncSession, patient_id: int
) -> list[HealthRecordDocument]:
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


async def _latest_bilan_with(
    db: AsyncSession, patient_id: int, column
) -> VitalSignBilan | None:
    return (
        await db.scalars(
            select(VitalSignBilan)
            .where(VitalSignBilan.patient_id == patient_id, column.is_not(None))
            .order_by(VitalSignBilan.recorded_at.desc(), VitalSignBilan.id.desc())
            .limit(1)
        )
    ).first()


async def get_vitals_summary(db: AsyncSession, patient_id: int) -> VitalsSummaryOut:
    """Each of the 4 fields is resolved independently: a bilan can fill only a
    subset of its 3 manual fields, and the weight snapshot always lives on a
    separate row (written by Patients.logic) — so "latest" is per-column, not
    per-row. Four small queries rather than one clever one, for clarity."""
    tension_row = await _latest_bilan_with(db, patient_id, VitalSignBilan.systolic)
    glycemia_row = await _latest_bilan_with(db, patient_id, VitalSignBilan.glycemia_g_l)
    heart_rate_row = await _latest_bilan_with(
        db, patient_id, VitalSignBilan.heart_rate_bpm
    )
    weight_row = await _latest_bilan_with(db, patient_id, VitalSignBilan.weight_kg)

    return VitalsSummaryOut(
        tension=TensionValueOut(
            systolic=tension_row.systolic,
            diastolic=tension_row.diastolic,
            recorded_at=tension_row.recorded_at,
        )
        if tension_row
        else None,
        glycemia=NumericVitalValueOut(
            value=float(glycemia_row.glycemia_g_l), recorded_at=glycemia_row.recorded_at
        )
        if glycemia_row
        else None,
        heart_rate=NumericVitalValueOut(
            value=float(heart_rate_row.heart_rate_bpm),
            recorded_at=heart_rate_row.recorded_at,
        )
        if heart_rate_row
        else None,
        weight=NumericVitalValueOut(
            value=float(weight_row.weight_kg), recorded_at=weight_row.recorded_at
        )
        if weight_row
        else None,
    )
