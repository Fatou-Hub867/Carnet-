"""Dev-only: create/reset the local admin account (no API endpoint exists, by design)."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from core.database import async_session_factory  # noqa: E402
from core.security import hash_password  # noqa: E402
from features.Auth.models import Admin  # noqa: E402

DEFAULT_EMAIL = "admin@carnetplus.dev"
DEFAULT_PASSWORD = "adminpassword1"
DEFAULT_FIRST_NAME = "Admin"
DEFAULT_LAST_NAME = "Carnet+"


async def seed_admin(reset_password: bool) -> None:
    email = os.environ.get("ADMIN_EMAIL", DEFAULT_EMAIL)
    password = os.environ.get("ADMIN_PASSWORD", DEFAULT_PASSWORD)
    first_name = os.environ.get("ADMIN_FIRST_NAME", DEFAULT_FIRST_NAME)
    last_name = os.environ.get("ADMIN_LAST_NAME", DEFAULT_LAST_NAME)

    async with async_session_factory() as session:
        existing = await session.scalar(select(Admin).where(Admin.email == email))
        if existing is None:
            session.add(
                Admin(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password_hash=hash_password(password),
                )
            )
            await session.commit()
            print(f"Admin cree : {email} / {password}")
        elif reset_password:
            existing.password_hash = hash_password(password)
            await session.commit()
            print(f"Mot de passe reinitialise : {email} / {password}")
        else:
            print(
                f"Admin deja existant : {email} (utiliser --reset-password pour changer le mot de passe)"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create or reset the local admin account."
    )
    parser.add_argument("--reset-password", action="store_true")
    args = parser.parse_args()
    asyncio.run(seed_admin(args.reset_password))
