"""Persistence operations exposed to modules such as M1."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from ..exceptions import (
    DatabaseOperationError,
    DatabaseUnavailableError,
    DuplicateDataError,
    InvalidDatabaseOperationError,
    UserNotFoundError,
)
from ..models.user import User, normalize_email


class UserRepository:
    COLLECTION = "users"
    EMAIL_INDEX = "uq_users_normalized_email"

    def __init__(self, database: Any) -> None:
        self._collection = database[self.COLLECTION]

    async def ensure_indexes(self) -> None:
        try:
            await self._collection.create_index(
                [("email", ASCENDING)], unique=True, name=self.EMAIL_INDEX
            )
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not initialize user constraints") from exc

    async def create_user(self, user: User) -> User:
        if not isinstance(user, User):
            raise InvalidDatabaseOperationError("A validated User is required")
        try:
            # Index on the stored normalized email enforces uniqueness in MongoDB.
            await self._collection.create_index(
                [("email", ASCENDING)], unique=True, name=self.EMAIL_INDEX
            )
            await self._collection.insert_one(user.to_document())
            return user
        except DuplicateKeyError as exc:
            raise DuplicateDataError("A user with this email already exists") from exc
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not save user") from exc

    async def find_by_email(self, email: str) -> User:
        try:
            normalized = normalize_email(email)
        except ValueError as exc:
            raise InvalidDatabaseOperationError("Email is invalid") from exc
        try:
            document = await self._collection.find_one({"email": normalized})
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not retrieve user") from exc
        if document is None:
            raise UserNotFoundError("User was not found")
        return self._decode(document)

    async def find_by_id(self, user_id: UUID | str) -> User:
        try:
            normalized_id = str(user_id if isinstance(user_id, UUID) else UUID(user_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidDatabaseOperationError("User identifier is invalid") from exc
        try:
            document = await self._collection.find_one({"_id": normalized_id})
        except PyMongoError as exc:
            raise DatabaseOperationError("Could not retrieve user") from exc
        if document is None:
            raise UserNotFoundError("User was not found")
        return self._decode(document)

    @staticmethod
    def _decode(document: dict[str, Any]) -> User:
        try:
            return User.from_document(document)
        except (KeyError, TypeError, ValueError) as exc:
            raise DatabaseOperationError("Stored user data is invalid") from exc
