"""Health record (carnet de santé) document management.

Only the two manual sources (patient upload, doctor upload) live here. The two
automatic sources are written inline by their producer, which is the only place
that holds the file key, original filename and source in scope, and keeps the
carnet write atomic with the event that triggered it:
  - PRESCRIPTION: features/Prescriptions/logic.create_prescription
  - MESSAGE:      features/Messaging/logic.send_message (doctor attachment)
"""

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_file_url
from features.Auth.models import Patient, PatientStatus
from features.HealthRecords.models import (
    DocumentAddedBy,
    DocumentSourceType,
    HealthRecordDocument,
    Vaccination,
    VitalSignBilan,
)
from features.HealthRecords.schemas import (
    HealthRecordSummaryOut,
    NumericVitalValueOut,
    TensionValueOut,
    VaccinationCreateRequest,
    VaccinationUpdateRequest,
    VitalBilanCreateRequest,
    VitalBilanUpdateRequest,
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


async def create_vital_bilan(
    db: AsyncSession, patient_id: int, data: VitalBilanCreateRequest
) -> VitalsSummaryOut:
    bilan = VitalSignBilan(
        patient_id=patient_id,
        systolic=data.systolic,
        diastolic=data.diastolic,
        glycemia_g_l=data.glycemia_g_l,
        heart_rate_bpm=data.heart_rate_bpm,
    )
    db.add(bilan)
    await db.commit()
    return await get_vitals_summary(db, patient_id)


async def _get_latest_bilan_row(
    db: AsyncSession, patient_id: int
) -> VitalSignBilan | None:
    return (
        await db.scalars(
            select(VitalSignBilan)
            .where(
                VitalSignBilan.patient_id == patient_id,
                or_(
                    VitalSignBilan.systolic.is_not(None),
                    VitalSignBilan.glycemia_g_l.is_not(None),
                    VitalSignBilan.heart_rate_bpm.is_not(None),
                ),
            )
            .order_by(VitalSignBilan.recorded_at.desc(), VitalSignBilan.id.desc())
            .limit(1)
        )
    ).first()


async def update_latest_vital_bilan(
    db: AsyncSession, patient_id: int, data: VitalBilanUpdateRequest
) -> VitalsSummaryOut:
    bilan = await _get_latest_bilan_row(db, patient_id)
    if bilan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bilan to update")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(bilan, field, value)
    if (
        bilan.systolic is None
        and bilan.glycemia_g_l is None
        and bilan.heart_rate_bpm is None
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Update would leave no data — use DELETE instead",
        )
    await db.commit()
    return await get_vitals_summary(db, patient_id)


async def delete_latest_vital_bilan(
    db: AsyncSession, patient_id: int
) -> VitalsSummaryOut:
    bilan = await _get_latest_bilan_row(db, patient_id)
    if bilan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bilan to delete")
    await db.delete(bilan)
    await db.commit()
    return await get_vitals_summary(db, patient_id)


async def list_vaccinations(db: AsyncSession, patient_id: int) -> list[Vaccination]:
    return list(
        (
            await db.scalars(
                select(Vaccination)
                .where(Vaccination.patient_id == patient_id)
                .order_by(Vaccination.administered_at.desc(), Vaccination.id.desc())
            )
        ).all()
    )


async def create_vaccination(
    db: AsyncSession, patient_id: int, data: VaccinationCreateRequest
) -> Vaccination:
    vaccination = Vaccination(patient_id=patient_id, **data.model_dump())
    db.add(vaccination)
    await db.commit()
    await db.refresh(vaccination)
    return vaccination


async def _get_owned_vaccination(
    db: AsyncSession, patient_id: int, vaccination_id: int
) -> Vaccination:
    vaccination = await db.get(Vaccination, vaccination_id)
    if vaccination is None or vaccination.patient_id != patient_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vaccination not found")
    return vaccination


async def update_vaccination(
    db: AsyncSession,
    patient_id: int,
    vaccination_id: int,
    data: VaccinationUpdateRequest,
) -> Vaccination:
    vaccination = await _get_owned_vaccination(db, patient_id, vaccination_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(vaccination, field, value)
    await db.commit()
    await db.refresh(vaccination)
    return vaccination


async def delete_vaccination(
    db: AsyncSession, patient_id: int, vaccination_id: int
) -> None:
    vaccination = await _get_owned_vaccination(db, patient_id, vaccination_id)
    await db.delete(vaccination)
    await db.commit()
