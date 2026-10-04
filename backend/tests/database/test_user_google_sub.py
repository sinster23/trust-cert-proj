"""M4 tests for the Google-based user model.

Covers: google_sub on the model, removal of password_hash, the unique
google_sub index, and UserRepository.find_by_google_sub. MongoDB is replaced
by a small in-memory fake that enforces unique and partial indexes.

Run from backend/:  python -m pytest tests/database -v
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database.exceptions import (
    DatabaseOperationError,
    DuplicateDataError,
    InvalidDatabaseOperationError,
    UserNotFoundError,
)
from app.database.models.user import User, normalize_google_sub
from app.database.repositories.user_repository import UserRepository


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}
        self.indexes: dict[str, dict] = {}
        self.fail_with: Exception | None = None

    async def create_index(self, keys, unique=False, name=None, **options):
        self.indexes[name] = {"field": keys[0][0], "unique": unique, **options}
        return name

    async def insert_one(self, doc):
        if self.fail_with:
            raise self.fail_with
        for name, spec in self.indexes.items():
            if not spec["unique"]:
                continue
            field = spec["field"]
            if "partialFilterExpression" in spec and not isinstance(doc.get(field), str):
                continue
            for existing in self.docs.values():
                if field in existing and field in doc and existing[field] == doc[field]:
                    raise DuplicateKeyError(f"E11000 duplicate key error index: {name} dup key")
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("E11000 duplicate key error index: _id_ dup key")
        self.docs[doc["_id"]] = dict(doc)

    async def find_one(self, query):
        if self.fail_with:
            raise self.fail_with
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in query.items()):
                return dict(doc)
        return None


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


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
class TestUserModel:
    def test_google_sub_is_stored_and_trimmed(self):
        user = User(email="A@Example.edu", google_sub="  1234567890  ")
        assert user.google_sub == "1234567890"
        assert user.email == "a@example.edu"

    def test_google_sub_is_case_sensitive(self):
        assert normalize_google_sub("AbC") == "AbC"

    @pytest.mark.parametrize("bad", ["", "   ", None, 123, b"abc"])
    def test_google_sub_required(self, bad):
        with pytest.raises(ValueError):
            User(email="a@example.edu", google_sub=bad)

    def test_password_hash_removed(self):
        with pytest.raises(TypeError):
            User(email="a@example.edu", google_sub="s", password_hash="x")  # type: ignore[call-arg]
        user = User(email="a@example.edu", google_sub="s")
        assert not hasattr(user, "password_hash")
        assert "password_hash" not in user.to_document()

    def test_id_is_a_random_uuid(self):
        a = User(email="a@example.edu", google_sub="s1")
        b = User(email="b@example.edu", google_sub="s2")
        assert isinstance(a.id, UUID) and a.id != b.id

    def test_document_round_trip(self):
        user = User(email="a@example.edu", google_sub="s1")
        document = user.to_document()
        assert document["google_sub"] == "s1"
        assert document["_id"] == str(user.id)
        assert User.from_document(document) == user

    def test_from_document_without_google_sub_fails(self):
        legacy = {
            "_id": str(uuid4()),
            "email": "a@example.edu",
            "password_hash": "old",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        with pytest.raises(KeyError):
            User.from_document(legacy)


# --------------------------------------------------------------------------- #
# Repository
# --------------------------------------------------------------------------- #
class TestRepositoryGoogleSub:
    def test_create_then_find_by_google_sub(self, repo):
        user = User(email="a@example.edu", google_sub="sub-1")
        run(repo.create_user(user))
        assert run(repo.find_by_google_sub("sub-1")) == user

    def test_find_by_google_sub_trims_input(self, repo):
        user = User(email="a@example.edu", google_sub="sub-1")
        run(repo.create_user(user))
        assert run(repo.find_by_google_sub("  sub-1 ")) == user

    def test_find_by_google_sub_is_case_sensitive(self, repo):
        run(repo.create_user(User(email="a@example.edu", google_sub="SubA")))
        with pytest.raises(UserNotFoundError):
            run(repo.find_by_google_sub("suba"))

    def test_unknown_google_sub_not_found(self, repo):
        with pytest.raises(UserNotFoundError):
            run(repo.find_by_google_sub("nobody"))

    @pytest.mark.parametrize("bad", ["", "   ", None, 42])
    def test_invalid_google_sub_rejected(self, repo, bad):
        with pytest.raises(InvalidDatabaseOperationError):
            run(repo.find_by_google_sub(bad))

    def test_other_lookups_still_work(self, repo):
        user = User(email="A@Example.edu", google_sub="sub-1")
        run(repo.create_user(user))
        assert run(repo.find_by_id(user.id)) == user
        assert run(repo.find_by_email("a@example.edu")) == user

    def test_two_users_resolve_independently(self, repo):
        a = run(repo.create_user(User(email="a@example.edu", google_sub="sub-a")))
        b = run(repo.create_user(User(email="b@example.edu", google_sub="sub-b")))
        assert run(repo.find_by_google_sub("sub-a")).id == a.id
        assert run(repo.find_by_google_sub("sub-b")).id == b.id


class TestUniqueIndexes:
    def test_ensure_indexes_creates_email_and_google_sub_indexes(self, repo, db):
        run(repo.ensure_indexes())
        indexes = db.collection.indexes
        assert indexes[UserRepository.EMAIL_INDEX]["unique"] is True
        google = indexes[UserRepository.GOOGLE_SUB_INDEX]
        assert google["unique"] is True
        assert google["field"] == "google_sub"
        assert google["partialFilterExpression"] == {"google_sub": {"$type": "string"}}

    def test_duplicate_google_sub_rejected(self, repo):
        run(repo.create_user(User(email="a@example.edu", google_sub="same")))
        with pytest.raises(DuplicateDataError) as info:
            run(repo.create_user(User(email="b@example.edu", google_sub="same")))
        assert "Google account" in str(info.value)

    def test_duplicate_email_still_rejected(self, repo):
        run(repo.create_user(User(email="a@example.edu", google_sub="sub-1")))
        with pytest.raises(DuplicateDataError) as info:
            run(repo.create_user(User(email="A@EXAMPLE.edu", google_sub="sub-2")))
        assert "email" in str(info.value)

    def test_legacy_documents_without_google_sub_do_not_collide(self, repo, db):
        run(repo.ensure_indexes())
        for email in ("old1@example.edu", "old2@example.edu"):
            run(db.collection.insert_one({"_id": str(uuid4()), "email": email}))
        run(repo.create_user(User(email="new@example.edu", google_sub="sub-new")))
        assert len(db.collection.docs) == 3

    def test_legacy_document_is_reported_as_invalid_stored_data(self, repo, db):
        legacy_id = str(uuid4())
        db.collection.docs[legacy_id] = {
            "_id": legacy_id,
            "email": "old@example.edu",
            "password_hash": "old",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        with pytest.raises(DatabaseOperationError):
            run(repo.find_by_email("old@example.edu"))


class TestErrorSanitizing:
    def test_database_errors_are_sanitized_on_lookup(self, repo, db):
        db.collection.fail_with = PyMongoError("connection string mongodb://user:secret@host")
        with pytest.raises(DatabaseOperationError) as info:
            run(repo.find_by_google_sub("sub-1"))
        assert "secret" not in str(info.value)

    def test_database_errors_are_sanitized_on_create(self, repo, db):
        db.collection.fail_with = PyMongoError("mongodb://user:secret@host")
        with pytest.raises(DatabaseOperationError) as info:
            run(repo.create_user(User(email="a@example.edu", google_sub="s")))
        assert "secret" not in str(info.value)

    def test_create_requires_user_instance(self, repo):
        with pytest.raises(InvalidDatabaseOperationError):
            run(repo.create_user({"email": "a@example.edu"}))  # type: ignore[arg-type]
