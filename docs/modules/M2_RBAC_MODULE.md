# M2 — Authorization & RBAC Module

## 1. Objective

Build Credence's **authorization and role-based access control (RBAC)** layer.

M2 answers:

> **What is this authenticated user allowed to do?**

M2 works on top of M1 authentication:

```text
Google Workspace
      ↓
M1 — Authentication
      ↓
Authenticated Credence User
      ↓
M2 — Authorization
      ↓
Role + Permissions
```

M2 must not implement authentication or its own JWT system.

---

## 2. Roles

Credence initially has three roles:

```text
STUDENT
ISSUER
ADMIN
```

### STUDENT — Default Role

Every newly authenticated institutional user should initially become:

```text
STUDENT
```

Having an institutional email **does not automatically grant elevated privileges**.

A Student can access functionality intended for their own academic information.

---

### ISSUER — Privileged Role

An `ISSUER` is an **explicitly authorized institutional user** who can perform certificate issuance/signing operations.

Important:

> Not every institutional/KIIT email account is an Issuer.

The user's institutional email only establishes institutional identity through M1. It does not establish Issuer authority.

An Issuer must be explicitly granted the role through the Credence authorization system.

Conceptually:

```text
Institutional User
      ↓
Default: STUDENT
      ↓
ADMIN approval
      ↓
ISSUER
```

Admins should also be able to revoke Issuer access.

---

### ADMIN — Privileged Role

`ADMIN` is reserved for authorized system administrators.

Having an institutional email does **not** automatically make someone an Admin.

The initial Admin must be provisioned through a controlled setup/bootstrap process.

After the system has an authorized Admin, Admins can manage privileged roles according to the defined authorization rules.

---

## 3. Required Structure

```text
backend/
├── app/
│   └── authorization/
│       ├── __init__.py
│       ├── router.py
│       ├── service.py
│       ├── schemas.py
│       ├── dependencies.py
│       └── permissions.py
│
└── tests/
    └── authorization/
        ├── __init__.py
        └── test_authorization.py
```

Do not create a separate FastAPI application.

M2 should use the existing shared FastAPI application and expose functionality through `APIRouter` where required.

---

## 4. File Responsibilities

### `router.py`

Handles authorization-related API endpoints, such as:

- User role information
- Admin role-management operations
- Authorization-related responses

Routes should not contain the main authorization logic.

### `service.py`

Handles authorization business logic, including:

- Role assignment
- Role revocation
- Permission checks
- User authorization decisions
- Privileged role management

Use M4 for persistence where required.

### `schemas.py`

Contains authorization request/response models, such as:

- Role information
- Permission information
- Role update requests
- Authorization responses

### `dependencies.py`

Provides reusable authorization dependencies for protected routes.

Conceptually:

```text
Request
   ↓
M1 Authentication
   ↓
Current User
   ↓
M2 Authorization
   ↓
Required Role/Permission
   ↓
Allow / Deny
```

### `permissions.py`

Defines the roles and permissions used by Credence.

Keep permission definitions centralized so different modules do not create their own authorization rules.

---

## 5. Role Assignment Model

The important distinction is:

```text
Institutional identity ≠ Privileged role
```

The normal flow is:

```text
Google Workspace Login
        ↓
M1 validates identity
        ↓
Credence user created
        ↓
Default role = STUDENT
```

Only controlled authorization operations can change the role:

```text
STUDENT
   ↓
ADMIN explicitly grants
   ↓
ISSUER
```

or:

```text
ISSUER
   ↓
ADMIN revokes
   ↓
STUDENT
```

The same principle applies to Admin accounts.

Do not implement role assignment using hard-coded email addresses.

For example, avoid:

```text
if email == "faculty@institution.edu":
    role = ISSUER
```

Role information should be maintained as application data.

---

## 6. Permission Model

Roles should map to permissions.

A conceptual starting point:

```text
STUDENT
 ├── view own certificate
 └── access own profile

ISSUER
 ├── create certificate
 ├── issue certificate
 └── perform authorized issuer operations

ADMIN
 ├── manage users
 ├── grant/revoke ISSUER
 ├── manage roles
 └── perform authorized administrative operations
```

The exact permission names and mappings can be decided during implementation.

Avoid granting unnecessary permissions.

---

## 7. M1 Integration

M2 must rely on M1 for authentication.

M2 receives the authenticated user from M1:

```text
Request
   ↓
M1 validates Credence JWT
   ↓
Authenticated User
   ↓
M2 checks role/permission
   ↓
Allow / Deny
```

M2 must not:

- Reimplement Google authentication
- Create another JWT system
- Independently authenticate users
- Duplicate M1's authentication dependencies

---

## 8. M4 Integration

M2 should use M4's database/repository layer for user and role persistence.

```text
M2
 ↓
M4 Repository
 ↓
MongoDB
```

M2 must not directly access MongoDB.

If the existing M4 user model needs a role-related field, coordinate with the integration lead before modifying the shared model.

---

## 9. Authorization Requirements

M2 must support:

- Checking a user's role
- Checking permissions
- Protecting endpoints
- Granting/revoking privileged roles
- Rejecting unauthorized requests
- Preventing ordinary users from modifying their own privileges

Authorization must always happen on the backend.

Frontend restrictions such as hiding buttons are **not security controls**.

---

## 10. Example: Issuer Operation

For a certificate issuance operation:

```text
POST /certificates
       ↓
M1: Is user authenticated?
       ↓
      YES
       ↓
M2: Is user an ISSUER?
       ↓
      YES
       ↓
Operation allowed
```

A normal institutional Student:

```text
POST /certificates
       ↓
M1: Authenticated
       ↓
M2: ISSUER?
       ↓
      NO
       ↓
403 Forbidden
```

Therefore, simply possessing an institutional email cannot provide certificate-issuing capability.

---

## 11. Admin Role Management

Admin should be able to manage privileged roles according to the defined system rules.

For example:

```text
ADMIN
  ↓
Select institutional user
  ↓
Grant ISSUER
```

or:

```text
ADMIN
  ↓
Select ISSUER
  ↓
Revoke ISSUER
  ↓
User returns to STUDENT
```

The system should record enough information to determine the current authorization state.

Do not allow:

```text
STUDENT → ADMIN
```

or:

```text
STUDENT → ISSUER
```

through arbitrary client requests.

---

## 12. Initial Admin Provisioning

Because an Admin is required to manage privileged roles, the system needs a controlled way to create the first Admin.

For the initial project version, this may be handled through a **bootstrap/setup process** rather than public registration.

After the first Admin exists:

```text
Initial Admin
      ↓
Manage privileged roles
      ↓
ISSUER / ADMIN management
```

The exact bootstrap mechanism should be agreed with the integration lead.

---

## 13. External Verifiers

External certificate verifiers are **not an M2 role** in the initial version.

They do not need institutional authentication to verify certificates.

```text
External Verifier
       ↓
Public Verification
       ↓
Certificate Result
```

A dedicated `VERIFIER` account can be considered later if Credence requires features such as verification history, organization dashboards, or bulk verification.

---

## 14. Security Requirements

M2 must:

- Perform authorization on the backend.
- Never trust frontend role information.
- Deny access when required authorization information is missing.
- Prevent users from assigning themselves privileged roles.
- Prevent ordinary users from modifying their own role.
- Restrict Issuer privileges to explicitly authorized users.
- Allow privileged role revocation.
- Return appropriate authorization errors.
- Avoid exposing unnecessary permission information.

---

## 15. Testing Requirements

`backend/tests/authorization/test_authorization.py` should cover:

### Role behavior

- New institutional user receives `STUDENT`
- Student permissions
- Issuer permissions
- Admin permissions
- Invalid/unknown role handling

### Issuer authorization

- Student cannot perform Issuer operations
- Authorized Issuer can perform Issuer operations
- Admin can grant Issuer
- Admin can revoke Issuer
- Revoked Issuer can no longer perform Issuer operations

### Admin authorization

- Student cannot perform Admin operations
- Issuer cannot perform Admin operations unless explicitly permitted
- Unauthorized users cannot assign themselves Admin
- Initial Admin provisioning works as designed

### Integration

- M2 correctly consumes the authenticated user from M1.
- M2 uses M4 for persistence.
- Authorization decisions are enforced at the backend/API level.

---

## 16. Module Boundaries

M2 must **not** implement:

- Google authentication
- JWT creation/validation
- Password authentication
- Direct MongoDB access
- Certificate creation
- Certificate signing
- Cryptographic verification
- Certificate verification
- AI analysis

| Module | Responsibility |
|---|---|
| **M1** | Authentication & identity |
| **M2** | Roles & authorization |
| **M3** | Cryptography & signing |
| **M4** | Database & persistence |
| **M5** | Certificate domain & verification |

---

## 17. Documentation & Dependencies

### README

Keep this README updated whenever:

- Roles or permissions change
- Module structure changes
- Authorization endpoints are added
- Shared interfaces change
- Configuration requirements change

The README should reflect the actual implementation when M2 is completed.

### `requirements.txt`

If M2 introduces a new Python dependency:

1. Add it to `backend/requirements.txt`.
2. Use an appropriate version constraint.
3. Ensure it is actually required.
4. Test installation from the requirements file.

Do not rely on packages installed only in a local environment.

---

## 18. Definition of Done

M2 is complete when:

- [ ] `STUDENT`, `ISSUER`, and `ADMIN` roles are defined.
- [ ] New institutional users default to `STUDENT`.
- [ ] `ISSUER` is explicitly granted by an authorized Admin.
- [ ] `ISSUER` access can be revoked.
- [ ] `ADMIN` is controlled through explicit provisioning.
- [ ] Role/permission mapping is implemented.
- [ ] M2 correctly consumes M1's authenticated user.
- [ ] Protected operations enforce required permissions.
- [ ] Unauthorized requests are rejected.
- [ ] Users cannot assign themselves privileged roles.
- [ ] M2 does not implement its own authentication/JWT system.
- [ ] M2 does not directly access MongoDB.
- [ ] Tests cover role and permission behavior.
- [ ] Required dependencies are added to `requirements.txt`.
- [ ] README reflects the final implementation.
- [ ] M2 integrates successfully with M1 and M4.

---

## 19. Implementation Freedom

The developer may choose:

- Exact role/permission implementation
- Permission naming
- Internal service methods
- Dependency implementation
- Role-management API design
- Error-handling structure
- Testing approach

provided the requirements and module boundaries are maintained.

Any change affecting M1, M3, M4, shared models, or shared API contracts must be discussed with the integration lead first.