# Credence --- Team Contributions and Implementation Progress

## 1. Project Overview

**Credence** is an academic certificate issuance and verification system
designed to protect certificate authenticity and integrity.

The system combines Google-based authentication, role-based access
control (RBAC), certificate validation, deterministic canonicalization,
Ed25519 digital signatures, and MongoDB persistence.

-   **Backend:** FastAPI and Python
-   **Frontend:** Next.js
-   **Database:** MongoDB
-   **Cryptography:** SHA-256 and Ed25519

The project uses a modular architecture with separate responsibilities
for authentication, authorization, cryptography, persistence, and
certificate-domain logic.

## 2. Team Contributions

### M1 --- Authentication and Verification API

**Implemented:** - Google identity/token validation and institutional
email checks. - User lookup/creation and Credence JWT authentication. -
Authentication dependencies for protected endpoints. - Public
certificate verification by Certificate ID. - Reconstruction and
canonicalization of the stored certificate before signature
verification. - Verification outcomes: `VALID`, `INVALID`, `REVOKED`,
`NOT_FOUND`, and `UNVERIFIABLE`. - Public certificate-details response
for successfully verified records, subject to the visibility setting. -
Server-side student ID masking. - Verification response handling for
malformed IDs, unavailable infrastructure, and internal errors.

**Verification API:** `GET /certificates/verify/{certificate_id}`

The endpoint is public and does not require login. It verifies the
official record stored in MongoDB; it does not currently inspect an
uploaded PDF or physical certificate.

**Configuration:** - `VERIFICATION_SHOW_DETAILS` controls whether public
certificate details are returned. - `VERIFICATION_RATE_LIMIT_PER_MINUTE`
configures the per-IP request limit. - `VERIFICATION_PROXY_SECRET`
authenticates trusted client-IP forwarding from the frontend proxy.

**Remaining validation:** - Confirm verification uses exactly the same
canonicalization process as issuance. - Test all verification outcomes
against persisted records. - Test key-unavailable, database-unavailable,
and malformed-record cases. - Confirm trusted proxy IP handling cannot
be spoofed.

### M2 --- Authorization, RBAC, and Frontend

**Implemented:** - Role-based access control for `STUDENT`, `ISSUER`,
and `ADMIN`. - New users default to `STUDENT`. - Issuer privileges
require explicit administrative authorization. - Backend authorization
checks for protected operations. - Admin RBAC frontend page for
role-management workflows. - Public certificate verification frontend. -
Manual verification entry page at `/verify`. - Direct result route at
`/verify/{certificate_id}`, which automatically verifies the supplied
ID. - Verification result handling for valid, invalid, revoked,
not-found, and unavailable outcomes. - Official certificate details
display when the backend makes them available. - Comparison guidance
explaining that the verifier should compare the presented certificate
with the official record. - Loading, retry, and error states for
verification requests.

**Remaining validation:** - Test role assignment and revocation through
the complete frontend-to-backend flow. - Confirm every protected
issuer/admin action is enforced by the backend. - Test all verification
result and error states on desktop and mobile.

### M3 --- Cryptography and Digital Signatures

**Implemented:** - SHA-256 hashing. - Ed25519 digital-signature
generation and verification. - Signing-key loading and validation. -
Public-key access and signing-key identification through a configured
key ID. - Controlled handling of cryptographic errors. - Integration
with certificate issuance and verification.

The cryptography module receives canonical certificate bytes from the
certificate-domain layer. It does not define certificate schemas or
decide user permissions.

**Remaining validation:** - Test valid signatures against persisted
certificate records. - Confirm modifications to signed certificate data
cause verification failure. - Validate key ID handling and public-key
selection. - Review key rotation and production key protection.

### M4 --- Database and Persistence

**Implemented:** - MongoDB connection management. - User creation and
lookup. - Google identity (`google_sub`) storage and email
normalization. - Persistent user roles and role update/lookups. -
Certificate persistence and retrieval through repository interfaces. -
Unique certificate ID enforcement. - Certificate lifecycle status and
revocation support.

Certificate records separate certificate data from signature metadata.
The certificate data includes the certificate ID, student information,
institution, degree, field of study, graduation date, issue date, and
schema version. Signature metadata includes the signature, key ID, and
algorithm.

**Remaining validation:** - Verify index initialization during
application startup. - Test duplicate certificate ID handling. - Test
issuance, retrieval, and revocation against persisted records. - Confirm
persistence failures cannot result in a successful issuance response.

### M5 --- Certificate Domain, Issuance, and Canonicalization

**Implemented:** - Academic certificate domain model and validation. -
Certificate ID generation and validation. - Deterministic
canonicalization into UTF-8 JSON bytes. - Signing integration with M3. -
Persistence integration with M4. - Certificate issuance and retrieval. -
Integration with the public verification workflow.

The certificate model includes: - Certificate ID - Student ID and name -
Institution - Degree - Field of study - Graduation date - Issue date -
Schema version

The certificate is validated and canonicalized before signing. The
resulting signature and certificate data are persisted through the
repository layer.

**Remaining validation:** - Test issuance-to-verification consistency. -
Test tampering of each signed field. - Confirm schema-version
compatibility and validation behaviour.

## 3. Frontend Implementation

The Next.js frontend currently provides: - Google authentication. -
Role-aware application access. - Certificate creation for authorized
issuers. - Issued certificate viewing. - Admin RBAC and role-management
interface. - Public certificate verification by ID. - Automatic
verification when opening `/verify/{certificate_id}`. - Verification
status and official certificate-details display when enabled. - Guidance
to compare the presented certificate with the official record.

The frontend does not independently authorize users, sign certificates,
or access MongoDB. Authorization and cryptographic verification remain
backend responsibilities.

## 4. Public Verification Behaviour

The public verification endpoint checks the certificate record stored in
Credence's database.

  -----------------------------------------------------------------------
  Outcome                             Meaning
  ----------------------------------- -----------------------------------
  `VALID`                             Signature is valid and the
                                      certificate is active.

  `INVALID`                           Signature verification failed.

  `REVOKED`                           Signature is valid, but the
                                      certificate has been revoked.

  `NOT_FOUND`                         No certificate exists for the
                                      supplied ID.

  `UNVERIFIABLE`                      Verification could not be completed
                                      because of a key or infrastructure
                                      issue.
  -----------------------------------------------------------------------

For `VALID` and `REVOKED` records, the backend can return selected
official certificate details when `VERIFICATION_SHOW_DETAILS=true`.
Student ID masking is performed on the server. Details are not returned
for invalid, missing, or unverifiable records.

The verification page distinguishes signature validity from certificate
lifecycle status. A revoked certificate may have a valid signature but
must not be presented as currently valid.

**Important limitation:** ID-based verification validates the official
database record. It does not automatically verify the contents of an
uploaded PDF or printed certificate. The verifier must compare the
document they received against the official details shown by Credence.
Automated PDF-content verification is not yet implemented.

## 5. Verification Security Controls

Implemented/configured controls include: - Configurable per-IP request
limiting for the public verification endpoint. - HTTP `429` responses
when the configured limit is exceeded. - `Retry-After` support. -
Shared-secret authentication for trusted client-IP forwarding from the
frontend proxy. - Server-side student ID masking. - Configurable public
certificate-detail visibility. - `Cache-Control: no-store` for
verification responses.

The current in-memory rate limiter is suitable for a single-process demo
environment. It is not a distributed rate limiter and resets when the
process restarts. A production deployment should use a shared gateway or
distributed store such as Redis.

Public certificate-detail visibility should remain disabled until the
institution approves disclosure of student information.

## 6. End-to-End Architecture

### Certificate issuance

1.  The user authenticates through Google.
2.  The backend validates identity and institutional requirements.
3.  M2 checks whether the user has issuer permissions.
4.  M5 validates and canonicalizes the certificate.
5.  M3 signs the canonical bytes using Ed25519.
6.  M4 persists the certificate and signature metadata in MongoDB.
7.  The frontend displays the issued certificate.

### Certificate verification

1.  A third party enters a Certificate ID or opens a direct verification
    link.
2.  The backend retrieves the official certificate record from MongoDB.
3.  The stored certificate is reconstructed and canonicalized.
4.  M3 verifies the signature using the appropriate trusted public key.
5.  The backend checks the certificate lifecycle status.
6.  The API returns the verification outcome and, when enabled, verified
    certificate details.
7.  The verifier compares the presented document with the official
    record.

## 7. Current Project Status

The team has implemented the core authentication, RBAC, certificate
issuance, digital signing, MongoDB persistence, certificate lifecycle
management, public ID-based verification, verification middleware, and
corresponding frontend interfaces.

The public verification page displays official certificate details when
public detail visibility is enabled. The admin RBAC interface is also
implemented.

**Implementation status does not by itself establish that every security
and failure case has passed testing.** End-to-end, tampering,
authorization, proxy-trust, rate-limit, and privacy checks remain part
of final validation.

## 8. Remaining Work and Next Phase

### Priority 1 --- End-to-End and Security Validation

-   Issue a certificate as an authorized issuer.
-   Confirm students and unauthenticated users cannot issue
    certificates.
-   Confirm the record is persisted and can be retrieved by ID.
-   Verify the signature against persisted canonical certificate data.
-   Modify each signed field and confirm verification fails.
-   Test revoked, missing, malformed, and unverifiable certificate
    cases.
-   Test rate limiting and trusted proxy IP handling.

### Priority 2 --- Deployment and Privacy Readiness

-   Confirm institutional approval before enabling public certificate
    details.
-   Review which student fields may be disclosed publicly.
-   Keep private keys, proxy secrets, and environment files out of
    source control.
-   Confirm production configuration and error handling.

### Priority 3 --- Future Enhancements

-   QR-code-based access to the public verification result page.
-   Automated PDF/document-content verification.
-   Stronger audit logging and production key-management procedures.
-   Distributed rate limiting for multi-instance deployments.

## 9. Development Principles

-   Use the shared FastAPI application.
-   Keep authentication, authorization, cryptography, certificate-domain
    logic, and persistence separated by responsibility.
-   Use repository interfaces for database operations.
-   Enforce authorization on the backend.
-   Verify signatures against canonical certificate bytes, not formatted
    frontend output.
-   Never commit private keys, `.env` files, or proxy secrets.
-   Keep API contracts, tests, and documentation aligned with the
    implementation.
-   Distinguish implemented functionality from functionality that has
    passed end-to-end validation.
