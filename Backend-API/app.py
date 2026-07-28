import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.storage import ensure_bucket_exists
from features.Admin.routes import public_router as reviews_complaints_router
from features.Admin.routes import router as admin_router
from features.Appointments.routes import router as appointments_router
from features.Auth.routes import router as auth_router
from features.ChronicCare.routes import router as chronic_care_router
from features.Doctors.routes import router as doctors_router
from features.HealthRecords.routes import router as health_records_router
from features.Messaging.routes import router as messaging_router
from features.Patients.routes import router as patients_router
from features.Prescriptions.routes import router as prescriptions_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # boto3 is synchronous; run the (one-off) bucket check off the event loop.
    await asyncio.to_thread(ensure_bucket_exists)
    yield


app = FastAPI(title="Medical Practice API", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(reviews_complaints_router)
app.include_router(patients_router)
app.include_router(doctors_router)
app.include_router(appointments_router)
app.include_router(prescriptions_router)
app.include_router(health_records_router)
app.include_router(messaging_router)
app.include_router(chronic_care_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
