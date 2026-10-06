"""M2 tests: roles, permissions, role management, API enforcement.

The M4 role methods do not exist yet, so a small in-memory FakeRepo stands in
for them. Authentication uses M1's REAL JWT code (tokens are signed with test
settings), so these tests also check that M2 consumes M1 correctly.

Run from backend/:  python -m pytest tests/authorization -v
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_settings, get_user_repository
from app.auth.security import AuthSettings, create_access_token
from app.authorization.dependencies import require_permission, require_role
from app.authorization.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    has_permission,
    parse_role,
    permissions_of,
    role_of,
)
from app.authorization.router import router as authorization_router
from app.authorization.service import (
    AuthorizationService,
    BootstrapNotAllowedError,
    InvalidRoleChangeError,
    PermissionDeniedError,
    TargetUserNotFoundError,
)
from app.database.exceptions import DatabaseOperationError, UserNotFoundError
from app.database.models.user import User

SETTINGS = AuthSettings(
    google_client_id="test-client-id",
    google_allowed_domain="institute.edu",
    jwt_secret="x" * 40,
)


# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FakeUser:
    email: str
    role: str | None = "STUDENT"
    is_active: bool = True
    id: UUID = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.id is None:
            object.__setattr__(self, "id", uuid4())


class FakeRepo:
    """In-memory stand-in for M1/M4's UserRepository role methods."""

    def __init__(self, *users: FakeUser) -> None:
        self.users = {u.id: u for u in users}
        self.fail = False

    def _check(self) -> None:
        if self.fail:
            raise DatabaseOperationError("boom")

    async def find_by_id(self, user_id):
        self._check()
        try:
            return self.users[user_id if isinstance(user_id, UUID) else UUID(str(user_id))]
        except KeyError:
            raise UserNotFoundError("User was not found")

    async def find_by_email(self, email):
        self._check()
        for u in self.users.values():
            if u.email == email:
                return u
        raise UserNotFoundError("User was not found")

    async def update_role(self, user_id, role):
        self._check()
        user = await self.find_by_id(user_id)
        updated = replace(user, role=role)
        self.users[updated.id] = updated
        return updated

    async def list_users(self, *, role=None, skip=0, limit=50):
        self._check()
        found = [u for u in self.users.values() if role is None or u.role == role]
        return found[skip : skip + limit]

    async def count_by_role(self, role):
        self._check()
        return sum(1 for u in self.users.values() if u.role == role)


def run(coro):
    return asyncio.run(coro)


def student(**kw):
    return FakeUser(email=kw.pop("email", "s@institute.edu"), role="STUDENT", **kw)


def issuer(**kw):
    return FakeUser(email=kw.pop("email", "i@institute.edu"), role="ISSUER", **kw)


def admin(**kw):
    return FakeUser(email=kw.pop("email", "a@institute.edu"), role="ADMIN", **kw)


# --------------------------------------------------------------------------- #
# API fixture: real M1 JWT auth + M2 router + a probe route for issuing
# --------------------------------------------------------------------------- #
def make_client(repo: FakeRepo) -> TestClient:
    app = FastAPI()
    app.include_router(authorization_router)

    @app.post("/probe/issue")
    async def probe_issue(user=Depends(require_permission(Permission.CERTIFICATE_ISSUE))):
        return {"ok": True}

    @app.get("/probe/admin-only")
    async def probe_admin(user=Depends(require_role(Role.ADMIN))):
        return {"ok": True}

    app.dependency_overrides[get_user_repository] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    return TestClient(app)


def auth(user: FakeUser) -> dict[str, str]:
    token, _ = create_access_token(str(user.id), SETTINGS)
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Role behaviour
# --------------------------------------------------------------------------- #
class TestRoles:
    def test_new_m4_user_without_role_field_is_student(self):
        user = User(email="new@institute.edu", google_sub="sub-1")
        assert role_of(user) == Role.STUDENT

    def test_student_permissions(self):
        assert permissions_of(student()) == {
            Permission.PROFILE_READ_OWN,
            Permission.CERTIFICATE_VIEW_OWN,
        }

    def test_issuer_permissions(self):
        p = permissions_of(issuer())
        assert Permission.CERTIFICATE_ISSUE in p and Permission.CERTIFICATE_CREATE in p
        assert Permission.ISSUER_MANAGE not in p and Permission.ADMIN_MANAGE not in p

    def test_admin_permissions(self):
        p = permissions_of(admin())
        assert {Permission.USER_LIST, Permission.ISSUER_MANAGE, Permission.ADMIN_MANAGE} <= p
        assert Permission.CERTIFICATE_ISSUE not in p  # least privilege

    @pytest.mark.parametrize("bad", ["admin", "SUPERUSER", "", None, 5, ["ADMIN"]])
    def test_unknown_role_gets_no_permissions(self, bad):
        user = FakeUser(email="x@institute.edu", role=bad)
        assert role_of(user) is None
        assert permissions_of(user) == frozenset()
        assert not has_permission(user, Permission.PROFILE_READ_OWN)

    def test_parse_role_is_exact(self):
        assert parse_role("ADMIN") == Role.ADMIN
        assert parse_role("admin") is None
        assert parse_role(None) is None

    def test_permission_map_is_read_only(self):
        with pytest.raises(TypeError):
            ROLE_PERMISSIONS[Role.STUDENT] = frozenset()  # type: ignore[index]


# --------------------------------------------------------------------------- #
# Service: role changes
# --------------------------------------------------------------------------- #
class TestRoleChangeService:
    def test_admin_grants_issuer(self):
        a, s = admin(), student()
        svc = AuthorizationService(FakeRepo(a, s))
        assert run(svc.change_role(a, s.id, Role.ISSUER)).role == "ISSUER"

    def test_admin_revokes_issuer(self):
        a, i = admin(), issuer()
        repo = FakeRepo(a, i)
        updated = run(AuthorizationService(repo).change_role(a, i.id, Role.STUDENT))
        assert updated.role == "STUDENT"

    def test_student_cannot_change_roles(self):
        s, t = student(), student(email="t@institute.edu")
        with pytest.raises(PermissionDeniedError):
            run(AuthorizationService(FakeRepo(s, t)).change_role(s, t.id, Role.ISSUER))

    def test_issuer_cannot_change_roles(self):
        i, t = issuer(), student(email="t@institute.edu")
        with pytest.raises(PermissionDeniedError):
            run(AuthorizationService(FakeRepo(i, t)).change_role(i, t.id, Role.ISSUER))

    @pytest.mark.parametrize("new", [Role.ADMIN, Role.ISSUER, Role.STUDENT])
    def test_nobody_changes_own_role(self, new):
        a, other = admin(), admin(email="b@institute.edu")
        with pytest.raises(PermissionDeniedError):
            run(AuthorizationService(FakeRepo(a, other)).change_role(a, a.id, new))

    def test_unprivileged_caller_learns_nothing_about_targets(self):
        s = student()
        with pytest.raises(PermissionDeniedError):  # 403, not 404
            run(AuthorizationService(FakeRepo(s)).change_role(s, uuid4(), Role.ISSUER))

    def test_unknown_target(self):
        a = admin()
        with pytest.raises(TargetUserNotFoundError):
            run(AuthorizationService(FakeRepo(a)).change_role(a, uuid4(), Role.ISSUER))

    def test_noop_change_rejected(self):
        a, i = admin(), issuer()
        with pytest.raises(InvalidRoleChangeError):
            run(AuthorizationService(FakeRepo(a, i)).change_role(a, i.id, Role.ISSUER))

    def test_cannot_grant_privileged_role_to_inactive_user(self):
        a, s = admin(), student(is_active=False)
        with pytest.raises(InvalidRoleChangeError):
            run(AuthorizationService(FakeRepo(a, s)).change_role(a, s.id, Role.ISSUER))

    def test_admin_can_demote_another_admin_when_two_exist(self):
        a, b = admin(), admin(email="b@institute.edu")
        updated = run(AuthorizationService(FakeRepo(a, b)).change_role(a, b.id, Role.STUDENT))
        assert updated.role == "STUDENT"

    def test_last_admin_cannot_be_demoted(self):
        only = admin(email="only@institute.edu")
        repo = FakeRepo(only)
        # The acting admin is not stored (e.g. stale record), so `only` is the sole admin.
        actor = admin(email="actor@institute.edu")
        with pytest.raises(InvalidRoleChangeError):
            run(AuthorizationService(repo).change_role(actor, only.id, Role.STUDENT))
        assert repo.users[only.id].role == "ADMIN"

    def test_corrupt_stored_role_can_only_be_repaired_by_admin(self):
        a, bad = admin(), FakeUser(email="x@institute.edu", role="WAT")
        updated = run(AuthorizationService(FakeRepo(a, bad)).change_role(a, bad.id, Role.STUDENT))
        assert updated.role == "STUDENT"

    def test_database_failure_is_reported_safely(self):
        a, s = admin(), student()
        repo = FakeRepo(a, s)
        repo.fail = True
        from app.authorization.service import AuthorizationUnavailableError

        with pytest.raises(AuthorizationUnavailableError):
            run(AuthorizationService(repo).change_role(a, s.id, Role.ISSUER))


# --------------------------------------------------------------------------- #
# Service: bootstrap
# --------------------------------------------------------------------------- #
class TestBootstrap:
    def test_first_admin_provisioned(self):
        s = student(email="first@institute.edu")
        updated = run(AuthorizationService(FakeRepo(s)).bootstrap_admin("first@institute.edu"))
        assert updated.role == "ADMIN"

    def test_refused_once_an_admin_exists(self):
        a, s = admin(), student(email="later@institute.edu")
        with pytest.raises(BootstrapNotAllowedError):
            run(AuthorizationService(FakeRepo(a, s)).bootstrap_admin("later@institute.edu"))

    def test_unknown_email(self):
        with pytest.raises(TargetUserNotFoundError):
            run(AuthorizationService(FakeRepo()).bootstrap_admin("nobody@institute.edu"))


# --------------------------------------------------------------------------- #
# API enforcement (real M1 JWT -> M2)
# --------------------------------------------------------------------------- #
class TestApi:
    def test_unauthenticated_rejected(self):
        client = make_client(FakeRepo())
        assert client.get("/authorization/me").status_code == 401
        assert client.post("/probe/issue").status_code == 401
        assert client.get("/authorization/users").status_code == 401

    def test_garbage_token_rejected(self):
        client = make_client(FakeRepo())
        r = client.get("/authorization/me", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401

    def test_me_returns_role_and_permissions(self):
        s = student()
        r = make_client(FakeRepo(s)).get("/authorization/me", headers=auth(s))
        assert r.status_code == 200
        assert r.json()["role"] == "STUDENT"
        assert "certificate:view_own" in r.json()["permissions"]

    def test_issuer_operation_gate(self):
        s, i, a = student(), issuer(), admin()
        client = make_client(FakeRepo(s, i, a))
        assert client.post("/probe/issue", headers=auth(s)).status_code == 403
        assert client.post("/probe/issue", headers=auth(i)).status_code == 200
        assert client.post("/probe/issue", headers=auth(a)).status_code == 403

    def test_require_role_gate(self):
        s, a = student(), admin()
        client = make_client(FakeRepo(s, a))
        assert client.get("/probe/admin-only", headers=auth(s)).status_code == 403
        assert client.get("/probe/admin-only", headers=auth(a)).status_code == 200

    def test_admin_grants_then_revokes_issuer_end_to_end(self):
        a, s = admin(), student()
        client = make_client(FakeRepo(a, s))
        assert client.post("/probe/issue", headers=auth(s)).status_code == 403

        r = client.put(f"/authorization/users/{s.id}/role", json={"role": "ISSUER"}, headers=auth(a))
        assert r.status_code == 200 and r.json()["role"] == "ISSUER"
        assert client.post("/probe/issue", headers=auth(s)).status_code == 200

        r = client.put(f"/authorization/users/{s.id}/role", json={"role": "STUDENT"}, headers=auth(a))
        assert r.status_code == 200
        # same still-valid token, role revoked in the database -> denied immediately
        assert client.post("/probe/issue", headers=auth(s)).status_code == 403

    def test_student_cannot_self_promote(self):
        s = student()
        client = make_client(FakeRepo(s))
        for role in ("ISSUER", "ADMIN"):
            r = client.put(f"/authorization/users/{s.id}/role", json={"role": role}, headers=auth(s))
            assert r.status_code == 403

    def test_issuer_cannot_grant_admin(self):
        i, s = issuer(), student()
        r = make_client(FakeRepo(i, s)).put(
            f"/authorization/users/{s.id}/role", json={"role": "ADMIN"}, headers=auth(i)
        )
        assert r.status_code == 403

    def test_role_claim_in_request_body_cannot_smuggle_extra_fields(self):
        a, s = admin(), student()
        r = make_client(FakeRepo(a, s)).put(
            f"/authorization/users/{s.id}/role",
            json={"role": "ISSUER", "is_active": True},
            headers=auth(a),
        )
        assert r.status_code == 422

    def test_invalid_role_value_rejected(self):
        a, s = admin(), student()
        client = make_client(FakeRepo(a, s))
        for bad in ("issuer", "ROOT", "", None):
            r = client.put(f"/authorization/users/{s.id}/role", json={"role": bad}, headers=auth(a))
            assert r.status_code == 422

    def test_unknown_user_404_and_bad_uuid_422(self):
        a = admin()
        client = make_client(FakeRepo(a))
        assert client.put(f"/authorization/users/{uuid4()}/role", json={"role": "ISSUER"}, headers=auth(a)).status_code == 404
        assert client.put("/authorization/users/not-a-uuid/role", json={"role": "ISSUER"}, headers=auth(a)).status_code == 422

    def test_conflicts_return_409(self):
        a, i = admin(), issuer()
        r = make_client(FakeRepo(a, i)).put(
            f"/authorization/users/{i.id}/role", json={"role": "ISSUER"}, headers=auth(a)
        )
        assert r.status_code == 409

    def test_list_users_admin_only(self):
        a, s, i = admin(), student(), issuer()
        client = make_client(FakeRepo(a, s, i))
        assert client.get("/authorization/users", headers=auth(s)).status_code == 403
        assert client.get("/authorization/users", headers=auth(i)).status_code == 403
        r = client.get("/authorization/users", headers=auth(a))
        assert r.status_code == 200 and len(r.json()["users"]) == 3
        r = client.get("/authorization/users?role=ISSUER", headers=auth(a))
        assert [u["role"] for u in r.json()["users"]] == ["ISSUER"]
        assert client.get("/authorization/users?limit=1000", headers=auth(a)).status_code == 422

    def test_responses_do_not_leak_internal_fields(self):
        a, s = admin(), student()
        r = make_client(FakeRepo(a, s)).put(
            f"/authorization/users/{s.id}/role", json={"role": "ISSUER"}, headers=auth(a)
        )
        assert set(r.json()) == {"id", "email", "role", "is_active"}

    def test_database_failure_gives_generic_503(self):
        a, s = admin(), student()
        repo = FakeRepo(a, s)
        client = make_client(repo)
        headers = auth(a)
        repo.fail = False
        ok = client.get("/authorization/me", headers=headers)
        assert ok.status_code == 200
        # M1's get_current_user also uses the repo, so a failure there is M1's 503
        repo.fail = True
        r = client.put(f"/authorization/users/{s.id}/role", json={"role": "ISSUER"}, headers=headers)
        assert r.status_code == 503
        assert "boom" not in r.text
