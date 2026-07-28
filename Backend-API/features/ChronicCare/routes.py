from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_doctor
from features.Auth.models import Doctor
from features.ChronicCare import logic
from features.ChronicCare.schemas import (
    CarePlanUpsertRequest,
    ChronicCareDashboardOut,
    ChronicFollowUpCreateRequest,
    ChronicPatientListItemOut,
    ManualAlertRequest,
)

router = APIRouter(prefix="/chronic-care", tags=["chronic-care"])


@router.get("/dashboard", response_model=ChronicCareDashboardOut)
async def get_dashboard(
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.get_chronic_care_dashboard(db, current_doctor.id)


@router.get("/patients", response_model=list[ChronicPatientListItemOut])
async def list_chronic_patients(
    search: str | None = None,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.list_chronic_patients(db, current_doctor.id, search)


@router.post("/follow-ups", status_code=status.HTTP_201_CREATED)
async def create_follow_up(
    data: ChronicFollowUpCreateRequest,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    follow_up = await logic.create_follow_up(db, current_doctor.id, data)
    return {"id": follow_up.id, "condition_name": follow_up.condition_name, "status": follow_up.status.value}


@router.post("/follow-ups/{follow_up_id}/alert")
async def set_manual_alert(
    follow_up_id: int,
    data: ManualAlertRequest,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    follow_up = await logic.set_manual_alert(db, current_doctor.id, follow_up_id, data)
    return {"id": follow_up.id, "manual_alert": follow_up.manual_alert}


@router.put("/follow-ups/{follow_up_id}/care-plan")
async def upsert_care_plan(
    follow_up_id: int,
    data: CarePlanUpsertRequest,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    care_plan = await logic.upsert_care_plan(db, current_doctor.id, follow_up_id, data)
    return {"id": care_plan.id, "status": care_plan.status.value}
