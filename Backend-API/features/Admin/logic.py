"""Doctor validation, reviews/complaints moderation, and account deletion.

Suspension rule (confirmed in brainstorming): the 5th active complaint
against a doctor triggers an automatic 1-month suspension; the account
reactivates automatically once suspended_until has passed, and an admin
can still delete the account directly if complaints keep coming in.

"Active" is tracked explicitly via Complaint.status: complaints count toward
the threshold while ACTIVE, and the batch that triggers a suspension is marked
RESOLVED so each suspension cycle starts from a clean count (a fresh set of 5
complaints is required to suspend again after reactivation).
"""

from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_file_url
from features.Admin.models import Complaint, ComplaintStatus, Review
from features.Admin.schemas import ComplaintCreateRequest, PendingDoctorOut, ReviewCreateRequest
from features.Appointments.models import Appointment, AppointmentStatus
from features.Auth.models import Doctor, DoctorStatus, Patient, PatientStatus
from features.Notifications import logic as notifications

COMPLAINT_THRESHOLD_FOR_SUSPENSION = 5
SUSPENSION_DURATION_DAYS = 30


async def submit_review(db: AsyncSession, patient_id: int, data: ReviewCreateRequest) -> None:
    appointment = await db.get(Appointment, data.appointment_id)
    if (
        appointment is None
        or appointment.patient_id != patient_id
        or appointment.doctor_id != data.doctor_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    if appointment.status != AppointmentStatus.COMPLETED:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can only review a completed consultation")

    already_reviewed = (
        await db.scalars(select(Review).where(Review.appointment_id == data.appointment_id))
    ).first()
    if already_reviewed is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This consultation has already been reviewed")

    db.add(
        Review(
            patient_id=patient_id,
            doctor_id=data.doctor_id,
            appointment_id=data.appointment_id,
            rating=data.rating,
            comment=data.comment,
        )
    )
    await db.commit()


async def submit_complaint(
    db: AsyncSession, patient_id: int, data: ComplaintCreateRequest, background_tasks: BackgroundTasks
) -> None:
    """Records the complaint, then suspends the doctor if the threshold is reached."""
    doctor = await db.get(Doctor, data.doctor_id)
    if doctor is None or doctor.status == DoctorStatus.DELETED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")

    db.add(
        Complaint(
            patient_id=patient_id,
            doctor_id=data.doctor_id,
            reason=data.reason,
            description=data.description,
        )
    )
    await db.flush()

    active_count = await db.scalar(
        select(func.count())
        .select_from(Complaint)
        .where(Complaint.doctor_id == data.doctor_id, Complaint.status == ComplaintStatus.ACTIVE)
    )
    # Only fire on the transition: a doctor already suspended must not re-trigger
    # on every further complaint.
    if doctor.status == DoctorStatus.VALIDATED and active_count >= COMPLAINT_THRESHOLD_FOR_SUSPENSION:
        suspended_until = datetime.now(timezone.utc) + timedelta(days=SUSPENSION_DURATION_DAYS)
        doctor.status = DoctorStatus.SUSPENDED
        doctor.suspended_until = suspended_until
        # Resolve the triggering batch so the next cycle needs a fresh set of 5.
        await db.execute(
            update(Complaint)
            .where(Complaint.doctor_id == data.doctor_id, Complaint.status == ComplaintStatus.ACTIVE)
            .values(status=ComplaintStatus.RESOLVED)
        )
        background_tasks.add_task(
            notifications.notify_doctor_suspended,
            doctor.email,
            doctor.first_name,
            suspended_until.date().isoformat(),
        )

    await db.commit()


async def list_pending_doctors(db: AsyncSession) -> list[PendingDoctorOut]:
    doctors = (
        await db.scalars(
            select(Doctor)
            .where(Doctor.status == DoctorStatus.PENDING_VALIDATION)
            .order_by(Doctor.created_at)
        )
    ).all()
    return [
        PendingDoctorOut(
            id=doctor.id,
            first_name=doctor.first_name,
            last_name=doctor.last_name,
            email=doctor.email,
            specialty=doctor.specialty,
            license_number=doctor.license_number,
            practice_name=doctor.practice_name,
            diploma_url=get_file_url(doctor.diploma_file_key) if doctor.diploma_file_key else None,
        )
        for doctor in doctors
    ]


async def _get_pending_doctor(db: AsyncSession, doctor_id: int) -> Doctor:
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    if doctor.status != DoctorStatus.PENDING_VALIDATION:
        raise HTTPException(status.HTTP_409_CONFLICT, "This account is not awaiting validation")
    return doctor


async def validate_doctor_account(
    db: AsyncSession, doctor_id: int, background_tasks: BackgroundTasks
) -> Doctor:
    doctor = await _get_pending_doctor(db, doctor_id)
    doctor.status = DoctorStatus.VALIDATED
    await db.commit()
    await db.refresh(doctor)
    background_tasks.add_task(notifications.notify_doctor_validated, doctor.email, doctor.first_name)
    return doctor


async def reject_doctor_account(
    db: AsyncSession, doctor_id: int, reason: str, background_tasks: BackgroundTasks
) -> Doctor:
    doctor = await _get_pending_doctor(db, doctor_id)
    doctor.status = DoctorStatus.REJECTED
    await db.commit()
    await db.refresh(doctor)
    background_tasks.add_task(notifications.notify_doctor_rejected, doctor.email, doctor.first_name, reason)
    return doctor


async def reactivate_expired_suspensions(db: AsyncSession) -> None:
    """Flips suspended doctors back to validated once their suspension has
    elapsed. Called lazily on doctor login (no scheduler in the V1)."""
    await db.execute(
        update(Doctor)
        .where(
            Doctor.status == DoctorStatus.SUSPENDED,
            Doctor.suspended_until.isnot(None),
            Doctor.suspended_until <= datetime.now(timezone.utc),
        )
        .values(status=DoctorStatus.VALIDATED, suspended_until=None)
    )
    await db.commit()


async def delete_account(db: AsyncSession, user_type: str, user_id: int) -> None:
    """Soft delete only: sets status to deleted, keeps medical records intact."""
    if user_type == "patient":
        user = await db.get(Patient, user_id)
        new_status = PatientStatus.DELETED
    elif user_type == "doctor":
        user = await db.get(Doctor, user_id)
        new_status = DoctorStatus.DELETED
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_type must be 'patient' or 'doctor'")

    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    user.status = new_status
    await db.commit()
