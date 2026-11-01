# Credence — M1 Module README

## Certificate Verification API and Service

**Implementation begins:** After M4's database lifecycle changes are merged.

**Target completion:** 2 November 2026.

## 1. Objective

M1 is responsible for implementing the certificate verification workflow in the existing FastAPI backend.

Users must be able to verify a certificate using its certificate ID without logging in.

M1 coordinates the existing M3 cryptographic service, M4 certificate repository, and M5 certificate domain functionality.

M1 must not duplicate functionality already implemented by other members.

## 2. Prerequisites

M1 must begin implementation after M4 has:

- Added certificate lifecycle status.
- Implemented certificate revocation.
- Updated certificate retrieval to return lifecycle status.
- Passed the relevant database tests.
- Merged the changes into the shared development branch.

M4's lifecycle changes have been submitted. M1 should confirm that the merged repository matches the interface documented below.

## 3. Existing modules and interfaces

Use the actual existing project modules.

| Responsibility | Module |
|---|---|
| Cryptography | `app.crypto.CryptoService` |
| Database | `app.database.repositories.certificate_repository` |
| Certificate domain | `app.certificates` |
| Canonicalization | `app.certificates.canonicalize(...)` |
| Existing FastAPI application | `app.main` |

### M3 — Cryptography

Reuse:

```python
crypto.verify_signature(
    canonical_data,
    signature,
    key_id=key_id
)
```

Other available interfaces:

```python
crypto.get_public_key_pem()
crypto.key_id
```

Do not implement Ed25519 signing or verification again.

**Important limitation of the existing CryptoService:**

Its `verify_signature()` method returns `False` for some infrastructure failures, including unavailable public keys and mismatched key IDs.

M1 must account for this behavior rather than interpreting every `False` result as an invalid signature.

Before calling `verify_signature()`:

1. Validate the stored signature metadata.
2. Confirm the algorithm is `Ed25519`.
3. Compare the stored `key_id` with `crypto.key_id`.
4. Call `crypto.get_public_key_pem()` to preflight public-key availability.
5. If the key is unavailable or its configuration is invalid, return `UNVERIFIABLE` with HTTP 503.
6. If the stored key ID does not match the configured key ID, return `UNVERIFIABLE` with HTTP 503.
7. Only then call `verify_signature()`.

A malformed or cryptographically invalid signature must produce `INVALID`, not an infrastructure error.

This preflight is required because M3's current implementation cannot reliably distinguish all infrastructure failures from invalid signatures by itself.

Historical key support is not currently established. Do not assume that certificates signed with older keys can be verified.

### M4 — Database

Reuse:

```python
from app.database.repositories.certificate_repository import (
    CertificateRepository,
    ACTIVE,
    REVOKED,
)
```

Existing methods:

```python
await repository.get_certificate_by_id(certificate_id)
```

```python
await repository.revoke_certificate(certificate_id)
```

The retrieved record contains:

```python
{
    "certificate_id": "CERT-...",
    "certificate_data": {...},
    "signature_metadata": {
        "signature": "...",
        "key_id": "...",
        "algorithm": "Ed25519"
    },
    "status": "ACTIVE"
}
```

M4 exposes database exceptions including `DatabaseError` and its subclasses.

Important exception handling:

- Missing certificate: handle as NOT_FOUND.
- Invalid database operation caused by malformed ID: prevent by validating the ID before calling M4.
- Database connection or operation failure: return HTTP 503.

Do not implement MongoDB queries directly in M1.

### M5 — Certificate domain

Reuse:

```python
from app.certificates import Certificate
```

Use the existing certificate ID validator:

```python
validate_certificate_id(certificate_id)
```

Use the existing canonicalization function:

```python
canonicalize(certificate_data)
```

Also reuse the existing certificate service and its domain exceptions where appropriate.

Do not create another certificate model or canonical serializer.

## 4. Required implementation structure

Create a dedicated verification module inside the existing backend application.

```text
backend/
└── app/
    ├── main.py
    ├── verification/
    │   ├── __init__.py
    │   ├── router.py
    │   ├── service.py
    │   ├── schemas.py
    │   └── exceptions.py
    │
    ├── crypto/
    ├── database/
    └── certificates/

└── tests/
    └── verification/
        ├── __init__.py
        ├── test_verification_service.py
        └── test_verification_router.py
```

Follow existing project naming and import conventions if the repository structure has changed.

### File responsibilities

**`verification/router.py`**

- Define the public verification endpoint.
- Validate the incoming certificate ID.
- Call the verification service.
- Map domain and infrastructure exceptions to HTTP responses.
- Return the agreed response schema.

**`verification/service.py`**

- Implement the complete asynchronous verification workflow.
- Retrieve certificate records through M4.
- Reconstruct and validate certificate data through M5.
- Generate canonical bytes through M5.
- Perform cryptographic verification through M3.
- Evaluate lifecycle status.
- Return a structured verification result.

The service must be `async` because M4's repository operations are asynchronous.

**`verification/schemas.py`**

Define the verification response schema.

The response must contain exactly five fields:

- `certificate_id`
- `status`
- `signature_valid`
- `certificate_status`
- `message`

Use nullable types for `signature_valid` and `certificate_status` where appropriate.

**`verification/exceptions.py`**

Define verification-specific exceptions only when necessary.

Reuse existing exceptions:

- `CryptoError`
- `DatabaseError` and its subclasses
- `CertificateError`
- `StoredCertificateError` where required

Note: `StoredCertificateError` is not exported through the `app.certificates` package initializer. Import it from its actual defining module if needed.

Do not duplicate existing exception classes.

## 5. Certificate reconstruction

M4 stores the certificate ID separately from certificate data.

Reconstruct the complete representation:

```python
certificate_data = {
    "certificate_id": record["certificate_id"],
    **record["certificate_data"]
}
```

Validate it using the existing certificate model:

```python
certificate = Certificate.from_dict(certificate_data)
```

Generate canonical bytes using:

```python
canonical_data = canonicalize(certificate.to_dict())
```

Use the actual return type of the existing canonicalization function.

Do not include signature metadata or lifecycle status in the signed certificate representation.

## 6. API specification

**Endpoint:**

`GET /certificates/verify/{certificate_id}`

Authentication: Not required.

The endpoint must be registered in the existing FastAPI application.

In `app/main.py`, follow this registration pattern:

```python
from app.verification.router import router as verification_router

app.include_router(verification_router)
```

Do not create another FastAPI application.

### Certificate ID validation

Validate the certificate ID before calling M4.

Use M5's existing `validate_certificate_id()` or equivalent FastAPI path validation using the exact existing pattern:

`^CERT-[0-9a-f]{32}$`

A malformed ID must return HTTP 422.

A correctly formatted but nonexistent certificate ID must return HTTP 404.

This prevents M4's `InvalidDatabaseOperationError` for malformed IDs from being incorrectly interpreted as a database outage.

## 7. Verification outcome rules

The following behavior is mandatory:

| Situation | Status | HTTP |
|---|---|---:|
| Valid signature + ACTIVE | VALID | 200 |
| Valid signature + REVOKED | REVOKED | 200 |
| Invalid signature | INVALID | 200 |
| Certificate not found | NOT_FOUND | 404 |
| Malformed certificate ID | Validation error | 422 |
| Malformed stored certificate data | INVALID | 200 |
| Missing or malformed signature metadata | INVALID | 200 |
| Unsupported signature algorithm | INVALID | 200 |
| Unsupported key ID | UNVERIFIABLE | 503 |
| Missing/unavailable public key | UNVERIFIABLE | 503 |
| Database unavailable | Service unavailable | 503 |
| Unknown lifecycle status | Internal data error | 500 |

### Additional rules

**Malformed stored certificate data**

If `Certificate.from_dict()` raises an existing certificate validation exception, classify the stored record as INVALID.

Do not expose internal validation details in the public response.

**Signature metadata**

Before cryptographic verification, check that metadata contains the required non-empty fields:

- `signature`
- `key_id`
- `algorithm`

The algorithm must be `Ed25519`.

Missing or malformed metadata and unsupported algorithms produce INVALID.

**Unsupported key ID**

Compare the stored key ID with `crypto.key_id` before calling `verify_signature()`.

A mismatch produces UNVERIFIABLE with HTTP 503 because the currently configured key cannot establish the certificate's authenticity.

**Unknown lifecycle status**

Only ACTIVE and REVOKED are valid lifecycle states.

Any other stored value must produce HTTP 500. Never assume an unknown status is ACTIVE.

**Invalid signature versus revoked status**

Signature verification takes priority.

If a certificate is revoked and its signature is also invalid, return INVALID.

A certificate is REVOKED only when its signature is valid and its lifecycle status is REVOKED.

## 8. Response format

All verification responses must use the same five-field schema.

No student information or additional internal data may be exposed.

### VALID

HTTP 200

```json
{
  "certificate_id": "CERT-example",
  "status": "VALID",
  "signature_valid": true,
  "certificate_status": "ACTIVE",
  "message": "Certificate is authentic and active."
}
```

### REVOKED

HTTP 200

```json
{
  "certificate_id": "CERT-example",
  "status": "REVOKED",
  "signature_valid": true,
  "certificate_status": "REVOKED",
  "message": "Certificate is authentic but has been revoked."
}
```

### INVALID

HTTP 200

```json
{
  "certificate_id": "CERT-example",
  "status": "INVALID",
  "signature_valid": false,
  "certificate_status": "ACTIVE",
  "message": "Certificate integrity verification failed."
}
```

If the lifecycle status cannot be safely determined, `certificate_status` must be null.

### NOT_FOUND

HTTP 404

Return the same five-field response schema:

```json
{
  "certificate_id": "CERT-example",
  "status": "NOT_FOUND",
  "signature_valid": null,
  "certificate_status": null,
  "message": "Certificate was not found."
}
```

Do not return FastAPI's default `{"detail": ...}` body for this outcome.

### UNVERIFIABLE

HTTP 503

```json
{
  "certificate_id": "CERT-example",
  "status": "UNVERIFIABLE",
  "signature_valid": null,
  "certificate_status": null,
  "message": "Certificate verification is temporarily unavailable."
}
```

Do not expose internal key configuration or infrastructure details.

### Malformed ID

HTTP 422.

Use the project's normal request-validation error format. The five-field verification response is not required because verification has not started.

### Internal errors

Unknown lifecycle states and unexpected stored-record inconsistencies must produce appropriate server errors without exposing stack traces or internal implementation details.

## 9. Dependency handling

M5's existing `app/certificates/router.py` defines:

- `get_crypto_service`
- `get_certificate_repository`

Do not import dependencies directly from another router module. That would couple the verification router to the certificate issuance router.

Prefer defining the verification dependencies locally or reusing shared application-level dependency providers if they already exist.

Do not refactor unrelated application dependencies just for this task.

## 10. Testing requirements

Tests must use the actual implementations wherever practical.

Use:

- The real `CertificateRepository` with M4's in-memory `FakeCollection`.
- A real `CryptoService` with a temporary Ed25519 key pair created using `tmp_path`.
- The real `CertificateService.issue_certificate()` to generate valid issued records.
- Stored certificate data modification to test tampering.

For asynchronous tests, use:

```python
@pytest.mark.asyncio
```

There is no existing pytest configuration guaranteeing automatic asyncio mode.

For router tests, use the existing `app.main.app` and `dependency_overrides`.

`TestClient(app)` without using it as a context manager is acceptable for these tests because it avoids running the application's MongoDB-connecting lifespan.

### Required scenarios

1. Valid signature and ACTIVE certificate.
2. Valid signature and REVOKED certificate.
3. Invalid signature.
4. Revoked certificate with an invalid signature.
5. Certificate not found.
6. Malformed certificate ID.
7. Malformed stored certificate data.
8. Missing or malformed signature metadata.
9. Unsupported signature algorithm.
10. Unsupported key ID.
11. Missing or unavailable public key.
12. Database retrieval failure.
13. Unknown lifecycle status.
14. Public endpoint accessible without authentication.
15. Response contains exactly five fields and no student information.

## 11. Restrictions

- Do not modify M4 repository implementation.
- Do not modify M3 cryptographic implementation unless a separate issue is agreed upon.
- Do not modify M5 certificate models or canonical serializer.
- Do not create another FastAPI application.
- Do not implement certificate issuance again.
- Do not implement signing or key generation.
- Do not duplicate existing functionality.
- Do not require authentication for public verification.
- Do not expose private keys, student data, or internal exception traces.
- Do not break existing authentication, RBAC, or certificate issuance.

## 12. Completion and merge requirements

Before merging:

- Implement the verification service and router.
- Complete the response schemas.
- Integrate M3, M4, and M5 functionality.
- Implement all defined outcome and error mappings.
- Complete the verification tests.
- Confirm existing certificate issuance remains functional.
- Register the router in `app/main.py`.
- Document actual implementation paths and test commands.
- Communicate the final API contract to M2.
- Commit and merge into the shared development branch.

**Definition of done:** A user can submit a certificate ID through the public API and receive an accurate VALID, INVALID, REVOKED, NOT_FOUND, or UNVERIFIABLE result based on the stored certificate, digital signature, and lifecycle status.