"""M4 tests for roles: the User.role field and the repository methods M2 uses
(update_role, list_users, count_by_role).

MongoDB is replaced by an in-memory fake that understands the few operators
the repository uses ($set, $or, $exists, sort/skip/limit). The last class runs
M2's AuthorizationService against the REAL UserRepository to prove the two
modules fit together.

Run from backend/:  python -m pytest tests/database/test_user_roles.py -v
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from app.authorization.permissions import Role
from app.authorization.service import (
    AuthorizationService,
    BootstrapNotAllowedError,
    InvalidRoleChangeError,
)
from app.database.exceptions import (
    DatabaseOperationError,
    InvalidDatabaseOperationError,
    UserNotFoundError,
)
from app.database.models.user import DEFAULT_ROLE, User, normalize_role
from app.database.repositories.user_repository import UserRepository

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# In-memory fake of the pieces of a Mongo collection the repository uses
# --------------------------------------------------------------------------- #
def _matches(doc: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(doc, sub) for sub in expected):
                return False
        elif isinstance(expected, dict) and "$exists" in expected:
            if (key in doc) != expected["$exists"]:
                return False
        elif doc.get(key) != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def sort(self, spec):
        for field, direction in reversed(spec):
            self._docs.sort(key=lambda d, f=field: d[f], reverse=direction == -1)
        return self

    def skip(self, n: int):
        self._docs = self._docs[n:]
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length=None):
        return [dict(d) for d in self._docs[:length]]


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}
        self.indexes: dict[str, dict] = {}
        self.fail_with: Exception | None = None

    def _maybe_fail(self) -> None:
        if self.fail_with:
            raise self.fail_with

    async def create_index(self, keys, unique=False, name=None, **options):
        self.indexes[name] = {"field": keys[0][0], "unique": unique, **options}
        return name

    async def insert_one(self, doc):
        self._maybe_fail()
        self.docs[doc["_id"]] = dict(doc)

    async def find_one(self, query):
        self._maybe_fail()
        return next((dict(d) for d in self.docs.values() if _matches(d, query)), None)

    async def find_one_and_update(self, query, update, return_document=False, **kw):
        self._maybe_fail()
        for doc in self.docs.values():
            if _matches(doc, query):
                doc.update(update["$set"])
                assert return_document == ReturnDocument.AFTER
                return dict(doc)
        return None

    def find(self, query):
        self._maybe_fail()
        return FakeCursor([dict(d) for d in self.docs.values() if _matches(d, query)])

    async def count_documents(self, query):
        self._maybe_fail()
        return sum(1 for d in self.docs.values() if _matches(d, query))


class FakeDatabase:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def __getitem__(self, name):
        assert name == UserRepository.COLLECTION
        return self.collection


@pytest.fixture
def db() -> FakeDatabase:
    return FakeDatabase()


@pytest.fixture
def repo(db) -> UserRepository:
    return UserRepository(db)


def run(coro):
    return asyncio.run(coro)


def make_user(n: int, **kw) -> User:
    kw.setdefault("created_at", T0 + timedelta(minutes=n))
    kw.setdefault("updated_at", T0 + timedelta(minutes=n))
    return User(email=f"u{n}@example.edu", google_sub=f"sub-{n}", **kw)


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
class TestUserRoleModel:
    def test_default_role_is_student(self):
        assert make_user(1).role == DEFAULT_ROLE == "STUDENT"

    def test_explicit_role_is_kept(self):
        assert make_user(1, role="ISSUER").role == "ISSUER"

    def test_role_is_stored_in_document_and_round_trips(self):
        user = make_user(1, role="ADMIN")
        assert user.to_document()["role"] == "ADMIN"
        assert User.from_document(user.to_document()) == user

    def test_document_without_role_loads_as_student(self):
        legacy = make_user(1).to_document()
        del legacy["role"]
        assert User.from_document(legacy).role == "STUDENT"

    @pytest.mark.parametrize(
        "bad",
        ["student", "Student", "", " ADMIN", "ADMIN ", "AD MIN", "X" * 33, None, 5, ["ADMIN"], {"$ne": "x"}],
    )
    def test_invalid_roles_rejected(self, bad):
        with pytest.raises(ValueError):
            User(email="a@example.edu", google_sub="s", role=bad)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            normalize_role(bad)  # type: ignore[arg-type]

    def test_invalid_stored_role_is_rejected_on_load(self):
        document = make_user(1).to_document()
        document["role"] = "hacked"
        with pytest.raises(ValueError):
            User.from_document(document)

    def test_user_is_immutable(self):
        with pytest.raises(Exception):
            make_user(1).role = "ADMIN"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Repository: creation, indexes, lookup
# --------------------------------------------------------------------------- #
class TestRepositoryRoleStorage:
    def test_created_user_is_stored_with_default_role(self, repo, db):
        user = make_user(1)
        run(repo.create_user(user))
        assert db.collection.docs[str(user.id)]["role"] == "STUDENT"
        assert run(repo.find_by_id(user.id)).role == "STUDENT"

    def test_legacy_document_without_role_is_found_as_student(self, repo, db):
        user = make_user(1)
        document = user.to_document()
        del document["role"]
        db.collection.docs[document["_id"]] = document
        assert run(repo.find_by_email("u1@example.edu")).role == "STUDENT"

    def test_corrupt_stored_role_fails_closed_with_safe_error(self, repo, db):
        user = make_user(1)
        document = user.to_document()
        document["role"] = "hacked"
        db.collection.docs[document["_id"]] = document
        with pytest.raises(DatabaseOperationError) as err:
            run(repo.find_by_id(user.id))
        assert "hacked" not in str(err.value)

    def test_role_index_is_created(self, repo, db):
        run(repo.ensure_indexes())
        assert db.collection.indexes[UserRepository.ROLE_INDEX] == {
            "field": "role",
            "unique": False,
        }


# --------------------------------------------------------------------------- #
# Repository: update_role
# --------------------------------------------------------------------------- #
class TestUpdateRole:
    def test_updates_role_and_returns_user(self, repo, db):
        user = make_user(1)
        run(repo.create_user(user))
        updated = run(repo.update_role(user.id, "ISSUER"))
        assert updated.role == "ISSUER"
        assert db.collection.docs[str(user.id)]["role"] == "ISSUER"
        assert run(repo.find_by_id(user.id)).role == "ISSUER"

    def test_other_fields_unchanged_and_updated_at_bumped(self, repo):
        user = make_user(1)
        run(repo.create_user(user))
        updated = run(repo.update_role(str(user.id), "ADMIN"))  # str id accepted
        assert (updated.id, updated.email, updated.google_sub) == (user.id, user.email, user.google_sub)
        assert updated.is_active == user.is_active and updated.created_at == user.created_at
        assert updated.updated_at > user.updated_at

    def test_only_target_user_changes(self, repo):
        a, b = make_user(1), make_user(2)
        run(repo.create_user(a))
        run(repo.create_user(b))
        run(repo.update_role(a.id, "ISSUER"))
        assert run(repo.find_by_id(b.id)).role == "STUDENT"

    def test_unknown_user(self, repo):
        with pytest.raises(UserNotFoundError):
            run(repo.update_role(uuid4(), "ISSUER"))

    @pytest.mark.parametrize("bad_id", ["nope", "", None, 123])
    def test_invalid_id(self, repo, bad_id):
        with pytest.raises(InvalidDatabaseOperationError):
            run(repo.update_role(bad_id, "ISSUER"))

    @pytest.mark.parametrize("bad_role", ["issuer", "", None, 5, {"$set": {"role": "ADMIN"}}])
    def test_invalid_role_rejected_and_nothing_written(self, repo, db, bad_role):
        user = make_user(1)
        run(repo.create_user(user))
        with pytest.raises(InvalidDatabaseOperationError):
            run(repo.update_role(user.id, bad_role))
        assert db.collection.docs[str(user.id)]["role"] == "STUDENT"

    def test_database_failure_is_sanitized(self, repo, db):
        user = make_user(1)
        run(repo.create_user(user))
        db.collection.fail_with = PyMongoError("mongodb://secret-host:27017 failed")
        with pytest.raises(DatabaseOperationError) as err:
            run(repo.update_role(user.id, "ISSUER"))
        assert "secret-host" not in str(err.value)


# --------------------------------------------------------------------------- #
# Repository: list_users
# --------------------------------------------------------------------------- #
class TestListUsers:
    @pytest.fixture
    def populated(self, repo):
        for n, role in enumerate(["STUDENT", "ISSUER", "STUDENT", "ADMIN", "STUDENT"], start=1):
            run(repo.create_user(make_user(n, role=role)))
        return repo

    def test_lists_all_oldest_first(self, populated):
        users = run(populated.list_users())
        assert [u.email for u in users] == [f"u{n}@example.edu" for n in range(1, 6)]

    def test_filters_by_role(self, populated):
        assert [u.role for u in run(populated.list_users(role="ISSUER"))] == ["ISSUER"]
        assert len(run(populated.list_users(role="STUDENT"))) == 3
        assert run(populated.list_users(role="UNUSED")) == []

    def test_pagination(self, populated):
        first = run(populated.list_users(skip=0, limit=2))
        second = run(populated.list_users(skip=2, limit=2))
        last = run(populated.list_users(skip=4, limit=2))
        assert [u.email for u in first + second + last] == [f"u{n}@example.edu" for n in range(1, 6)]
        assert len(last) == 1
        assert run(populated.list_users(skip=10)) == []

    def test_users_without_role_field_count_as_student(self, populated, db):
        legacy = make_user(9)
        document = legacy.to_document()
        del document["role"]
        db.collection.docs[document["_id"]] = document
        students = run(populated.list_users(role="STUDENT"))
        assert legacy.id in {u.id for u in students} and len(students) == 4

    def test_empty_collection(self, repo):
        assert run(repo.list_users()) == []

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"skip": -1},
            {"limit": 0},
            {"limit": 101},
            {"skip": True},
            {"limit": True},
            {"limit": "5"},
            {"skip": 1.5},
            {"role": "admin"},
            {"role": {"$ne": None}},
        ],
    )
    def test_invalid_arguments(self, repo, kwargs):
        with pytest.raises(InvalidDatabaseOperationError):
            run(repo.list_users(**kwargs))

    def test_maximum_page_size_allowed(self, populated):
        assert len(run(populated.list_users(limit=UserRepository.MAX_PAGE_SIZE))) == 5

    def test_database_failure_is_sanitized(self, repo, db):
        db.collection.fail_with = PyMongoError("secret-host")
        with pytest.raises(DatabaseOperationError) as err:
            run(repo.list_users())
        assert "secret-host" not in str(err.value)


# --------------------------------------------------------------------------- #
# Repository: count_by_role
# --------------------------------------------------------------------------- #
class TestCountByRole:
    def test_counts_per_role(self, repo):
        for n, role in enumerate(["STUDENT", "ISSUER", "ISSUER", "ADMIN"], start=1):
            run(repo.create_user(make_user(n, role=role)))
        assert run(repo.count_by_role("STUDENT")) == 1
        assert run(repo.count_by_role("ISSUER")) == 2
        assert run(repo.count_by_role("ADMIN")) == 1
        assert run(repo.count_by_role("UNUSED")) == 0

    def test_users_without_role_field_count_as_student(self, repo, db):
        run(repo.create_user(make_user(1)))
        legacy = make_user(2).to_document()
        del legacy["role"]
        db.collection.docs[legacy["_id"]] = legacy
        assert run(repo.count_by_role("STUDENT")) == 2

    def test_count_follows_role_changes(self, repo):
        user = make_user(1)
        run(repo.create_user(user))
        run(repo.update_role(user.id, "ADMIN"))
        assert run(repo.count_by_role("ADMIN")) == 1
        assert run(repo.count_by_role("STUDENT")) == 0

    @pytest.mark.parametrize("bad", ["admin", "", None, 5, {"$gt": ""}])
    def test_invalid_role(self, repo, bad):
        with pytest.raises(InvalidDatabaseOperationError):
            run(repo.count_by_role(bad))

    def test_database_failure_is_sanitized(self, repo, db):
        db.collection.fail_with = PyMongoError("secret-host")
        with pytest.raises(DatabaseOperationError) as err:
            run(repo.count_by_role("ADMIN"))
        assert "secret-host" not in str(err.value)


# --------------------------------------------------------------------------- #
# Contract: M2's service running on the REAL UserRepository
# --------------------------------------------------------------------------- #
class TestM2OnRealRepository:
    def test_bootstrap_grant_revoke_and_last_admin_guard(self, repo):
        boss, teacher, other = make_user(1), make_user(2), make_user(3)
        for user in (boss, teacher, other):
            run(repo.create_user(user))
        service = AuthorizationService(repo)

        admin = run(service.bootstrap_admin(boss.email))
        assert admin.role == "ADMIN"
        with pytest.raises(BootstrapNotAllowedError):
            run(service.bootstrap_admin(other.email))

        assert run(service.change_role(admin, teacher.id, Role.ISSUER)).role == "ISSUER"
        assert [u.email for u in run(service.list_users(admin, role=Role.ISSUER))] == [teacher.email]
        assert run(service.change_role(admin, teacher.id, Role.STUDENT)).role == "STUDENT"

        # with two admins one may demote the other...
        second = run(service.change_role(admin, other.id, Role.ADMIN))
        run(service.change_role(second, admin.id, Role.STUDENT))
        assert run(repo.count_by_role("ADMIN")) == 1
        # ...but the only remaining admin cannot be removed
        outsider = make_user(8, role="ADMIN")  # an admin actor that is not stored
        with pytest.raises(InvalidRoleChangeError):
            run(service.change_role(outsider, second.id, Role.STUDENT))
        assert run(repo.find_by_id(second.id)).role == "ADMIN"
