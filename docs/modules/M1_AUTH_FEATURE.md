# M1 — Authentication Module

## 1. Objective

Build Credence's authentication and identity layer.

M1 answers:

> Who is this user?

Credence will use Google Workspace authentication for institutional users.

After successful Google authentication, M1 will:

1. Validate the Google identity.
2. Find or create the corresponding Credence user through M4.
3. Issue a Credence JWT for authenticated API requests.

Authentication and authorization are separate responsibilities:

- **M1:** Who are you?
- **M2:** What are you allowed to do?

---

## 2. Current Backend Status

The shared FastAPI application has already been created by the integration lead.

M4 — Database Foundation is also complete.

Current progress:

```text
Backend
│
├── FastAPI application       ✅ Foundation
│
├── M4 Database Foundation    ✅ Complete
│
└── M1 Authentication         🔄 Current task
```

M1 must build on top of the existing backend and must not create a separate FastAPI application.

---

## 3. Required Structure

```text
backend/
├── app/
│   ├── main.py                    # Shared FastAPI application
│   │
│   ├── auth/                      # M1
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   ├── dependencies.py
│   │   └── security.py
│   │
│   └── database/                  # M4
│       ├── __init__.py
│       ├── connection.py
│       ├── exceptions.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── user.py
│       └── repositories/
│           ├── __init__.py
│           └── user_repository.py
│
├── tests/
│   ├── database/                  # M4
│   │   ├── __init__.py
│   │   └── test_user_repository.py
│   │
│   └── auth/                      # M1
│       ├── __init__.py
│       └── test_auth.py
│
├── requirements.txt
├── .env
└── .env.example
```

Do not create another FastAPI application or server.

M1 should expose its endpoints through an `APIRouter` and integrate that router into the existing `app.main` application.

---

## 4. User Model

Initial authenticated Credence roles:

```text
STUDENT
ISSUER
ADMIN
```

M1 does **not** assign permissions or implement RBAC.

Those responsibilities belong to M2.

External certificate verifiers do not require an account in the initial system. They will use the public verification functionality later.

---

## 5. File Responsibilities

### `router.py`

Responsible for authentication API endpoints.

Possible responsibilities include:

- Google authentication flow
- Authentication response
- `/auth/me`
- Authentication-related errors

Use FastAPI `APIRouter`.

Do not put the main authentication logic directly inside the router.

---

### `service.py`

Responsible for the authentication workflow:

```text
Google identity
      ↓
Validate identity
      ↓
Find/create Credence user
      ↓
Issue Credence JWT
```

Use the M4 repository for persistence.

Do not directly access MongoDB.

---

### `schemas.py`

Contains authentication request/response models and public user representations.

---

### `dependencies.py`

Provides reusable authentication dependencies for other modules.

Other modules should be able to obtain the authenticated Credence user without implementing JWT validation themselves.

---

### `security.py`

Responsible for authentication security operations, including:

- Google identity/token validation
- JWT creation
- JWT validation
- Authentication security configuration

---

## 6. Google Authentication

Institutional users authenticate through Google Workspace.

The backend must independently validate the Google authentication result.

Relevant validation should include:

- Token authenticity/signature
- Issuer
- Audience
- Expiration
- Email verification
- Institutional domain/Workspace requirement

The institutional domain must come from configuration/environment variables.

Example:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_ALLOWED_DOMAIN=...
JWT_SECRET=...
```

Do not hard-code secrets or credentials.

Do not rely only on frontend checks such as:

```text
email.endsWith("@institution-domain")
```

The backend must perform the actual validation.

---

## 7. Google Identity

Use Google's stable:

```text
sub
```

identifier to associate a Google account with a Credence user.

Do not use email as the permanent external identity key.

Conceptually:

```text
Google Account
      ↓
Google `sub`
      ↓
Credence User
```

Email may still be stored as user information.

---

## 8. Authentication Flow

### First login

```text
Google Login
     ↓
M1 validates identity
     ↓
User not found
     ↓
Create user through M4
     ↓
Issue Credence JWT
```

### Existing user

```text
Google Login
     ↓
M1 validates identity
     ↓
Find user through M4
     ↓
Issue Credence JWT
```

M1 must not create users from arbitrary client-provided information.

---

## 9. M4 Integration

M4 — Database Foundation is already complete.

M1 must use M4's repository layer:

```text
M1 Authentication
       ↓
M4 User Repository
       ↓
MongoDB
```

M1 must not:

- Create another MongoDB connection
- Directly query MongoDB
- Create another user repository
- Duplicate M4 database functionality

If changes to the shared user model are required, coordinate with the integration lead before modifying M4.

---

## 10. JWT Requirements

After successful Google authentication, M1 issues a Credence JWT.

The token should contain only the claims required by the application.

At minimum, the implementation must consistently handle:

- User identity
- Issuer
- Expiration
- Audience where applicable
- Token type/purpose where applicable

M1 must:

- Validate token signature
- Validate expiration
- Validate required claims
- Reject malformed/invalid tokens
- Keep signing secrets outside source control

Other modules should use M1's authentication dependency instead of implementing JWT validation themselves.

---

## 11. Role Boundaries

M1 authenticates the user but does not decide their permissions.

For example:

```text
Google account
      ↓
M1
      ↓
Credence user
      ↓
M2
      ↓
Role / permissions
```

An institutional email does not automatically make someone:

```text
ADMIN
```

or:

```text
ISSUER
```

Role assignment and authorization will be handled by M2.

---

## 12. FastAPI Integration

The project has one shared FastAPI application:

```text
backend/app/main.py
```

M1 must not create another `FastAPI()` instance.

M1 should expose its routes using an `APIRouter`.

The router will then be included in the shared application.

Conceptually:

```text
main.py
   │
   ├── M1 auth router
   ├── M5 certificate router
   └── verification router
```

The exact endpoint structure can be decided by the M1 developer as long as it follows the module contract.

---

## 13. Security Requirements

M1 must:

- Validate Google authentication on the backend.
- Enforce the institutional account requirement.
- Never trust frontend authentication alone.
- Keep secrets in environment/configuration.
- Reject expired and invalid credentials.
- Avoid exposing internal authentication errors.
- Never expose private keys or secrets.
- Use HTTPS in deployed environments.

---

## 14. Testing Requirements

`backend/tests/auth/test_auth.py` should cover at minimum:

### Google authentication

- Valid institutional account
- Invalid token
- Expired token
- Incorrect audience/issuer
- Unverified email
- Non-institutional account

### User handling

- Existing user login
- New user creation
- Correct `sub` → Credence user mapping

### JWT

- Valid JWT
- Expired JWT
- Invalid signature
- Malformed JWT
- Missing/invalid required claims

### Authentication dependency

- Authenticated request returns current user
- Missing authentication is rejected
- Invalid authentication is rejected

External Google services should be mocked during tests.

---

## 15. Module Boundaries

M1 must NOT implement:

- RBAC/permissions
- Certificate creation
- Certificate verification
- Certificate signing
- Certificate hashing
- Certificate revocation
- QR verification
- AI analysis
- Direct MongoDB access

Responsibilities:

| Module | Responsibility |
|---|---|
| M1 | Authentication & identity |
| M2 | Roles & authorization |
| M3 | Cryptography & signing |
| M4 | Database & persistence |
| M5 | Certificate domain & verification |

---

## 16. Documentation & Dependencies

While implementing M1, keep the module documentation up to date.

### README

Update this README whenever:

- The module structure changes
- An endpoint is added/removed
- A dependency or integration requirement changes
- An important configuration variable is introduced
- The authentication flow changes
- A shared interface with another module changes

The README should describe the **current state of the module**, not only the original plan.

### `requirements.txt`

Whenever M1 introduces a Python dependency required by its implementation:

1. Add it to `backend/requirements.txt`.
2. Use an appropriate version constraint.
3. Ensure the dependency is actually required.
4. Test installation from the requirements file.

Do not leave required dependencies only installed locally.

Do not add unrelated packages.

---

## 17. Definition of Done

M1 is complete when:

- [ ] Google Workspace authentication works.
- [ ] Backend validates Google identity.
- [ ] Institutional account/domain requirement is enforced.
- [ ] Google `sub` is used as the stable external identity.
- [ ] Existing users can authenticate.
- [ ] New users can be created through M4.
- [ ] Credence JWT is issued after authentication.
- [ ] JWT validation works correctly.
- [ ] Other modules can obtain the authenticated user through M1.
- [ ] M1 integrates with the existing FastAPI application.
- [ ] M1 does not directly access MongoDB.
- [ ] M1 does not implement RBAC.
- [ ] Authentication tests pass.
- [ ] Required dependencies are present in `requirements.txt`.
- [ ] README reflects the final implementation.
- [ ] No secrets are committed to Git.
- [ ] M1 is ready for M2 integration.

---

## 18. Implementation Freedom

The developer may choose:

- Google authentication flow/library
- JWT library
- Internal service methods
- Helper functions
- Token claim structure
- Testing approach

provided the requirements and module boundaries are maintained.

If an implementation decision affects M2, M3, M4, shared models, shared APIs, or the FastAPI application structure, discuss it with the integration lead before changing it.

