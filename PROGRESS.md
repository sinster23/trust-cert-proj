# Credence — Team Contributions and Implementation Progress

## 1. Project Overview

**Credence** is a secure academic certificate issuance and verification system designed to establish the authenticity and integrity of institutional certificates.

The system combines Google-based authentication, role-based access control, certificate validation, deterministic canonicalization, Ed25519 digital signatures, and MongoDB persistence.

The backend is built using **FastAPI and Python**, with MongoDB as the database. The frontend is built using **Next.js** and communicates with the backend API.

The project follows a modular architecture in which each member is responsible for a specific part of the system. Modules integrate through defined service and repository interfaces rather than implementing duplicate authentication, cryptography, or database logic.

## 2. Team Contributions

### M1 — Authentication

**Responsibility:** Establish the identity of users accessing Credence and provide authenticated access to protected backend resources.

**Implementation:**

- Google-based user authentication.
- Validation of Google identity tokens and institutional identity requirements.
- Use of Google's stable `sub` claim to identify users.
- User lookup and creation through the M4 database layer.
- Credence JWT generation and authentication for subsequent API requests.
- Authentication dependencies for protected backend endpoints.

**How it works:**

1. A user signs in through the frontend using Google.
2. The backend validates the Google identity token rather than trusting identity details supplied by the browser.
3. Institutional email/domain requirements are checked.
4. The user's Google identity is matched with the corresponding Credence user record through M4.
5. The backend establishes a Credence session using a JWT.
6. Protected API requests use that JWT to identify the current user.

**Integration with other modules:**

- Uses M4 for persistent user records.
- Provides the authenticated identity used by M2 to evaluate permissions.
- Protects endpoints that require a logged-in user.

**Remaining work:**

- Verify token expiry, invalid-token handling, and session failure cases.
- Confirm the institutional identity policy is enforced consistently.
- Test authentication through the complete frontend-to-backend flow.

### M2 — Authorization and Role-Based Access Control

**Responsibility:** Decide what an authenticated user is permitted to do.

**Implementation:**

Credence defines three roles:

- `STUDENT`
- `ISSUER`
- `ADMIN`

The authorization layer separates authentication from permission checks. A valid login establishes identity, but it does not automatically grant certificate-issuing privileges.

Implemented authorization rules include:

- New users default to `STUDENT`.
- Issuer privileges must be explicitly granted by an administrator.
- Administrator access is explicitly provisioned.
- Users cannot grant themselves additional roles.
- Protected backend operations enforce permissions through authorization dependencies.
- Role changes and user-role lookups use the database/repository layer.

The documented authorization endpoints include:

- `GET /authorization/me` — retrieve the current user's authorization information.
- `GET /authorization/users` — retrieve users for authorized administrative workflows.
- `PUT /authorization/users/{id}/role` — update a user's role through the authorized role-management workflow.

**How it works:**

1. M1 authenticates the user and establishes the Credence identity.
2. M2 obtains the authenticated user context.
3. The authorization dependency checks the user's assigned role and the permission required by the endpoint.
4. Authorized requests proceed; requests without the required permission are rejected.

For example, an authenticated student cannot issue a certificate merely because they have a valid JWT. The backend must establish that the user has the `ISSUER` role.

**Integration with other modules:**

- Uses M1's authenticated user context.
- Uses M4 to persist and retrieve role assignments.
- Protects certificate issuance operations in M5.

**Remaining work:**

- Verify role changes and permission checks against real API requests.
- Confirm that every certificate-issuing route requires issuer authorization.
- Test missing JWTs, invalid JWTs, student access, and administrator-only operations.

### M3 — Cryptography and Digital Signatures

**Responsibility:** Provide the cryptographic operations used to establish certificate integrity and authenticity.

**Implementation:**

The cryptography module is located under `app/crypto/`.

Its responsibilities include:

- SHA-256 hashing.
- Ed25519 digital-signature generation.
- Digital-signature verification.
- Signing-key loading and validation.
- Public-key access.
- Signing key identification through a configured key ID.
- Controlled handling of cryptographic errors.

The implementation uses the Python `cryptography` library.

Private-key and public-key paths are configured through environment variables, including:

- `SIGNING_PRIVATE_KEY_PATH`
- `SIGNING_PUBLIC_KEY_PATH`
- `SIGNING_KEY_ID`

The private key is loaded from a PEM-encoded PKCS#8 Ed25519 key. If the public-key path is omitted, the public key can be derived from the private key.

Signatures use unpadded URL-safe Base64 encoding. The service result includes the signature, key ID, and algorithm label.

**How it works:**

1. M5 produces the canonical byte representation of a certificate.
2. M3 signs those exact bytes using the configured Ed25519 private key.
3. M3 returns the signature and associated signing metadata.
4. During verification, the corresponding public key verifies the signature against the original canonical bytes.
5. If the certificate data changes, the resulting canonical bytes differ and signature verification should fail.

M3 deliberately does not define the academic certificate schema, serialize certificate objects, or decide whether a user is authorized to issue certificates.

**Integration with other modules:**

- Receives canonical bytes from M5.
- Supplies signature metadata for persistence through M4.
- Provides cryptographic verification for certificate-verification workflows.

**Remaining work:**

- Verify signatures using persisted certificate records.
- Confirm tampered certificate data fails verification.
- Validate key ID handling and public-key selection.
- Strengthen key rotation and key protection before production use.

### M4 — Database and Persistence

**Responsibility:** Manage persistent application data and provide repository interfaces to the other modules.

**Implementation:**

The database layer is located under `app/database/` and uses **PyMongo Async** for asynchronous MongoDB operations.

The user-persistence functionality includes:

- MongoDB connection management.
- User model and repository.
- User creation and lookup.
- Google identity (`google_sub`) storage.
- Email normalization.
- Duplicate-email protection.
- Persistent user roles.
- Role update and lookup operations.
- Database error handling.

The certificate-persistence work extends this foundation with a repository for issued certificates.

The intended issued-certificate record separates certificate content from signature metadata:

```text
Issued Certificate
├── certificate_id
├── certificate_data
│   ├── student_id
│   ├── student_name
│   ├── institution
│   ├── degree
│   ├── field_of_study
│   ├── graduation_date
│   ├── issue_date
│   └── schema_version
└── signature_metadata
    ├── signature
    ├── key_id
    └── algorithm
```

A unique index on `certificate_id` prevents duplicate certificate identifiers. The repository provides operations to create a certificate record and retrieve a certificate by its identifier.

**How it works:**

1. M1 uses the user repository to find or create authenticated users.
2. M2 uses persisted role information to make authorization decisions.
3. M5 creates the certificate data and obtains its signature from M3.
4. M5 passes the certificate and signature metadata to the certificate repository.
5. M4 stores the issued record in MongoDB and retrieves it when requested.

Other modules should use the repository layer rather than creating their own MongoDB connections or accessing collections directly.

**Remaining work:**

- Verify index initialization during application startup.
- Confirm duplicate certificate IDs are handled safely.
- Test persistence and retrieval using the same record returned by the issuance API.
- Confirm failures during persistence do not result in a successful issuance response.

### M5 — Certificate Domain, Issuance, and Canonicalization

**Responsibility:** Define the academic certificate structure, validate certificate information, generate deterministic canonical bytes, and coordinate signing and persistence.

**Implementation:**

The certificate domain includes:

- Certificate data models.
- Request and response schemas.
- Domain validation and custom exceptions.
- Certificate identifier generation.
- Deterministic canonicalization.
- Integration with M3's signing service.
- Integration with M4's certificate repository.
- Certificate retrieval.

The academic certificate model contains:

- Certificate ID.
- Student ID and name.
- Institution.
- Degree.
- Field of study.
- Graduation date.
- Issue date.
- Schema version.

Certificate IDs use the `CERT-` prefix followed by a UUID-derived hexadecimal identifier.

The domain validates required fields, text normalization, identifier formats, ISO calendar dates, and the supported schema version. The issue date cannot precede the graduation date.

Canonicalization serializes the validated certificate into deterministic UTF-8 JSON bytes using sorted keys and compact separators. This ensures that signing and verification use a consistent byte representation.

**How it works:**

1. The issuance request is validated against the certificate schema and domain rules.
2. M5 creates a certificate with a server-generated identifier and issue date.
3. The certificate is canonicalized into deterministic bytes.
4. M3 signs those bytes.
5. M5 builds a persistence record containing certificate data and signature metadata.
6. M4 stores the record.
7. The issuance response returns the certificate and its digital signature metadata.
8. The retrieval workflow obtains the persisted record using the certificate ID.

**Integration with other modules:**

- Receives authenticated and authorized requests through M1 and M2.
- Uses M3 for signing and, in the verification workflow, signature verification.
- Uses M4 for persistent certificate storage and retrieval.
- Supplies certificate information to the Next.js frontend.

**Remaining work:**

- Complete independent verification against the retrieved certificate data.
- Ensure the public key corresponds to the stored signing key ID.
- Return a clear verification result for valid, modified, and unknown certificates.
- Add certificate status and revocation handling.
- Preserve compatibility when certificate schema versions evolve.

## 3. Frontend Implementation

The Next.js frontend provides the user-facing interface for the existing backend functionality.

The current reported features include:

- Google authentication.
- Role-aware access to application functionality.
- Certificate creation for authorized issuers.
- Viewing issued certificates.
- Displaying digital-signature information.

**How the frontend interacts with the backend:**

1. The user authenticates through the frontend.
2. The frontend uses the authenticated session when calling protected API endpoints.
3. The backend remains responsible for validating identity and enforcing permissions.
4. An authorized issuer submits certificate details through the certificate form.
5. The backend validates, signs, and persists the certificate.
6. The frontend displays the result returned by the backend.

The frontend is a client of the API; it does not independently authorize issuers, sign certificates, or access MongoDB.

## 4. End-to-End Architecture

```text
Next.js Frontend
       |
       v
M1: Google Authentication
       |
       v
M2: Role and Permission Checks
       |
       v
M5: Certificate Validation
       |
       v
M5: Canonicalization
       |
       v
M3: Ed25519 Signing
       |
       v
M4: MongoDB Persistence
       |
       v
Certificate Issued and Displayed
```

Certificate verification follows the complementary path: retrieve the persisted certificate, reconstruct the canonical bytes, and verify the signature using the appropriate public key.

## 5. Current Project Status

The team has reported implementation of the core authentication and role-based access flow, certificate creation by authorized issuers, digital signing, database persistence, and frontend certificate viewing.

The existence of these features does not alone establish that every security and failure case has been validated. The next milestone is to prove the integrated workflow through API checks and a small automated integration suite.

## 6. Next Phase

### Priority 1 — End-to-End Validation

- Issue a certificate as an authorized issuer.
- Confirm a student or unauthenticated user cannot issue a certificate.
- Confirm the record is stored in MongoDB.
- Retrieve the same certificate by its ID.
- Verify the signature against the original canonical certificate data.
- Modify certificate data and confirm verification fails.

### Priority 2 — Independent Verification

Implement and validate a verification workflow that does not trust the frontend's displayed signature status. It should use the persisted certificate data, canonicalization rules, and the correct public key.

### Priority 3 — Certificate Lifecycle

Introduce certificate status and revocation support so a cryptographically valid certificate can still be reported as revoked or otherwise invalidated.

### Priority 4 — Security Hardening

Improve key management, audit logging, error handling, and API validation. Ensure role enforcement, signing-key protection, and database constraints are applied consistently.

### Priority 5 — Documentation and Integration

Keep the module READMEs, API contracts, environment configuration, and repository interfaces aligned with the final integrated implementation.

## 7. Development Principles

- Use the shared FastAPI application.
- Keep authentication, authorization, cryptography, certificate-domain logic, and database persistence separated by responsibility.
- Use repository interfaces for database operations.
- Enforce authorization on the backend.
- Keep private keys and environment secrets out of source control.
- Validate signatures against canonical certificate bytes rather than formatted frontend output.
- Update documentation when implementation contracts change.
- Prioritize meaningful integration checks over large, redundant test suites.
