"""Patient profile management and dashboard aggregation."""

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_file_url
from features.Appointments.models import Appointment, AppointmentStatus, Availability
from features.Auth.models import Doctor, Patient
from features.HealthRecords.models import VitalSignBilan
from features.Patients.schemas import (
    DoseReminder,
    PatientDashboardOut,
    PatientProfileOut,
    PatientProfileUpdateRequest,
    TreatmentSummary,
    UpcomingAppointment,
)
from features.Prescriptions.models import (
    Prescription,
    Treatment,
    TreatmentIntake,
    TreatmentIntakeStatus,
    TreatmentSchedule,
)


def build_profile_out(patient: Patient) -> PatientProfileOut:
    return PatientProfileOut(
        id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        place_of_birth=patient.place_of_birth,
        address=patient.address,
        phone_number=patient.phone_number,
        country_of_residence=patient.country_of_residence,
        gender=patient.gender,
        city=patient.city,
        email=patient.email,
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        weight_kg=float(patient.weight_kg) if patient.weight_kg is not None else None,
        photo_url=get_file_url(patient.photo_file_key)
        if patient.photo_file_key
        else None,
    )


async def update_patient_profile(
    db: AsyncSession, patient: Patient, data: PatientProfileUpdateRequest
) -> PatientProfileOut:
    updates = data.model_dump(exclude_unset=True)
    current_weight = float(patient.weight_kg) if patient.weight_kg is not None else None
    weight_changed = (
        "weight_kg" in updates
        and updates["weight_kg"] is not None
        and updates["weight_kg"] != current_weight
    )

    for field, value in updates.items():
        setattr(patient, field, value)

    if weight_changed:
        db.add(VitalSignBilan(patient_id=patient.id, weight_kg=updates["weight_kg"]))

    await db.commit()
    await db.refresh(patient)
    return build_profile_out(patient)


async def update_patient_photo(
    db: AsyncSession, patient: Patient, file_key: str
) -> PatientProfileOut:
    patient.photo_file_key = file_key
    await db.commit()
    await db.refresh(patient)
    return build_profile_out(patient)


async def get_patient_dashboard(
    db: AsyncSession, patient_id: int
) -> PatientDashboardOut:
    """Aggregates active treatments, today's doses and upcoming appointments.
    Computed on read (no stored notification state), per the passive-reminders
    decision from brainstorming."""
    today = date.today()

    # --- Active treatments (belong to the patient via their prescription) ---
    treatments = list(
        (
            await db.scalars(
                select(Treatment)
                .join(Prescription, Treatment.prescription_id == Prescription.id)
                .where(
                    Prescription.patient_id == patient_id,
                    Treatment.is_active.is_(True),
                    Treatment.end_date >= today,
                )
                .order_by(Treatment.medication_name)
            )
        ).all()
    )
    treatments_by_id = {t.id: t for t in treatments}

    # Intake times per treatment. No scheduler exists, so "today's doses" are
    # derived live from the schedule rather than from pre-generated intake rows.
    schedule_rows = (
        await db.execute(
            select(
                TreatmentSchedule.id,
                TreatmentSchedule.treatment_id,
                TreatmentSchedule.time_of_day,
            )
            .where(TreatmentSchedule.treatment_id.in_(treatments_by_id.keys()))
            .order_by(TreatmentSchedule.time_of_day)
        )
    ).all()

    times_by_treatment: dict[int, list] = defaultdict(list)
    for _schedule_id, treatment_id, time_of_day in schedule_rows:
        times_by_treatment[treatment_id].append(time_of_day)

    active_treatments = [
        TreatmentSummary(
            treatment_id=t.id,
            medication_name=t.medication_name,
            dosage=t.dosage,
            start_date=t.start_date,
            end_date=t.end_date,
            times_of_day=times_by_treatment.get(t.id, []),
        )
        for t in treatments
    ]

    # --- Today's doses, annotated with whether they were already logged ---
    schedule_ids = [row[0] for row in schedule_rows]
    taken_schedule_ids: set[int] = set()
    if schedule_ids:
        taken_rows = (
            await db.execute(
                select(TreatmentIntake.treatment_schedule_id).where(
                    TreatmentIntake.treatment_schedule_id.in_(schedule_ids),
                    TreatmentIntake.date == today,
                    TreatmentIntake.status == TreatmentIntakeStatus.TAKEN,
                )
            )
        ).all()
        taken_schedule_ids = {row[0] for row in taken_rows}

    today_doses = [
        DoseReminder(
            treatment_id=treatment_id,
            medication_name=treatments_by_id[treatment_id].medication_name,
            dosage=treatments_by_id[treatment_id].dosage,
            time_of_day=time_of_day,
            taken=schedule_id in taken_schedule_ids,
        )
        for schedule_id, treatment_id, time_of_day in schedule_rows
    ]
    today_doses.sort(key=lambda d: d.time_of_day)

    # --- Upcoming confirmed appointments ---
    appointment_rows = (
        await db.execute(
            select(
                Appointment.id,
                Doctor.first_name,
                Doctor.last_name,
                Doctor.specialty,
                Availability.date,
                Availability.start_time,
                Appointment.mode,
            )
            .join(Availability, Appointment.availability_id == Availability.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.status == AppointmentStatus.CONFIRMED,
                Availability.date >= today,
            )
            .order_by(Availability.date, Availability.start_time)
        )
    ).all()

    upcoming_appointments = [
        UpcomingAppointment(
            appointment_id=appt_id,
            doctor_name=f"{first_name} {last_name}",
            specialty=specialty,
            date=appt_date,
            start_time=start_time,
            mode=mode,
        )
        for appt_id, first_name, last_name, specialty, appt_date, start_time, mode in appointment_rows
    ]

    return PatientDashboardOut(
        active_treatments=active_treatments,
        today_doses=today_doses,
        upcoming_appointments=upcoming_appointments,
    )
