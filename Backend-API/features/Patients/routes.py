from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_patient
from core.storage import upload_file
from features.Auth.models import Patient
from features.Patients import logic
from features.Patients.schemas import (
    PatientDashboardOut,
    PatientProfileOut,
    PatientProfileUpdateRequest,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/me", response_model=PatientProfileOut)
async def get_my_profile(current_patient: Patient = Depends(get_current_patient)):
    return logic.build_profile_out(current_patient)


@router.patch("/me", response_model=PatientProfileOut)
async def update_my_profile(
    data: PatientProfileUpdateRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    return await logic.update_patient_profile(db, current_patient, data)


@router.post("/me/photo", response_model=PatientProfileOut)
async def upload_my_photo(
    photo: UploadFile,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    file_key = upload_file(await photo.read(), photo.filename, photo.content_type)
    return await logic.update_patient_photo(db, current_patient, file_key)


@router.get("/me/dashboard", response_model=PatientDashboardOut)
async def get_my_dashboard(
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    return await logic.get_patient_dashboard(db, current_patient.id)
