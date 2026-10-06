# Credence Backend

Backend API for the Credence project, built with **FastAPI** and **MongoDB**.

---

## Setup

### 1. Create and activate virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file using `.env.example` as a reference.

Do not commit `.env` or any secrets.

### 4. Run the backend

From the `backend/` directory:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Current Progress

### FastAPI Foundation ✅

A shared FastAPI application is implemented in:

```text
app/main.py
```

All backend modules use this shared application.

---

### M4 — Database Foundation ✅

The MongoDB database layer is implemented under:

```text
app/database/
```

It provides:

- MongoDB connection management
- User model
- User repository
- User creation and lookup
- Google identity (`google_sub`) storage
- Email normalization
- Duplicate-email protection
- Persistent user roles
- Role update and lookup operations
- Database error handling

M4 uses **PyMongo Async**.

Other modules should use the database/repository layer instead of accessing
MongoDB collections directly.

---

### M2 — Authorization & RBAC ✅

The authorization layer is implemented under:

```text
app/authorization/
```

Current roles:

- `STUDENT`
- `ISSUER`
- `ADMIN`

Key rules:

- New institutional users default to `STUDENT`.
- `ISSUER` access must be explicitly granted by an `ADMIN`.
- `ADMIN` access is explicitly provisioned.
- Users cannot change their own roles.
- Backend permissions are enforced using authorization dependencies.

Current endpoints include:

```text
GET  /authorization/me
GET  /authorization/users
PUT  /authorization/users/{id}/role
```

Admin bootstrap:

```bash
python -m scripts.bootstrap_admin <email>
```

Run from the `backend/` directory after the user has logged in at least once.

Detailed module documentation:

```text
docs/modules/M2_RBAC_MODULE.md
```

---

### M1 — Authentication ✅

Authentication is being implemented under:

```text
app/auth/
```

The planned authentication flow is:

```text
Google Workspace Login
        ↓
Google ID Token Validation
        ↓
Institutional Identity Validation
        ↓
Find / Create Credence User
        ↓
Credence JWT
        ↓
Protected API Access
```

M1 is responsible for:

- Google Workspace authentication
- Google ID token validation
- Institutional email/domain validation
- Google `sub` based identity
- User lookup/creation through M4
- Credence JWT generation
- Current-user authentication dependency

External certificate verifiers do not require an account in the initial
implementation.

---

### M3 — Cryptography 🔄

The cryptography module is planned under:

```text
app/crypto/
```

It will provide:

- Cryptographic hashing
- Digital signatures
- Signature verification
- Signing key handling
- Public key access
- Key identification/versioning
- Controlled cryptographic errors

M3 operates on canonical data supplied by the certificate/domain layer.
Certificate structure and canonicalization are handled separately.

---

### M5 — Certificate Domain & Verification ⏳

The certificate domain and complete verification workflow will be implemented
in a later phase.

Planned responsibilities include:

- Standardized academic certificate model
- Certificate canonicalization
- Certificate issuance
- Digital signing integration
- Certificate verification
- Trusted record comparison
- Certificate status/revocation

---

## Backend Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── database/
│   ├── auth/
│   ├── authorization/
│   └── crypto/
│
├── tests/
│   ├── database/
│   ├── auth/
│   ├── authorization/
│   └── crypto/
│
├── scripts/
├── requirements.txt
├── .env
└── .env.example
```

---

## Development Notes

- Use the existing shared FastAPI application.
- Do not create a separate FastAPI server for individual modules.
- Keep required Python dependencies updated in `requirements.txt`.
- Keep `.env` and private keys out of Git.
- Do not access MongoDB directly from unrelated modules; use the repository
  layer.
- Backend authorization must be enforced server-side.
- Update this README when adding a major backend feature or changing the
  setup process.
- Add or update tests when changing module functionality.

---

## Development Workflow

Use feature branches for module development.

```text
main
├── feature/m1-auth
├── feature/m2-authorization
├── feature/m3-crypto
├── feature/m4-database
└── feature/m5-certificate
```

Before integration:

1. Run the module's tests.
2. Run the complete backend test suite.
3. Verify the FastAPI application starts successfully.
4. Test relevant API endpoints.
5. Update documentation and dependencies if required.
```

### One important correction

I would **not** keep:

> `### Next — M1 Authentication`

because M1 is no longer simply "next"; it is an **active implementation/integration module**.

Also, for M3 I used `🔄` rather than `✅` because from our current project state we have **defined its architecture/README**, but we haven't established that the actual cryptographic implementation is complete yet.

So your backend README should answer only three things:

**1. How do I run the backend?**  
**2. What is currently implemented?**  
**3. What is coming next?**

The detailed implementation requirements should remain in the individual module READMEs.