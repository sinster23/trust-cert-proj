"""LOCAL TEST HELPER for the live verification check. Do NOT commit this file.

Run from backend/ (reads MONGODB_* and SIGNING_* from .env):

    python live_verification_helper.py issue
    python live_verification_helper.py revoke      CERT-<32 hex>
    python live_verification_helper.py tamper      CERT-<32 hex> [new_student_name]
    python live_verification_helper.py set-status  CERT-<32 hex> SUSPENDED
    python live_verification_helper.py set-key-id  CERT-<32 hex> retired-key-v0

``issue`` signs and stores a real test certificate through the project's own
CertificateService, CryptoService and CertificateRepository (no login needed).
``revoke`` uses the repository's real ACTIVE -> REVOKED transition.
``tamper``, ``set-status`` and ``set-key-id`` write to MongoDB directly, on
purpose, to simulate corrupted data. Use a throwaway database for these.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from app.certificates.service import CertificateService  # noqa: E402
from app.crypto import CryptoService  # noqa: E402
from app.crypto.exceptions import CryptoError  # noqa: E402
from app.database.connection import DatabaseManager  # noqa: E402
from app.database.exceptions import DatabaseError  # noqa: E402
from app.database.repositories.certificate_repository import CertificateRepository  # noqa: E402

SAMPLE = {
    "student_id": "TEST-001",
    "student_name": "Test Student",
    "institution": "Test Institute",
    "degree": "Bachelor of Technology",
    "field_of_study": "Computer Science",
    "graduation_date": "2025-06-15",
    "issue_date": "2025-07-01",
}


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("issue", help="issue and store a signed test certificate")
    for name in ("revoke", "tamper", "set-status", "set-key-id"):
        sub = commands.add_parser(name)
        sub.add_argument("certificate_id")
        if name == "tamper":
            sub.add_argument("value", nargs="?", default="Mallory Smith")
        elif name != "revoke":
            sub.add_argument("value")
    return parser.parse_args(argv)


async def run(args: argparse.Namespace, database) -> int:
    repository = CertificateRepository(database)

    if args.command == "issue":
        await repository.ensure_indexes()
        signed = await CertificateService(CryptoService(), repository).issue_certificate(**SAMPLE)
        print(signed.certificate.certificate_id)
        return 0

    if args.command == "revoke":
        record = await repository.revoke_certificate(args.certificate_id)
        print(f"status is now {record['status']}")
        return 0

    field = {
        "tamper": "certificate_data.student_name",
        "set-status": "status",
        "set-key-id": "signature_metadata.key_id",
    }[args.command]
    result = await database[CertificateRepository.COLLECTION].update_one(
        {"certificate_id": args.certificate_id}, {"$set": {field: args.value}}
    )
    print(f"matched {result.matched_count} document(s); set {field} = {args.value!r}")
    return 0 if result.matched_count else 1


async def main(argv: list[str]) -> int:
    args = parse(argv)
    manager = DatabaseManager()
    try:
        database = await manager.connect()
        return await run(args, database)
    except (DatabaseError, CryptoError) as exc:
        print(f"Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        await manager.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
