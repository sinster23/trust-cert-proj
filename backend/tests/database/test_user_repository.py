from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database.connection import DatabaseManager
from app.database.exceptions import (
    DatabaseOperationError,
    DatabaseUnavailableError,
    DuplicateDataError,
    InvalidDatabaseOperationError,
    UserNotFoundError,
)
from app.database.models.user import User
from app.database.repositories.user_repository import UserRepository


class FakeCollection:
    def __init__(self):
        self.documents = {}
        self.index_args = None
        self.fail = None

    async def create_index(self, keys, **kwargs):
        self.index_args = (keys, kwargs)
        if self.fail:
            raise self.fail

    async def insert_one(self, document):
        if self.fail:
            raise self.fail
        if any(row["email"] == document["email"] for row in self.documents.values()):
            raise DuplicateKeyError("private mongo detail")
        self.documents[document["_id"]] = document.copy()

    async def find_one(self, query):
        if self.fail:
            raise self.fail
        if "_id" in query:
            return self.documents.get(query["_id"])
        return next((row for row in self.documents.values() if row["email"] == query["email"]), None)


class FakeDatabase:
    def __init__(self):
        self.collection = FakeCollection()

    def __getitem__(self, name):
        assert name == "users"
        return self.collection


@pytest.fixture
def database():
    return FakeDatabase()


@pytest.fixture
def repository(database):
    return UserRepository(database)


@pytest.mark.asyncio
async def test_user_creation_persists_required_data_and_unique_index(repository, database):
    now = datetime(2025, 1, 2, tzinfo=timezone.utc)
    user = User(email="  ALICE@Example.COM ", google_sub="google-sub-1", created_at=now, updated_at=now)
    result = await repository.create_user(user)
    stored = database.collection.documents[str(user.id)]
    assert result.id == user.id
    assert set(stored) == {"_id", "email", "google_sub", "is_active", "role", "created_at", "updated_at"}
    assert stored["role"] == "STUDENT"
    assert stored["email"] == "alice@example.com"
    assert stored["google_sub"] == "google-sub-1"
    assert "password" not in stored
    assert database.collection.index_args[0] == [("google_sub", 1)]
    assert database.collection.index_args[1]["unique"] is True


@pytest.mark.asyncio
async def test_email_normalization_and_id_retrieval(repository):
    user = User(email="Alice@Example.com", google_sub="google-sub-1")
    await repository.create_user(user)
    assert await repository.find_by_email(" alice@example.COM ") == user
    assert await repository.find_by_id(user.id) == user
    assert await repository.find_by_id(str(user.id)) == user


@pytest.mark.asyncio
async def test_duplicate_email_rejected(repository):
    await repository.create_user(User(email="alice@example.com", google_sub="google-sub-1"))
    with pytest.raises(DuplicateDataError) as error:
        await repository.create_user(User(email=" ALICE@example.com ", google_sub="google-sub-2"))
    assert "private mongo detail" not in str(error.value)


@pytest.mark.asyncio
async def test_missing_and_invalid_identifiers(repository):
    with pytest.raises(UserNotFoundError):
        await repository.find_by_email("missing@example.com")
    with pytest.raises(UserNotFoundError):
        await repository.find_by_id(uuid4())
    with pytest.raises(InvalidDatabaseOperationError):
        await repository.find_by_id("not-a-uuid")


@pytest.mark.asyncio
async def test_database_errors_are_sanitized(repository, database):
    database.collection.fail = PyMongoError("mongodb://user:secret@host/internal")
    with pytest.raises(DatabaseOperationError) as error:
        await repository.find_by_email("alice@example.com")
    assert "secret" not in str(error.value)


@pytest.mark.asyncio
async def test_connection_lifecycle_and_connection_failure(monkeypatch):
    class Admin:
        async def command(self, command):
            assert command == "ping"

    class Client:
        def __init__(self, uri, **kwargs):
            self.admin = Admin()
            self.closed = False

        def __getitem__(self, name):
            return name

        async def close(self):
            self.closed = True

    monkeypatch.setattr("app.database.connection.AsyncMongoClient", Client)
    manager = DatabaseManager("mongodb://localhost:27017", "isolated_test_db")
    assert await manager.connect() == "isolated_test_db"
    assert manager.get_database() == "isolated_test_db"
    client = manager._client
    await manager.close()
    assert client.closed

    class BrokenAdmin:
        async def command(self, command):
            raise PyMongoError("sensitive server detail")

    class BrokenClient(Client):
        def __init__(self, uri, **kwargs):
            super().__init__(uri, **kwargs)
            self.admin = BrokenAdmin()

    monkeypatch.setattr("app.database.connection.AsyncMongoClient", BrokenClient)
    with pytest.raises(DatabaseUnavailableError) as error:
        await DatabaseManager("mongodb://local", "isolated_test_db").connect()
    assert "sensitive" not in str(error.value)
