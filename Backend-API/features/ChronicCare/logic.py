"""Chronic patient follow-up, care plans, and the combined alert computation.

Reuses Prescriptions.TreatmentIntake (missed doses) and Appointments.Appointment
(missed follow-up visits) rather than introducing new tracking tables.

Missed doses are computed passively (expected doses over a recent window minus
confirmed TAKEN intakes), consistent with the no-scheduler design: nothing ever
writes TreatmentIntake rows with status MISSED, so a raw MISSED count would
always be zero.
"""

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from features.Appointments.models import Appointment, AppointmentStatus, Availability
from features.Auth.models import Patient, PatientStatus
from features.ChronicCare.models import CarePlan, CarePlanStatus, ChronicFollowUp, FollowUpStatus
from features.ChronicCare.schemas import (
    CarePlanUpsertRequest,
    ChronicCareDashboardOut,
    ChronicFollowUpCreateRequest,
    ChronicPatientListItemOut,
    ManualAlertRequest,
)
from features.Prescriptions.models import (
    Prescription,
    Treatment,
    TreatmentIntake,
    TreatmentIntakeStatus,
    TreatmentSchedule,
)

MISSED_DOSES_ALERT_THRESHOLD = 3
MISSED_DOSES_WINDOW_DAYS = 7


async def _get_owned_follow_up(db: AsyncSession, doctor_id: int, follow_up_id: int) -> ChronicFollowUp:
    follow_up = await db.get(ChronicFollowUp, follow_up_id)
    if follow_up is None or follow_up.doctor_id != doctor_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Follow-up not found")
    return follow_up


async def _has_missed_follow_up(db: AsyncSession, patient_id: int, doctor_id: int) -> bool:
    """A confirmed appointment whose slot date has passed but was never completed
    reads as a missed follow-up visit."""
    count = await db.scalar(
        select(func.count())
        .select_from(Appointment)
        .join(Availability, Appointment.availability_id == Availability.id)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Availability.date < date.today(),
        )
    )
    return (count or 0) > 0


async def _count_missed_doses(db: AsyncSession, patient_id: int) -> int:
    """Expected doses over the last MISSED_DOSES_WINDOW_DAYS (from the schedules,
    bounded by each treatment's date range) minus the doses actually confirmed."""
    today = date.today()
    window_start = today - timedelta(days=MISSED_DOSES_WINDOW_DAYS)
    window_end = today - timedelta(days=1)  # today's doses aren't "missed" yet
    if window_end < window_start:
        return 0

    schedule_rows = (
        await db.execute(
            select(TreatmentSchedule.id, Treatment.start_date, Treatment.end_date)
            .join(Treatment, TreatmentSchedule.treatment_id == Treatment.id)
            .join(Prescription, Treatment.prescription_id == Prescription.id)
            .where(Prescription.patient_id == patient_id, Treatment.is_active.is_(True))
        )
    ).all()
    if not schedule_rows:
        return 0

    expected = 0
    schedule_ids = []
    for schedule_id, t_start, t_end in schedule_rows:
        schedule_ids.append(schedule_id)
        overlap_start = max(window_start, t_start)
        overlap_end = min(window_end, t_end)
        if overlap_end >= overlap_start:
            expected += (overlap_end - overlap_start).days + 1  # one dose per day per schedule
    if expected == 0:
        return 0

    taken = await db.scalar(
        select(func.count())
        .select_from(TreatmentIntake)
        .where(
            TreatmentIntake.treatment_schedule_id.in_(schedule_ids),
            TreatmentIntake.status == TreatmentIntakeStatus.TAKEN,
            TreatmentIntake.date >= window_start,
            TreatmentIntake.date <= window_end,
        )
    )
    return max(0, expected - (taken or 0))


async def _compute_alert(db: AsyncSession, follow_up: ChronicFollowUp) -> bool:
    if follow_up.manual_alert:
        return True
    if await _has_missed_follow_up(db, follow_up.patient_id, follow_up.doctor_id):
        return True
    return await _count_missed_doses(db, follow_up.patient_id) >= MISSED_DOSES_ALERT_THRESHOLD


async def create_follow_up(db: AsyncSession, doctor_id: int, data: ChronicFollowUpCreateRequest) -> ChronicFollowUp:
    patient = await db.get(Patient, data.patient_id)
    if patient is None or patient.status != PatientStatus.ACTIVE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")

    follow_up = ChronicFollowUp(
        patient_id=data.patient_id,
        doctor_id=doctor_id,
        condition_name=data.condition_name,
        start_date=data.start_date,
    )
    db.add(follow_up)
    await db.commit()
    await db.refresh(follow_up)
    return follow_up


async def set_manual_alert(
    db: AsyncSession, doctor_id: int, follow_up_id: int, data: ManualAlertRequest
) -> ChronicFollowUp:
    follow_up = await _get_owned_follow_up(db, doctor_id, follow_up_id)
    follow_up.manual_alert = data.alert
    follow_up.manual_alert_reason = data.reason if data.alert else None
    await db.commit()
    await db.refresh(follow_up)
    return follow_up


async def is_in_alert(db: AsyncSession, follow_up_id: int) -> bool:
    """manual_alert OR missed-doses-above-threshold OR missed follow-up appointment."""
    follow_up = await db.get(ChronicFollowUp, follow_up_id)
    if follow_up is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Follow-up not found")
    return await _compute_alert(db, follow_up)


async def upsert_care_plan(
    db: AsyncSession, doctor_id: int, follow_up_id: int, data: CarePlanUpsertRequest
) -> CarePlan:
    await _get_owned_follow_up(db, doctor_id, follow_up_id)
    try:
        plan_status = CarePlanStatus(data.status)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "status must be 'active' or 'inactive'") from exc

    # One care plan per follow-up: update it in place if it already exists.
    care_plan = (
        await db.scalars(select(CarePlan).where(CarePlan.chronic_follow_up_id == follow_up_id))
    ).first()
    if care_plan is None:
        care_plan = CarePlan(
            chronic_follow_up_id=follow_up_id, description=data.description, status=plan_status
        )
        db.add(care_plan)
    else:
        care_plan.description = data.description
        care_plan.status = plan_status
    await db.commit()
    await db.refresh(care_plan)
    return care_plan


async def _next_appointment_date(db: AsyncSession, patient_id: int, doctor_id: int) -> date | None:
    return await db.scalar(
        select(func.min(Availability.date))
        .select_from(Appointment)
        .join(Availability, Appointment.availability_id == Availability.id)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Availability.date >= date.today(),
        )
    )


async def _has_active_care_plan(db: AsyncSession, follow_up_id: int) -> bool:
    count = await db.scalar(
        select(func.count())
        .select_from(CarePlan)
        .where(CarePlan.chronic_follow_up_id == follow_up_id, CarePlan.status == CarePlanStatus.ACTIVE)
    )
    return (count or 0) > 0


async def list_chronic_patients(
    db: AsyncSession, doctor_id: int, search: str | None
) -> list[ChronicPatientListItemOut]:
    query = (
        select(ChronicFollowUp, Patient)
        .join(Patient, ChronicFollowUp.patient_id == Patient.id)
        .where(ChronicFollowUp.doctor_id == doctor_id, ChronicFollowUp.status == FollowUpStatus.ACTIVE)
    )
    if search:
        like = f"%{search}%"
        query = query.where(
            or_(
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
                ChronicFollowUp.condition_name.ilike(like),
            )
        )
    rows = (await db.execute(query.order_by(Patient.last_name, Patient.first_name))).all()

    # N+1 over the doctor's chronic patients (a bounded list); fine for the V1.
    items = []
    for follow_up, patient in rows:
        items.append(
            ChronicPatientListItemOut(
                patient_id=follow_up.patient_id,
                first_name=patient.first_name,
                last_name=patient.last_name,
                condition_name=follow_up.condition_name,
                next_appointment=await _next_appointment_date(db, follow_up.patient_id, doctor_id),
                care_plan_active=await _has_active_care_plan(db, follow_up.id),
                is_in_alert=await _compute_alert(db, follow_up),
            )
        )
    return items


async def get_chronic_care_dashboard(db: AsyncSession, doctor_id: int) -> ChronicCareDashboardOut:
    follow_ups = list(
        (
            await db.scalars(
                select(ChronicFollowUp).where(
                    ChronicFollowUp.doctor_id == doctor_id,
                    ChronicFollowUp.status == FollowUpStatus.ACTIVE,
                )
            )
        ).all()
    )

    alert_patient_ids = {fu.patient_id for fu in follow_ups if await _compute_alert(db, fu)}
    chronic_patient_ids = {fu.patient_id for fu in follow_ups}

    active_care_plans = await db.scalar(
        select(func.count())
        .select_from(CarePlan)
        .join(ChronicFollowUp, CarePlan.chronic_follow_up_id == ChronicFollowUp.id)
        .where(ChronicFollowUp.doctor_id == doctor_id, CarePlan.status == CarePlanStatus.ACTIVE)
    )

    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)
    appointments_this_week = 0
    if chronic_patient_ids:
        appointments_this_week = await db.scalar(
            select(func.count())
            .select_from(Appointment)
            .join(Availability, Appointment.availability_id == Availability.id)
            .where(
                Appointment.doctor_id == doctor_id,
                Appointment.patient_id.in_(chronic_patient_ids),
                Appointment.status == AppointmentStatus.CONFIRMED,
                Availability.date >= week_start,
                Availability.date <= week_end,
            )
        )

    return ChronicCareDashboardOut(
        followed_patients=len(chronic_patient_ids),
        active_care_plans=active_care_plans or 0,
        patients_in_alert=len(alert_patient_ids),
        appointments_this_week=appointments_this_week or 0,
    )
