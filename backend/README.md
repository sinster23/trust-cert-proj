# Credence Backend

Backend API for the Credence project, built with **FastAPI** and **MongoDB**.

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

Required variables:

| Variable | Used by | Description |
|---|---|---|
| `MONGODB_URI` | M4 | MongoDB connection string |
| `MONGODB_DATABASE` | M4 | Database name |
| `GOOGLE_CLIENT_ID` | M1 | Google OAuth client ID (the expected token audience) |
| `GOOGLE_ALLOWED_DOMAIN` | M1 | Allowed Google Workspace domain, e.g. `example.edu` (no `@`) |
| `JWT_SECRET` | M1 | Secret used to sign Credence JWTs, at least 32 characters |

Optional variables (M1):

| Variable | Default | Description |
|---|---|---|
| `JWT_ISSUER` | `credence` | JWT `iss` claim |
| `JWT_AUDIENCE` | `credence-api` | JWT `aud` claim |
| `JWT_EXPIRE_MINUTES` | `60` | Credence JWT lifetime in minutes |

Generate a `JWT_SECRET` with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 4. Run the backend

From the `backend/` directory:

```bash
uvicorn app.main:app --reload
```

If `uvicorn` is not recognised (common on Windows), run it through Python:

```bash
python -m uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

### 5. Run the tests

From the `backend/` directory:

```bash
python -m pytest tests -v
```

---

## Current Progress

### FastAPI Foundation
- Shared FastAPI application created in `app/main.py`.

### M4 — Database Foundation ✅

The initial MongoDB database layer is implemented under:

```text
app/database/
```

It currently provides:

- MongoDB connection management
- User model
- User repository
- User creation and lookup
- Email normalization
- Duplicate-email protection
- Database error handling

M4 uses **PyMongo Async**.

Other modules should use the database/repository layer rather than accessing MongoDB directly.

### M1 — Authentication ✅

Google Workspace authentication and Credence JWT-based API authentication are implemented under:

```text
app/auth/
```

M1 answers **"who is this user?"**. It does not decide what the user may do; roles and permissions belong to M2. Details are in the [M1 section](#m1--authentication) below.

### Next

Remaining modules: M2 (roles and authorization), M3 (cryptography and signing), M5 (certificate domain and verification).

---

## M1 — Authentication

### Structure

```text
app/auth/
├── __init__.py
├── router.py          # /auth endpoints (APIRouter)
├── service.py         # authentication workflow
├── schemas.py         # request/response models
├── dependencies.py    # get_current_user and related dependencies
└── security.py        # settings, Google token validation, JWT create/validate
tests/auth/test_auth.py
```

### Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/google` | none | Exchanges a Google ID token for a Credence JWT |
| `GET` | `/auth/me` | Bearer JWT | Returns the current authenticated user |

**`POST /auth/google`**

Request body (no other fields are accepted):

```json
{ "id_token": "<Google ID token>" }
```

Response `200`:

```json
{
  "access_token": "<Credence JWT>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "student@example.edu",
    "is_active": true,
    "created_at": "2026-10-02T08:35:56.694Z"
  }
}
```

**`GET /auth/me`**

Send `Authorization: Bearer <access_token>`. Returns the public user (`id`, `email`, `is_active`, `created_at`). `password_hash` is never returned.

### Error responses

Error messages are intentionally generic and never expose internal details.

| Status | When |
|---|---|
| `401` | Invalid, expired or non-institutional Google token; missing, malformed, expired or invalid Credence JWT; user no longer exists or is inactive |
| `403` | The account cannot be used, e.g. it is deactivated, or the email already belongs to a different Credence user |
| `422` | Invalid request body (empty token, unknown fields) |
| `503` | Authentication is misconfigured, or the database is unavailable |

### Authentication flow

```text
Google login (frontend obtains a Google ID token)
        ↓
POST /auth/google
        ↓
Backend validates the token
        ↓
Find user through the M4 repository
        ├── found      → use existing user
        └── not found  → create user from the validated Google claims
        ↓
Issue Credence JWT
```

The backend never trusts frontend checks. Users are created only from claims in a validated Google token, never from client-supplied fields.

### Google token validation

The backend independently verifies:

- Token signature (Google public certificates)
- Issuer (`accounts.google.com`)
- Audience (must equal `GOOGLE_CLIENT_ID`)
- Expiration
- Email verified (`email_verified` must be `true`)
- Institutional Workspace: the signed `hd` claim **and** the email domain must both equal `GOOGLE_ALLOWED_DOMAIN`

Personal accounts (for example `@gmail.com`) have no `hd` claim and are rejected.

### Identity mapping (Google `sub` → Credence user)

The stable Google `sub` is the permanent external identity. Email is stored as information only and is never the identity key.

The M4 `User` model has no field for the Google `sub`, and M4 must not be changed by M1. M1 therefore derives the Credence user id deterministically:

```text
user_id = uuid5(CREDENCE_GOOGLE_NAMESPACE, "google:" + sub)
```

and looks users up with `find_by_id`. The same Google account always maps to the same Credence user.

- `CREDENCE_GOOGLE_NAMESPACE` is a fixed constant in `service.py`. It is not a secret and **must never change**, because changing it would map every Google account to a different user.
- M4 requires a `password_hash`, so users created by M1 get the placeholder `!google-oauth-no-password`, which can never match a password.
- If M4 later gains a dedicated `google_sub` field, only `google_sub_to_user_id` and the lookup in `_get_or_create_user` (`service.py`) need to change.

### Credence JWT

Algorithm: `HS256`, signed with `JWT_SECRET`.

| Claim | Meaning |
|---|---|
| `sub` | Credence user id (UUID) |
| `iss` | `JWT_ISSUER` |
| `aud` | `JWT_AUDIENCE` |
| `iat` | Issued at |
| `exp` | Expiration (`JWT_EXPIRE_MINUTES`) |
| `typ` | Token type, always `access` |
| `jti` | Unique token id |

Validation checks the signature, expiration, issuer, audience, token type, that all required claims are present, and that `sub` is a valid UUID. Tokens signed with `alg: none` or another algorithm are rejected.

### Using M1 from other modules

Other modules never validate JWTs themselves. They depend on `get_current_user`, which returns the M4 `User` or raises `401` (`503` if the database is unavailable):

```python
from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.database.models.user import User

router = APIRouter()

@router.get("/example")
async def example(user: User = Depends(get_current_user)):
    return {"user_id": str(user.id)}
```

### Integration requirements

`app/main.py` must:

1. Call `load_dotenv()` before the application is created.
2. Store M4's `DatabaseManager` on `app.state` as `db_manager`.
3. Include the auth router:

```python
from app.auth.router import router as auth_router

app.include_router(auth_router)
```

M1 looks for the `DatabaseManager` on `app.state` under `db_manager`, `database_manager`, `database` or `db` (see `DATABASE_MANAGER_STATE_ATTRS` in `app/auth/dependencies.py`). If it cannot find one, authenticated endpoints return `503`.

### Google Cloud setup

1. Create an OAuth client ID of type **Web application** in Google Cloud Console.
2. Add the frontend origin(s) under **Authorized JavaScript origins**.
3. Put the client ID in `GOOGLE_CLIENT_ID`.

Only the client ID is used by the backend. The client secret is not needed for this flow and must never be committed.

### Testing

```bash
python -m pytest tests/auth -v
```

The tests cover Google validation (valid, invalid, expired, wrong audience/issuer, unverified email, non-institutional account), user handling (new user, existing user, `sub` mapping, email conflicts, inactive users), JWT handling (valid, expired, bad signature, malformed, missing or invalid claims) and the authentication dependency. Google is mocked and MongoDB is replaced by an in-memory fake repository, so no network or database is needed.

For a real end-to-end check, start the backend, obtain a Google ID token with an institutional account from a page that uses Google Sign-In, and call `POST /auth/google` (for example from `/docs`). Then use the returned `access_token` with **Authorize** and call `GET /auth/me`. Signing in again should return the same `user.id`.

### Known limitations

- **No roles.** M1 does not assign or expose roles. M2 will need a place to store them.
- **Email changes.** If a user's Google email changes, the stored email is not updated, because M4 has no update operation.
- **Email conflicts.** If the email of a first-time Google user already belongs to a different Credence user, login returns `403`; accounts are not linked automatically by email.
- **HTTPS.** HTTPS must be provided by the deployment (for example a reverse proxy). It is not enforced in application code.

---

## Development Notes

- Use the existing shared FastAPI application. Do not create a separate FastAPI server for individual modules.
- Keep required Python dependencies updated in `requirements.txt`.
- Keep `.env` out of Git.
- Update this README when adding a major backend feature or changing the setup process.
