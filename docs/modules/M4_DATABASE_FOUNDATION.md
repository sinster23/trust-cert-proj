# M4 — Database Foundation

**Project:** Credence  
**Phase:** Phase 1 — Secure Certificate Issuance Foundation  
**Module:** M4 — Database Foundation  
**Current Milestone:** Shared Database Foundation

---

## 1. Objective

M4 is responsible for creating the **shared database foundation** for Credence.

The module will provide secure and reusable database access that other modules can use without directly interacting with MongoDB.

The first requirement is to support the **User entity**, because the Authentication module (M1) will depend on persistent user data.

The database architecture should also be structured so that future Credence entities such as certificates, audit records, and revocation information can be added without restructuring the entire database layer.

---

# 2. Current Scope

For this milestone, M4 is responsible for:

- MongoDB connectivity
- Database configuration
- Database lifecycle management
- User data model
- User persistence
- User retrieval
- Required database constraints/indexes
- Database error handling
- Database security foundation
- Database testing
- Providing the persistence interface required by M1

### Important

This is **only the database foundation**.

Certificate creation and certificate-related database functionality will be introduced later.

---

# 3. Technology

The project uses:

- **Python**
- **FastAPI**
- **MongoDB**
- **PyMongo Async**

The database should be accessed asynchronously because the Credence backend is asynchronous.

The member is free to decide the internal implementation approach and supporting utilities as long as the requirements and module boundaries defined in this document are maintained.

---

# 4. Required Folder and File Structure

The following structure is the **required location for M4 files**.

Do not randomly create additional top-level folders or move module files to other locations.

```text
credence/
│
├── backend/
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   │
│   │   └── database/
│   │       ├── __init__.py
│   │       ├── connection.py
│   │       ├── exceptions.py
│   │       │
│   │       ├── models/
│   │       │   ├── __init__.py
│   │       │   └── user.py
│   │       │
│   │       └── repositories/
│   │           ├── __init__.py
│   │           └── user_repository.py
│   │
│   └── tests/
│       └── database/
│           ├── __init__.py
│           └── test_user_repository.py
│
└── docs/
    └── modules/
        └── M4_DATABASE_FOUNDATION.md
```

### Existing shared files

M4 may need to work with existing shared backend files such as:

```text
backend/
├── requirements.txt
└── .env.example
```

These are **shared project files**, not M4-owned files.

If a change to a shared file is required, coordinate it with the integration lead.

---

# 5. Purpose of Each M4 File

### `database/connection.py`

Responsible for:

- MongoDB connection management
- Database access
- Connection lifecycle
- Database connectivity handling

It should provide whatever shared database access mechanism the other modules need.

---

### `database/exceptions.py`

Responsible for database-layer exceptions.

Examples of situations that may need controlled handling:

- Database unavailable
- Duplicate data
- Invalid database operation
- Unexpected database failure

The exact exception design is left to the member.

---

### `database/models/user.py`

Responsible for the database representation of a Credence user.

The initial user data should support:

```text
id
email
password_hash
is_active
created_at
updated_at
```

Additional fields should not be added unless required by the agreed architecture.

**Do not add roles or permissions here yet.**

Those belong to M2.

---

### `database/repositories/user_repository.py`

Responsible for providing the persistence operations required by M1.

At minimum, the repository must support:

```text
Create user
Find user by email
Find user by ID
```

The repository should hide MongoDB-specific operations from M1.

---

### `tests/database/test_user_repository.py`

Contains tests for the M4 user persistence functionality.

The member may organize the tests internally as required, but all M4 database behavior must be adequately tested here.

---

# 6. User Data Requirements

The initial User entity must contain enough information for M1 Authentication to operate.

Required information:

| Field | Requirement |
|---|---|
| ID | Unique user identifier |
| Email | Required and unique |
| Password hash | Required |
| Active status | Required |
| Created timestamp | Required |
| Updated timestamp | Required |

### Password requirement

M4 receives and stores a **password hash**.

M4 does **not** handle:

- Password hashing
- Password verification
- Plaintext passwords

The database must never intentionally store a plaintext user password.

---

# 7. Required Database Functionality

M4 must provide functionality equivalent to the following capabilities.

### Create User

The database layer must allow M1 to persist a new user.

It should:

- Store the required user information.
- Enforce email uniqueness.
- Return enough information to identify the created user.
- Handle persistence failures appropriately.

### Find User by Email

The database layer must allow M1 to retrieve a user using their email.

It should:

- Return the matching user when one exists.
- Return an appropriate not-found result when one does not exist.
- Apply consistent email normalization.

### Find User by ID

The database layer must allow M1 to retrieve a user using their identifier.

It should:

- Return the matching user when one exists.
- Handle invalid identifiers safely.
- Return an appropriate not-found result when one does not exist.

The exact function/class names may be chosen by the member **unless an interface is later frozen by the integration lead**.

---

# 8. Database Constraints

The database must enforce appropriate constraints.

### Email uniqueness

Two users must not be able to have the same normalized email.

This must be enforced at the **database level**, not only through application logic.

### Required fields

Required user information should not be silently omitted.

### Consistent timestamps

Creation and update timestamps should be maintained consistently.

---

# 9. Configuration and Secrets

Database configuration must not be hardcoded.

The implementation should use environment-based configuration.

The project should provide an example configuration showing the required variables without exposing real credentials.

For example:

```text
MONGODB_URI
MONGODB_DATABASE
```

The actual values must remain outside Git.

Never commit:

```text
MongoDB passwords
Atlas credentials
Connection strings containing secrets
API keys
Private keys
Production credentials
```

---

# 10. Security Requirements

M4 must establish a secure database foundation.

### Backend-only database access

The architecture must remain:

```text
Frontend
    ↓
FastAPI Backend
    ↓
Database Layer
    ↓
MongoDB
```

The frontend must **never connect directly to MongoDB**.

### Credential protection

Database credentials must be externalized and protected.

### Password protection

Only password hashes may be persisted.

### Error protection

Raw database errors containing sensitive implementation details must not be exposed to users.

### Database access control

The MongoDB environment should use appropriate access restrictions and credentials rather than unrestricted database access.

### Test isolation

Automated tests must not accidentally operate on the team's shared development data.

---

# 11. Interface With M1

M1 Authentication will depend on M4.

The intended relationship is:

```text
M1 Authentication
        │
        │ User persistence operations
        ▼
M4 Database Layer
        │
        ▼
     MongoDB
```

M1 should not need to know:

- MongoDB query syntax
- Collection implementation
- Database connection details
- Database lifecycle management
- MongoDB-specific error handling

M4 provides the persistence boundary.

---

# 12. Module Boundaries

### M4 owns

```text
Database
├── Connection
├── Persistence
├── User storage
├── User retrieval
├── Database constraints
├── Database errors
└── Database tests
```

### M4 does NOT own

```text
Authentication
JWT
Password hashing
Password verification
RBAC
Permissions
Digital signatures
Cryptographic keys
Certificate creation
Certificate verification
AI analysis
Frontend
```

These responsibilities belong to other modules or later milestones.

---

# 13. Required Tests

M4 must provide tests demonstrating that its functionality works.

At minimum, test:

### Connection

- Successful database connection
- Appropriate handling of connection failure

### User creation

- User can be created
- Required information is persisted
- Password hash is stored
- Plaintext password is not stored
- Duplicate email is rejected

### User retrieval

- User can be retrieved by email
- User can be retrieved by ID
- Nonexistent user is handled correctly
- Invalid user ID is handled safely

### Data consistency

- Email normalization is consistent
- Email uniqueness is maintained
- Timestamps are handled correctly

### Error handling

- Database failures are handled appropriately
- Sensitive database information is not exposed

### Test isolation

- Tests operate against an isolated test environment/database
- Tests do not modify shared development data

Additional tests are encouraged where they improve reliability or security.

---

# 14. Integration Requirements

Before M4 is submitted for integration:

- The module must work independently.
- All required tests must pass.
- The database interface must be documented.
- M1 must be able to consume the database functionality without accessing MongoDB directly.
- Configuration requirements must be documented.
- No secrets may be present in the repository.
- M4 must not introduce unnecessary changes outside its assigned scope.

The integration lead will review and test the module before merging it into the main branch.

---

# 15. Future Compatibility

Credence will eventually require database support for additional functionality such as:

```text
Certificates
Certificate status
Revocation
Audit records
Issuer information
Verification records
```

M4 should therefore establish a database structure that can be extended later.

However:

> **Do not implement future certificate/verification functionality as part of this assignment.**

We will introduce those requirements when their respective modules are started.

---

# 16. Implementation Freedom

This document defines **what M4 must provide**, not how the member must implement it.

The member is free to decide:

- Internal class/function organization
- Repository implementation approach
- Internal validation strategy
- Error-handling structure
- Supporting helper functions
- Test organization
- Internal database abstractions

The member must, however, maintain the required folder structure and provide the functionality and behavior defined in this document.

If an implementation decision affects another module's contract or requires changing the agreed architecture, discuss it with the integration lead before making the change.

---

# 17. Definition of Done

M4 is considered complete when:

- [ ] Required folder/file structure is maintained.
- [ ] MongoDB connectivity works.
- [ ] Database configuration is externalized.
- [ ] User persistence works.
- [ ] User retrieval by email works.
- [ ] User retrieval by ID works.
- [ ] Email uniqueness is enforced.
- [ ] Password hashes can be stored securely.
- [ ] Plaintext passwords are not stored.
- [ ] Database errors are handled appropriately.
- [ ] Required tests are implemented and passing.
- [ ] Tests use an isolated database/environment.
- [ ] No credentials or secrets are committed.
- [ ] M1 can consume the database functionality.
- [ ] Documentation is complete.
- [ ] Pull request is submitted for integration review.

---

## Final Principle

**M4 defines the database boundary for Credence.**

The member has freedom over the internal implementation, but the rest of the team should be able to rely on a predictable database layer without needing to understand or modify its internal workings.
