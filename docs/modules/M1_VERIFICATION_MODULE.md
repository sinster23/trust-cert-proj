# Credence — M1 Module README

## Certificate Verification API and Service

**Implementation order:** After M4 completes and merges database lifecycle changes.

**Target completion:** 1 November 2026.

### 1. Objective

M1 is responsible for implementing the certificate verification workflow in the existing FastAPI backend.

The API must allow anyone to verify a certificate using its certificate ID without requiring authentication.

M1 is responsible for coordinating the existing M3 cryptographic service, M4 certificate repository, and M5 certificate domain functionality.

M1 must not duplicate functionality already implemented by other members.

### 2. Prerequisites

M1 must begin implementation only after M4 has:

- Added certificate lifecycle status.
- Implemented certificate revocation.
- Updated certificate retrieval to return lifecycle status.
- Passed the relevant database tests.
- Merged the changes into the shared development branch.

Before implementation, inspect the actual merged repository method signatures and exception classes.

The existing M3 `CryptoService` and M5 certificate model and canonical serializer must also be reused.

### 3. Scope and responsibilities

M1 must implement:

1. Certificate verification service.
2. Public verification API endpoint.
3. Integration with M4 certificate retrieval.
4. Integration with M3 signature verification.
5. Integration with M5 certificate reconstruction and canonicalization.
6. Verification result schemas.
7. Appropriate error handling.
8. Verification API tests.

### 4. API specification

**Endpoint:**

`GET /certificates/verify/{certificate_id}`

Authentication: Not required.

The endpoint must be publicly accessible without a Credence JWT.

Example successful response:

```json
{
  "certificate_id": "CERT-example",
  "status": "VALID",
  "signature_valid": true,
  "certificate_status": "ACTIVE",
  "message": "Certificate is authentic and active."
}
```

Possible verification outcomes:

| Status | Meaning |
|---|---|
| VALID | Signature is valid and certificate is active. |
| INVALID | Signature verification fails. |
| REVOKED | Signature is valid but certificate has been revoked. |
| NOT_FOUND | Certificate does not exist; return HTTP 404. |

Infrastructure failures must return appropriate server errors. Do not report a certificate as invalid merely because the database or cryptographic service is unavailable.

### 5. Integration with M4 — Database

Use the existing certificate repository.

Expected logical interface:

```python
get_certificate_by_id(
    certificate_id: str
) -> dict | None
```

The retrieved record should contain:

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

M1 must not implement database queries directly.

Use the repository's existing exception handling and dependency configuration.

### 6. Integration with M3 — Cryptography

Reuse the existing `CryptoService`.

The available verification method is:

```python
verify_signature(
    canonical_data: bytes,
    signature: str,
    *,
    public_key=None,
    key_id: str | None = None
) -> bool
```

The available properties and methods include:

```python
crypto_service.key_id
crypto_service.get_public_key_pem()
```

For certificate verification, M1 must:

1. Pass the canonical certificate bytes.
2. Pass the stored signature.
3. Pass the stored key ID.
4. Respect the existing algorithm and key-management behavior.

Do not implement Ed25519 verification again.

**Important limitation:** The current M3 implementation checks the supplied key ID against its configured key ID. It does not establish support for a historical public-key registry. Do not assume that certificates signed with older keys can already be verified.

If the stored key ID is unsupported, handle the result according to the existing crypto service behavior and document the limitation.

### 7. Integration with M5 — Certificate domain

Reuse the existing M5 implementation:

- `Certificate.from_dict()`
- Existing canonical serialization implementation.

The repository stores the certificate ID separately from `certificate_data`.

Therefore, reconstruct the complete certificate representation before validation:

```python
certificate_data = {
    "certificate_id": record["certificate_id"],
    **record["certificate_data"]
}
```

Rebuild the certificate using the existing domain model.

Then generate canonical bytes using the existing canonical serializer.

Do not:

- Create another certificate model.
- Implement another canonical serializer.
- Include signature metadata in the signed certificate data.
- Include lifecycle status in the signed certificate data.

### 8. Verification workflow

The verification service must follow this sequence:

1. Receive the certificate ID.
2. Retrieve the certificate using M4.
3. If no record exists, return HTTP 404.
4. Reconstruct the complete certificate data.
5. Validate the certificate using M5's existing model.
6. Generate canonical bytes using M5's existing serializer.
7. Extract signature metadata.
8. Call M3's `CryptoService.verify_signature()`.
9. Read the certificate lifecycle status.
10. Construct and return the verification response.

Result handling:

- Valid signature + ACTIVE status = `VALID`.
- Valid signature + REVOKED status = `REVOKED`.
- Invalid signature = `INVALID`.
- Missing certificate = HTTP 404.

**Important:** A revoked certificate can still have a valid digital signature. Cryptographic authenticity and certificate lifecycle status are separate checks.

### 9. Response and privacy requirements

The public verification endpoint must not expose:

- Private keys.
- Internal database identifiers.
- Authentication tokens.
- Unnecessary student information.
- Internal exception traces.

Return only the certificate fields approved for public verification and the verification result.

Keep the response structure consistent for frontend integration.

### 10. Testing requirements

Add tests covering:

1. Valid signature and ACTIVE certificate.
2. Valid signature and REVOKED certificate.
3. Invalid signature.
4. Certificate not found.
5. Malformed certificate data.
6. Malformed signature metadata.
7. Unsupported key ID.
8. Database retrieval failure.
9. Cryptographic service failure.
10. Public endpoint accessible without authentication.

Tests must use the actual integrated M3 and M4 implementations. Do not build the implementation around mocked dependencies.

### 11. Restrictions

- Do not modify M4 database implementation.
- Do not modify M3 cryptographic implementation unless a separately agreed issue is identified.
- Do not modify M5 certificate model or canonical serializer.
- Do not create another FastAPI application.
- Do not implement certificate issuance again.
- Do not implement signing or key generation.
- Do not require authentication for public certificate verification.
- Do not break existing authentication, RBAC, or certificate issuance functionality.

### 12. Completion and merge requirements

M1 is complete when:

- The verification service is implemented.
- The public verification endpoint works.
- M3, M4, and M5 functionality is integrated correctly.
- All verification tests pass.
- Existing certificate issuance remains functional.
- The API response structure is documented.
- Frontend integration details are communicated to M2.
- Changes are committed and merged into the shared development branch.

**Definition of done:** A user can submit a certificate ID through the public API and receive an accurate VALID, INVALID, REVOKED, or NOT_FOUND result based on the stored certificate, its digital signature, and its lifecycle status.