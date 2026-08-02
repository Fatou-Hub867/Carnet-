"""Dev-only: wipe test data (patients, doctors, and everything derived from
them), keeping admins. Mirrors seed_admin.py's pattern of a small standalone
script rather than an API endpoint — there is no "reset the database" route
by design."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.database import async_session_factory  # noqa: E402

TABLES = [
    "care_plans",
    "chronic_follow_ups",
    "complaints",
    "reviews",
    "messages",
    "conversations",
    "health_record_documents",
    "treatment_intakes",
    "treatment_schedules",
    "treatments",
    "prescriptions",
    "appointments",
    "availabilities",
    "email_verification_tokens",
    "password_reset_tokens",
    "doctors",
    "patients",
]


async def reset_dev_data() -> None:
    async with async_session_factory() as session:
        await session.execute(
            text(f"TRUNCATE TABLE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
        )
        await session.commit()
    print(f"Tables videes : {', '.join(TABLES)} (admins conserves)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Vide les donnees patients/medecins/RDV/etc. Garde les admins."
    )
    parser.add_argument(
        "--yes", action="store_true", help="Confirme sans prompt interactif."
    )
    args = parser.parse_args()
    if not args.yes:
        confirm = input(
            "Ceci va supprimer TOUTES les donnees patients/medecins/RDV/etc. "
            "Continuer ? [y/N] "
        )
        if confirm.strip().lower() != "y":
            print("Annule.")
            raise SystemExit(0)
    asyncio.run(reset_dev_data())
