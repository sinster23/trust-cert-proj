"""One-time provisioning of the first ADMIN (M2).

Usage, from backend/ (user must have logged in via Google once):

    python -m scripts.bootstrap_admin someone@institute.edu

Refuses to run if an administrator already exists.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from app.authorization.service import AuthorizationError, AuthorizationService  # noqa: E402
from app.database.connection import DatabaseManager  # noqa: E402
from app.database.repositories.user_repository import UserRepository  # noqa: E402


async def main(email: str) -> int:
    manager = DatabaseManager()
    db = await manager.connect()
    try:
        service = AuthorizationService(UserRepository(db))
        user = await service.bootstrap_admin(email)
        print(f"{user.email} is now ADMIN")
        return 0
    except AuthorizationError as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await manager.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m scripts.bootstrap_admin <email>", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
