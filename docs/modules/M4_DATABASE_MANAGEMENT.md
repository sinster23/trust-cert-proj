# Credence — M4 Module README

## Certificate Database Lifecycle Management

**Priority:** First implementation task\
**Deadline:** Complete and merge before M3 begins.

### 1. Objective

M4 is responsible for extending the existing certificate repository to support certificate lifecycle management.

The existing repository supports certificate insertion and retrieval. The next requirement is to support certificate revocation while preserving the integrity of the original certificate data and digital signature.

M4 must work within the existing DB module. Do not create another database connection or duplicate the certificate domain model.

### 2. Existing implementation

The following functionality is already implemented:

- `CertificateRepository`
- `create_certificate()`
- `get_certificate_by_id()`
- Unique index on `certificate_id`
- Record shape validation
- Duplicate certificate ID handling
- Database exception handling

The existing certificate record contains:

- `certificate_id`
- `certificate_data`
- `signature_metadata`

Preserve the existing structure and functionality.

### 3. Required changes

#### A. Add certificate lifecycle status

Extend the persisted record with:

`status: "ACTIVE"`

Newly issued certificates must automatically receive ACTIVE status.

The status must be stored outside `certificate_data` and `signature_metadata`.

Do not include lifecycle status in the signed certificate representation.

#### B. Implement certificate revocation

Add:

```
async def revoke_certificate(
    self,
    certificate_id: str
) -> dict[str, Any]:
    ...
```

Requirements:

- Validate the certificate ID.
- Find the corresponding certificate.
- Change its status from ACTIVE to REVOKED.
- Do not modify certificate data.
- Do not modify signature metadata.
- Handle nonexistent certificates appropriately.
- Handle repeated revocation attempts explicitly.
- Preserve database exception handling.

Use an atomic database update to prevent conflicting lifecycle changes.

#### C. Update certificate retrieval

The existing method:

```
async def get_certificate_by_id(
    self,
    certificate_id: str
) -> dict[str, Any] | None:
    ...
```

Must continue returning the complete record, including its lifecycle status.

Ensure existing certificate issuance and retrieval functionality remains compatible.

### 4. Record structure after implementation

New records should follow this structure:

```
{
    "certificate_id": "CERT-...",
    "certificate_data": {
        # Existing certificate fields
    },
    "signature_metadata": {
        "signature": "...",
        "key_id": "...",
        "algorithm": "Ed25519"
    },
    "status": "ACTIVE"
}
```

After revocation:

```
{
    "certificate_id": "CERT-...",
    "certificate_data": {
        # Unchanged certificate fields
    },
    "signature_metadata": {
        "signature": "...",
        "key_id": "...",
        "algorithm": "Ed25519"
    },
    "status": "REVOKED"
}
```

### 5. Important restrictions

- Do not import M5 certificate models into the DB module.
- Do not implement signing or signature verification.
- Do not modify certificate data during revocation.
- Do not modify signature metadata.
- Do not add certificate update or delete functionality.
- Do not create a separate FastAPI application.
- Do not break existing certificate issuance.
- Do not change existing repository interfaces unnecessarily.

The only permitted mutation is the controlled lifecycle status transition.

### 6. Testing requirements

Add tests covering:

1. Newly inserted certificates receive ACTIVE status.
2. Certificate retrieval returns lifecycle status.
3. An ACTIVE certificate can be revoked.
4. Revocation preserves certificate data.
5. Revocation preserves signature metadata.
6. A nonexistent certificate cannot be revoked.
7. Repeated revocation is handled correctly.
8. Database errors are handled correctly.
9. Existing certificate insertion and retrieval tests continue passing.

### 7. Completion and merge requirements

Before M3 begins, M4 must:

- Complete the repository changes.
- Update relevant DB tests.
- Run all existing DB tests.
- Confirm certificate issuance still works.
- Update the DB README with the new methods and record structure.
- Commit and merge the changes into the shared development branch.

M4 must communicate the final method signatures and exception behavior to M1 and M3.

**Definition of done:** Certificate persistence, retrieval and revocation work correctly, and the changes are merged without breaking existing issuance functionality.

## Implemented repository contract

`CertificateRepository` continues to accept the existing three-field issue record in `create_certificate(record)`. The repository adds `status: "ACTIVE"` itself, stores it alongside (not inside) `certificate_data` and `signature_metadata`, and returns the complete persisted shape. `get_certificate_by_id(certificate_id)` returns that complete record, including status. Legacy records without a status are exposed as `ACTIVE` and can be revoked.

`revoke_certificate(certificate_id) -> dict[str, Any]` validates the canonical `CERT-` plus 32 lowercase hexadecimal identifier and uses a single atomic MongoDB update to transition `ACTIVE` (or a legacy record with no status) to `REVOKED`. Its update only sets `status`, preserving the certificate data and signature metadata. It returns the revoked record.

The repository raises `InvalidDatabaseOperationError` for malformed IDs, `CertificateNotFoundError` when no record exists, and `CertificateAlreadyRevokedError` for repeated revocation. Database failures are wrapped in `DatabaseOperationError` with a sanitized message. `create_certificate()` retains its existing `DuplicateDataError` behavior. These exceptions are database-layer errors; API callers should map them to appropriate HTTP responses without exposing chained driver details.

M1 and M3 consumers continue using the unchanged issuance and retrieval signatures. The lifecycle status is not included in certificate data or the signed representation. Repository tests are in `backend/tests/database/test_certificate_repository.py` and run with the other DB tests from `backend` using `python -m pytest tests/database`.
