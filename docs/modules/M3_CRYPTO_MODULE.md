# M3 — Cryptography & Digital Signing Module

## 1. Objective

Build Credence's core **cryptography and digital signing layer**.

M3 is responsible for securely signing trusted certificate data and managing the cryptographic keys required for signing.

Conceptually:

Certificate Data
      ↓
Canonical Data / Hash
      ↓
M3 Cryptography
      ↓
Digital Signature
      ↓
Signed Certificate Data

M3 provides cryptographic operations to other modules. It does not decide who is allowed to issue certificates — that is handled by M2.

---

## 2. Scope

M3 should provide the cryptographic foundation required for certificate issuance.

Main responsibilities:

- Digital signature generation
- Signature verification primitive
- Cryptographic hashing
- Signing key loading/handling
- Public key access
- Key identification/versioning
- Safe cryptographic error handling

Full certificate verification workflows will be implemented later.

M3 may provide the low-level `verify_signature()` primitive now, but must not implement the complete certificate verification process.

---

## 3. Required Structure

```text
backend/
├── app/
│   └── crypto/
│       ├── __init__.py
│       ├── service.py
│       ├── keys.py
│       ├── hashing.py
│       ├── signatures.py
│       └── exceptions.py
│
└── tests/
    └── crypto/
        ├── __init__.py
        └── test_crypto.py
```

M3 is primarily a service module and does not need its own API router unless an actual project requirement later requires one.

Other backend modules should call M3's service interface.

---

## 4. File Responsibilities

### `service.py`

Provides the main cryptographic interface used by other modules.

It should coordinate operations such as:

```text
Data
 ↓
Hash / Prepare
 ↓
Sign
 ↓
Signature Result
```

Other modules should not need to know the internal cryptographic implementation.

---

### `keys.py`

Responsible for signing-key handling.

Responsibilities may include:

- Loading the private signing key
- Loading/exposing the corresponding public key
- Key identifiers
- Key version information
- Validating key availability

Private signing keys must never be exposed through API responses or logs.

Keys must not be committed to Git.

---

### `hashing.py`

Contains cryptographic hashing operations required by the system.

Use secure cryptographic hash algorithms.

Do not implement custom hashing algorithms.

---

### `signatures.py`

Contains the low-level digital-signature operations.

Responsibilities:

- Sign trusted bytes/data
- Verify signatures
- Encode/decode signatures where required

Do not implement custom cryptographic algorithms.

Use established cryptographic libraries.

---

### `exceptions.py`

Contains controlled M3 exceptions such as:

- Signing failure
- Invalid key
- Missing key
- Invalid signature
- Cryptographic operation failure

Internal cryptographic details should not be unnecessarily exposed to clients.

---

## 5. Signing Flow

The intended flow is:

```text
Authorized certificate operation
          ↓
M2 Authorization
          ↓
Certificate data
          ↓
Canonical representation
          ↓
M3
   ├── hash
   └── sign
          ↓
Digital Signature
```

M3 performs the cryptographic operation.

M3 does **not** decide whether the requesting user is an Issuer.

---

## 6. Canonicalization Boundary

Digital signatures must operate on a deterministic representation of certificate data.

Conceptually:

```text
Certificate
     ↓
Canonical Serialization
     ↓
Same bytes every time
     ↓
M3 signs those bytes
```

M5 owns the certificate/domain representation and canonicalization rules.

M3 should accept the canonical bytes/data supplied through the agreed interface rather than inventing its own certificate format.

M3 may provide hashing/signing utilities, but certificate-specific serialization belongs to M5.

---

## 7. Digital Signatures

Use an established, secure digital-signature scheme provided by a trusted cryptographic library.

The implementation must support:

```text
Private Key
    +
Canonical Data
    ↓
Signature
```

and the corresponding primitive:

```text
Public Key
    +
Canonical Data
    +
Signature
    ↓
Valid / Invalid
```

The developer may select the exact supported algorithm/library, but the choice should be documented and reviewed with the integration lead before it becomes a shared certificate format dependency.

Do not design a custom signature algorithm.

---

## 8. Key Management

The private signing key is one of the most sensitive assets in Credence.

M3 must ensure:

- Private keys are never committed to Git.
- Private keys are never returned through API responses.
- Private keys are never logged.
- Key paths/configuration are not hard-coded.
- Key configuration comes from environment/configuration.
- Missing or invalid keys fail safely.

Example configuration may include:

```env
SIGNING_PRIVATE_KEY_PATH=...
SIGNING_PUBLIC_KEY_PATH=...
SIGNING_KEY_ID=...
```

Do not place actual keys inside `.env`.

`.env` should contain configuration such as paths or identifiers, not private-key contents.

---

## 9. Key Identification

Signatures should be associated with a key identifier where appropriate.

Conceptually:

```text
Signature
├── signature value
├── key_id
└── algorithm/version information
```

This allows Credence to identify which trusted public key should later be used for verification and supports future key rotation.

The exact representation should be coordinated with M5 before becoming part of the certificate schema.

---

## 10. Hashing

M3 should provide secure hashing functionality required by certificate integrity/signing.

Use established cryptographic hash functions such as SHA-256 or another reviewed secure choice.

Conceptually:

```text
Canonical Certificate Data
          ↓
Cryptographic Hash
          ↓
Fixed Integrity Digest
```

Do not use weak algorithms such as MD5 or SHA-1 for certificate integrity.

---

## 11. M2 Integration

M2 owns authorization.

M3 should never assume:

```text
User called signing function
        =
User is authorized
```

The application flow must enforce authorization before protected signing operations are reached.

```text
Authenticated User
       ↓
M2
       ↓
ISSUER permission
       ↓
Certificate operation
       ↓
M3 signing
```

M3 itself remains focused on cryptographic operations.

---

## 12. M5 Integration

M5 will eventually provide the certificate data that M3 signs.

Expected relationship:

```text
M5 Certificate Domain
        ↓
Canonical Data
        ↓
M3
        ↓
Signature
```

Later verification will use:

```text
Certificate
    ↓
M5 canonicalization
    ↓
M3 signature verification primitive
    ↓
Cryptographic result
```

M3 must not duplicate M5's certificate models or canonicalization logic.

---

## 13. Security Requirements

M3 must:

- Use established cryptographic libraries.
- Never implement custom cryptographic algorithms.
- Protect private signing keys.
- Never log private keys or sensitive key material.
- Never expose private keys through APIs.
- Use secure cryptographic randomness where required.
- Reject malformed keys/signatures safely.
- Use deterministic certificate input supplied through the agreed canonicalization interface.
- Avoid leaking unnecessary internal cryptographic errors.
- Keep secrets/key material outside source control.

---

## 14. Testing Requirements

`tests/crypto/test_crypto.py` should cover at minimum:

### Hashing

- Same input produces the same hash
- Modified input produces a different hash
- Invalid input is handled correctly

### Signing

- Valid data can be signed
- Signature is produced successfully
- Modified data does not validate against the original signature
- Invalid signatures are rejected

### Keys

- Valid keys can be loaded
- Missing key is handled safely
- Invalid key is rejected
- Public/private key pairing works correctly

### Security

- Private key material is not returned by public service methods
- Cryptographic errors are controlled
- Key configuration is not hard-coded

---

## 15. Module Boundaries

M3 must NOT implement:

- Google authentication
- JWT authentication
- RBAC or role management
- User management
- Direct MongoDB access unless a later approved key-storage design requires persistence
- Certificate business logic
- Certificate-specific canonicalization
- Complete certificate verification workflows
- AI analysis

| Module | Responsibility |
|---|---|
| M1 | Authentication & identity |
| M2 | Roles & authorization |
| M3 | Cryptography, signing & keys |
| M4 | Database & persistence |
| M5 | Certificate domain, integrity & verification |

---

## 16. Cross-Module Changes

If M3 requires a **small change** in another existing module to integrate correctly, the M3 developer may implement that change within the same branch.

Examples:

- Adding a small shared interface
- Adding a required field
- Extending an existing repository/service
- Minor configuration changes

The developer must update affected tests and documentation.

If the required change is large, changes another module's architecture significantly, affects multiple modules, or may break existing contracts, **contact the integration lead before implementing it**.

Do not redesign another member's module independently.

---

## 17. Documentation & Dependencies

Keep this README updated as implementation changes.

If M3 introduces cryptographic libraries or other Python dependencies:

1. Add them to `backend/requirements.txt`.
2. Use appropriate version constraints.
3. Do not rely on locally installed packages.
4. Verify installation from `requirements.txt`.

If setup changes, also update the short `backend/README.md`.

Never commit private keys, signing secrets, or sensitive test credentials.

---

## 18. Definition of Done

M3 is complete when:

- [ ] Secure hashing is implemented.
- [ ] Digital signing is implemented.
- [ ] Signature verification primitive is implemented.
- [ ] Signing/public keys are handled safely.
- [ ] Private keys are outside source control.
- [ ] Key identification/version information is supported where required.
- [ ] M3 exposes a clean interface for M5.
- [ ] M3 does not implement certificate-specific canonicalization.
- [ ] M3 does not implement authorization.
- [ ] Invalid keys/signatures fail safely.
- [ ] Crypto tests pass.
- [ ] Existing backend tests still pass.
- [ ] Dependencies are updated.
- [ ] README reflects the final implementation.
- [ ] No secrets/private keys are committed.

---

## 19. Implementation Freedom

The M3 developer may choose:

- Internal cryptographic service structure
- Helper functions
- Key-loading implementation
- Signature encoding
- Testing approach

The cryptographic algorithm/library choice should be documented and reviewed with the integration lead because M5 and future verification will depend on it.

Implementation must use established cryptographic libraries rather than custom cryptographic algorithms.