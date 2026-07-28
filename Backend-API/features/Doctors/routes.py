from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_doctor
from features.Auth.models import Doctor
from features.Doctors import logic
from features.Doctors.schemas import (
    DoctorDashboardOut,
    DoctorProfileOut,
    DoctorProfileUpdateRequest,
    DoctorPublicOut,
)

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorPublicOut])
async def search_doctors(
    specialty: str | None = None, city: str | None = None, db: AsyncSession = Depends(get_db)
):
    return await logic.search_doctors(db, specialty, city)


@router.get("/me", response_model=DoctorProfileOut)
async def get_my_profile(current_doctor: Doctor = Depends(get_current_doctor)):
    # The authenticated doctor is already loaded from the token; no query needed.
    return current_doctor


@router.patch("/me", response_model=DoctorProfileOut)
async def update_my_profile(
    data: DoctorProfileUpdateRequest,
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.update_doctor_profile(db, current_doctor, data)


@router.get("/me/dashboard", response_model=DoctorDashboardOut)
async def get_my_dashboard(
    current_doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    return await logic.get_doctor_dashboard(db, current_doctor.id)


# Kept last: a literal path like /me must be matched before this catch-all,
# otherwise "me" would be parsed as a doctor_id.
@router.get("/{doctor_id}", response_model=DoctorPublicOut)
async def get_doctor(doctor_id: int, db: AsyncSession = Depends(get_db)):
    return await logic.get_doctor_profile(db, doctor_id)
