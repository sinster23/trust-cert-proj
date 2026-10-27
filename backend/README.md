# Credence Backend

Backend API for **Credence**, a secure academic certificate issuance and verification system built with FastAPI, MongoDB, and Ed25519 digital signatures.

## Setup

```bash
python -m venv .venv
```

Activate the environment on Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies and configure the environment:

```bash
pip install -r requirements.txt
```

Create `.env` using `.env.example` as a reference. Configure MongoDB and signing-key paths without committing secrets.

Run from the `backend/` directory:

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

## Current Implementation

- **M1 — Authentication:** Google identity validation, institutional email checks, user lookup/creation, and Credence JWT authentication.
- **M2 — Authorization:** Role-based access control for `STUDENT`, `ISSUER`, and `ADMIN`. Issuer access requires explicit authorization.
- **M3 — Cryptography:** SHA-256 hashing, Ed25519 signing and verification, and signing-key identification.
- **M4 — Database:** MongoDB connection management, user persistence, role storage, and certificate persistence through repository interfaces.
- **M5 — Certificate Domain:** Academic certificate validation, deterministic canonicalization, certificate issuance, signing integration, and certificate retrieval.

## How It Works

1. Users authenticate through Google.
2. The backend validates identity and applies role-based permissions.
3. Authorized issuers submit academic certificate details.
4. M5 validates and canonicalizes the certificate.
5. M3 digitally signs the canonical bytes.
6. M4 persists the certificate and signature metadata in MongoDB.
7. The frontend displays the issued certificate and its digital signature.

## Next Steps

- Complete end-to-end integration and automated workflow checks.
- Implement and validate independent certificate verification.
- Verify signatures against the original canonical certificate data.
- Add certificate status and revocation support.
- Strengthen key management, audit logging, and security checks.

## Development Guidelines

- Use the shared FastAPI application in `app/main.py`.
- Access MongoDB through the database/repository layer.
- Enforce authorization on the backend.
- Keep private keys, `.env`, and other secrets out of source control.
- Update module documentation and tests when functionality changes.
