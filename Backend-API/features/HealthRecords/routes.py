from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_doctor, get_current_patient
from core.storage import upload_file
from features.Auth.models import Doctor, Patient
from features.HealthRecords import logic
from features.HealthRecords.schemas import (
    HealthRecordDocumentOut,
    HealthRecordSummaryOut,
    VitalsSummaryOut,
)

router = APIRouter(prefix="/health-records", tags=["health-records"])


@router.get("/me", response_model=HealthRecordSummaryOut)
async def get_my_health_record(
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    return await logic.get_health_record_summary(db, current_patient.id)


@router.get("/me/documents", response_model=list[HealthRecordDocumentOut])
async def list_my_documents(
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_documents(db, current_patient.id)


@router.post(
    "/me/documents",
    response_model=HealthRecordDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    file_key = upload_file(await file.read(), file.filename, file.content_type)
    return await logic.upload_document_from_patient(
        db, current_patient.id, file_key, file.filename
    )


@router.get("/me/documents/{document_id}/download")
async def download_document(
    document_id: int,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    url = await logic.get_document_url(db, current_patient.id, document_id)
    return {"download_url": url}


@router.post(
    "/patients/{patient_id}/documents",
    response_model=HealthRecordDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def doctor_upload_document(
    patient_id: int,
    file: UploadFile,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    file_key = upload_file(await file.read(), file.filename, file.content_type)
    return await logic.upload_document_from_doctor(
        db, patient_id, current_doctor.id, file_key, file.filename
    )


@router.get("/me/vitals", response_model=VitalsSummaryOut)
async def get_my_vitals(
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    return await logic.get_vitals_summary(db, current_patient.id)
