"""Admin space endpoints, plus patient-facing review/complaint submission.

Reviews and complaints are exposed here (not under Doctors/Patients)
because the moderation logic they feed — suspension, deletion — lives in
this feature; the two routers are kept separate only so `public_router`
can be mounted without the `/admin` auth-gated prefix.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_admin, get_current_patient
from features.Admin import logic
from features.Admin.schemas import (
    AccountDeletionRequest,
    ComplaintCreateRequest,
    ComplaintOut,
    DoctorValidationDecision,
    PendingDoctorOut,
    ReviewCreateRequest,
)
from features.Auth.models import Admin, Patient

router = APIRouter(prefix="/admin", tags=["admin"])
public_router = APIRouter(tags=["reviews-complaints"])


@router.get("/doctors/pending", response_model=list[PendingDoctorOut])
async def list_pending_doctors(
    _admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_pending_doctors(db)


@router.get("/doctors/{doctor_id}/diploma/download")
async def get_doctor_diploma_download_url(
    doctor_id: int,
    _admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return {"download_url": await logic.get_doctor_diploma_url(db, doctor_id)}


@router.get("/complaints", response_model=list[ComplaintOut])
async def list_complaints(
    _admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_complaints(db)


@router.post("/doctors/{doctor_id}/validate")
async def validate_doctor(
    doctor_id: int,
    decision: DoctorValidationDecision,
    background_tasks: BackgroundTasks,
    _admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if decision.approve:
        doctor = await logic.validate_doctor_account(db, doctor_id, background_tasks)
    else:
        reason = decision.rejection_reason or "No reason provided"
        doctor = await logic.reject_doctor_account(
            db, doctor_id, reason, background_tasks
        )
    return {"id": doctor.id, "status": doctor.status.value}


@router.delete("/{user_type}/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user_type: str,
    user_id: int,
    data: AccountDeletionRequest,
    _admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    await logic.delete_account(db, user_type, user_id)


@public_router.post("/doctors/{doctor_id}/reviews", status_code=status.HTTP_201_CREATED)
async def create_review(
    doctor_id: int,
    data: ReviewCreateRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    if doctor_id != data.doctor_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "doctor_id in path and body must match"
        )
    await logic.submit_review(db, current_patient.id, data)
    return {"status": "review recorded"}


@public_router.post(
    "/doctors/{doctor_id}/complaints", status_code=status.HTTP_201_CREATED
)
async def create_complaint(
    doctor_id: int,
    data: ComplaintCreateRequest,
    background_tasks: BackgroundTasks,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    if doctor_id != data.doctor_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "doctor_id in path and body must match"
        )
    await logic.submit_complaint(db, current_patient.id, data, background_tasks)
    return {"status": "complaint recorded"}
