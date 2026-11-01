# Credence Backend

Backend API for **Credence**, a secure academic certificate issuance and verification system built using FastAPI, MongoDB, and Ed25519 digital signatures.

## Tech Stack
- FastAPI
- Python
- MongoDB
- Ed25519 Cryptography
- JWT Authentication

## Project Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── auth/             # Authentication and JWT
│   ├── authorization/    # Role-based access control
│   ├── crypto/           # Signing and signature verification
│   ├── database/         # MongoDB and repositories
│   ├── certificates/     # Certificate models and issuance
│   └── verification/     # Public certificate verification
├── tests/                # Automated tests
├── .env.example          # Environment configuration template
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv .venv
```

Activate the environment and install dependencies:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file using `.env.example` and configure MongoDB, authentication, signing keys, and verification settings.

Run from the `backend/` directory:

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

## Key Features

- **Authentication:** Google identity validation, institutional email checks, and JWT authentication.
- **Role-Based Access Control:** STUDENT, ISSUER, and ADMIN roles with controlled issuer authorization.
- **Certificate Issuance:** Academic certificate creation, validation, and unique ID generation.
- **Digital Signatures:** SHA-256 hashing and Ed25519 signing and verification.
- **Certificate Verification:** Public verification by Certificate ID with signature and revocation checks.
- **Database Management:** MongoDB persistence for users, roles, and certificates.
- **Security:** Student ID masking, configurable public detail visibility, trusted proxy authentication, and per-IP rate limiting.

## Verification

Public endpoint:

```http
GET /certificates/verify/{certificate_id}
```

Supported outcomes: `VALID`, `INVALID`, `REVOKED`, `NOT_FOUND`, and `UNVERIFIABLE`.

Verified certificate details can be displayed for public comparison when enabled through environment configuration.

**Note:** Current verification validates the official database record. Automated PDF verification and QR-code integration are planned enhancements.

## Development Guidelines

- Use the shared FastAPI application in `app/main.py`.
- Access MongoDB through repository interfaces.
- Enforce authorization on the backend.
- Keep private keys and environment secrets out of source control.
- Maintain tests and documentation alongside module changes.