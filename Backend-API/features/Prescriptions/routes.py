from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_doctor, get_current_patient
from features.Auth.models import Doctor, Patient
from features.Prescriptions import logic
from features.Prescriptions.schemas import (
    PrescriptionCreateRequest,
    PrescriptionOut,
    TreatmentIntakeConfirmRequest,
)

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


@router.post("", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED)
async def create_prescription(
    data: PrescriptionCreateRequest,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.create_prescription(db, current_doctor.id, data)


@router.get("", response_model=list[PrescriptionOut])
async def list_my_prescriptions(
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_patient_prescriptions(db, current_patient.id)


@router.get("/{prescription_id}/download")
async def download_prescription(
    prescription_id: int,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    url = await logic.get_prescription_pdf_url(db, current_patient.id, prescription_id)
    return {"download_url": url}


@router.post("/treatment-intakes/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_treatment_intake(
    data: TreatmentIntakeConfirmRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    await logic.confirm_treatment_intake(db, current_patient.id, data.treatment_schedule_id, data.date)
