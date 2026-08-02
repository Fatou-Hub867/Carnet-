"""Prescription creation (PDF generation + storage) and treatment intake tracking."""

from collections import defaultdict
from datetime import date, datetime

from fastapi import HTTPException, status
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_file_url, upload_file
from features.Appointments.models import Appointment, AppointmentStatus
from features.Auth.models import Doctor, Patient
from features.HealthRecords.models import (
    DocumentAddedBy,
    DocumentSourceType,
    HealthRecordDocument,
)
from features.Prescriptions.models import (
    Prescription,
    Treatment,
    TreatmentIntake,
    TreatmentIntakeStatus,
    TreatmentSchedule,
)
from features.Prescriptions.schemas import (
    PrescriptionCreateRequest,
    PrescriptionOut,
    TreatmentLineOut,
    TreatmentLineRequest,
)


def _latin1(text: str) -> str:
    # fpdf2 core fonts (Helvetica) only support latin-1; free-text medical fields
    # may contain characters outside it, so replace rather than crash.
    return text.encode("latin-1", "replace").decode("latin-1")


def _build_prescription_pdf(
    doctor: Doctor,
    patient: Patient,
    notes: str | None,
    treatments: list[TreatmentLineRequest],
) -> bytes:
    pdf = FPDF()
    pdf.add_page()

    def line(text: str, height: float = 6) -> None:
        # Force each line back to the left margin on a new row; multi_cell's
        # default new_x leaves the cursor at the right edge, which would make the
        # next full-width cell zero-width.
        pdf.multi_cell(0, height, _latin1(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "B", 16)
    line("Ordonnance", 10)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    line(f"Dr {doctor.first_name} {doctor.last_name} - {doctor.specialty}")
    line(doctor.practice_name)
    pdf.ln(2)
    line(f"Patient : {patient.first_name} {patient.last_name}")
    line(f"Date de naissance : {patient.date_of_birth.isoformat()}")
    line(f"Date : {date.today().isoformat()}")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    line("Traitements prescrits :", 7)
    pdf.set_font("Helvetica", "", 11)
    for treatment in treatments:
        times = ", ".join(t.strftime("%H:%M") for t in treatment.intake_times)
        line(
            f"- {treatment.medication_name} ({treatment.dosage}) | "
            f"{treatment.start_date.isoformat()} -> {treatment.end_date.isoformat()} | prises : {times}"
        )

    if notes:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        line("Notes :", 7)
        pdf.set_font("Helvetica", "", 11)
        line(notes)

    return bytes(pdf.output())


async def create_prescription(
    db: AsyncSession, doctor_id: int, data: PrescriptionCreateRequest
) -> PrescriptionOut:
    """Only allowed if the appointment status is completed. Generates the PDF
    with fpdf2, uploads it via core.storage, then creates the Treatment and
    TreatmentSchedule rows from the submitted treatment lines."""
    appointment = await db.get(Appointment, data.appointment_id)
    if appointment is None or appointment.doctor_id != doctor_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    if appointment.status != AppointmentStatus.COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The consultation must be completed before prescribing",
        )

    for line in data.treatments:
        if line.end_date < line.start_date:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A treatment's end_date is before its start_date",
            )
        if not line.intake_times:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Each treatment needs at least one intake time",
            )

    doctor = await db.get(Doctor, doctor_id)
    patient = await db.get(Patient, appointment.patient_id)

    # boto3 is synchronous; called inline here as elsewhere in the codebase
    # (see the diploma upload in Auth/routes.py).
    pdf_key = upload_file(
        _build_prescription_pdf(doctor, patient, data.notes, data.treatments),
        "ordonnance.pdf",
        "application/pdf",
    )

    prescription = Prescription(
        patient_id=patient.id,
        doctor_id=doctor_id,
        appointment_id=appointment.id,
        notes=data.notes,
        pdf_file_key=pdf_key,
    )
    db.add(prescription)
    await db.flush()  # need prescription.id for the treatment and health-record FKs

    for line in data.treatments:
        treatment = Treatment(
            prescription_id=prescription.id,
            medication_name=line.medication_name,
            dosage=line.dosage,
            start_date=line.start_date,
            end_date=line.end_date,
        )
        db.add(treatment)
        await db.flush()  # need treatment.id for its schedule rows
        for intake_time in line.intake_times:
            db.add(
                TreatmentSchedule(treatment_id=treatment.id, time_of_day=intake_time)
            )

    # The prescription PDF is automatically filed in the patient's health record.
    db.add(
        HealthRecordDocument(
            patient_id=patient.id,
            source_type=DocumentSourceType.PRESCRIPTION,
            added_by=DocumentAddedBy.SYSTEM,
            file_key=pdf_key,
            original_filename=f"ordonnance-{prescription.id}.pdf",
            prescription_id=prescription.id,
        )
    )

    await db.commit()
    await db.refresh(prescription)
    return PrescriptionOut(
        id=prescription.id,
        patient_id=prescription.patient_id,
        doctor_id=prescription.doctor_id,
        doctor_name=f"{doctor.first_name} {doctor.last_name}",
        appointment_id=prescription.appointment_id,
        notes=prescription.notes,
        created_at=prescription.created_at,
        treatments=[
            TreatmentLineOut(
                medication_name=line.medication_name,
                dosage=line.dosage,
                start_date=line.start_date,
                end_date=line.end_date,
            )
            for line in data.treatments
        ],
    )


async def list_patient_prescriptions(
    db: AsyncSession, patient_id: int
) -> list[PrescriptionOut]:
    rows = (
        await db.execute(
            select(Prescription, Doctor)
            .join(Doctor, Prescription.doctor_id == Doctor.id)
            .where(Prescription.patient_id == patient_id)
            .order_by(Prescription.created_at.desc())
        )
    ).all()
    prescriptions = [p for p, _ in rows]
    prescription_ids = [p.id for p in prescriptions]

    treatment_rows: list[Treatment] = []
    if prescription_ids:
        treatment_rows = list(
            (
                await db.scalars(
                    select(Treatment).where(
                        Treatment.prescription_id.in_(prescription_ids)
                    )
                )
            ).all()
        )
    treatments_by_prescription: dict[int, list[TreatmentLineOut]] = defaultdict(list)
    for t in treatment_rows:
        treatments_by_prescription[t.prescription_id].append(
            TreatmentLineOut(
                medication_name=t.medication_name,
                dosage=t.dosage,
                start_date=t.start_date,
                end_date=t.end_date,
            )
        )

    return [
        PrescriptionOut(
            id=p.id,
            patient_id=p.patient_id,
            doctor_id=p.doctor_id,
            doctor_name=f"{doctor.first_name} {doctor.last_name}",
            appointment_id=p.appointment_id,
            notes=p.notes,
            created_at=p.created_at,
            treatments=treatments_by_prescription.get(p.id, []),
        )
        for p, doctor in rows
    ]


async def get_prescription_pdf_url(
    db: AsyncSession, patient_id: int, prescription_id: int
) -> str:
    prescription = await db.get(Prescription, prescription_id)
    if prescription is None or prescription.patient_id != patient_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prescription not found")
    return get_file_url(prescription.pdf_file_key)


async def confirm_treatment_intake(
    db: AsyncSession, patient_id: int, treatment_schedule_id: int, date_: date
) -> None:
    # Verify the schedule belongs to this patient: schedule -> treatment -> prescription.
    owner_id = await db.scalar(
        select(Prescription.patient_id)
        .join(Treatment, Treatment.prescription_id == Prescription.id)
        .join(TreatmentSchedule, TreatmentSchedule.treatment_id == Treatment.id)
        .where(TreatmentSchedule.id == treatment_schedule_id)
    )
    if owner_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Treatment schedule not found")
    if owner_id != patient_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This treatment schedule is not yours"
        )

    intake = (
        await db.scalars(
            select(TreatmentIntake).where(
                TreatmentIntake.treatment_schedule_id == treatment_schedule_id,
                TreatmentIntake.date == date_,
            )
        )
    ).first()
    now_time = datetime.now().time()
    if intake is None:
        db.add(
            TreatmentIntake(
                treatment_schedule_id=treatment_schedule_id,
                date=date_,
                status=TreatmentIntakeStatus.TAKEN,
                actual_time=now_time,
            )
        )
    else:
        intake.status = TreatmentIntakeStatus.TAKEN
        intake.actual_time = now_time
    await db.commit()
